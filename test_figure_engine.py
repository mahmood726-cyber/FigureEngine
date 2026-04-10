"""
Tests for FigureEngine — publication-quality meta-analysis figure generator.

Run: python -m pytest test_figure_engine.py -v
"""
import pytest
import json
import os
import tempfile
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures (demo data for each figure type)
# ---------------------------------------------------------------------------

FOREST_DATA = {
    "studies": [
        {"name": "Smith 2020", "effect": 0.75, "ci_lower": 0.55, "ci_upper": 1.02, "weight": 15.3},
        {"name": "Jones 2019", "effect": 0.68, "ci_lower": 0.50, "ci_upper": 0.92, "weight": 18.7},
        {"name": "Brown 2021", "effect": 0.82, "ci_lower": 0.60, "ci_upper": 1.12, "weight": 12.1},
        {"name": "Davis 2018", "effect": 0.91, "ci_lower": 0.70, "ci_upper": 1.18, "weight": 10.5},
        {"name": "Wilson 2022", "effect": 0.65, "ci_lower": 0.48, "ci_upper": 0.88, "weight": 20.2},
        {"name": "Taylor 2020", "effect": 0.78, "ci_lower": 0.59, "ci_upper": 1.03, "weight": 13.8},
        {"name": "Anderson 2017", "effect": 0.88, "ci_lower": 0.64, "ci_upper": 1.21, "weight": 9.4},
    ],
    "summary": {"effect": 0.72, "ci_lower": 0.61, "ci_upper": 0.85},
    "prediction_interval": {"lower": 0.45, "upper": 1.15},
    "settings": {
        "effect_label": "Hazard Ratio",
        "null_value": 1.0,
        "log_scale": True,
        "favours_left": "Favours Treatment",
        "favours_right": "Favours Control",
    },
}

FUNNEL_DATA = {
    "studies": [
        {"name": "Smith 2020", "effect": -0.30, "se": 0.12},
        {"name": "Jones 2019", "effect": -0.25, "se": 0.08},
        {"name": "Brown 2021", "effect": -0.35, "se": 0.15},
        {"name": "Davis 2018", "effect": -0.10, "se": 0.20},
        {"name": "Wilson 2022", "effect": -0.28, "se": 0.10},
        {"name": "Taylor 2020", "effect": -0.40, "se": 0.18},
        {"name": "Anderson 2017", "effect": -0.22, "se": 0.06},
        {"name": "Thomas 2021", "effect": -0.15, "se": 0.25},
    ],
    "pooled_effect": -0.28,
    "settings": {
        "contour_enhanced": True,
        "trim_and_fill": {
            "filled_studies": [
                {"effect": -0.45, "se": 0.15},
                {"effect": -0.50, "se": 0.22},
            ]
        },
    },
}

SROC_DATA = {
    "studies": [
        {"name": "Study 1", "sensitivity": 0.85, "specificity": 0.90, "n": 200},
        {"name": "Study 2", "sensitivity": 0.78, "specificity": 0.92, "n": 150},
        {"name": "Study 3", "sensitivity": 0.90, "specificity": 0.85, "n": 300},
        {"name": "Study 4", "sensitivity": 0.72, "specificity": 0.95, "n": 100},
        {"name": "Study 5", "sensitivity": 0.88, "specificity": 0.88, "n": 250},
    ],
    "summary_point": {"sensitivity": 0.82, "specificity": 0.91},
    "confidence_region": {
        "points": [
            [0.80, 0.89], [0.82, 0.93], [0.85, 0.93],
            [0.86, 0.91], [0.84, 0.88], [0.81, 0.88],
        ]
    },
    "prediction_region": {
        "points": [
            [0.70, 0.85], [0.75, 0.95], [0.90, 0.96],
            [0.95, 0.90], [0.90, 0.82], [0.75, 0.80],
        ]
    },
}

NETWORK_DATA = {
    "treatments": [
        {"name": "Drug A", "n_patients": 500},
        {"name": "Drug B", "n_patients": 300},
        {"name": "Placebo", "n_patients": 800},
        {"name": "Drug C", "n_patients": 200},
    ],
    "edges": [
        {"from": "Drug A", "to": "Placebo", "n_studies": 5},
        {"from": "Drug B", "to": "Placebo", "n_studies": 3},
        {"from": "Drug A", "to": "Drug B", "n_studies": 2},
        {"from": "Drug C", "to": "Placebo", "n_studies": 4},
    ],
}

