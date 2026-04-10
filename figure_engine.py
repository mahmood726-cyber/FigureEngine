#!/usr/bin/env python
"""
FigureEngine: Publication-quality meta-analysis figure generator.

Usage:
    python figure_engine.py --type forest --data results.json --style bmj --output fig1.svg
    python figure_engine.py --type funnel --data results.json --output fig2.tiff --dpi 300
    python figure_engine.py --type network --data network.json --style lancet --output fig3.png
    python figure_engine.py --type prisma --data prisma.json --output fig4.svg
    python figure_engine.py --type sroc --data dta.json --output fig5.svg
    python figure_engine.py --type cumulative --data results.json --output fig6.svg
"""
import argparse
import json
import sys
import os
import math

# Non-interactive backend BEFORE importing pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
from matplotlib.collections import PatchCollection
import numpy as np

# ---------------------------------------------------------------------------
# Journal style templates
# ---------------------------------------------------------------------------
STYLES = {
    'bmj': {
        'width_mm': 174, 'font': 'Helvetica', 'font_size': 8,
        'colors': {'primary': '#1a1a2e', 'accent': '#e94560', 'background': 'white'},
        'line_width': 0.8,
    },
    'lancet': {
        'width_mm': 180, 'font': 'Arial', 'font_size': 8,
        'colors': {'primary': '#003366', 'accent': '#0066cc', 'background': 'white'},
        'line_width': 0.8,
    },
    'jama': {
        'width_mm': 178, 'font': 'Arial', 'font_size': 7.5,
        'colors': {'primary': '#2d2d2d', 'accent': '#8b0000', 'background': 'white'},
        'line_width': 0.7,
    },
    'nejm': {
        'width_mm': 178, 'font': 'Helvetica', 'font_size': 7,
        'colors': {'primary': '#000000', 'accent': '#cc0000', 'background': 'white'},
        'line_width': 0.6,
    },
    'default': {
        'width_mm': 170, 'font': 'DejaVu Sans', 'font_size': 9,
        'colors': {'primary': '#333333', 'accent': '#2196F3', 'background': 'white'},
        'line_width': 1.0,
    },
}

FIGURE_TYPES = ('forest', 'funnel', 'sroc', 'network', 'prisma', 'cumulative')


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _apply_style(style_name: str, override_width_mm: float | None = None):
    """Return resolved style dict and figure width in inches."""
    style = STYLES.get(style_name, STYLES['default']).copy()
    width_mm = override_width_mm if override_width_mm else style['width_mm']
    width_in = width_mm / 25.4

    # Try the requested font, fall back to DejaVu Sans (always available)
    try:
        matplotlib.font_manager.findfont(style['font'], fallback_to_default=False)
    except Exception:
        style['font'] = 'DejaVu Sans'

    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': [style['font'], 'DejaVu Sans', 'Arial'],
        'font.size': style['font_size'],
        'axes.linewidth': style['line_width'],
        'lines.linewidth': style['line_width'],
        'svg.fonttype': 'none',  # text as text in SVG
    })
    return style, width_in


def _save(fig, output_path: str, dpi: int):
    """Save figure to the requested format."""
    ext = os.path.splitext(output_path)[1].lower()
    kwargs = {'bbox_inches': 'tight', 'pad_inches': 0.15}
    if ext in ('.tiff', '.tif'):
        kwargs['dpi'] = dpi
        kwargs['pil_kwargs'] = {'compression': 'tiff_lzw'}
    elif ext == '.png':
        kwargs['dpi'] = dpi
    elif ext == '.pdf':
        pass  # vector, no dpi needed
    # SVG is default
    fig.savefig(output_path, **kwargs)
    plt.close(fig)


def _validate_studies(data: dict, required_keys: list[str]):
    """Validate that data has a non-empty studies list with required keys."""
    studies = data.get('studies')
    if not studies or not isinstance(studies, list) or len(studies) == 0:
        raise ValueError("Data must contain a non-empty 'studies' list.")
    for i, s in enumerate(studies):
        for k in required_keys:
            if k not in s:
                raise ValueError(f"Study {i} missing required key '{k}'.")


