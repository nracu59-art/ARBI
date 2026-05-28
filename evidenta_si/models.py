import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'evidenta_si.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sisteme (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            denumire TEXT NOT NULL UNIQUE,
            furnizor TEXT,
            tip_acces TEXT,
            descriere TEXT,
            data_inregistrare TEXT,
            statut TEXT DEFAULT 'activ',
            observatii TEXT
        );

        CREATE TABLE IF NOT EXISTS utilizatori (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL,
            nume TEXT NOT NULL,
            sistem_id INTEGER NOT NULL REFERENCES sisteme(id) ON DELETE CASCADE,
            din_data TEXT,
            pina_la TEXT,
            statut TEXT DEFAULT 'activ',
            observatii TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_utilizatori_sistem ON utilizatori(sistem_id);
        CREATE INDEX IF NOT EXISTS idx_utilizatori_login ON utilizatori(login);
        CREATE INDEX IF NOT EXISTS idx_utilizatori_nume ON utilizatori(nume);
    """)
    conn.commit()
    conn.close()
