"""Procedural map generation using multi-octave noise."""
import random
from typing import Dict, Optional, Tuple

import numpy as np

from game.constants import *
from game.hex_grid import Hex, offset_to_axial


# ── Noise ─────────────────────────────────────────────────────────────────────

def _bilinear_noise(width: int, height: int, freq: float, seed: int) -> np.ndarray:
    """Single octave: random grid bilinearly upsampled to (height, width)."""
    rng = np.random.RandomState(seed)
    nx = max(2, int(width  * freq) + 2)
    ny = max(2, int(height * freq) + 2)
    g  = rng.rand(ny, nx).astype(np.float32)

    xs = np.linspace(0, nx - 2, width,  dtype=np.float32)
    ys = np.linspace(0, ny - 2, height, dtype=np.float32)
    ix = np.floor(xs).astype(np.int32)
    iy = np.floor(ys).astype(np.int32)
    tx = xs - ix
    ty = ys - iy

    ix1 = np.clip(ix + 1, 0, nx - 1)
    iy1 = np.clip(iy + 1, 0, ny - 1)

    # shapes: (H, W) via outer product-style indexing
    v00 = g[np.ix_(iy,  ix )]
    v10 = g[np.ix_(iy,  ix1)]
    v01 = g[np.ix_(iy1, ix )]
    v11 = g[np.ix_(iy1, ix1)]

    tx2d = tx[np.newaxis, :]
    ty2d = ty[:, np.newaxis]

    return ((v00*(1-tx2d) + v10*tx2d) * (1-ty2d) +
            (v01*(1-tx2d) + v11*tx2d) *    ty2d)


def _fbm(width: int, height: int, base_freq: float, octaves: int, seed: int) -> np.ndarray:
    """Fractional Brownian Motion: sum of octaves with halving amplitude."""
    out   = np.zeros((height, width), dtype=np.float32)
    amp   = 1.0
    freq  = base_freq
    total = 0.0
    for o in range(octaves):
        out   += _bilinear_noise(width, height, freq, seed + o * 997) * amp
        total += amp
        amp   *= 0.5
        freq  *= 2.0
    out /= total
    mn, mx = out.min(), out.max()
    if mx > mn:
        out = (out - mn) / (mx - mn)
    return out


# ── Terrain assignment ────────────────────────────────────────────────────────

def _classify(elev: float, moist: float, lat: float) -> str:
    """Map (elevation, moisture, latitude) → terrain type."""
    if elev < 0.22:
        return TERRAIN_DEEP_WATER
    if elev < 0.30:
        return TERRAIN_WATER
    if elev < 0.34:
        return TERRAIN_COAST

    # Land
    if lat > 0.88:
        return TERRAIN_ARCTIC
    if elev > 0.82:
        return TERRAIN_MOUNTAINS
    if elev > 0.62:
        return TERRAIN_HILLS if moist > 0.35 else TERRAIN_MOUNTAINS
    if moist < 0.22:
        return TERRAIN_DESERT
    if moist > 0.62:
        return TERRAIN_FOREST
    return TERRAIN_PLAINS


# ── Public API ────────────────────────────────────────────────────────────────

TerrainMap = Dict[Tuple[int, int], str]


def generate_map(
    width:       int            = DEFAULT_MAP_WIDTH,
    height:      int            = DEFAULT_MAP_HEIGHT,
    seed:        Optional[int]  = None,
    water_ratio: float          = 0.38,
    city_ratio:  float          = 0.025,
) -> TerrainMap:
    """
    Generate a rectangular hex map as a dict { (q, r): terrain_id }.
    Uses odd-r offset internally; converts to axial for the key.
    """
    if seed is None:
        seed = random.randint(0, 999_999)

    rng = random.Random(seed)

    elev  = _fbm(width, height, base_freq=0.12, octaves=6, seed=seed)
    moist = _fbm(width, height, base_freq=0.18, octaves=4, seed=seed + 3001)

    # Rescale elevation so `water_ratio` fraction of cells are water
    sorted_e = np.sort(elev.ravel())
    threshold = float(sorted_e[int(water_ratio * len(sorted_e))])
    if threshold > 0:
        elev = elev / threshold * 0.30   # water boundary → 0.30
    elev = np.clip(elev, 0.0, 1.0)

    terrain_map: TerrainMap = {}

    for row in range(height):
        lat_factor = abs(row / height - 0.5) * 2.0  # 0 at equator, 1 at poles
        for col in range(width):
            h = offset_to_axial(col, row)
            terrain_map[h.to_tuple()] = _classify(
                float(elev[row, col]),
                float(moist[row, col]),
                lat_factor,
            )

    # Scatter urban / industrial on passable land
    land = [k for k, v in terrain_map.items()
            if v in (TERRAIN_PLAINS, TERRAIN_HILLS, TERRAIN_COAST)]
    n_cities = int(len(land) * city_ratio)
    for coord in rng.sample(land, min(n_cities, len(land))):
        terrain_map[coord] = TERRAIN_URBAN if rng.random() < 0.65 else TERRAIN_INDUSTRIAL

    return terrain_map