# ---------------------------------------------------------------------------
# 1. Forest Plot
# ---------------------------------------------------------------------------

def draw_forest(data: dict, style: dict, width_in: float, title: str | None):
    """Generate a forest plot."""
    _validate_studies(data, ['name', 'effect', 'ci_lower', 'ci_upper', 'weight'])
    studies = data['studies']
    summary = data.get('summary')
    pi = data.get('prediction_interval')
    settings = data.get('settings', {})
    effect_label = settings.get('effect_label', 'Effect Size')
    null_value = settings.get('null_value', 1.0)
    log_scale = settings.get('log_scale', False)
    favours_left = settings.get('favours_left', '')
    favours_right = settings.get('favours_right', '')

    n = len(studies)
    colors = style['colors']

    # Figure dimensions
    row_h = 0.35
    header_h = 1.0
    footer_h = 1.8
    fig_h = header_h + n * row_h + footer_h + (0.4 if summary else 0)
    fig, ax = plt.subplots(figsize=(width_in, max(fig_h, 3)))

    # Collect all x-values for axis limits
    all_x = [s['effect'] for s in studies] + [s['ci_lower'] for s in studies] + [s['ci_upper'] for s in studies]
    if summary:
        all_x += [summary['effect'], summary['ci_lower'], summary['ci_upper']]
    if pi:
        all_x += [pi['lower'], pi['upper']]

    x_min_data = min(all_x)
    x_max_data = max(all_x)
    if log_scale and x_min_data > 0:
        pad_factor = 1.5
        x_min = x_min_data / pad_factor
        x_max = x_max_data * pad_factor
    else:
        pad = (x_max_data - x_min_data) * 0.25
        x_min = x_min_data - pad
        x_max = x_max_data + pad

    # Normalise weights for marker sizing
    weights = [s['weight'] for s in studies]
    max_w = max(weights) if weights else 1
    min_marker = 4
    max_marker = 14

    # Y positions (top to bottom)
    y_positions = list(range(n - 1, -1, -1))

    # Draw null line
    ax.axvline(null_value, color='grey', linewidth=0.5, linestyle='--', zorder=0)

    # Draw studies
    for i, s in enumerate(studies):
        y = y_positions[i]
        eff = s['effect']
        lo = s['ci_lower']
        hi = s['ci_upper']
        w = s['weight']
        marker_size = min_marker + (w / max_w) * (max_marker - min_marker)

        # CI line
        ax.plot([lo, hi], [y, y], color=colors['primary'], linewidth=style['line_width'], zorder=1)
        # Square marker
        ax.plot(eff, y, marker='s', color=colors['primary'], markersize=marker_size, zorder=2)

        # Annotations (name on left, effect [CI] and weight on right)
        ax.text(x_min - (x_max - x_min) * 0.02, y, s['name'],
                ha='right', va='center', fontsize=style['font_size'],
                color=colors['primary'], clip_on=False)

        ci_text = f"{eff:.2f} [{lo:.2f}, {hi:.2f}]"
        ax.text(x_max + (x_max - x_min) * 0.02, y, ci_text,
                ha='left', va='center', fontsize=style['font_size'] - 0.5,
                color=colors['primary'], clip_on=False, family='monospace')

        wt_text = f"{w:.1f}%"
        ax.text(x_max + (x_max - x_min) * 0.35, y, wt_text,
                ha='left', va='center', fontsize=style['font_size'] - 0.5,
                color=colors['primary'], clip_on=False)

    # Summary diamond
    summary_y = -1.2
    if summary:
        se = summary['effect']
        sl = summary['ci_lower']
        sh = summary['ci_upper']
        diamond_h = 0.35
        diamond = Polygon(
            [[sl, summary_y], [se, summary_y + diamond_h / 2],
             [sh, summary_y], [se, summary_y - diamond_h / 2]],
            closed=True, facecolor=colors['accent'], edgecolor=colors['primary'],
            linewidth=style['line_width'], zorder=3
        )
        ax.add_patch(diamond)
        ax.text(x_min - (x_max - x_min) * 0.02, summary_y, 'Summary',
                ha='right', va='center', fontsize=style['font_size'],
                fontweight='bold', color=colors['primary'], clip_on=False)
        ci_text = f"{se:.2f} [{sl:.2f}, {sh:.2f}]"
        ax.text(x_max + (x_max - x_min) * 0.02, summary_y, ci_text,
                ha='left', va='center', fontsize=style['font_size'] - 0.5,
                fontweight='bold', color=colors['primary'], clip_on=False, family='monospace')

    # Prediction interval
    if pi:
        pi_y = summary_y if summary else -1.2
        ax.plot([pi['lower'], pi['upper']], [pi_y, pi_y],
                color=colors['accent'], linewidth=style['line_width'],
                linestyle='--', zorder=1, label='Prediction interval')

    # Column headers
    header_y = n - 0.3 + 0.8
    ax.text(x_min - (x_max - x_min) * 0.02, header_y, 'Study',
            ha='right', va='center', fontsize=style['font_size'],
            fontweight='bold', color=colors['primary'], clip_on=False)
    ax.text(x_max + (x_max - x_min) * 0.02, header_y, f'{effect_label} [95% CI]',
            ha='left', va='center', fontsize=style['font_size'],
            fontweight='bold', color=colors['primary'], clip_on=False)
    ax.text(x_max + (x_max - x_min) * 0.35, header_y, 'Weight',
            ha='left', va='center', fontsize=style['font_size'],
            fontweight='bold', color=colors['primary'], clip_on=False)

    # Favours labels
    if favours_left or favours_right:
        bottom_y = summary_y - 0.8 if summary else -2.0
        mid = null_value
        if favours_left:
            ax.text((x_min + mid) / 2, bottom_y, favours_left,
                    ha='center', va='top', fontsize=style['font_size'] - 1,
                    fontstyle='italic', color=colors['primary'])
            ax.annotate('', xy=(x_min, bottom_y + 0.15), xytext=(mid, bottom_y + 0.15),
                        arrowprops=dict(arrowstyle='->', color=colors['primary'], lw=0.6))
        if favours_right:
            ax.text((x_max + mid) / 2, bottom_y, favours_right,
                    ha='center', va='top', fontsize=style['font_size'] - 1,
                    fontstyle='italic', color=colors['primary'])
            ax.annotate('', xy=(x_max, bottom_y + 0.15), xytext=(mid, bottom_y + 0.15),
                        arrowprops=dict(arrowstyle='->', color=colors['primary'], lw=0.6))

    # Axes
    if log_scale:
        ax.set_xscale('log')
    ax.set_xlim(x_min, x_max)
    y_lo = (summary_y - 1.2) if summary else -1.5
    ax.set_ylim(y_lo, n + 0.5)
    ax.set_xlabel(effect_label, fontsize=style['font_size'])
    ax.yaxis.set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    if title:
        ax.set_title(title, fontsize=style['font_size'] + 2, fontweight='bold', pad=10)

    fig.set_facecolor(colors['background'])
    return fig


