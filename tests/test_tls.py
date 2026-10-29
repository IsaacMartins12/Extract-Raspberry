"""Handshake TLS real, com certificado temporário e verificação de confiança."""
import json
import os
import shutil
import socket
import ssl
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import uvicorn
import painel
import security
import server
from configurar_seguranca import certificate


@unittest.skipUnless(shutil.which('openssl'), 'OpenSSL não disponível no PATH')
class TLSTests(unittest.TestCase):
    def test_real_tls_requires_trusted_certificate_and_authentication(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            cert, key = folder / 'certs/cert.pem', folder / 'certs/key.pem'
            certificate(cert, key, {'localhost'})
            data, token = security.credentials('admin', 'tls-test-password-123')
            sock = socket.socket()
            sock.bind(('127.0.0.1', 0))
            address = 'https://127.0.0.1:' + str(sock.getsockname()[1])
            config = uvicorn.Config(server.app, log_level='critical',
                ssl_certfile=str(cert), ssl_keyfile=str(key), proxy_headers=False)
            process = uvicorn.Server(config)
            with patch.dict(os.environ, {'EXTRACT_MODE': 'protected'}), \
                 patch.object(painel, 'DB', folder / 'history.sqlite3'), \
                 patch.object(painel, 'collect', side_effect=lambda stop: stop.wait(10)), \
                 patch.object(server.Authentication, 'load', return_value=security.Authentication(data)):
                thread = threading.Thread(target=process.run, kwargs={'sockets': [sock]}, daemon=True)
                thread.start()
                try:
                    deadline = time.monotonic() + 10
                    while not process.started and thread.is_alive() and time.monotonic() < deadline:
                        threading.Event().wait(0.05)
                    self.assertTrue(process.started)
                    with self.assertRaises(URLError):
                        urlopen(address + '/api/history', timeout=3)
                    context = ssl.create_default_context(cafile=str(cert))
                    with self.assertRaises(HTTPError) as error:
                        urlopen(address + '/api/history', context=context, timeout=3)
                    self.assertEqual(error.exception.code, 401)
                    error.exception.close()
                    request = Request(address + '/api/history', headers={'Authorization': 'Bearer ' + token})
                    with urlopen(request, context=context, timeout=3) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(json.load(response)['points'], [])
                finally:
                    process.should_exit = True
                    thread.join(timeout=10)
                    sock.close()
                    self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
