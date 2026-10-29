import json
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import painel
import server


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(painel, 'DB', Path(self.temp.name) / 'test.sqlite3')
        self.db_patch.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.db_patch.stop)
        painel.init_db()

    def sample(self, ts, cpu=20, temp=57, ram=40):
        return dict(ts=ts, cpu=cpu, temp=temp, ram=ram)

    def test_database_survives_initialization_and_keeps_missing_temperature(self):
        painel.save_sample(self.sample(int(time.time()), temp=None))
        painel.init_db()
        result = painel.history('1h')
        self.assertEqual(result['total_samples'], 1)
        self.assertIsNone(result['points'][0]['temp'])

    def test_retention_preserves_recent_and_boundary_samples(self):
        now = int(time.time())
        painel.save_sample(self.sample(now - 2592001))
        painel.save_sample(self.sample(now - 2592000))
        painel.save_sample(self.sample(now), prune=True)
        with closing(sqlite3.connect(painel.DB)) as db:
            timestamps = [row[0] for row in db.execute('SELECT ts FROM metrics ORDER BY ts')]
        self.assertEqual(timestamps, [now - 2592000, now])

    def test_history_averages_samples_and_ignores_future_records(self):
        now = int(time.time())
        bucket = (now // 30) * 30 - 60
        painel.save_sample(self.sample(bucket + 1, cpu=20, temp=None, ram=40))
        painel.save_sample(self.sample(bucket + 10, cpu=80, temp=60, ram=60))
        painel.save_sample(self.sample(now + 100, cpu=100))
        result = painel.history('1h')
        self.assertEqual(len(result['points']), 1)
        point = result['points'][0]
        self.assertEqual(point['samples'], 2)
        self.assertEqual(point['cpu'], 50)
        self.assertEqual(point['temp'], 60)
        self.assertEqual(point['ram'], 50)

    def test_full_month_has_bounded_graph_size(self):
        now = int(time.time())
        with closing(sqlite3.connect(painel.DB)) as db:
            db.executemany('INSERT INTO metrics VALUES (?, ?, ?, ?)',
                           ((now - n * 30, n % 100, 57, 40) for n in range(86400)))
            db.commit()
        for period in painel.PERIODS:
            with self.subTest(period=period):
                result = painel.history(period)
                self.assertLessEqual(len(result['points']), 600)
                self.assertGreater(len(result['points']), 0)

    def test_empty_history(self):
        result = painel.history('1h')
        self.assertEqual(result['points'], [])
        self.assertIsNone(result['first'])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(painel, 'DB', Path(self.temp.name) / 'test.sqlite3')
        self.collect_patch = patch.object(painel, 'collect', side_effect=lambda stop: stop.wait(5))
        self.db_patch.start()
        self.collect_patch.start()
        self.client_context = TestClient(server.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.collect_patch.stop()
        self.db_patch.stop()
        self.temp.cleanup()

    def test_page_and_current_sample(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Sua Pi', response.text)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        with patch.object(painel, 'LATEST', {'ts': 123, 'cpu': 12}):
            self.assertEqual(self.client.get('/api').json()['cpu'], 12)

    def test_waiting_for_first_sample(self):
        self.assertEqual(self.client.get('/api').status_code, 503)

    def test_invalid_period_and_private_file(self):
        self.assertEqual(self.client.get('/api/history?period=bad').status_code, 422)
        self.assertEqual(self.client.get('/historico.sqlite3').status_code, 404)

    def test_history_route_queries_database(self):
        painel.save_sample(dict(ts=int(time.time()), cpu=12, temp=57, ram=30))
        data = self.client.get('/api/history?period=24h').json()
        self.assertEqual(data['total_samples'], 1)
        self.assertEqual(data['points'][0]['cpu'], 12)

    def test_legacy_status_preserves_fields_and_collects_per_request(self):
        gib = 1024**3
        memory = SimpleNamespace(total=8*gib, used=2*gib, available=5*gib, percent=37.5)
        with patch.object(server.psutil, 'virtual_memory', return_value=memory), \
             patch.object(server.psutil, 'cpu_percent', side_effect=[12.5, 25.0]) as cpu, \
             patch.object(server.psutil, 'sensors_temperatures', create=True,
                          return_value={'cpu_thermal': [SimpleNamespace(current=57.0)]}), \
             patch.object(server, 'get_disk_usage', return_value=dict(total=32*gib, used=10*gib, free=22*gib)):
            first = self.client.get('/status').json()
            second = self.client.get('/status').json()
        self.assertEqual(first['cpu_usage'], 12.5)
        self.assertEqual(second['cpu_usage'], 25)
        self.assertEqual(first['memory'], dict(total=8, used=2, free=5, percent=37.5))
        self.assertEqual(first['disk'], dict(total=32, used=10, free=22))
        self.assertEqual(first['temperature'], 57)
        self.assertEqual(set(first), {'cpu_usage', 'memory', 'disk', 'temperature', 'power', 'os', 'os_version'})
        self.assertEqual(cpu.call_count, 2)
        cpu.assert_called_with(interval=1)

    def test_legacy_temperature_fallback_and_documentation(self):
        with patch.object(server.psutil, 'sensors_temperatures', create=True, return_value={}), \
             patch.object(server.psutil, 'cpu_percent', return_value=0):
            self.assertEqual(self.client.get('/status').json()['temperature'], 'N/A')
        self.assertEqual(self.client.get('/docs').status_code, 200)
        schema = self.client.get('/openapi.json').json()
        self.assertIn('/status', schema['paths'])
        self.assertIn('/api/history', schema['paths'])


if __name__ == '__main__':
    unittest.main()
