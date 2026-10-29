"""Migração idempotente do layout antigo, sem apagar ou substituir dados."""
import argparse
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from .paths import PROJECT_DIR


def migrate(root):
    root = Path(root).resolve()
    config = root / 'config'
    config.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in ('auth.json', 'mode.json'):
        source, destination = root / name, config / name
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)
            os.chmod(destination, 0o600)
    for name in ('cert.pem', 'key.pem'):
        source, destination = root / 'certs' / name, config / 'certs' / name
        if source.is_file() and not destination.exists():
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            os.chmod(destination, 0o600)
    source, destination = root / 'historico.sqlite3', root / 'data/historico.sqlite3'
    if source.is_file() and not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.sqlite3', delete=False) as file:
            temporary = Path(file.name)
        try:
            # A API de backup inclui transações do WAL e não modifica o original.
            with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
                with closing(sqlite3.connect(temporary)) as dst:
                    src.backup(dst)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=PROJECT_DIR)
    args = parser.parse_args()
    migrate(args.root.resolve())


if __name__ == '__main__':
    main()
