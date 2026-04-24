"""
Core map rendering helpers.
Draws the hex grid (terrain, fog, units, missions) onto a pygame Surface.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Set, Tuple

import pygame

from game.constants import *
from game.hex_grid import (Hex, hex_corners, hex_to_pixel, pixel_to_hex,
                            hex_range, axial_to_offset)
from game.models import Campaign, Unit, Mission
from game.terrain import TERRAIN, terrain_color
from ui.colors import (FOG, FOG_KNOWN, GRID_LINE, GRID_HOVER, SELECTED,
                        MISSION_CLR, MISSION_BDR, TEXT, TEXT_DIM)


def _dim_color(c: tuple, factor: float = 0.32) -> tuple:
    """Darken a terrain color for the explored-but-not-visible state."""
    return (int(c[0] * factor), int(c[1] * factor), int(c[2] * factor))

# Unit-type single letter labels
UNIT_LABEL = {
    UNIT_MECH:      "M",
    UNIT_VEHICLE:   "V",
    UNIT_AEROSPACE: "A",
    UNIT_INFANTRY:  "I",
    UNIT_DROPSHIP:  "D",
}

# When the strategic hex reaches this pixel radius, switch to drawing
# its 37-hex low-altitude sub-grid inline (seamless zoom).
SUBHEX_ZOOM_THRESHOLD  = 65

# When the strategic hex reaches this, recurse one more level and draw
# the 19 mapsheet tiles inside each low-altitude sub-hex.
TACTICAL_ZOOM_THRESHOLD = 200

# Sub-hex radius as a fraction of parent hex radius. Tuned so the full
# radius-3 cluster fits CLEANLY inside the parent hex (geometry: furthest
# corner of the outermost sub-hex is at 6.083*r from center; must be ≤
# parent_edge_distance = R*sqrt(3)/2 ≈ 0.866R).
#   0.866 / 6.083 ≈ 0.1424  →  R/7.02.  Use 1/7.1 for a small margin.
SUBHEX_RATIO = 1.0 / 7.1

# Mapsheet radius as fraction of low-altitude sub-hex radius. Similar
# geometry for radius-2 cluster: outer corner at 4.359*r, must be ≤
# 0.866*R_sub.  0.866/4.359 ≈ 0.1988  →  R_sub/5.03.  Use 1/5.1 margin.
TACTICAL_RATIO = 1.0 / 5.1

# Faint outlines at each level
STRAT_GUIDE  = (200, 200, 120)   # strategic hex boundary (yellow)
SUBHEX_GUIDE = (120, 200, 220)   # low-altitude hex boundary (cyan)


# ── Hierarchical coordinate helpers (module-level) ────────────────────────────

def pixel_to_hierarchical(px: float, py: float, hex_size: float,
                          ox: float, oy: float):
    """
    Convert a pixel to (strategic_hex, sub_hex_or_None, tac_hex_or_None).
    Returns sub/tac only at the zoom levels where they're relevant.
    Returns None for levels the click isn't precise enough for.
    """
    from game.hex_grid import pixel_to_hex, hex_to_pixel, Hex, hex_distance
    from game.constants import OPERATIONAL_RADIUS, TACTICAL_RADIUS

    strat = pixel_to_hex(px, py, hex_size, ox, oy)
    if hex_size < SUBHEX_ZOOM_THRESHOLD:
        return strat, None, None

    sub_size = hex_size * SUBHEX_RATIO
    scx, scy = hex_to_pixel(strat, hex_size, ox, oy)
    dx, dy   = px - scx, py - scy
    sub = pixel_to_hex(dx, dy, sub_size, 0, 0)
    if hex_distance(Hex(0, 0), sub) > OPERATIONAL_RADIUS:
        return strat, None, None

    if hex_size < TACTICAL_ZOOM_THRESHOLD:
        return strat, sub.to_tuple(), None

    tac_size  = sub_size * TACTICAL_RATIO
    sub_cx, sub_cy = hex_to_pixel(sub, sub_size, 0, 0)
    ddx, ddy  = dx - sub_cx, dy - sub_cy
    tac = pixel_to_hex(ddx, ddy, tac_size, 0, 0)
    if hex_distance(Hex(0, 0), tac) > TACTICAL_RADIUS:
        return strat, sub.to_tuple(), None

    return strat, sub.to_tuple(), tac.to_tuple()


def hierarchical_offset(sub_pos, tac_pos, hex_size: float):
    """
    Return (dx, dy) offset from a strategic hex's center to the given
    sub/tac position, honoring the current zoom level.
    """
    from game.hex_grid import hex_to_pixel, Hex
    if sub_pos is None or hex_size < SUBHEX_ZOOM_THRESHOLD:
        return 0.0, 0.0
    sub_size = hex_size * SUBHEX_RATIO
    sx, sy   = hex_to_pixel(Hex.from_tuple(sub_pos), sub_size, 0, 0)
    if tac_pos is None or hex_size < TACTICAL_ZOOM_THRESHOLD:
        return sx, sy
    tac_size = sub_size * TACTICAL_RATIO
    tx, ty   = hex_to_pixel(Hex.from_tuple(tac_pos), tac_size, 0, 0)
    return sx + tx, sy + ty

# Status border colors
STATUS_COLORS = {
    STATUS_ACTIVE:    (255, 255, 255),
    STATUS_CRIPPLED:  (255, 200,  50),
    STATUS_RETREATED: (180, 180, 255),
    STATUS_RESERVE:   (130, 130, 130),
    STATUS_DESTROYED: ( 80,  80,  80),
}


class MapRenderer:
    """
    Renders a hex map (strategic or operational) to a pygame Surface.

    Parameters
    ----------
    surface   : target pygame Surface
    rect      : pygame.Rect defining the area to draw in
    campaign  : the campaign data
    hex_size  : pixel radius of each hex
    pan       : (pan_x, pan_y) viewport offset in pixels
    scale     : SCALE_STRATEGIC or SCALE_OPERATIONAL
    op_hex    : (q, r) of the strategic hex whose sub-map to show (operational only)
    fog_set   : set of (q,r) tuples that ARE visible (None = no fog / GM view)
    hover_hex : hex under the cursor (highlighted)
    selected  : selected hex (q,r)
    """

    def __init__(
        self,
        surface:      pygame.Surface,
        rect:         pygame.Rect,
        campaign:     Campaign,
        hex_size:     float             = 20.0,
        pan:          Tuple[float, float] = (0.0, 0.0),
        scale:        str               = SCALE_STRATEGIC,
        op_hex:       Optional[Tuple[int, int]] = None,
        fog_set:      Optional[Set[Tuple[int, int]]] = None,
        explored_set: Optional[Set[Tuple[int, int]]] = None,
        hover_hex:    Optional[Tuple[int, int]] = None,
        selected:     Optional[Tuple[int, int]] = None,
    ):
        self.surface      = surface
        self.rect         = rect
        self.campaign     = campaign
        self.hex_size     = hex_size
        self.pan          = pan
        self.scale        = scale
        self.op_hex       = op_hex
        self.fog_set      = fog_set
        self.explored_set = explored_set
        self.hover        = hover_hex
        self.selected     = selected

        self._font_sm = pygame.font.SysFont("monospace", max(9, int(hex_size * 0.55)), bold=True)
        self._font_co = pygame.font.SysFont("monospace", max(7, int(hex_size * 0.35)))

    # ── origin helper ─────────────────────────────────────────────────────────

    @property
    def ox(self) -> float:
        return self.rect.x + self.pan[0]

    @property
    def oy(self) -> float:
        return self.rect.y + self.pan[1]

    # ── coordinate helpers ────────────────────────────────────────────────────

    def hex_center(self, h: Hex) -> Tuple[float, float]:
        return hex_to_pixel(h, self.hex_size, self.ox, self.oy)

    def mouse_to_hex(self, mx: float, my: float) -> Hex:
        return pixel_to_hex(mx, my, self.hex_size, self.ox, self.oy)

    # ── terrain map source ────────────────────────────────────────────────────

    def _terrain_map(self) -> Dict[Tuple[int, int], str]:
        if self.scale == SCALE_OPERATIONAL and self.op_hex is not None:
            from game.campaign import get_operational_map
            return get_operational_map(self.campaign, self.op_hex)
        return self.campaign.terrain_map

    # ── viewport culling ──────────────────────────────────────────────────────

    def _visible_terrain_hexes(self) -> list:
        """Return only hexes whose center is within the draw rect (+ margin)."""
        tmap = self._terrain_map()
        margin = self.hex_size * 2
        r = self.rect
        result = []
        for key, terrain in tmap.items():
            h = Hex.from_tuple(key)
            cx, cy = self.hex_center(h)
            if (r.left - margin <= cx <= r.right + margin and
                    r.top - margin <= cy <= r.bottom + margin):
                result.append((h, terrain))
        return result

    # ── draw ──────────────────────────────────────────────────────────────────

    def draw(self) -> None:
        """Render everything onto self.surface within self.rect."""
        self.surface.set_clip(self.rect)
        pygame.draw.rect(self.surface, (10, 10, 14), self.rect)

        hexes = self._visible_terrain_hexes()
        tmap  = self._terrain_map()

        # Group units by hex for this scale
        units_by_hex: Dict[Tuple[int, int], list] = {}
        if self.scale == SCALE_STRATEGIC:
            for unit in self.campaign.units.values():
                if unit.position is not None:
                    units_by_hex.setdefault(unit.position, []).append(unit)

        missions_by_hex: Dict[Tuple[int, int], list] = {}
        if self.scale == SCALE_STRATEGIC:
            for m in self.campaign.missions.values():
                missions_by_hex.setdefault(m.position, []).append(m)

        # If zoomed in far enough on the strategic map, draw sub-hexes inside
        # each strategic hex (the low-altitude hex grid). Parent hex appears as
        # a faint outline guide.
        show_subhexes = (self.scale == SCALE_STRATEGIC
                         and self.hex_size >= SUBHEX_ZOOM_THRESHOLD)

        if show_subhexes:
            for h, terrain in hexes:
                self._draw_subhexes(h, terrain)
            # Thin strategic-hex guide lines on top
            for h, _ in hexes:
                self._draw_hex_outline(h, STRAT_GUIDE, 2)
        else:
            # Draw fill
            for h, terrain in hexes:
                self._draw_hex_fill(h, terrain)

            # Draw grid lines
            for h, _ in hexes:
                self._draw_hex_border(h)

        # Draw missions
        for h, terrain in hexes:
            key = h.to_tuple()
            if key in missions_by_hex:
                self._draw_mission_icon(h, missions_by_hex[key])

        # Draw units
        for h, terrain in hexes:
            key = h.to_tuple()
            if key in units_by_hex:
                self._draw_units(h, units_by_hex[key])

        # Draw hover / selection overlay
        if self.hover is not None and Hex.from_tuple(self.hover).to_tuple() in {h.to_tuple() for h, _ in hexes}:
            self._draw_hex_outline(Hex.from_tuple(self.hover), GRID_HOVER, 2)
        if self.selected is not None:
            self._draw_hex_outline(Hex.from_tuple(self.selected), SELECTED, 3)

        # Coord labels at large zoom
        if self.hex_size >= 35:
            for h, _ in hexes:
                self._draw_coord_label(h)

        self.surface.set_clip(None)

    # ── per-hex drawing ───────────────────────────────────────────────────────

    def _draw_subhexes(self, parent: Hex, parent_terrain: str) -> None:
        """Render the 37 low-altitude sub-hexes that make up a strategic hex.
        If zoomed in even further, each sub-hex recursively shows its 19
        mapsheet-level tiles."""
        from game.campaign import get_operational_map
        sub_tmap = get_operational_map(self.campaign, parent.to_tuple())

        pcx, pcy = self.hex_center(parent)
        sub_r   = max(2.0, self.hex_size * SUBHEX_RATIO)
        sqrt3   = math.sqrt(3)
        sqrt3_2 = sqrt3 * 0.5

        key_parent  = parent.to_tuple()
        is_fog      = (self.fog_set is not None and key_parent not in self.fog_set)
        is_explored = (is_fog and self.explored_set is not None
                       and key_parent in self.explored_set)

        show_tactical = self.hex_size >= TACTICAL_ZOOM_THRESHOLD
        border_col = (45, 45, 55)

        for (sq, sr), terrain in sub_tmap.items():
            # Local axial → pixel offset (flat-top)
            dx = sub_r * 1.5 * sq
            dy = sub_r * (sqrt3_2 * sq + sqrt3 * sr)
            cx = pcx + dx
            cy = pcy + dy

            if show_tactical and not is_fog:
                # Recurse: draw the 19 mapsheet tiles inside this sub-hex
                self._draw_mapsheets(parent.to_tuple(), (sq, sr),
                                     cx, cy, sub_r, terrain)
                # Cyan guide line around the low-alt sub-hex
                corners = [
                    (cx + sub_r * math.cos(math.pi / 3 * i),
                     cy + sub_r * math.sin(math.pi / 3 * i))
                    for i in range(6)
                ]
                pygame.draw.polygon(self.surface, SUBHEX_GUIDE, corners, 2)
            else:
                corners = [
                    (cx + sub_r * math.cos(math.pi / 3 * i),
                     cy + sub_r * math.sin(math.pi / 3 * i))
                    for i in range(6)
                ]
                if not is_fog:
                    color = terrain_color(terrain)
                elif is_explored:
                    color = _dim_color(terrain_color(terrain))
                else:
                    color = FOG
                pygame.draw.polygon(self.surface, color, corners)
                if sub_r >= 4:
                    pygame.draw.polygon(self.surface, border_col, corners, 1)

    def _draw_mapsheets(self, strategic_hex: Tuple[int, int],
                        sub_hex:       Tuple[int, int],
                        scx: float, scy: float,
                        sub_r: float, parent_terrain: str) -> None:
        """Render the 19 mapsheet-level tiles inside one low-altitude sub-hex."""
        from game.campaign import get_tactical_map
        tac_tmap = get_tactical_map(self.campaign, strategic_hex, sub_hex)

        tac_r  = max(1.5, sub_r * TACTICAL_RATIO)
        sqrt3   = math.sqrt(3)
        sqrt3_2 = sqrt3 * 0.5
        border_col = (30, 30, 35)

        for (tq, tr), terrain in tac_tmap.items():
            dx = tac_r * 1.5 * tq
            dy = tac_r * (sqrt3_2 * tq + sqrt3 * tr)
            cx = scx + dx
            cy = scy + dy
            corners = [
                (cx + tac_r * math.cos(math.pi / 3 * i),
                 cy + tac_r * math.sin(math.pi / 3 * i))
                for i in range(6)
            ]
            pygame.draw.polygon(self.surface, terrain_color(terrain), corners)
            if tac_r >= 3:
                pygame.draw.polygon(self.surface, border_col, corners, 1)

    def _draw_hex_fill(self, h: Hex, terrain: str) -> None:
        key = h.to_tuple()
        if self.fog_set is None:
            color = terrain_color(terrain)
        elif key in self.fog_set:
            color = terrain_color(terrain)
        elif self.explored_set and key in self.explored_set:
            color = _dim_color(terrain_color(terrain))
        else:
            color = FOG
        pts = hex_corners(h, self.hex_size, self.ox, self.oy)
        pygame.draw.polygon(self.surface, color, pts)

    def _draw_hex_border(self, h: Hex) -> None:
        pts = hex_corners(h, self.hex_size, self.ox, self.oy)
        pygame.draw.polygon(self.surface, GRID_LINE, pts, 1)

    def _draw_hex_outline(self, h: Hex, color: tuple, width: int = 2) -> None:
        pts = hex_corners(h, self.hex_size, self.ox, self.oy)
        pygame.draw.polygon(self.surface, color, pts, width)

    def _draw_coord_label(self, h: Hex) -> None:
        key = h.to_tuple()
        is_fog = (self.fog_set is not None and key not in self.fog_set)
        if is_fog:
            return
        cx, cy = self.hex_center(h)
        col, row = axial_to_offset(h)
        label = f"{col},{row}"
        surf = self._font_co.render(label, True, (80, 80, 90))
        r = surf.get_rect(center=(int(cx), int(cy) + int(self.hex_size * 0.5)))
        self.surface.blit(surf, r)

    def _draw_mission_icon(self, h: Hex, missions: list) -> None:
        key = h.to_tuple()
        is_fog = (self.fog_set is not None and key not in self.fog_set)
        if is_fog:
            return
        cx, cy = self.hex_center(h)
        r = max(4, int(self.hex_size * 0.28))
        pygame.draw.polygon(
            self.surface, MISSION_CLR,
            [(cx, cy - r), (cx + r, cy + r), (cx - r, cy + r)],
        )
        pygame.draw.polygon(
            self.surface, MISSION_BDR,
            [(cx, cy - r), (cx + r, cy + r), (cx - r, cy + r)],
            1,
        )

    def _draw_units(self, h: Hex, units: list) -> None:
        key = h.to_tuple()
        is_fog = (self.fog_set is not None and key not in self.fog_set)
        pcx, pcy = self.hex_center(h)

        # Group units by where they actually render at the current zoom so
        # they stack cleanly even if they share a strategic hex but differ in
        # sub/tac position.
        groups: Dict[Tuple[float, float], list] = {}
        for u in units:
            dx, dy = hierarchical_offset(u.sub_position, u.tac_position, self.hex_size)
            # Quantize so nearly-coincident offsets group together
            cx = pcx + dx
            cy = pcy + dy
            key_px = (round(cx), round(cy))
            groups.setdefault(key_px, []).append(u)

        # Smaller unit radius when sub-hexes are showing (to fit inside them)
        if self.hex_size >= TACTICAL_ZOOM_THRESHOLD:
            radius = max(4, int(self.hex_size * SUBHEX_RATIO * TACTICAL_RATIO * 0.85))
        elif self.hex_size >= SUBHEX_ZOOM_THRESHOLD:
            radius = max(4, int(self.hex_size * SUBHEX_RATIO * 0.55))
        else:
            radius = max(4, int(self.hex_size * 0.32))

        for (gx, gy), g_units in groups.items():
            n = len(g_units)
            offsets = _unit_offsets(n, radius * 1.4)
            for i, unit in enumerate(g_units):
                ux = gx + offsets[i][0]
                uy = gy + offsets[i][1]
                faction = self.campaign.factions.get(unit.faction_id)
                fc = tuple(faction.color) if faction else (150, 150, 150)
                status_border = STATUS_COLORS.get(unit.status, (255, 255, 255))
                _draw_unit_circle(self.surface, (ux, uy), radius, fc, status_border,
                                  UNIT_LABEL.get(unit.unit_type, "?"), self._font_sm,
                                  unit.status == STATUS_DESTROYED)

    # ── export surface ────────────────────────────────────────────────────────

    def render_to_surface(
        self,
        width:    int,
        height:   int,
        faction_id: Optional[str] = None,
    ) -> pygame.Surface:
        """
        Return a new Surface of size (width, height) rendered for the given
        faction (fog of war applied) or GM view (faction_id=None).
        """
        from game.vision import visible_hexes, visible_units, visible_missions

        surf   = pygame.Surface((width, height))
        old_s  = self.surface
        old_r  = self.rect
        old_f  = self.fog_set

        self.surface = surf
        self.rect    = pygame.Rect(0, 0, width, height)

        if faction_id is not None:
            vis = visible_hexes(self.campaign, faction_id)
            self.fog_set = vis
            # Filter units to only what this faction can see
            vis_units = visible_units(self.campaign, faction_id, vis)
            # Temporarily replace units in draw context
            old_units = {u.id: u for u in self.campaign.units.values()}
            self.campaign.units = vis_units
        else:
            self.fog_set = None

        self.draw()

        if faction_id is not None:
            self.campaign.units = old_units  # type: ignore[assignment]

        self.surface = old_s
        self.rect    = old_r
        self.fog_set = old_f
        return surf


# ── helpers ────────────────────────────────────────────────────────────────────

def _unit_offsets(n: int, spread: float) -> list:
    """Compute (dx, dy) offsets for up to n units stacked in a hex."""
    if n == 1:
        return [(0.0, 0.0)]
    angles = [math.pi * 2 / n * i - math.pi / 2 for i in range(n)]
    r      = spread * min(1.0, 0.5 + n * 0.1)
    return [(math.cos(a) * r, math.sin(a) * r) for a in angles]


def _draw_unit_circle(
    surface:  pygame.Surface,
    center:   Tuple[float, float],
    radius:   int,
    fill:     tuple,
    border:   tuple,
    label:    str,
    font:     pygame.font.Font,
    dead:     bool = False,
) -> None:
    cx, cy = int(center[0]), int(center[1])
    alpha_fill = tuple(max(0, min(255, int(c * (0.5 if dead else 1.0)))) for c in fill)
    pygame.draw.circle(surface, alpha_fill, (cx, cy), radius)
    pygame.draw.circle(surface, border,     (cx, cy), radius, max(1, radius // 4))
    if dead:
        pygame.draw.line(surface, (200, 40, 40), (cx - radius + 2, cy - radius + 2),
                         (cx + radius - 2, cy + radius - 2), 2)
    else:
        txt = font.render(label, True, (255, 255, 255))
        surface.blit(txt, txt.get_rect(center=(cx, cy)))
