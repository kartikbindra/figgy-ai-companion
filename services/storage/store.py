"""Short SQLite transactions. No connection/transaction spans model execution."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import threading
import uuid

from services.inference.jobs import JobError
from services.personality.compose import Personality


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.checkpoints = {}
        with self.connect() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] > 1:
                raise ValueError('This database was created by a newer application version.')
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, settings TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    request_key TEXT UNIQUE NOT NULL, input_hash TEXT NOT NULL, message TEXT NOT NULL,
                    status TEXT NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE UNIQUE INDEX IF NOT EXISTS one_pending_turn ON turns(conversation_id) WHERE status='pending';
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY, profile TEXT NOT NULL DEFAULT 'local', key TEXT NOT NULL,
                    content TEXT NOT NULL, source_turn TEXT REFERENCES turns(id) ON DELETE CASCADE,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(profile,key));
                PRAGMA user_version=1;
            ''')
            rows = db.execute("SELECT id,snapshot FROM turns WHERE status='pending'").fetchall()
            for row in rows:
                snapshot = json.loads(row['snapshot'])
                snapshot.update(status='interrupted', error='Service restarted before this turn finished.')
                db.execute("UPDATE turns SET status='interrupted',snapshot=? WHERE id=?", (json.dumps(snapshot), row['id']))

    @contextmanager
    def connect(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            try:
                with db:
                    yield db
            finally:
                db.close()

    def create(self, title='New conversation'):
        if not isinstance(title, str) or not title.strip() or len(title) > 100:
            raise ValueError('Conversation title must contain 1–100 characters.')
        identifier = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO conversations(id,title,settings) VALUES (?,?,?)',
                       (identifier, title.strip(), json.dumps(Personality().document())))
        return self.conversation(identifier)

    def conversations(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT id,title,created_at FROM conversations ORDER BY rowid DESC LIMIT 100')]

    def conversation(self, identifier):
        with self.connect() as db:
            row = db.execute('SELECT * FROM conversations WHERE id=?', (identifier,)).fetchone()
            if not row:
                raise JobError(404, 'Conversation not found.')
            result = dict(row)
            result['settings'] = json.loads(result['settings'])
            result['turns'] = [json.loads(t['snapshot']) for t in db.execute(
                'SELECT snapshot FROM (SELECT rowid,snapshot FROM turns WHERE conversation_id=? ORDER BY rowid DESC LIMIT 100) ORDER BY rowid',
                (identifier,))]
            return result

    def settings(self, identifier, value):
        settings = Personality.parse(value).document()
        with self.connect() as db:
            if not db.execute('UPDATE conversations SET settings=? WHERE id=?', (json.dumps(settings), identifier)).rowcount:
                raise JobError(404, 'Conversation not found.')
        return settings

    def previous(self, key, input_hash):
        with self.connect() as db:
            row = db.execute('SELECT * FROM turns WHERE request_key=?', (key,)).fetchone()
            if row:
                if row['input_hash'] != input_hash:
                    raise JobError(409, 'This submission key belongs to a different turn.')
                return json.loads(row['snapshot'])

    def ensure_available(self, identifier):
        with self.connect() as db:
            if db.execute("SELECT 1 FROM turns WHERE conversation_id=? AND status='pending'", (identifier,)).fetchone():
                raise JobError(409, 'Wait for this conversation’s active turn to finish, or stop it.')

    def bind(self, snapshot, key, input_hash):
        request = snapshot['request']
        with self.connect() as db:
            db.execute('INSERT INTO turns(id,conversation_id,request_key,input_hash,message,status,snapshot) VALUES (?,?,?,?,?,?,?)',
                       (snapshot['id'], request['conversation_id'], key, input_hash, request['prompt'], 'pending', json.dumps(snapshot)))

    def finish(self, snapshot):
        if snapshot['request'].get('kind') != 'chat':
            return
        with self.connect() as db:
            row = db.execute('SELECT * FROM turns WHERE id=?', (snapshot['id'],)).fetchone()
            if not row or row['status'] != 'pending':
                return
            db.execute('UPDATE turns SET status=?,snapshot=? WHERE id=?', (snapshot['status'], json.dumps(snapshot), snapshot['id']))
            self.checkpoints.pop(snapshot['id'], None)
            config = json.loads(snapshot['request']['provenance'])['settings']
            if snapshot['status'] == 'complete' and config['memory']:
                # Explicit facts only. No model call or unbounded background task.
                for pattern, key, template in (
                    (r'\b(?:my name is|call me)\s+([\w-]+)', 'user_name', 'Name: {}'),
                    (r'\bi (?:like|love|enjoy)\s+([^.!?\n]{2,60})', 'interest', 'Enjoys {}'),
                    (r'\bi live in\s+([^.!?\n]{2,60})', 'location', 'Lives in {}'),
                ):
                    match = re.search(pattern, row['message'], re.IGNORECASE)
                    if match:
                        content = template.format(match.group(1).strip())
                        db.execute('''INSERT INTO memories(key,content,source_turn) VALUES (?,?,?)
                            ON CONFLICT(profile,key) DO UPDATE SET content=excluded.content,
                            source_turn=excluded.source_turn,updated_at=CURRENT_TIMESTAMP''', (key, content, row['id']))

    def checkpoint(self, snapshot):
        import time
        if snapshot['request'].get('kind') != 'chat':
            return
        now = time.monotonic()
        with self.lock:
            if now - self.checkpoints.get(snapshot['id'], 0) < 1:
                return
            with self.connect() as db:
                db.execute("UPDATE turns SET snapshot=? WHERE id=? AND status='pending'", (json.dumps(snapshot), snapshot['id']))
            self.checkpoints[snapshot['id']] = now

    def memories(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM memories WHERE profile='local' ORDER BY updated_at DESC,id DESC LIMIT 100")]

    def delete_memory(self, identifier):
        with self.connect() as db:
            if not db.execute("DELETE FROM memories WHERE id=? AND profile='local'", (identifier,)).rowcount:
                raise JobError(404, 'Memory not found.')
