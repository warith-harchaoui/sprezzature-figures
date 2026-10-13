#!/usr/bin/env python3
"""
_project3d — the camera shared by the three-dimensional make_<id>.py figures.

One rotation and one perspective divide, used by every figure that draws
a scene rather than a plane. It was copied between ``make_scatter3d`` and
``make_wireframe3d`` first, and four more figures were about to copy it
again, which is the point at which an identical twenty lines stops being
a coincidence.

The three places those two copies genuinely differed are parameters here
rather than edits:

* **How the scene is fitted to the box.** A point cloud is squared off
  against the smaller of width and height so the axis gizmo stays inside
  the frame; a surface is keyed to the width alone so it claims the
  frame rather than floating in whitespace. ``fit`` picks between them.
* **Zoom.** The interactive figures multiply the fit scale so the
  server-rendered still and the browser's first frame coincide; the
  static ones leave it at one.
* **Shape.** A cloud is a flat list of points, a lattice is a grid. This
  takes and returns flat arrays; a caller holding a grid ravels on the
  way in and reshapes on the way out, which is one line each and keeps
  the camera ignorant of the caller's topology.

Vertical exaggeration is deliberately *not* here. Stretching z to make a
ripple read is a statement about the data, not about the camera, and the
figure that makes it should be the figure that shows it.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

#: How far down the camera's -y axis the eye sits, in model units. Large
#: enough that the perspective is a hint rather than a fisheye.
_EYE_DISTANCE = 4.0

#: Half-width of the model space the scene is scaled against. A rotated
#: unit cube spans about 1.4; the extra leaves head-room so a vertical
#: axis arm clears the title band.
_SPAN = 1.55


def rotate(points: np.ndarray, elev_deg: float, azim_deg: float) -> np.ndarray:
    """Rotate model-space points by an azimuth then an elevation.

    The azimuth turns the scene about the world ``z`` (up) axis; the
    elevation then tips the camera down toward the floor. Working on the
    stacked ``(N, 3)`` array keeps the whole scene in one matmul.

    Parameters
    ----------
    points : numpy.ndarray
        ``(N, 3)`` points ``(x, y, z)`` in model space.
    elev_deg, azim_deg : float
        Elevation and azimuth of the camera, in degrees.

    Returns
    -------
    numpy.ndarray
        ``(N, 3)`` rotated points in camera space.
    """
    az = np.radians(azim_deg)
    el = np.radians(elev_deg)
    # Azimuth: rotate about z.
    ca, sa = np.cos(az), np.sin(az)
    rz = np.array([[ca, -sa, 0.0], [sa, ca, 0.0], [0.0, 0.0, 1.0]])
    # Elevation: rotate about x (tip toward viewer).
    ce, se = np.cos(el), np.sin(el)
    rx = np.array([[1.0, 0.0, 0.0], [0.0, ce, -se], [0.0, se, ce]])
    return points @ rz.T @ rx.T


def project(
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    *,
    elev_deg: float,
    azim_deg: float,
    plot_w: float,
    plot_h: float,
    cx: float,
    cy: float,
    zoom: float = 1.0,
    fit: str = "box",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rotate a scene and project it to pixel space with a light perspective.

    This is the *reference* projection: where a figure ships interactive
    chrome, its embedded JavaScript reproduces this arithmetic exactly --
    rotation, perspective divide, fit scale, zoom multiplier -- so the
    server-rendered still and the browser's first frame coincide.

    Parameters
    ----------
    xs, ys, zs : numpy.ndarray
        ``(N,)`` model-space coordinates. A caller holding a grid passes
        ``grid.ravel()`` and reshapes the results.
    elev_deg, azim_deg : float
        Camera elevation and azimuth, in degrees.
    plot_w, plot_h : float
        Pixel extent available for the projected scene.
    cx, cy : float
        Pixel centre the scene is drawn around.
    zoom : float, optional
        Multiplier on the fit scale; 1.0 is the still's framing.
    fit : str, optional
        ``"box"`` scales against the smaller of width and height, which
        keeps an axis gizmo inside the frame; ``"width"`` scales against
        the width alone and lets the shorter projected height follow.

    Returns
    -------
    tuple of numpy.ndarray
        ``(px, py, depth)``: pixel x, pixel y, and a depth that grows
        toward the camera, for painter's-algorithm ordering or shading.
    """
    if fit not in ("box", "width"):
        raise ValueError(f"fit is 'box' or 'width', got {fit!r}")
    points = np.column_stack([xs, ys, zs])
    camera = rotate(points, elev_deg, azim_deg)
    cx_m, cy_m, cz_m = camera[:, 0], camera[:, 1], camera[:, 2]

    # Simple perspective: points farther from the camera shrink slightly.
    # The camera sits down the -y axis, so larger y is farther away.
    perspective = _EYE_DISTANCE / (_EYE_DISTANCE - cy_m)
    sx = cx_m * perspective
    sy = cz_m * perspective  # camera-space up maps to screen up

    extent = min(plot_w, plot_h) if fit == "box" else plot_w
    scale = extent / (2.0 * _SPAN) * zoom
    px = cx + sx * scale
    py = cy - sy * scale  # SVG y grows downward

    # Depth for ordering and sizing: nearer the camera is larger. The
    # camera looks down -y, so smaller cy_m is nearer; negate so "near"
    # is the maximum.
    return px, py, -cy_m
