import csv
import tempfile
import unittest
from pathlib import Path

from beam_calculations import SECTIONS, PointLoad, UniformLoad, analyze_beam
from beam_results_export import CSV_COLUMNS, export_results_csv


STEEL = "Steel W-shape"
W12 = next(section for section in SECTIONS[STEEL] if section.name == "W12x26")


class BeamResultsExportTests(unittest.TestCase):
    def test_csv_has_sampled_results_and_right_support_shear_jump(self):
        result = analyze_beam(
            20, "Simply supported", [], [UniformLoad(1, 0, 20)],
            STEEL, W12, 360
        )
        with tempfile.TemporaryDirectory() as directory:
            path = export_results_csv(Path(directory) / "results.csv", result)
            raw = path.read_bytes()
            with path.open(encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                rows = list(reader)

        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(tuple(reader.fieldnames), CSV_COLUMNS)
        self.assertEqual(len(rows), len(result.x_ft) + 1)
        self.assertEqual(float(rows[-2]["x (ft)"]), 20)
        self.assertEqual(float(rows[-2]["V (kips)"]), -10)
        self.assertEqual(float(rows[-1]["V (kips)"]), 0)
        self.assertEqual(float(rows[-1]["M (kip-ft)"]), 0)
        self.assertAlmostEqual(float(rows[-1]["Deflection (in)"]), 0)

    def test_csv_preserves_one_sided_shear_at_point_load(self):
        result = analyze_beam(
            20, "Simply supported", [PointLoad(10, 5)], [],
            STEEL, W12, 360
        )
        with tempfile.TemporaryDirectory() as directory:
            path = export_results_csv(Path(directory) / "point-load.csv", result)
            with path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
        at_load = [row for row in rows if float(row["x (ft)"]) == 5]
        self.assertEqual(len(at_load), 2)
        self.assertAlmostEqual(float(at_load[0]["V (kips)"]), 7.5)
        self.assertAlmostEqual(float(at_load[1]["V (kips)"]), -2.5)
        self.assertEqual(at_load[0]["M (kip-ft)"], at_load[1]["M (kip-ft)"])


if __name__ == "__main__":
    unittest.main()
