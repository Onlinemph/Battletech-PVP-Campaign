"""Axial hex coordinate system with cube-coordinate math (flat-top orientation)."""
import math
from typing import List, Tuple


class Hex:
    """Immutable axial hex coordinate (q, r)."""
    __slots__ = ("q", "r")

    def __init__(self, q: int, r: int):
        object.__setattr__(self, "q", int(q))
        object.__setattr__(self, "r", int(r))

    def __setattr__(self, *_):
        raise AttributeError("Hex is immutable")

    @property
    def s(self) -> int:
        return -self.q - self.r

    def __eq__(self, other) -> bool:
        return isinstance(other, Hex) and self.q == other.q and self.r == other.r

    def __hash__(self) -> int:
        return hash((self.q, self.r))

    def __repr__(self) -> str:
        return f"Hex({self.q}, {self.r})"

    def __add__(self, other: "Hex") -> "Hex":
        return Hex(self.q + other.q, self.r + other.r)

    def __sub__(self, other: "Hex") -> "Hex":
        return Hex(self.q - other.q, self.r - other.r)

    def to_tuple(self) -> Tuple[int, int]:
        return (self.q, self.r)

    @classmethod
    def from_tuple(cls, t: Tuple[int, int]) -> "Hex":
        return cls(t[0], t[1])


# Six axial direction vectors (flat-top, starting East, going counter-clockwise)
HEX_DIRECTIONS = [
    Hex( 1,  0),   # 0 E
    Hex( 1, -1),   # 1 NE
    Hex( 0, -1),   # 2 NW
    Hex(-1,  0),   # 3 W
    Hex(-1,  1),   # 4 SW
    Hex( 0,  1),   # 5 SE
]


def hex_distance(a: Hex, b: Hex) -> int:
    return max(abs(a.q - b.q), abs(a.r - b.r), abs(a.s - b.s))


def hex_neighbor(h: Hex, direction: int) -> Hex:
    return h + HEX_DIRECTIONS[direction % 6]


def hex_neighbors(h: Hex) -> List[Hex]:
    return [h + d for d in HEX_DIRECTIONS]


def hex_ring(center: Hex, radius: int) -> List[Hex]:
    """All hexes exactly `radius` steps from center."""
    if radius == 0:
        return [center]
    results: List[Hex] = []
    h = center + Hex(-radius, 0)   # start SW corner
    for i in range(6):
        for _ in range(radius):
            results.append(h)
            h = hex_neighbor(h, (i + 2) % 6)
    return results


def hex_range(center: Hex, radius: int) -> List[Hex]:
    """All hexes within `radius` steps of center (inclusive)."""
    results: List[Hex] = []
    for q in range(-radius, radius + 1):
        r_lo = max(-radius, -q - radius)
        r_hi = min( radius, -q + radius)
        for r in range(r_lo, r_hi + 1):
            results.append(Hex(center.q + q, center.r + r))
    return results


# ── Pixel ↔ Hex conversions (flat-top) ────────────────────────────────────────

def hex_to_pixel(h: Hex, size: float, ox: float = 0.0, oy: float = 0.0) -> Tuple[float, float]:
    """Axial → pixel center for a flat-top hex of radius `size`."""
    x = size * 1.5 * h.q
    y = size * (math.sqrt(3) * 0.5 * h.q + math.sqrt(3) * h.r)
    return (x + ox, y + oy)


def pixel_to_hex(px: float, py: float, size: float, ox: float = 0.0, oy: float = 0.0) -> Hex:
    """Pixel → nearest axial hex coord (flat-top)."""
    px -= ox
    py -= oy
    q = (2.0 / 3.0 * px) / size
    r = (-1.0 / 3.0 * px + math.sqrt(3) / 3.0 * py) / size
    return _hex_round(q, r)


def _hex_round(fq: float, fr: float) -> Hex:
    fs = -fq - fr
    q, r, s = round(fq), round(fr), round(fs)
    dq, dr, ds = abs(q - fq), abs(r - fr), abs(s - fs)
    if dq > dr and dq > ds:
        q = -r - s
    elif dr > ds:
        r = -q - s
    return Hex(int(q), int(r))


def hex_corners(h: Hex, size: float, ox: float = 0.0, oy: float = 0.0) -> List[Tuple[float, float]]:
    """Six corner pixels of a flat-top hex."""
    cx, cy = hex_to_pixel(h, size, ox, oy)
    return [
        (cx + size * math.cos(math.pi / 3 * i),
         cy + size * math.sin(math.pi / 3 * i))
        for i in range(6)
    ]


# ── Offset ↔ Axial (odd-r offset, used for rectangular map storage) ────────────

def offset_to_axial(col: int, row: int) -> Hex:
    """Convert odd-r offset grid position to axial."""
    q = col - (row - (row & 1)) // 2
    return Hex(q, row)


def axial_to_offset(h: Hex) -> Tuple[int, int]:
    """Convert axial to odd-r offset (col, row)."""
    col = h.q + (h.r - (h.r & 1)) // 2
    return (col, h.r)
