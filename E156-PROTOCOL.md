# E156 Protocol — FigureEngine

**Project**: FigureEngine
**Created**: 2026-04-09
**Status**: v1.0 complete

## E156 Body

A Python CLI tool generates publication-quality meta-analysis figures (forest, funnel, SROC, network, PRISMA, cumulative) from JSON input, applying journal-specific style templates (BMJ, Lancet, JAMA, NEJM) to SVG, TIFF, PNG, and PDF outputs with correct typography, scaling, and color palettes. The tool accepts structured JSON describing study-level data (effects, CIs, weights, diagnostic accuracy pairs, or network edges) and renders matplotlib figures using non-interactive Agg backend with text preserved as editable SVG elements. Forest plots include weighted squares, summary diamonds, prediction intervals, and favours labels; funnel plots support contour-enhanced p-value shading and trim-and-fill overlays; SROC curves show study bubbles, confidence and prediction regions, and summary operating points; network graphs use spring-electric layout with node and edge sizing proportional to sample size and study count. All 20 automated tests pass, validating output validity, content correctness, multi-format rendering, style differentiation, and error handling. The tool eliminates manual figure formatting, ensuring reproducible journal-compliant graphics from standardized data. Boundary: does not perform statistical analysis or data extraction — it renders pre-computed results only.

## Dashboard

N/A (CLI tool)

## Repository

`C:\Models\FigureEngine\`
