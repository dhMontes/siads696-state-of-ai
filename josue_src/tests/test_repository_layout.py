"""Verify source-location metadata in the repository layout and an override.
"""
import csv
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

PREPARATION = Path(__file__).resolve().parents[1]


class RepositoryLayoutTests(unittest.TestCase):
    def test_default_repository_source_and_metadata_agree(self):
        self.check_layout(override=False)

    def test_explicit_source_override_is_reported_without_old_location(self):
        self.check_layout(override=True)

    def check_layout(self, override):
        with tempfile.TemporaryDirectory(prefix='repository-layout-', dir=PREPARATION / 'tests') as temporary:
            root = Path(temporary).resolve()
            self.assertTrue(root.is_relative_to((PREPARATION / 'tests').resolve()))
            code = root / 'josue_src'
            code.mkdir()
            shutil.copyfile(PREPARATION / 'pipeline.py', code / 'pipeline.py')
            spec = importlib.util.spec_from_file_location('repository_fixture_pipeline', code / 'pipeline.py')
            pipeline = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(pipeline)
            source = root / ('alternate/source.csv' if override else 'data/raw/Final_Database.csv')
            source.parent.mkdir(parents=True)
            row = {name: '' for name in pipeline.INPUT_COLUMNS}
            row.update({'Bill_Number':'H 1','Jurisdiction':'Synthetic State','Year':'2025',
                        'Bill_Text':'AI shall not disclose private data.',
                        'Bill_Title':'Synthetic fixture','Sponsor':'[]','Sponsor_Party':'[]'})
            with source.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=pipeline.INPUT_COLUMNS)
                writer.writeheader()
                writer.writerow(row)
            original = source.read_bytes()
            selected = source if override else pipeline.DEFAULT_SOURCE
            self.assertEqual(selected.resolve(), source.resolve())
            summary = pipeline.run_pipeline(selected, root / 'output', expected_sha256=None, expected_rows=1)
            relative = summary['source']['path_relative_to_preparation']
            expected = '../alternate/source.csv' if override else '../data/raw/Final_Database.csv'
            self.assertEqual(relative, expected)
            self.assertEqual((code / relative).resolve(), source.resolve())
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(summary['source']['sha256_before'], pipeline.sha256_bytes(original))


if __name__ == '__main__':
    unittest.main()
