"""One model owner, atomic paired jobs, bounded replay, cooperative cancellation."""
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import copy
import threading
import time
import uuid

from .contracts import ComparisonRequest

TERMINAL = {'complete', 'stopped', 'failed'}


class JobError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


@dataclass
class Job:
    id: str
    request: ComparisonRequest
    runtime: dict
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = 'queued'
    outputs: dict = field(default_factory=lambda: {'original': '', 'remix': ''})
    metrics: dict = field(default_factory=dict)
    error: str | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    events: deque = field(default_factory=lambda: deque(maxlen=64))
    sequence: int = 0
    finished: float | None = None
    subscribers: int = 0
    last_seen: float = field(default_factory=time.monotonic)
    started: float | None = None


class JobManager:
    def __init__(self, runtime, *, capacity=4, retained=12, ttl=900, orphan_timeout=45, deadline=600):
        self.runtime = runtime
        self.capacity, self.retained, self.ttl = capacity, retained, ttl
        self.orphan_timeout, self.deadline = orphan_timeout, deadline
        self.condition = threading.Condition(threading.RLock())
        self.jobs = {}
        self.keys = {}
        self.queue = deque()
        self.closing = False
        self.worker = threading.Thread(target=self._work, name='comparison-worker', daemon=True)
        self.worker.start()
        self.monitor = threading.Thread(target=self._watch, name='comparison-watchdog', daemon=True)
        self.monitor.start()

    def _prune(self, reserve=False):
        now = time.monotonic()
        terminal = sorted((j for j in self.jobs.values() if j.finished is not None and not j.subscribers),
                          key=lambda j: j.finished)
        remove = {j.id for j in terminal if now - j.finished > self.ttl}
        remaining = [j for j in terminal if j.id not in remove]
        if reserve:
            remove.update(j.id for j in remaining[:max(0, len(self.jobs) - len(remove) - self.retained + 1)])
        for job_id in remove:
            self.jobs.pop(job_id, None)
        self.keys = {k: v for k, v in self.keys.items() if v[0] in self.jobs}
        self.queue = deque(key for key in self.queue
                           if key in self.jobs and self.jobs[key].status == 'queued')

    def snapshot(self, job):
        position = None
        if job.status == 'queued':
            pending = [key for key in self.queue if key in self.jobs and self.jobs[key].status == 'queued']
            if job.id in pending:
                position = pending.index(job.id) + 1
        return {'id': job.id, 'schema_version': 1, 'sequence': job.sequence,
                'created_at': job.created_at, 'status': job.status, 'request': asdict(job.request),
                'runtime': copy.deepcopy(job.runtime), 'outputs': dict(job.outputs),
                'metrics': copy.deepcopy(job.metrics), 'error': job.error, 'queue_position': position}

    def _emit(self, job, event_type, side=None):
        job.sequence += 1
        event = {'id': job.sequence, 'type': event_type, 'side': side, 'job': self.snapshot(job)}
        job.events.append(event)
        self.condition.notify_all()

    def _finish(self, job, status):
        if job.status in TERMINAL:
            return
        job.status = status
        job.finished = time.monotonic()
        self._emit(job, status)

    def submit(self, request, key):
        if not isinstance(key, str) or not 8 <= len(key) <= 100 or not key.isascii():
            raise JobError(400, 'Use a valid idempotency key.')
        with self.condition:
            self._prune()
            if key in self.keys:
                job_id, fingerprint = self.keys[key]
                if fingerprint != request.fingerprint():
                    raise JobError(409, 'This submission key already belongs to different settings.')
                return self.snapshot(self.jobs[job_id])
            self._prune(reserve=True)
            if self.closing:
                raise JobError(503, 'The instrument is shutting down.')
            if self.runtime.status()['state'] != 'ready':
                raise JobError(503, 'Load the local model before running a comparison.')
            active = sum(j.status not in TERMINAL for j in self.jobs.values())
            if active >= self.capacity + 1:
                raise JobError(429, 'The instrument queue is full. Wait for a run to finish.')
            if len(self.jobs) >= self.retained:
                raise JobError(429, 'Too many comparisons are retained. Close old streams and try again.')
            job = Job(uuid.uuid4().hex, request, self.runtime.status())
            self.jobs[job.id] = job
            self.keys[key] = (job.id, request.fingerprint())
            self.queue.append(job.id)
            self._emit(job, 'queued')
            return self.snapshot(job)

    def get(self, job_id):
        with self.condition:
            if job_id not in self.jobs:
                raise JobError(404, 'This local comparison is no longer available.')
            self.jobs[job_id].last_seen = time.monotonic()
            return self.snapshot(self.jobs[job_id])

    def cancel(self, job_id):
        with self.condition:
            if job_id not in self.jobs:
                raise JobError(404, 'Comparison not found.')
            job = self.jobs[job_id]
            if job.status not in TERMINAL:
                job.cancel.set()
                if job.status == 'queued':
                    self._finish(job, 'stopped')
                    self.queue = deque(key for key in self.queue if key != job.id)
                elif job.status != 'stopping':
                    job.status = 'stopping'
                    self._emit(job, 'stopping')
            return self.snapshot(job)

    def events(self, job_id, after=0):
        with self.condition:
            if job_id not in self.jobs:
                raise JobError(404, 'Comparison no longer available.')
            job = self.jobs[job_id]
            if after < 0 or after > job.sequence:
                raise JobError(400, 'Invalid event cursor.')
            if job.subscribers >= 3:
                raise JobError(429, 'Too many streams for this comparison.')
            job.subscribers += 1
            job.last_seen = time.monotonic()
        try:
            while True:
                with self.condition:
                    pending = [event for event in job.events if event['id'] > after]
                    terminal = job.status in TERMINAL
                    if not pending and not terminal:
                        self.condition.wait(timeout=10)
                        pending = [event for event in job.events if event['id'] > after]
                        terminal = job.status in TERMINAL
                if not pending:
                    if terminal:
                        return
                    yield None  # heartbeat; no manager lock held while writing.
                else:
                    # Every event includes a complete snapshot, including after a replay-buffer gap.
                    for event in pending:
                        after = event['id']
                        yield event
                if terminal:
                    return
        finally:
            with self.condition:
                job.subscribers -= 1
                job.last_seen = time.monotonic()

    def _sweep(self, now):
        with self.condition:
            for job in list(self.jobs.values()):
                if job.status in TERMINAL or job.status == 'stopping':
                    continue
                orphaned = not job.subscribers and now - job.last_seen > self.orphan_timeout
                timed_out = job.started is not None and now - job.started > self.deadline
                if orphaned or timed_out:
                    self.cancel(job.id)

    def _watch(self):
        while True:
            with self.condition:
                if self.closing:
                    return
                self.condition.wait(timeout=1)
            self._sweep(time.monotonic())

    def _work(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.queue or self.closing)
                if self.closing and not self.queue:
                    return
                job = self.jobs.get(self.queue.popleft())
                if job is None or job.status in TERMINAL:
                    continue
            try:
                # This lock spans both independent legs and all hook teardown.
                with self.runtime.model_lock:
                    with self.condition:
                        job.started = time.monotonic()
                    for side, strength in (('original', 0), ('remix', job.request.strength)):
                        with self.condition:
                            if job.cancel.is_set():
                                break
                            job.status = f'running-{side}'
                            self._emit(job, 'started', side)

                        def on_text(text, response_side=side):
                            with self.condition:
                                if len(job.outputs[response_side]) + len(text) > 20000:
                                    raise ValueError('Output exceeded the local text limit.')
                                job.outputs[response_side] += text
                                self._emit(job, 'text', response_side)

                        result = self.runtime.generate(job.request.prompt, strength,
                            job.request.max_tokens, job.cancel, on_text)
                        with self.condition:
                            job.metrics[side] = asdict(result)
                            self._emit(job, 'deck-complete', side)
                with self.condition:
                    self._finish(job, 'stopped' if job.cancel.is_set() else 'complete')
            except Exception as exc:
                if 'cleanup failed' in str(exc).lower():
                    self.runtime._state('error', 'Steering cleanup failed. Restart the local runtime.')
                with self.condition:
                    job.error = str(exc)[:500]
                    self._finish(job, 'stopped' if job.cancel.is_set() else 'failed')

    def close(self):
        with self.condition:
            self.closing = True
            for job in self.jobs.values():
                if job.status not in TERMINAL:
                    job.cancel.set()
            self.condition.notify_all()
