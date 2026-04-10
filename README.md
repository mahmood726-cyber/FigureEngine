# FigureEngine

Publication-quality meta-analysis figure generator. Produces forest plots, funnel plots, SROC curves, network graphs, PRISMA flow diagrams, and cumulative forest plots in SVG/TIFF/PNG/PDF format with journal-specific style templates.

## Installation

Requires Python 3.10+ with:
- matplotlib
- numpy

```bash
pip install matplotlib numpy
```

## Usage

```bash
# Forest plot (BMJ style, SVG)
python figure_engine.py --type forest --data results.json --style bmj --output fig1.svg

# Funnel plot (TIFF at 300 DPI for submission)
python figure_engine.py --type funnel --data funnel.json --output fig2.tiff --dpi 300

# SROC curve
python figure_engine.py --type sroc --data dta.json --output fig3.svg

# Network graph (Lancet style)
python figure_engine.py --type network --data network.json --style lancet --output fig4.png

# PRISMA 2020 flow diagram
python figure_engine.py --type prisma --data prisma.json --output fig5.svg

# Cumulative forest plot
python figure_engine.py --type cumulative --data cumulative.json --output fig6.pdf
```

## CLI Arguments

| Argument   | Required | Description                                        |
|------------|----------|----------------------------------------------------|
| `--type`   | Yes      | `forest`, `funnel`, `sroc`, `network`, `prisma`, `cumulative` |
| `--data`   | Yes      | Path to JSON input file                            |
| `--output` | Yes      | Output path (format from extension: .svg, .tiff, .png, .pdf) |
| `--style`  | No       | `bmj`, `lancet`, `jama`, `nejm`, `default`         |
| `--dpi`    | No       | DPI for raster formats (default: 300)              |
| `--width`  | No       | Override width in mm                               |
| `--title`  | No       | Optional figure title                              |

## Journal Styles

| Style   | Width | Font      | Size |
|---------|-------|-----------|------|
| BMJ     | 174mm | Helvetica | 8pt  |
| Lancet  | 180mm | Arial     | 8pt  |
| JAMA    | 178mm | Arial     | 7.5pt|
| NEJM    | 178mm | Helvetica | 7pt  |
| Default | 170mm | DejaVu Sans | 9pt |

## Input JSON Formats

See `test_figure_engine.py` for complete examples of each figure type's JSON schema.

### Forest Plot
```json
{
  "studies": [{"name": "...", "effect": 0.75, "ci_lower": 0.55, "ci_upper": 1.02, "weight": 15.3}],
  "summary": {"effect": 0.72, "ci_lower": 0.61, "ci_upper": 0.85},
  "prediction_interval": {"lower": 0.45, "upper": 1.15},
  "settings": {"effect_label": "Hazard Ratio", "null_value": 1.0, "log_scale": true,
                "favours_left": "Favours Treatment", "favours_right": "Favours Control"}
}
```

### Funnel Plot
```json
{
  "studies": [{"effect": -0.30, "se": 0.12}],
  "pooled_effect": -0.28,
  "settings": {"contour_enhanced": true, "trim_and_fill": {"filled_studies": [{"effect": -0.45, "se": 0.15}]}}
}
```

### Network Graph
```json
{
  "treatments": [{"name": "Drug A", "n_patients": 500}],
  "edges": [{"from": "Drug A", "to": "Placebo", "n_studies": 5}]
}
```

## Testing

```bash
python -m pytest test_figure_engine.py -v
```

20 tests covering all figure types, styles, output formats, and error handling.

## Output

- **SVG**: Scalable, text as text (editable in Inkscape/Illustrator)
- **TIFF**: LZW-compressed, 300 DPI default (journal submission ready)
- **PNG**: Preview quality (150 DPI recommended)
- **PDF**: Vector, suitable for manuscript embedding
