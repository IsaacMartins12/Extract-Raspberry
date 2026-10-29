import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from extract_raspberry.migration import migrate


class MigrationTests(unittest.TestCase):
    def test_legacy_database_wal_and_configuration_are_copied(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'auth.json').write_text('{"original":true}')
            (root / 'mode.json').write_text('{"mode":"protected"}')
            (root / 'certs').mkdir()
            (root / 'certs/key.pem').write_text('private-key-fixture')
            with closing(sqlite3.connect(root / 'historico.sqlite3')) as db:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('PRAGMA wal_autocheckpoint=0')
                db.execute('CREATE TABLE metrics (ts INTEGER)')
                db.execute('INSERT INTO metrics VALUES (123)')
                db.commit()
                migrate(root)
                with closing(sqlite3.connect(root / 'data/historico.sqlite3')) as copied:
                    self.assertEqual(copied.execute('SELECT ts FROM metrics').fetchone()[0], 123)
            self.assertTrue(json.loads((root / 'config/auth.json').read_text())['original'])
            self.assertEqual((root / 'config/certs/key.pem').read_text(), 'private-key-fixture')
            self.assertTrue((root / 'historico.sqlite3').exists())
            self.assertTrue((root / 'auth.json').exists())

    def test_new_files_are_never_overwritten_on_reinstallation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'auth.json').write_text('old')
            (root / 'config').mkdir()
            (root / 'config/auth.json').write_text('new')
            (root / 'data').mkdir()
            (root / 'data/historico.sqlite3').write_text('existing')
            (root / 'historico.sqlite3').write_text('not read when destination exists')
            migrate(root)
            migrate(root)
            self.assertEqual((root / 'config/auth.json').read_text(), 'new')
            self.assertEqual((root / 'data/historico.sqlite3').read_text(), 'existing')


if __name__ == '__main__':
    unittest.main()
