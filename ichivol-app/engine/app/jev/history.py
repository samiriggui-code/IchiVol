import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/data/jev-shadow/history.db")

def save_evaluation(symbol, timeframe, original_decision, jev_result, latency_ms):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, timeout=5) as db:
        db.execute("CREATE TABLE IF NOT EXISTS evaluations (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, symbol TEXT NOT NULL, timeframe TEXT NOT NULL, original_decision TEXT, jev_result TEXT NOT NULL, latency_ms REAL)")
        db.execute("INSERT INTO evaluations (created_at,symbol,timeframe,original_decision,jev_result,latency_ms) VALUES (?,?,?,?,?,?)", (datetime.now(timezone.utc).isoformat(),symbol,timeframe,original_decision,json.dumps(jev_result),latency_ms))

def list_evaluations(limit=50):
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH, timeout=5) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute("SELECT * FROM evaluations ORDER BY id DESC LIMIT ?", (min(max(int(limit),1),100),))]