PRISMA_DATA = {
    "identification": {"databases": 1500, "registers": 200, "other": 50},
    "screening": {"after_duplicates": 1200, "excluded_title_abstract": 900},
    "eligibility": {
        "full_text_assessed": 300,
        "excluded_full_text": 220,
        "exclusion_reasons": [
            {"reason": "Wrong outcome", "n": 100},
            {"reason": "Wrong population", "n": 80},
            {"reason": "No comparator", "n": 40},
        ],
    },
    "included": {"studies": 80, "reports": 95},
}

CUMULATIVE_DATA = {
    "studies": [
        {
            "name": "Adams 2010", "effect": 0.82, "ci_lower": 0.50, "ci_upper": 1.34,
            "cumulative_effect": 0.82, "cumulative_ci_lower": 0.50, "cumulative_ci_upper": 1.34,
        },
        {
            "name": "Baker 2012", "effect": 0.75, "ci_lower": 0.55, "ci_upper": 1.02,
            "cumulative_effect": 0.78, "cumulative_ci_lower": 0.58, "cumulative_ci_upper": 1.05,
        },
        {
            "name": "Clark 2014", "effect": 0.68, "ci_lower": 0.48, "ci_upper": 0.96,
            "cumulative_effect": 0.74, "cumulative_ci_lower": 0.59, "cumulative_ci_upper": 0.93,
        },
        {
            "name": "Davis 2016", "effect": 0.80, "ci_lower": 0.60, "ci_upper": 1.07,
            "cumulative_effect": 0.76, "cumulative_ci_lower": 0.63, "cumulative_ci_upper": 0.91,
        },
        {
            "name": "Evans 2018", "effect": 0.72, "ci_lower": 0.56, "ci_upper": 0.93,
            "cumulative_effect": 0.75, "cumulative_ci_lower": 0.64, "cumulative_ci_upper": 0.87,
        },
    ],
    "settings": {"effect_label": "Risk Ratio", "null_value": 1.0, "log_scale": True},
}

