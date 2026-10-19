"""Shared preparation keeps source values while deduplicating and adding sponsor features."""
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.prepare import TEXT_COLUMNS, prepare_data


def source_frame():
    base = {name: "" for name in TEXT_COLUMNS}
    rows = [
        {**base, "Bill_Text": "Same  text", "Sponsor_Party": '["R"]', "Introduction_Date": "01/02/2024", "Version_Date": ""},
        {**base, "Bill_Text": "Other text", "Sponsor_Party": '["D", "R"]', "Introduction_Date": "", "Version_Date": "03/04/2025"},
        {**base, "Bill_Text": "Same text", "Sponsor_Party": '["D"]', "Introduction_Date": "01/02/2024", "Version_Date": ""},
    ]
    return pd.DataFrame(rows)


class PrepareTests(unittest.TestCase):
    def test_original_fields_survive_deduplication_and_sponsor_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "source.csv", Path(folder) / "out.csv"
            original = source_frame()
            original.to_csv(source, index=False)
            prepare_data(source, output)
            saved = pd.read_csv(output, dtype=str, keep_default_na=False)
        # Cleaned duplicate text keeps the last record; source_row still locates the source.
        self.assertEqual(saved.source_row.tolist(), ["2", "3"])
        self.assertEqual(saved.Sponsor_Party.tolist(), ['["D", "R"]', '["D"]'])
        pd.testing.assert_frame_equal(saved[original.columns], original.iloc[[1, 2]].reset_index(drop=True))
        self.assertEqual(saved.Bipartisan_Support.tolist(), ["1", "0"])
        self.assertEqual(saved.D_Count.tolist(), ["1", "1"])

    def test_source_with_a_prepared_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.csv"
            source_frame().assign(Bipartisan_Support="1").to_csv(source, index=False)
            with self.assertRaisesRegex(ValueError, "preparation column"):
                prepare_data(source, Path(folder) / "out.csv")


if __name__ == "__main__":
    unittest.main()