# ---------------------------------------------------------------------------
# 2. Funnel Plot
# ---------------------------------------------------------------------------

def draw_funnel(data: dict, style: dict, width_in: float, title: str | None):
    """Generate a funnel plot."""
    _validate_studies(data, ['effect', 'se'])
    studies = data['studies']
    pooled = data.get('pooled_effect', 0)
    settings = data.get('settings', {})
    contour = settings.get('contour_enhanced', False)
    taf = settings.get('trim_and_fill', {})

    colors = style['colors']
    fig, ax = plt.subplots(figsize=(width_in, width_in * 0.8))

    effects = [s['effect'] for s in studies]
    ses = [s['se'] for s in studies]
    se_max = max(ses) * 1.15
    se_min = 0

    # Pseudo 95% CI funnel
    se_range = np.linspace(0.001, se_max, 200)
    ci_left = pooled - 1.96 * se_range
    ci_right = pooled + 1.96 * se_range

    if contour:
        # Contour-enhanced: p-value regions
        ci90_left = pooled - 1.645 * se_range
        ci90_right = pooled + 1.645 * se_range
        ci99_left = pooled - 2.576 * se_range
        ci99_right = pooled + 2.576 * se_range

        # p > 0.10 (white), 0.05 < p < 0.10 (light), 0.01 < p < 0.05 (medium), p < 0.01 (dark)
        ax.fill_betweenx(se_range, ci99_left, ci99_right, color='#e8e8e8', alpha=0.5, label='p < 0.01')
        ax.fill_betweenx(se_range, ci_left, ci_right, color='#cccccc', alpha=0.5, label='0.01 < p < 0.05')
        ax.fill_betweenx(se_range, ci90_left, ci90_right, color='#f5f5f5', alpha=0.5, label='0.05 < p < 0.10')
    else:
        ax.plot(ci_left, se_range, '--', color='grey', linewidth=0.7)
        ax.plot(ci_right, se_range, '--', color='grey', linewidth=0.7)

    # Pooled effect line
    ax.axvline(pooled, color=colors['primary'], linewidth=0.6, linestyle='-')

    # Study points
    ax.scatter(effects, ses, s=30, color=colors['primary'], zorder=3, label='Studies')

    # Trim-and-fill
    filled = taf.get('filled_studies', [])
    if filled:
        f_eff = [f['effect'] for f in filled]
        f_se = [f['se'] for f in filled]
        ax.scatter(f_eff, f_se, s=30, facecolors='none', edgecolors=colors['accent'],
                   linewidth=1.2, zorder=3, label='Filled (T&F)')

    ax.set_ylim(se_max, se_min)  # Inverted y-axis
    ax.set_xlabel('Effect Size', fontsize=style['font_size'])
    ax.set_ylabel('Standard Error', fontsize=style['font_size'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    if title:
        ax.set_title(title, fontsize=style['font_size'] + 2, fontweight='bold', pad=10)
    ax.legend(fontsize=style['font_size'] - 1, loc='lower right')

    fig.set_facecolor(colors['background'])
    return fig


# ---------------------------------------------------------------------------
# 3. SROC Curve
# ---------------------------------------------------------------------------

def draw_sroc(data: dict, style: dict, width_in: float, title: str | None):
    """Generate an SROC curve."""
    _validate_studies(data, ['sensitivity', 'specificity'])
    studies = data['studies']
    summary_pt = data.get('summary_point', {})
    conf_region = data.get('confidence_region', {})
    pred_region = data.get('prediction_region', {})

    colors = style['colors']
    fig, ax = plt.subplots(figsize=(width_in, width_in))

    # Chance line
    ax.plot([0, 1], [0, 1], '--', color='lightgrey', linewidth=0.8, label='Chance line')

    # Study bubbles
    for s in studies:
        x = 1.0 - s['specificity']
        y = s['sensitivity']
        n = s.get('n', 100)
        size = max(20, min(300, n / 2))
        ax.scatter(x, y, s=size, alpha=0.5, color=colors['accent'],
                   edgecolors=colors['primary'], linewidth=0.5, zorder=3)
        if 'name' in s:
            ax.annotate(s['name'], (x, y), fontsize=style['font_size'] - 2,
                        xytext=(5, 5), textcoords='offset points', alpha=0.7)

    # Confidence region (solid ellipse outline)
    if conf_region and 'points' in conf_region and len(conf_region['points']) >= 3:
        pts = np.array(conf_region['points'])
        # Convert: x = 1 - specificity, y = sensitivity
        xs = 1.0 - pts[:, 1] if pts.shape[1] == 2 else pts[:, 0]
        ys = pts[:, 0] if pts.shape[1] == 2 else pts[:, 1]
        # Close the polygon
        xs = np.append(xs, xs[0])
        ys = np.append(ys, ys[0])
        ax.plot(xs, ys, '-', color=colors['accent'], linewidth=1.2, label='95% confidence region')

    # Prediction region (dashed ellipse outline)
    if pred_region and 'points' in pred_region and len(pred_region['points']) >= 3:
        pts = np.array(pred_region['points'])
        xs = 1.0 - pts[:, 1] if pts.shape[1] == 2 else pts[:, 0]
        ys = pts[:, 0] if pts.shape[1] == 2 else pts[:, 1]
        xs = np.append(xs, xs[0])
        ys = np.append(ys, ys[0])
        ax.plot(xs, ys, '--', color=colors['accent'], linewidth=1.0, label='95% prediction region')

    # Summary operating point
    if summary_pt and 'sensitivity' in summary_pt and 'specificity' in summary_pt:
        sx = 1.0 - summary_pt['specificity']
        sy = summary_pt['sensitivity']
        ax.plot(sx, sy, 'D', color=colors['accent'], markersize=10,
                markeredgecolor=colors['primary'], markeredgewidth=1.2, zorder=5,
                label='Summary point')

    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel('1 - Specificity (FPR)', fontsize=style['font_size'])
    ax.set_ylabel('Sensitivity', fontsize=style['font_size'])
    ax.set_aspect('equal')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=style['font_size'] - 1, loc='lower right')
    if title:
        ax.set_title(title, fontsize=style['font_size'] + 2, fontweight='bold', pad=10)

    fig.set_facecolor(colors['background'])
    return fig


# ---------------------------------------------------------------------------
# 4. Network Graph
# ---------------------------------------------------------------------------

def _kamada_kawai_layout(treatments: list[dict], edges: list[dict]) -> dict:
    """Simple Kamada-Kawai-inspired layout using numpy only."""
    names = [t['name'] for t in treatments]
    n = len(names)
    if n == 0:
        return {}
    if n == 1:
        return {names[0]: (0.5, 0.5)}
    if n == 2:
        return {names[0]: (0.3, 0.5), names[1]: (0.7, 0.5)}

    # Build adjacency / distance matrix (shortest path via Floyd-Warshall)
    idx = {name: i for i, name in enumerate(names)}
    dist = np.full((n, n), float('inf'))
    np.fill_diagonal(dist, 0)
    for e in edges:
        i, j = idx.get(e['from']), idx.get(e['to'])
        if i is not None and j is not None:
            dist[i, j] = 1
            dist[j, i] = 1
    # Floyd-Warshall
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if dist[i, k] + dist[k, j] < dist[i, j]:
                    dist[i, j] = dist[i, k] + dist[k, j]
    # Replace inf with max + 1
    max_d = np.max(dist[dist < float('inf')])
    dist[dist == float('inf')] = max_d + 1

    # Initial layout: circle
    rng = np.random.default_rng(42)
    pos = np.zeros((n, 2))
    for i in range(n):
        angle = 2.0 * math.pi * i / n
        pos[i, 0] = 0.5 + 0.35 * math.cos(angle)
        pos[i, 1] = 0.5 + 0.35 * math.sin(angle)

    # Spring-electric optimisation (simple)
    L0 = 1.0 / max_d  # ideal edge length unit
    for iteration in range(200):
        forces = np.zeros_like(pos)
        for i in range(n):
            for j in range(i + 1, n):
                diff = pos[i] - pos[j]
                d_actual = max(np.linalg.norm(diff), 1e-6)
                d_ideal = dist[i, j] * L0
                # Spring force
                f_mag = (d_actual - d_ideal) / d_actual
                force = f_mag * diff * 0.1
                forces[i] -= force
                forces[j] += force
        step = 0.05 / (1 + iteration * 0.02)
        pos += forces * step

    # Normalize to [0.1, 0.9]
    for dim in range(2):
        mn, mx = pos[:, dim].min(), pos[:, dim].max()
        if mx - mn > 1e-8:
            pos[:, dim] = 0.1 + 0.8 * (pos[:, dim] - mn) / (mx - mn)
        else:
            pos[:, dim] = 0.5

    return {names[i]: (pos[i, 0], pos[i, 1]) for i in range(n)}


def draw_network(data: dict, style: dict, width_in: float, title: str | None):
    """Generate a network graph."""
    treatments = data.get('treatments', [])
    edges = data.get('edges', [])
    if not treatments:
        raise ValueError("Network data must contain a non-empty 'treatments' list.")

    colors = style['colors']
    fig, ax = plt.subplots(figsize=(width_in, width_in * 0.85))

    layout = _kamada_kawai_layout(treatments, edges)

    # Node sizes
    patients = {t['name']: t.get('n_patients', 100) for t in treatments}
    max_p = max(patients.values()) if patients else 1
    min_node = 300
    max_node = 2000

    # Draw edges
    edge_studies = [e.get('n_studies', 1) for e in edges]
    max_studies = max(edge_studies) if edge_studies else 1
    for e in edges:
        p1 = layout.get(e['from'])
        p2 = layout.get(e['to'])
        if p1 and p2:
            ns = e.get('n_studies', 1)
            lw = 1.0 + (ns / max_studies) * 6.0
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], '-',
                    color='#999999', linewidth=lw, zorder=1)
            # Edge label
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            ax.text(mx, my, str(ns), ha='center', va='center',
                    fontsize=style['font_size'] - 1, color='#666666',
                    bbox=dict(boxstyle='round,pad=0.15', facecolor='white', edgecolor='none', alpha=0.8))

    # Draw nodes
    for t in treatments:
        name = t['name']
        pos = layout.get(name, (0.5, 0.5))
        np_ = t.get('n_patients', 100)
        size = min_node + (np_ / max_p) * (max_node - min_node)
        ax.scatter(pos[0], pos[1], s=size, color=colors['accent'],
                   edgecolors=colors['primary'], linewidth=1.5, zorder=3)
        ax.text(pos[0], pos[1] - 0.06, name, ha='center', va='top',
                fontsize=style['font_size'], fontweight='bold',
                color=colors['primary'], zorder=4)

    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.1, 1.1)
    ax.set_aspect('equal')
    ax.axis('off')
    if title:
        ax.set_title(title, fontsize=style['font_size'] + 2, fontweight='bold', pad=10)

    fig.set_facecolor(colors['background'])
    return fig


