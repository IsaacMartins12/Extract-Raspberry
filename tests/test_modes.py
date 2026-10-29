import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from extract_raspberry import metrics as painel
from extract_raspberry import app as server


class SimpleModeTests(unittest.TestCase):
    def test_default_mode_needs_no_credentials_and_protects_local_files(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {}, clear=True), \
             patch.object(painel, 'DB', Path(folder) / 'test.sqlite3'), \
             patch.object(painel, 'collect', side_effect=lambda stop: stop.wait(5)), \
             patch.object(server.Authentication, 'load', side_effect=AssertionError('Auth must not load')):
            with TestClient(server.app, base_url='http://testserver') as client:
                for path in ['/', '/api/history', '/docs', '/openapi.json',
                             '/static/styles.css', '/static/dashboard.js']:
                    self.assertEqual(client.get(path).status_code, 200)
                self.assertNotIn('security', client.get('/openapi.json').json())
                self.assertEqual(client.get('/api').status_code, 503)
                with patch.object(server.psutil, 'cpu_percent', return_value=0):
                    self.assertEqual(client.get('/status').status_code, 200)
                for path in ['/auth.json', '/certs/key.pem', '/historico.sqlite3',
                             '/config/auth.json', '/config/certs/key.pem', '/data/historico.sqlite3']:
                    self.assertEqual(client.get(path).status_code, 404)

    def test_invalid_mode_does_not_start_anonymous_server(self):
        with patch.dict(os.environ, {'EXTRACT_MODE': 'typo'}):
            with self.assertRaises(RuntimeError):
                with TestClient(server.app):
                    pass


class CommandLineTests(unittest.TestCase):
    def test_simple_default_and_secure_opt_in_set_transport_and_port(self):
        import uvicorn
        for arguments, mode, port in [([], 'simple', 8080),
                (['--mode', 'protected'], 'protected', 8443),
                (['--mode', 'simple', '--port', '9000'], 'simple', 9000)]:
            with self.subTest(arguments=arguments), \
                 patch.dict(os.environ, {}, clear=True), \
                 patch('sys.argv', ['server.py'] + arguments), \
                 patch.object(uvicorn, 'run') as run:
                server.run()
                options = run.call_args.kwargs
                self.assertEqual(options['port'], port)
                self.assertEqual(os.environ['EXTRACT_MODE'], mode)
                self.assertEqual('ssl_keyfile' in options, mode == 'protected')


if __name__ == '__main__':
    unittest.main()
