import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_mendeley_data import COLUMNS, clean_rows, prepare


class MendeleyTests(unittest.TestCase):
    def test_source_split_is_reproducible_and_projects_do_not_overlap(self):
        source = ROOT / "data/raw/Data set_MENDLEY.csv"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report = prepare(source, output)
            self.assertEqual((report["rows_clean"], report["rows_train"], report["rows_test"]), (50, 40, 10))
            self.assertEqual(report["repeated_project_identifiers"], ["Pr29"])
            def projects(name):
                with (output / name).open(newline="", encoding="utf-8") as file:
                    return {row["ProjName"] for row in csv.DictReader(file)}
            self.assertFalse(projects("mendeley_train.csv") & projects("mendeley_test.csv"))
            first = (output / "mendeley_train.csv").read_bytes()
            prepare(source, output)
            self.assertEqual(first, (output / "mendeley_train.csv").read_bytes())

    def test_duplicate_missing_negative_and_invalid_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            row = ["1", "Pr01", "-5", "", *(["1"] * 9), "10"]
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(COLUMNS)
                writer.writerows([row, row, ["2", "Pr02", *(["2"] * 12)]])
            rows, report = clean_rows(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(report["exact_duplicates_removed"], 1)
            self.assertEqual(rows[0]["AreaSite"], "")
            self.assertEqual(rows[0]["BuiltArea"], "")
            self.assertEqual(len(report["issues"]), 1)
            path.write_text(",".join(COLUMNS) + "\n" + ",".join(row[:-1] + ["0"]) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "positive"):
                clean_rows(path)


if __name__ == "__main__":
    unittest.main()