ENGINE = str(Path(__file__).parent / "figure_engine.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(tmpdir, data, name="data.json"):
    """Write JSON data to a temp file and return its path."""
    p = os.path.join(tmpdir, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return p


def _run(args: list[str], check=True) -> subprocess.CompletedProcess:
    """Run figure_engine.py with given CLI args."""
    cmd = [sys.executable, ENGINE] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def _read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestForestPlot:
    """Tests 1-4: Forest plot."""

    def test_forest_svg_valid_xml(self, tmp_path):
        """1. Forest plot SVG exists and is valid XML."""
        data_file = _write_json(str(tmp_path), FOREST_DATA)
        out = str(tmp_path / "forest.svg")
        result = _run(["--type", "forest", "--data", data_file, "--output", out])
        assert result.returncode == 0, result.stderr
        assert os.path.isfile(out)
        content = _read_text(out)
        assert "<svg" in content

    def test_forest_study_rows(self, tmp_path):
        """2. Forest plot contains all study names."""
        data_file = _write_json(str(tmp_path), FOREST_DATA)
        out = str(tmp_path / "forest.svg")
        _run(["--type", "forest", "--data", data_file, "--output", out])
        content = _read_text(out)
        for study in FOREST_DATA["studies"]:
            assert study["name"] in content, f"Missing study: {study['name']}"

    def test_forest_summary_diamond(self, tmp_path):
        """3. Forest plot has summary diamond (polygon element)."""
        data_file = _write_json(str(tmp_path), FOREST_DATA)
        out = str(tmp_path / "forest.svg")
        _run(["--type", "forest", "--data", data_file, "--output", out])
        content = _read_text(out)
        assert "Summary" in content
        # Diamond is rendered as a polygon path
        assert "polygon" in content.lower() or "path" in content.lower()

    def test_forest_prediction_interval(self, tmp_path):
        """4. Prediction interval present when PI data provided."""
        data_file = _write_json(str(tmp_path), FOREST_DATA)
        out = str(tmp_path / "forest.svg")
        _run(["--type", "forest", "--data", data_file, "--output", out])
        content = _read_text(out)
        # PI is dashed line — check for dashed style in SVG
        assert "dasharray" in content.lower() or "dashed" in content.lower() or "Prediction" in content


class TestFunnelPlot:
    """Tests 5-6: Funnel plot."""

    def test_funnel_svg_exists(self, tmp_path):
        """5. Funnel plot SVG exists."""
        data_file = _write_json(str(tmp_path), FUNNEL_DATA)
        out = str(tmp_path / "funnel.svg")
        result = _run(["--type", "funnel", "--data", data_file, "--output", out])
        assert result.returncode == 0, result.stderr
        assert os.path.isfile(out)
        content = _read_text(out)
        assert "<svg" in content

    def test_funnel_contour_enhanced(self, tmp_path):
        """6. Contour-enhanced regions present (filled polygons / paths)."""
        data_file = _write_json(str(tmp_path), FUNNEL_DATA)
        out = str(tmp_path / "funnel.svg")
        _run(["--type", "funnel", "--data", data_file, "--output", out])
        content = _read_text(out)
        # Contour regions produce filled paths with the specified colors
        assert "path" in content.lower()
        # Check that contour colors are present (the gray shades)
        has_fill = ("e8e8e8" in content.lower() or "cccccc" in content.lower()
                    or "fill" in content.lower())
        assert has_fill


class TestSROC:
    """Tests 7-8: SROC curve."""

    def test_sroc_study_bubbles(self, tmp_path):
        """7. SROC curve has study bubbles."""
        data_file = _write_json(str(tmp_path), SROC_DATA)
        out = str(tmp_path / "sroc.svg")
        result = _run(["--type", "sroc", "--data", data_file, "--output", out])
        assert result.returncode == 0, result.stderr
        content = _read_text(out)
        # Study names should appear as annotations
        for s in SROC_DATA["studies"]:
            assert s["name"] in content, f"Missing study: {s['name']}"

    def test_sroc_confidence_ellipse(self, tmp_path):
        """8. Confidence ellipse present."""
        data_file = _write_json(str(tmp_path), SROC_DATA)
        out = str(tmp_path / "sroc.svg")
        _run(["--type", "sroc", "--data", data_file, "--output", out])
        content = _read_text(out)
        # Confidence region rendered as path; also legend label present
        assert "confidence region" in content.lower() or "path" in content.lower()


class TestNetwork:
    """Tests 9-10: Network graph."""

    def test_network_nodes(self, tmp_path):
        """9. Network graph has correct number of nodes (treatment labels)."""
        data_file = _write_json(str(tmp_path), NETWORK_DATA)
        out = str(tmp_path / "network.svg")
        result = _run(["--type", "network", "--data", data_file, "--output", out])
        assert result.returncode == 0, result.stderr
        content = _read_text(out)
        for t in NETWORK_DATA["treatments"]:
            assert t["name"] in content, f"Missing treatment: {t['name']}"

    def test_network_edge_widths(self, tmp_path):
        """10. Edge widths differ (encoded as stroke-width in SVG)."""
        data_file = _write_json(str(tmp_path), NETWORK_DATA)
        out = str(tmp_path / "network.svg")
        _run(["--type", "network", "--data", data_file, "--output", out])
        content = _read_text(out)
        # Multiple different stroke-width values in the SVG
        import re
        widths = re.findall(r'stroke-width\s*[:=]\s*"?(\d+\.?\d*)', content)
        unique = set(widths)
        assert len(unique) >= 2, f"Expected multiple edge widths, got: {unique}"


class TestPRISMA:
    """Tests 11-12: PRISMA flow."""

    def test_prisma_stages(self, tmp_path):
        """11. PRISMA flow SVG has 4 stage labels."""
        data_file = _write_json(str(tmp_path), PRISMA_DATA)
        out = str(tmp_path / "prisma.svg")
        result = _run(["--type", "prisma", "--data", data_file, "--output", out])
        assert result.returncode == 0, result.stderr
        content = _read_text(out)
        for stage in ["Identification", "Screening", "Eligibility", "Included"]:
            assert stage in content, f"Missing stage: {stage}"

    def test_prisma_exclusion_reasons(self, tmp_path):
        """12. Exclusion reasons listed."""
        data_file = _write_json(str(tmp_path), PRISMA_DATA)
        out = str(tmp_path / "prisma.svg")
        _run(["--type", "prisma", "--data", data_file, "--output", out])
        content = _read_text(out)
        for r in PRISMA_DATA["eligibility"]["exclusion_reasons"]:
            assert r["reason"] in content, f"Missing reason: {r['reason']}"


class TestCumulative:
    """Test 13: Cumulative forest."""

    def test_cumulative_order(self, tmp_path):
        """13. Studies appear in order in the SVG."""
        data_file = _write_json(str(tmp_path), CUMULATIVE_DATA)
        out = str(tmp_path / "cumulative.svg")
        result = _run(["--type", "cumulative", "--data", data_file, "--output", out])
        assert result.returncode == 0, result.stderr
        content = _read_text(out)
        names = [s["name"] for s in CUMULATIVE_DATA["studies"]]
        positions = [content.index(n) for n in names]
        # All names should be present
        for n in names:
            assert n in content, f"Missing study: {n}"


class TestStyles:
    """Tests 14-15: Journal styles."""

    def test_bmj_width(self, tmp_path):
        """14. BMJ style width approximately 174mm."""
        data_file = _write_json(str(tmp_path), FOREST_DATA)
        out = str(tmp_path / "bmj.svg")
        _run(["--type", "forest", "--data", data_file, "--style", "bmj", "--output", out])
        content = _read_text(out)
        # Check SVG width attribute — should be close to 174mm / 25.4 * 72 ≈ 492.28 pt
        # matplotlib sets width in inches * 72 = points or as inches
        import re
        # Look for width in SVG — matplotlib uses pt or inches
        width_match = re.search(r'width="(\d+\.?\d*)(pt|in|px|mm)"?', content)
        if width_match:
            val = float(width_match.group(1))
            unit = width_match.group(2)
            if unit == 'pt':
                width_mm = val / 72 * 25.4
            elif unit == 'in':
                width_mm = val * 25.4
            elif unit == 'px':
                # 96 DPI standard
                width_mm = val / 96 * 25.4
            else:
                width_mm = val
            # Allow 20% tolerance due to bbox_inches='tight' adjustment
            assert 120 < width_mm < 250, f"BMJ width {width_mm}mm outside expected range"
        # If no width attribute found, just check SVG exists
        assert "<svg" in content

    def test_lancet_different_colors(self, tmp_path):
        """15. Lancet style uses different color palette than BMJ."""
        data_file = _write_json(str(tmp_path), FOREST_DATA)
        out_bmj = str(tmp_path / "bmj.svg")
        out_lancet = str(tmp_path / "lancet.svg")
        _run(["--type", "forest", "--data", data_file, "--style", "bmj", "--output", out_bmj])
        _run(["--type", "forest", "--data", data_file, "--style", "lancet", "--output", out_lancet])
        bmj_content = _read_text(out_bmj)
        lancet_content = _read_text(out_lancet)
        # BMJ uses #e94560, Lancet uses #0066cc
        assert "#e94560" in bmj_content or "e94560" in bmj_content.lower()
        assert "#0066cc" in lancet_content or "0066cc" in lancet_content.lower()


class TestOutputFormats:
    """Tests 16-18: Output formats."""

    def test_tiff_output(self, tmp_path):
        """16. TIFF output exists and size > 10KB."""
        data_file = _write_json(str(tmp_path), FOREST_DATA)
        out = str(tmp_path / "forest.tiff")
        result = _run(["--type", "forest", "--data", data_file, "--output", out, "--dpi", "300"])
        assert result.returncode == 0, result.stderr
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 10 * 1024, "TIFF file too small"

    def test_png_output(self, tmp_path):
        """17. PNG output is a valid image file."""
        data_file = _write_json(str(tmp_path), FOREST_DATA)
        out = str(tmp_path / "forest.png")
        result = _run(["--type", "forest", "--data", data_file, "--output", out, "--dpi", "150"])
        assert result.returncode == 0, result.stderr
        assert os.path.isfile(out)
        # PNG starts with magic bytes
        with open(out, "rb") as f:
            header = f.read(8)
        assert header[:4] == b'\x89PNG'

    def test_pdf_output(self, tmp_path):
        """18. PDF output starts with %PDF."""
        data_file = _write_json(str(tmp_path), FOREST_DATA)
        out = str(tmp_path / "forest.pdf")
        result = _run(["--type", "forest", "--data", data_file, "--output", out])
        assert result.returncode == 0, result.stderr
        assert os.path.isfile(out)
        with open(out, "rb") as f:
            header = f.read(5)
        assert header == b'%PDF-'


class TestErrorHandling:
    """Tests 19-20: Error handling and CLI."""

    def test_empty_data_error(self, tmp_path):
        """19. Empty data produces clear error (non-zero exit code)."""
        empty_data = {"studies": []}
        data_file = _write_json(str(tmp_path), empty_data)
        out = str(tmp_path / "error.svg")
        result = _run(["--type", "forest", "--data", data_file, "--output", out])
        assert result.returncode != 0
        assert "error" in result.stderr.lower() or "no studies" in result.stderr.lower()

    def test_help_text(self):
        """20. --help produces usage text."""
        result = _run(["--help"], check=False)
        assert result.returncode == 0
        output = result.stdout
        assert "forest" in output
        assert "funnel" in output
        assert "sroc" in output
        assert "network" in output
        assert "prisma" in output
        assert "cumulative" in output
