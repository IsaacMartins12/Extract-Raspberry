"""Caminhos independentes do diretório corrente e separados do código."""
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
WEB_DIR = PACKAGE_DIR / 'web'
DATA_DIR = PROJECT_DIR / 'data'
CONFIG_DIR = PROJECT_DIR / 'config'
CERT_DIR = CONFIG_DIR / 'certs'
