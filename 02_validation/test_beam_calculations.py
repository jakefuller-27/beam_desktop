import re
import tempfile
import unittest
from pathlib import Path

from beam_calculations import (
    SECTIONS,
    analyze_beam,
    lightest_passing_section,
    PointLoad,
    UniformLoad,
)
from beam_print import export_calculation_sheet


STEEL = "Steel W-shape"
WOOD = "Douglas Fir-Larch lumber"
W12 = next(section for section in SECTIONS[STEEL] if section.name == "W12x26")
TWO_BY_TEN = next(section for section in SECTIONS[WOOD] if section.name == "2x10")


class BeamCalculationTests(unittest.TestCase):
    def test_default_simply_supported_uniform_load(self):
        result = analyze_beam(
            20, "Simply supported", [], [UniformLoad(1, 0, 20)],
            STEEL, W12, 360
        )
        self.assertAlmostEqual(result.left_reaction_kip, 10, places=5)
        self.assertAlmostEqual(result.right_reaction_kip, 10, places=5)
        self.assertAlmostEqual(result.max_moment_kip_ft, 50, places=4)
        self.assertAlmostEqual(result.max_moment_position_ft, 10, places=4)
        self.assertAlmostEqual(result.checks.bending_stress_ksi, 17.96, delta=0.01)
        self.assertAlmostEqual(result.max_deflection_in, 0.609, delta=0.003)
        self.assertTrue(result.checks.passes)

    def test_point_load_reactions_and_deflection(self):
        result = analyze_beam(
            20, "Simply supported", [PointLoad(10, 5)], [],
            STEEL, W12, 360
        )
        self.assertAlmostEqual(result.left_reaction_kip, 7.5, places=5)
        self.assertAlmostEqual(result.right_reaction_kip, 2.5, places=5)
        self.assertAlmostEqual(result.max_moment_kip_ft, 37.5, places=5)
        self.assertAlmostEqual(result.max_moment_position_ft, 5, places=5)
        self.assertAlmostEqual(result.max_deflection_in, 0.340, delta=0.003)
        self.assertAlmostEqual(result.max_deflection_position_ft, 8.82, delta=0.02)
        load_position, left_shear, right_shear = result.point_load_shear[0]
        self.assertEqual(load_position, 5)
        self.assertAlmostEqual(left_shear, 7.5)
        self.assertAlmostEqual(right_shear, -2.5)

    def test_cantilever_free_end_load(self):
        result = analyze_beam(
            10, "Cantilever", [PointLoad(5, 10)], [],
            STEEL, W12, 360
        )
        self.assertAlmostEqual(result.left_reaction_kip, 5)
        self.assertAlmostEqual(result.fixed_end_moment_kip_ft, 50)
        self.assertAlmostEqual(result.max_moment_kip_ft, -50)
        self.assertAlmostEqual(result.max_deflection_in, 0.487, delta=0.003)
        self.assertAlmostEqual(result.max_deflection_position_ft, 10)
        self.assertFalse(result.checks.deflection_passes)

    def test_upward_load_keeps_signed_results_and_absolute_checks(self):
        result = analyze_beam(
            20, "Simply supported", [], [UniformLoad(-1, 0, 20)],
            STEEL, W12, 360
        )
        self.assertAlmostEqual(result.max_moment_kip_ft, -50.0, places=4)
        self.assertAlmostEqual(result.max_deflection_in, -0.609, delta=0.003)
        self.assertAlmostEqual(result.checks.bending_stress_ksi, 17.96, delta=0.01)
        self.assertTrue(result.checks.passes)

    def test_lumber_uniform_load(self):
        result = analyze_beam(
            12, "Simply supported", [], [UniformLoad(0.05, 0, 12)],
            WOOD, TWO_BY_TEN, 360
        )
        self.assertAlmostEqual(result.max_moment_kip_ft, 0.90, places=5)
        self.assertAlmostEqual(result.checks.bending_stress_ksi, 0.505, delta=0.002)
        self.assertAlmostEqual(result.max_deflection_in, 0.147, delta=0.002)
        self.assertTrue(result.checks.passes)

    def test_self_weight_is_added_to_loads_and_checks(self):
        steel = analyze_beam(
            20, "Simply supported", [], [UniformLoad(1, 0, 20)],
            STEEL, W12, 360, include_self_weight=True
        )
        self.assertAlmostEqual(steel.effective_uniform_loads[-1].magnitude_kip_ft, 0.026)
        self.assertAlmostEqual(steel.left_reaction_kip, 10.26, places=5)
        self.assertAlmostEqual(steel.max_moment_kip_ft, 51.30, places=4)
        self.assertAlmostEqual(steel.checks.bending_stress_ksi, 18.43, delta=0.01)
        self.assertAlmostEqual(steel.max_deflection_in, 0.625, delta=0.003)

        wood = analyze_beam(
            12, "Simply supported", [], [UniformLoad(0.05, 0, 12)],
            WOOD, TWO_BY_TEN, 360, include_self_weight=True
        )
        self.assertAlmostEqual(wood.max_moment_kip_ft, 0.961, delta=0.001)
        self.assertAlmostEqual(wood.checks.bending_stress_ksi, 0.539, delta=0.002)
        self.assertAlmostEqual(wood.max_deflection_in, 0.157, delta=0.002)

    def test_partial_uniform_load_reactions_and_extremum(self):
        section = next(section for section in SECTIONS[STEEL] if section.name == "W18x35")
        result = analyze_beam(
            30, "Simply supported", [], [UniformLoad(2, 0, 15)],
            STEEL, section, 360
        )
        self.assertAlmostEqual(result.left_reaction_kip, 22.5)
        self.assertAlmostEqual(result.right_reaction_kip, 7.5)
        self.assertAlmostEqual(result.max_moment_kip_ft, 126.5625, delta=0.01)
        self.assertAlmostEqual(result.max_moment_position_ft, 11.25, delta=0.01)

    def test_recommendation_is_lightest_passing_section(self):
        section = lightest_passing_section(
            20, "Simply supported", [], [UniformLoad(1, 0, 20)],
            STEEL, 360, False
        )
        self.assertIsNotNone(section)
        self.assertEqual(section.name, "W14x22")

    def test_equal_weight_steel_recommendation_prefers_larger_ix(self):
        section = lightest_passing_section(
            20, "Simply supported", [], [UniformLoad(1.5, 0, 20)],
            STEEL, 360, False
        )
        self.assertIsNotNone(section)
        self.assertEqual(section.name, "W16x26")

    def test_invalid_load_position_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze_beam(
                20, "Simply supported", [PointLoad(1, 21)], [],
                STEEL, W12, 360
            )

    def test_print_sheet_is_a_single_page_pdf(self):
        loads = (UniformLoad(1, 0, 20),)
        result = analyze_beam(20, "Simply supported", [], loads, STEEL, W12, 360)
        with tempfile.TemporaryDirectory() as directory:
            path = export_calculation_sheet(
                Path(directory) / "sheet.pdf",
                span_ft=20,
                support="Simply supported",
                material=STEEL,
                section=W12,
                deflection_limit=360,
                include_self_weight=False,
                point_loads=(),
                uniform_loads=loads,
                result=result,
                recommendation=None,
            )
            data = path.read_bytes()
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", data)), 1)


if __name__ == "__main__":
    unittest.main()