# ---------------------------------------------------------------------------
# 5. PRISMA Flow Diagram
# ---------------------------------------------------------------------------

def draw_prisma(data: dict, style: dict, width_in: float, title: str | None):
    """Generate a PRISMA 2020 flow diagram."""
    ident = data.get('identification', {})
    screen = data.get('screening', {})
    elig = data.get('eligibility', {})
    incl = data.get('included', {})

    colors = style['colors']
    fig_h = width_in * 1.2
    fig, ax = plt.subplots(figsize=(width_in, fig_h))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    box_color = colors['background']
    edge_color = colors['primary']
    accent = colors['accent']
    fs = style['font_size']

    def _box(x, y, w, h, text, bold=False):
        """Draw a rounded box with text."""
        rect = FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                               boxstyle="round,pad=0.1",
                               facecolor=box_color, edgecolor=edge_color,
                               linewidth=style['line_width'])
        ax.add_patch(rect)
        weight = 'bold' if bold else 'normal'
        ax.text(x, y, text, ha='center', va='center', fontsize=fs,
                fontweight=weight, color=edge_color, wrap=True,
                multialignment='center')

    def _arrow(x1, y1, x2, y2):
        """Draw an arrow from (x1,y1) to (x2,y2)."""
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                     arrowprops=dict(arrowstyle='->', color=edge_color,
                                     lw=style['line_width']))

    # Layout constants
    col_left = 3.5
    col_right = 7.5

    # Stage 1: Identification
    db = ident.get('databases', 0)
    reg = ident.get('registers', 0)
    other = ident.get('other', 0)
    total_id = db + reg + other
    id_text = f"Records identified\n(databases: {db}, registers: {reg}, other: {other})\nn = {total_id}"
    _box(col_left, 9.0, 4.5, 1.2, id_text, bold=True)

    # Stage 2: Screening
    after_dup = screen.get('after_duplicates', 0)
    excluded_ta = screen.get('excluded_title_abstract', 0)
    dup_removed = total_id - after_dup
    _arrow(col_left, 8.35, col_left, 7.45)
    _box(col_left, 7.0, 4.5, 0.9, f"Records after duplicates removed\nn = {after_dup}")

    _arrow(col_left, 6.55, col_left, 5.75)
    _box(col_left, 5.3, 4.5, 0.9, f"Records screened\nn = {after_dup}")

    # Exclusion box (right)
    _arrow(5.75, 5.3, 6.5, 5.3)
    _box(col_right, 5.3, 2.5, 0.9, f"Records excluded\nn = {excluded_ta}")

    # Stage 3: Eligibility
    ft_assessed = elig.get('full_text_assessed', 0)
    ft_excluded = elig.get('excluded_full_text', 0)
    _arrow(col_left, 4.85, col_left, 4.05)
    _box(col_left, 3.6, 4.5, 0.9, f"Full-text articles assessed\nn = {ft_assessed}")

    # Exclusion reasons box
    reasons = elig.get('exclusion_reasons', [])
    reason_lines = [f"Full-text excluded (n = {ft_excluded})"]
    for r in reasons:
        reason_lines.append(f"  {r['reason']}: {r['n']}")
    reason_text = '\n'.join(reason_lines)
    reason_h = 0.9 + len(reasons) * 0.3
    _arrow(5.75, 3.6, 6.5, 3.6)
    _box(col_right, 3.6, 2.5, reason_h, reason_text)

    # Stage 4: Included
    n_studies = incl.get('studies', 0)
    n_reports = incl.get('reports', 0)
    _arrow(col_left, 3.15, col_left, 2.15)
    incl_text = f"Studies included\nn = {n_studies}"
    if n_reports:
        incl_text += f"\n(reports: {n_reports})"
    _box(col_left, 1.7, 4.5, 0.9, incl_text, bold=True)

    # Stage labels on far left
    stage_labels = [
        (0.7, 9.0, 'Identification'),
        (0.7, 6.15, 'Screening'),
        (0.7, 3.6, 'Eligibility'),
        (0.7, 1.7, 'Included'),
    ]
    for sx, sy, label in stage_labels:
        ax.text(sx, sy, label, ha='center', va='center', fontsize=fs - 1,
                fontweight='bold', color=accent, rotation=0, fontstyle='italic')

    if title:
        ax.set_title(title, fontsize=fs + 2, fontweight='bold', pad=10)

    fig.set_facecolor(colors['background'])
    return fig


