"""Shared, color-blind-friendly plotting style for classroom figures."""
import matplotlib as mpl

C_BLUE = "#2c7fb8"
C_ORANGE = "#d95f0e"
C_GREEN = "#2ca25f"
C_YELLOW = "#f0a202"
C_GRAY = "#7a8790"
C_DARK = "#34424c"
C_GRID = "#d9e1e6"
C_LIGHT_BLUE = "#dceef8"


def apply_classroom_style() -> None:
    """Apply the shared projector-readable Matplotlib style."""
    mpl.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "font.family": "DejaVu Sans",
        "font.size": 14,
        "axes.titlesize": 17,
        "axes.titleweight": "bold",
        "axes.labelsize": 15,
        "axes.edgecolor": C_DARK,
        "axes.linewidth": 0.9,
        "xtick.labelsize": 13,
        "ytick.labelsize": 13,
        "legend.fontsize": 12.5,
        "lines.linewidth": 2.3,
        "lines.markersize": 6.5,
        "grid.color": C_GRID,
        "grid.linewidth": 0.7,
        "grid.alpha": 0.9,
    })


apply_classroom_style()
