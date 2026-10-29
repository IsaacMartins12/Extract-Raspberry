import logging
import shutil
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'historico.sqlite3'
LOCK = threading.Lock()
LATEST = None
PERIODS = {'1h': (3600, 30), '24h': (86400, 180),
           '7d': (604800, 1200), '30d': (2592000, 5400)}


def init_db():
    with closing(sqlite3.connect(DB)) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('''CREATE TABLE IF NOT EXISTS metrics (
            ts INTEGER PRIMARY KEY, cpu REAL NOT NULL,
            temp REAL, ram REAL NOT NULL)''')
        db.commit()


def read_cpu():
    values = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    return sum(values), values[3] + values[4]


def read_metrics(previous, current):
    elapsed = current[0] - previous[0]
    cpu = 100 * (1 - (current[1] - previous[1]) / elapsed) if elapsed > 0 else 0
    memory = {k: int(v.split()[0]) for k, v in
              (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())}
    total = memory['MemTotal']
    used = total - memory['MemAvailable']
    disk = shutil.disk_usage('/')
    try:
        temp = float(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
    except (OSError, ValueError):
        temp = None
    return dict(ts=int(time.time()), cpu=round(max(0, min(100, cpu)), 2),
                temp=temp, ram=round(100 * used / total, 2),
                ram_used=used / 1048576, ram_total=total / 1048576,
                disk_used=disk.used / 2**30, disk_total=disk.total / 2**30,
                uptime=float(Path('/proc/uptime').read_text().split()[0]))


def save_sample(sample, prune=False):
    with closing(sqlite3.connect(DB, timeout=10)) as db:
        db.execute('INSERT OR REPLACE INTO metrics VALUES (?, ?, ?, ?)',
                   tuple(sample[k] for k in ('ts', 'cpu', 'temp', 'ram')))
        if prune:
            db.execute('DELETE FROM metrics WHERE ts < ?', (sample['ts'] - 2592000,))
        db.commit()


def collect(stop_event=None):
    global LATEST
    previous = None
    last_save = last_prune = 0
    stop_event = stop_event if stop_event is not None else threading.Event()
    while not stop_event.is_set():
        try:
            current = read_cpu()
            if previous is not None:
                sample = read_metrics(previous, current)
                with LOCK:
                    LATEST = sample
                if time.monotonic() - last_save >= 30 or last_save == 0:
                    prune = time.monotonic() - last_prune >= 86400 or last_prune == 0
                    save_sample(sample, prune)
                    last_save = time.monotonic()
                    if prune:
                        last_prune = last_save
            previous = current
        except Exception:
            logging.exception('Erro ao coletar ou salvar métricas')
            previous = None
        stop_event.wait(5 if previous is not None and LATEST is not None else 0.5)


def history(period):
    seconds, bucket = PERIODS[period]
    end = int(time.time())
    start = end - seconds
    with closing(sqlite3.connect(DB, timeout=10)) as db:
        rows = db.execute('''SELECT CAST(ts / ? AS INTEGER) * ?, AVG(ts),
            AVG(cpu), AVG(temp), AVG(ram), COUNT(*) FROM metrics
            WHERE ts >= ? AND ts <= ? GROUP BY 1 ORDER BY 1''',
            (bucket, bucket, start, end)).fetchall()
        count, first = db.execute('SELECT COUNT(*), MIN(ts) FROM metrics').fetchone()
    points = [dict(ts=r[1], cpu=r[2], temp=r[3], ram=r[4], samples=r[5]) for r in rows]
    return dict(points=points, start=start, end=end, bucket=bucket,
                total_samples=count, first=first)


if __name__ == '__main__':
    from server import run
    run()