# ---------------------------------------------------------------------------
# 6. Cumulative Forest Plot
# ---------------------------------------------------------------------------

def draw_cumulative(data: dict, style: dict, width_in: float, title: str | None):
    """Generate a cumulative meta-analysis forest plot."""
    _validate_studies(data, ['name', 'cumulative_effect', 'cumulative_ci_lower', 'cumulative_ci_upper'])
    studies = data['studies']
    settings = data.get('settings', {})
    effect_label = settings.get('effect_label', 'Effect Size')
    null_value = settings.get('null_value', 1.0)
    log_scale = settings.get('log_scale', False)

    n = len(studies)
    colors = style['colors']

    row_h = 0.35
    fig_h = 1.5 + n * row_h + 1.0
    fig, ax = plt.subplots(figsize=(width_in, max(fig_h, 3)))

    all_x = []
    for s in studies:
        all_x += [s['cumulative_effect'], s['cumulative_ci_lower'], s['cumulative_ci_upper']]

    x_min_data = min(all_x)
    x_max_data = max(all_x)
    if log_scale and x_min_data > 0:
        x_min = x_min_data / 1.4
        x_max = x_max_data * 1.4
    else:
        pad = (x_max_data - x_min_data) * 0.25
        x_min = x_min_data - pad
        x_max = x_max_data + pad

    y_positions = list(range(n - 1, -1, -1))

    # Null line
    ax.axvline(null_value, color='grey', linewidth=0.5, linestyle='--', zorder=0)

    # Shade cumulative path
    cum_effects = [s['cumulative_effect'] for s in studies]
    cum_lo = [s['cumulative_ci_lower'] for s in studies]
    cum_hi = [s['cumulative_ci_upper'] for s in studies]
    ax.fill_betweenx(y_positions, cum_lo, cum_hi,
                     alpha=0.1, color=colors['accent'], zorder=0)
    ax.plot(cum_effects, y_positions, '-', color=colors['accent'],
            linewidth=style['line_width'], alpha=0.6, zorder=1)

    for i, s in enumerate(studies):
        y = y_positions[i]
        eff = s['cumulative_effect']
        lo = s['cumulative_ci_lower']
        hi = s['cumulative_ci_upper']

        # CI line
        ax.plot([lo, hi], [y, y], color=colors['primary'], linewidth=style['line_width'], zorder=2)
        # Diamond for cumulative
        dh = 0.25
        diamond = Polygon(
            [[lo, y], [eff, y + dh / 2], [hi, y], [eff, y - dh / 2]],
            closed=True, facecolor=colors['accent'], edgecolor=colors['primary'],
            linewidth=style['line_width'] * 0.7, alpha=0.8, zorder=3
        )
        ax.add_patch(diamond)

        # Label
        ax.text(x_min - (x_max - x_min) * 0.02, y, s['name'],
                ha='right', va='center', fontsize=style['font_size'],
                color=colors['primary'], clip_on=False)
        ci_text = f"{eff:.2f} [{lo:.2f}, {hi:.2f}]"
        ax.text(x_max + (x_max - x_min) * 0.02, y, ci_text,
                ha='left', va='center', fontsize=style['font_size'] - 0.5,
                color=colors['primary'], clip_on=False, family='monospace')

    # Header
    header_y = n - 1 + 1.0
    ax.text(x_min - (x_max - x_min) * 0.02, header_y, 'Study added',
            ha='right', va='center', fontsize=style['font_size'],
            fontweight='bold', color=colors['primary'], clip_on=False)
    ax.text(x_max + (x_max - x_min) * 0.02, header_y, f'Cumulative {effect_label} [95% CI]',
            ha='left', va='center', fontsize=style['font_size'],
            fontweight='bold', color=colors['primary'], clip_on=False)

    if log_scale:
        ax.set_xscale('log')
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(-1, n + 0.8)
    ax.set_xlabel(effect_label, fontsize=style['font_size'])
    ax.yaxis.set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    if title:
        ax.set_title(title, fontsize=style['font_size'] + 2, fontweight='bold', pad=10)

    fig.set_facecolor(colors['background'])
    return fig


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

