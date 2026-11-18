from functools import wraps
from pathlib import Path
from threading import RLock
import json
import sqlite3


def serialized(function):
    @wraps(function)
    def call(db, *args, **kwargs):
        with db.lock:
            return function(db, *args, **kwargs)
    return call


class Database:
    def __init__(self, path):
        self.observations = {}
        self.traces = {}
        self.lock = RLock()
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.execute('CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, value TEXT NOT NULL)')

    @serialized
    def put(self, key, value):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO records VALUES (?, ?)', (key, json.dumps(value)))

    @serialized
    def get(self, key):
        row = self.connection.execute('SELECT value FROM records WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None

    @serialized
    def scan(self, prefix):
        rows = self.connection.execute('SELECT key, value FROM records WHERE key >= ? AND key < ? ORDER BY key', (prefix, prefix + '\uffff')).fetchall()
        return [(key, json.loads(value)) for key, value in rows]

    @serialized
    def delete_many(self, keys):
        with self.connection:
            self.connection.executemany('DELETE FROM records WHERE key=?', [(key,) for key in keys])

    def close(self):
        self.connection.close()

    @serialized
    def put_many(self, records):
        rows = [(key, json.dumps(value)) for key, value in records.items()]
        with self.connection:
            self.connection.executemany('INSERT OR REPLACE INTO records VALUES (?, ?)', rows)