def generate_elevation_map(terrain_map: TerrainMap, seed: int) -> Dict[Tuple[int, int], int]:
    """Generate integer elevation (0-10) for each hex, terrain-consistent.

    Uses TERRAIN_ELEVATION_RANGE so mountains are always high, water always
    low, etc.  A different seed offset means the elevation noise is independent
    of the terrain noise while still being fully deterministic.
    """
    rng = random.Random(seed ^ 0xE1E07A71)
    result: Dict[Tuple[int, int], int] = {}
    for pos, terrain in terrain_map.items():
        lo, hi = TERRAIN_ELEVATION_RANGE.get(terrain, (2, 4))
        result[pos] = rng.randint(lo, hi)
    return result


def generate_tactical_map(
    parent_terrain: str,
    composite_key:  str,
    seed_base:      int,
) -> TerrainMap:
    """
    Generate the 19-hex mapsheet-level tile grid for one low-altitude sub-hex.
    Each tile ≈ one Battletech mapsheet (500m).
    """
    from game.hex_grid import hex_range
    from game.constants import TACTICAL_RADIUS
    seed = seed_base ^ (hash(composite_key) & 0xFFFFFF)
    rng  = random.Random(seed)
    hexes = hex_range(Hex(0, 0), TACTICAL_RADIUS)

    water_like    = parent_terrain in (TERRAIN_DEEP_WATER, TERRAIN_WATER, TERRAIN_COAST)
    mountain_like = parent_terrain in (TERRAIN_MOUNTAINS, TERRAIN_VOLCANIC)

    result: TerrainMap = {}
    for h in hexes:
        r = rng.random()
        if water_like:
            t = TERRAIN_WATER if r < 0.75 else TERRAIN_COAST
        elif mountain_like:
            t = TERRAIN_MOUNTAINS if r < 0.55 else TERRAIN_HILLS
        elif parent_terrain == TERRAIN_FOREST:
            t = TERRAIN_FOREST if r < 0.65 else TERRAIN_PLAINS
        elif parent_terrain == TERRAIN_HILLS:
            t = TERRAIN_HILLS if r < 0.5 else (TERRAIN_PLAINS if r < 0.85 else TERRAIN_FOREST)
        elif parent_terrain == TERRAIN_PLAINS:
            if   r < 0.70: t = TERRAIN_PLAINS
            elif r < 0.85: t = TERRAIN_HILLS
            else:          t = TERRAIN_FOREST
        elif parent_terrain in (TERRAIN_URBAN, TERRAIN_INDUSTRIAL):
            if   r < 0.45: t = parent_terrain
            elif r < 0.75: t = TERRAIN_PLAINS
            else:          t = TERRAIN_HILLS
        elif parent_terrain == TERRAIN_DESERT:
            t = TERRAIN_DESERT if r < 0.80 else TERRAIN_HILLS
        elif parent_terrain == TERRAIN_ARCTIC:
            t = TERRAIN_ARCTIC if r < 0.80 else TERRAIN_HILLS
        else:
            t = rng.choice([TERRAIN_PLAINS, TERRAIN_PLAINS, TERRAIN_HILLS,
                            TERRAIN_FOREST])
        result[h.to_tuple()] = t
    return result


def generate_operational_map(
    parent_terrain: str,
    parent_hex: Tuple[int, int],
    seed_base: int,
) -> TerrainMap:
    """
    Generate the sub-map for one strategic hex (OPERATIONAL_RADIUS).
    Returns axial-keyed terrain dict (local coordinates, origin 0,0).
    """
    from game.hex_grid import hex_range
    seed = seed_base ^ (hash(parent_hex) & 0xFFFFFF)
    rng  = random.Random(seed)

    # Build list of local axial hexes
    from game.constants import OPERATIONAL_RADIUS
    hexes = hex_range(Hex(0, 0), OPERATIONAL_RADIUS)

    result: TerrainMap = {}
    for h in hexes:
        r = rng.random()
        if parent_terrain == TERRAIN_DEEP_WATER:
            t = TERRAIN_DEEP_WATER
        elif parent_terrain == TERRAIN_WATER:
            t = TERRAIN_DEEP_WATER if r < 0.20 else TERRAIN_WATER
        elif parent_terrain == TERRAIN_COAST:
            if r < 0.35:   t = TERRAIN_COAST
            elif r < 0.65: t = TERRAIN_WATER
            else:          t = TERRAIN_PLAINS
        elif parent_terrain in (TERRAIN_MOUNTAINS, TERRAIN_VOLCANIC):
            t = TERRAIN_MOUNTAINS if r < 0.5 else TERRAIN_HILLS
        elif parent_terrain == TERRAIN_FOREST:
            t = TERRAIN_FOREST if r < 0.6 else TERRAIN_PLAINS
        elif parent_terrain in (TERRAIN_URBAN, TERRAIN_INDUSTRIAL):
            if r < 0.4:
                t = parent_terrain
            elif r < 0.7:
                t = TERRAIN_PLAINS
            else:
                t = TERRAIN_HILLS
        elif parent_terrain == TERRAIN_DESERT:
            t = TERRAIN_DESERT if r < 0.7 else TERRAIN_PLAINS
        elif parent_terrain == TERRAIN_ARCTIC:
            t = TERRAIN_ARCTIC if r < 0.7 else TERRAIN_HILLS
        else:
            t = rng.choice([TERRAIN_PLAINS, TERRAIN_PLAINS, TERRAIN_HILLS,
                            TERRAIN_FOREST, TERRAIN_COAST])
        result[h.to_tuple()] = t
    return result