DRAWERS = {
    'forest': draw_forest,
    'funnel': draw_funnel,
    'sroc': draw_sroc,
    'network': draw_network,
    'prisma': draw_prisma,
    'cumulative': draw_cumulative,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog='FigureEngine',
        description='Publication-quality meta-analysis figure generator.',
        epilog='Supported output formats: .svg (default), .tiff, .png, .pdf',
    )
    parser.add_argument('--type', required=True, choices=FIGURE_TYPES,
                        help='Figure type to generate')
    parser.add_argument('--data', required=True,
                        help='Path to JSON input file')
    parser.add_argument('--style', default='default', choices=list(STYLES.keys()),
                        help='Journal style template (default: default)')
    parser.add_argument('--output', required=True,
                        help='Output file path (format inferred from extension)')
    parser.add_argument('--dpi', type=int, default=300,
                        help='DPI for raster formats (default: 300)')
    parser.add_argument('--width', type=float, default=None,
                        help='Override width in mm')
    parser.add_argument('--title', default=None,
                        help='Optional figure title')
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load data
    if not os.path.isfile(args.data):
        print(f"Error: data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.data, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {args.data}: {e}", file=sys.stderr)
        sys.exit(1)

    # Apply style
    style, width_in = _apply_style(args.style, args.width)

    # Validate data is not empty
    fig_type = args.type
    if fig_type in ('forest', 'funnel', 'sroc', 'cumulative'):
        studies = data.get('studies', [])
        if not studies:
            print(f"Error: no studies found in data for {fig_type} plot.", file=sys.stderr)
            sys.exit(1)
    elif fig_type == 'network':
        if not data.get('treatments'):
            print("Error: no treatments found in data for network graph.", file=sys.stderr)
            sys.exit(1)
    elif fig_type == 'prisma':
        if not data.get('identification') and not data.get('included'):
            print("Error: PRISMA data requires at least identification or included data.", file=sys.stderr)
            sys.exit(1)

    # Draw
    try:
        drawer = DRAWERS[fig_type]
        fig = drawer(data, style, width_in, args.title)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error generating {fig_type} figure: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure output directory exists
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Save
    try:
        _save(fig, args.output, args.dpi)
    except Exception as e:
        print(f"Error saving figure: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Figure saved: {args.output}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
