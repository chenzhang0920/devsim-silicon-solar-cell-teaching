"""Render reusable teaching animations as self-contained GIF images."""
from __future__ import annotations

import os
import tempfile

import numpy as np
import matplotlib.pyplot as plt


def _default_fig():
    """Create the default single-panel animation canvas."""
    return plt.subplots(figsize=(8, 4.2))


def frames_to_gif(draw, frames, make_fig=None, interval: int = 350,
                  dpi: int = 100) -> bytes:
    """Render caller-supplied Matplotlib frames into in-memory GIF bytes."""
    from matplotlib.animation import FuncAnimation

    frame_idx = range(frames) if isinstance(frames, int) else list(frames)

    if make_fig is None:
        make_fig = _default_fig

    fig, axes = make_fig()

    def update(k: int) -> None:
        if isinstance(axes, np.ndarray):
            for a in axes.ravel():
                a.clear()
        elif isinstance(axes, (list, tuple)):
            for a in axes:
                a.clear()
        else:
            axes.clear()
        draw(k, axes)


    ani = FuncAnimation(fig, update, frames=frame_idx)


    try:
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "animation.gif")
            ani.save(out, writer="pillow", fps=1000 / interval, dpi=dpi)
            with open(out, "rb") as f:
                data = f.read()
    finally:
        plt.close(fig)
    return data
