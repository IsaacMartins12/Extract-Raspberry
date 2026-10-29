"""Credenciais locais: senha com PBKDF2 e token de API armazenado como hash."""
import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / 'auth.json'
ITERATIONS = 600000


def credentials(username, password):
    if not username or ':' in username or len(username) > 128:
        raise ValueError('Usuário inválido (não use dois-pontos).')
    if len(password) < 12 or len(password) > 1024:
        raise ValueError('Use uma senha entre 12 e 1024 caracteres.')
    salt = secrets.token_hex(16)
    token = secrets.token_urlsafe(32)
    data = dict(username=username, salt=salt, iterations=ITERATIONS,
                password_hash=hashlib.pbkdf2_hmac('sha256', password.encode(),
                    bytes.fromhex(salt), ITERATIONS).hex(),
                token_hash=hashlib.sha256(token.encode()).hexdigest())
    return data, token


class Authentication:
    def __init__(self, data):
        self.data = data
        # Verifica a configuração antes de começar a atender requisições.
        if not 100000 <= data['iterations'] <= 2000000:
            raise ValueError('Número de iterações inválido.')
        if len(bytes.fromhex(data['salt'])) < 16:
            raise ValueError('Salt inválido.')
        for key in ('password_hash', 'token_hash'):
            if len(bytes.fromhex(data[key])) != 32:
                raise ValueError('Hash inválido.')
        if not data['username'] or ':' in data['username']:
            raise ValueError('Usuário inválido.')
        self.secret = secrets.token_bytes(32)
        self.cache = {}
        self.failures = {}
        self.lock = threading.Lock()

    @classmethod
    def load(cls):
        try:
            return cls(json.loads(CONFIG_PATH.read_text(encoding='utf-8')))
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise RuntimeError('Configure as credenciais com configurar_seguranca.py antes de iniciar.') from error

    def authenticate(self, header, address):
        if not header or len(header) > 4096:
            return 401
        now = time.monotonic()
        key = hmac.digest(self.secret, header.encode(), 'sha256')
        with self.lock:
            if self.cache.get(key, 0) > now:
                return 200
            attempts, until = self.failures.get(address, (0, 0))
            if until > now and attempts >= 5:
                return 429
        valid = False
        try:
            scheme, value = header.split(' ', 1)
            if scheme.lower() == 'bearer':
                valid = hmac.compare_digest(hashlib.sha256(value.encode()).hexdigest(),
                                            self.data['token_hash'])
            elif scheme.lower() == 'basic':
                user, password = base64.b64decode(value, validate=True).decode('utf-8').split(':', 1)
                digest = hashlib.pbkdf2_hmac('sha256', password.encode(),
                    bytes.fromhex(self.data['salt']), self.data['iterations']).hex()
                correct_password = hmac.compare_digest(digest, self.data['password_hash'])
                correct_user = hmac.compare_digest(user.encode(), self.data['username'].encode())
                valid = correct_user and correct_password
        except (ValueError, UnicodeError):
            pass
        with self.lock:
            if valid:
                if len(self.cache) >= 32:
                    self.cache.clear()
                self.cache[key] = now + 60
                self.failures.pop(address, None)
                return 200
            if len(self.failures) >= 512 and address not in self.failures:
                self.failures.pop(next(iter(self.failures)))
            attempts, until = self.failures.get(address, (0, 0))
            self.failures[address] = (attempts + 1 if until > now else 1,
                                      until if until > now else now + 60)
        return 401
