import base64
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import painel
import security
import server

DATA, TOKEN = security.credentials('admin', 'strong-test-password-123')


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.auth = security.Authentication(DATA)

    def basic(self, user='admin', password='strong-test-password-123'):
        return 'Basic ' + base64.b64encode((user + ':' + password).encode()).decode()

    def test_valid_password_and_token(self):
        self.assertEqual(self.auth.authenticate(self.basic(), 'local'), 200)
        self.assertEqual(self.auth.authenticate('Bearer ' + TOKEN, 'local'), 200)
        self.assertNotIn(TOKEN, json.dumps(DATA))
        self.assertNotIn('strong-test-password-123', json.dumps(DATA))

    def test_bad_credentials_and_malformed_headers(self):
        for header in [None, 'Basic ???', 'Bearer wrong', self.basic(password='wrong')]:
            self.assertEqual(self.auth.authenticate(header, 'local'), 401)

    def test_rate_limit_and_expiry(self):
        with patch.object(security.time, 'monotonic', return_value=100):
            for _ in range(5):
                self.assertEqual(self.auth.authenticate('Bearer wrong', 'local'), 401)
            self.assertEqual(self.auth.authenticate('Bearer wrong', 'local'), 429)
        with patch.object(security.time, 'monotonic', return_value=161):
            self.assertEqual(self.auth.authenticate('Bearer ' + TOKEN, 'local'), 200)

    def test_verified_password_cache_avoids_rehashing_every_poll(self):
        self.assertEqual(self.auth.authenticate(self.basic(), 'local'), 200)
        with patch.object(security.hashlib, 'pbkdf2_hmac', side_effect=AssertionError('Unexpected hash')):
            self.assertEqual(self.auth.authenticate(self.basic(), 'local'), 200)

    def test_missing_or_invalid_configuration_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'auth.json'
            with patch.object(security, 'CONFIG_PATH', path):
                with self.assertRaises(RuntimeError):
                    security.Authentication.load()
                path.write_text('{}')
                with self.assertRaises(RuntimeError):
                    security.Authentication.load()


class ProtectedRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = patch.object(painel, 'DB', Path(self.temp.name) / 'test.sqlite3')
        self.collect = patch.object(painel, 'collect', side_effect=lambda stop: stop.wait(5))
        self.auth = patch.object(server.Authentication, 'load', return_value=security.Authentication(DATA))
        self.db.start()
        self.collect.start()
        self.auth.start()
        self.client = TestClient(server.app, base_url='https://testserver')
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.auth.stop()
        self.collect.stop()
        self.db.stop()
        self.temp.cleanup()

    def test_all_routes_require_credentials(self):
        for path in ['/', '/api', '/status', '/api/history', '/docs', '/openapi.json']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertIn('Basic', response.headers['WWW-Authenticate'])

    def test_token_can_query_history(self):
        response = self.client.get('/api/history', headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['points'], [])

    def test_plain_http_is_rejected_even_with_credentials(self):
        response = self.client.get('http://testserver/api', headers={
            'Authorization': 'Bearer ' + TOKEN, 'X-Forwarded-Proto': 'https'})
        self.assertEqual(response.status_code, 400)

    def test_openapi_declares_both_authentication_methods(self):
        response = self.client.get('/openapi.json', headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['security'], [{'BasicAuth': []}, {'BearerAuth': []}])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')


if __name__ == '__main__':
    unittest.main()
