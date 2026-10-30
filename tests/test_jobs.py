import threading
import time
import unittest
from services.inference.contracts import ComparisonRequest
from services.inference.jobs import JobError, JobManager
from services.inference.runtime import GenerationResult


class ControlledRuntime:
    def __init__(self):
        self.model_lock = threading.RLock()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = []
    def status(self):
        return {'state': 'ready', 'profile': {'device': 'test'}}
    def generate(self, prompt, strength, tokens, cancel, on_text):
        self.calls.append((prompt, strength))
        self.entered.set()
        self.release.wait(3)
        on_text(f'test-only {strength}')
        return GenerationResult(1, .01, 'stopped' if cancel.is_set() else 'end')


def wait_for(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError('Timed out waiting for worker state.')


class JobTests(unittest.TestCase):
    def setUp(self):
        self.runtime = ControlledRuntime()
        self.manager = JobManager(self.runtime, capacity=1)
        self.request = ComparisonRequest.parse({'prompt': 'hello', 'strength': .5})
    def tearDown(self):
        self.runtime.release.set()
        self.manager.close()
        self.manager.worker.join(3)
    def test_idempotency_and_payload_conflict(self):
        first = self.manager.submit(self.request, 'same-key-123')
        second = self.manager.submit(self.request, 'same-key-123')
        self.assertEqual(first['id'], second['id'])
        with self.assertRaises(JobError) as ctx:
            self.manager.submit(ComparisonRequest('different'), 'same-key-123')
        self.assertEqual(ctx.exception.status, 409)
    def test_cancellation_waits_for_generation_and_cleanup(self):
        first = self.manager.submit(self.request, 'first-key-123')
        self.assertTrue(self.runtime.entered.wait(1))
        second = self.manager.submit(self.request, 'second-key-123')
        self.manager.cancel(first['id'])
        self.assertEqual(self.manager.get(first['id'])['status'], 'stopping')
        self.assertEqual(self.manager.get(second['id'])['status'], 'queued')
        self.assertEqual(len(self.runtime.calls), 1)
        self.runtime.release.set()
        wait_for(lambda: self.manager.get(second['id'])['status'] == 'complete')
        self.assertEqual(self.manager.get(first['id'])['status'], 'stopped')
        self.assertEqual(len(self.runtime.calls), 3)
    def test_queued_cancel_never_calls_model(self):
        first = self.manager.submit(self.request, 'first-key-123')
        self.runtime.entered.wait(1)
        second = self.manager.submit(self.request, 'second-key-123')
        self.manager.cancel(second['id'])
        self.runtime.release.set()
        wait_for(lambda: self.manager.get(first['id'])['status'] == 'complete')
        self.assertEqual(len(self.runtime.calls), 2)
        self.assertEqual(self.manager.get(second['id'])['outputs']['remix'], '')
    def test_stream_reconnect_is_snapshot_and_does_not_regenerate(self):
        job = self.manager.submit(self.request, 'stream-key-123')
        self.runtime.release.set()
        wait_for(lambda: self.manager.get(job['id'])['status'] == 'complete')
        events = list(self.manager.events(job['id'], after=1))
        self.assertEqual(events[-1]['job']['status'], 'complete')
        self.assertEqual(events[-1]['job']['outputs']['remix'], 'test-only 0.5')
        self.assertEqual(len(self.runtime.calls), 2)
        self.assertEqual(list(self.manager.events(job['id'], events[-1]['id'])), [])
    def test_queue_is_bounded(self):
        self.manager.submit(self.request, 'first-key-123')
        self.runtime.entered.wait(1)
        self.manager.submit(self.request, 'second-key-123')
        with self.assertRaises(JobError) as ctx:
            self.manager.submit(self.request, 'third-key-123')
        self.assertEqual(ctx.exception.status, 429)

    def test_repeated_queued_cancellation_keeps_physical_queue_bounded(self):
        self.manager.submit(self.request, 'blocking-key')
        self.runtime.entered.wait(1)
        for index in range(50):
            queued = self.manager.submit(self.request, f'cancelled-{index}')
            self.manager.cancel(queued['id'])
        self.assertEqual(len(self.manager.queue), 0)
        self.assertLessEqual(len(self.manager.jobs), self.manager.retained)

    def test_idempotent_retry_at_retention_limit_does_not_regenerate(self):
        self.manager.retained = 3
        self.runtime.release.set()
        originals = []
        for index in range(3):
            value = self.manager.submit(self.request, f'retained-{index}')
            wait_for(lambda: self.manager.get(value['id'])['status'] == 'complete')
            originals.append(value)
        retry = self.manager.submit(self.request, 'retained-0')
        self.assertEqual(retry['id'], originals[0]['id'])
        self.assertEqual(len(self.runtime.calls), 6)

    def test_orphan_timeout_requests_stop_without_releasing_model(self):
        job = self.manager.submit(self.request, 'orphan-key-123')
        self.runtime.entered.wait(1)
        self.manager._sweep(time.monotonic() + 46)
        self.assertEqual(self.manager.get(job['id'])['status'], 'stopping')
        self.assertEqual(len(self.runtime.calls), 1)
        self.runtime.release.set()
        wait_for(lambda: self.manager.get(job['id'])['status'] == 'stopped')


if __name__ == '__main__':
    unittest.main()
