import json
import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path):
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.execute('CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, value TEXT NOT NULL)')

    def put(self, key, value):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO records VALUES (?, ?)', (key, json.dumps(value)))

    def get(self, key):
        row = self.connection.execute('SELECT value FROM records WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def close(self):
        self.connection.close()
