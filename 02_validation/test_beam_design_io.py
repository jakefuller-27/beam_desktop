import json
import tempfile
import unittest
from pathlib import Path

from beam_calculations import PointLoad, UniformLoad
from beam_design_io import BeamDesign, load_design, save_design


class BeamDesignIOTests(unittest.TestCase):
    def test_round_trip_preserves_settings_and_load_order(self):
        design = BeamDesign(
            support_type="Cantilever",
            span_ft=12.5,
            material="Douglas Fir-Larch lumber",
            section_name="2x10",
            deflection_limit=240,
            include_self_weight=True,
            loads=(
                UniformLoad(0.08, 1, 10),
                PointLoad(-2.5, 6.25),
                UniformLoad(-0.02, 0, 2),
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = save_design(Path(directory) / "design.beam.json", design)
            loaded = load_design(path)

        self.assertEqual(loaded, design)

    def test_rejects_invalid_design_without_writing_file(self):
        design = BeamDesign(
            support_type="Simply supported",
            span_ft=20,
            material="Steel W-shape",
            section_name="W12x26",
            deflection_limit=360,
            include_self_weight=False,
            loads=(PointLoad(1, 21),),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.beam.json"
            with self.assertRaises(ValueError):
                save_design(path, design)
            self.assertFalse(path.exists())

    def test_rejects_malformed_and_unsupported_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.beam.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid beam design JSON"):
                load_design(path)

            path.write_text(
                json.dumps({"format": "other", "version": 1}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "not a supported"):
                load_design(path)


if __name__ == "__main__":
    unittest.main()
