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

# Structure type → (letter, background-color)
STRUCTURE_GLYPH = {
    "City":           ("C", (155, 135, 115)),
    "Town":           ("T", (145, 125, 105)),
    "Village":        ("v", (125, 105,  85)),
    "Military Base":  ("B", ( 55, 105,  45)),
    "FOB":            ("f", ( 65,  95,  45)),
    "Supply Depot":   ("S", ( 55,  85, 155)),
    "Airfield":       ("A", ( 45, 105, 165)),
    "Factory":        ("X", ( 95,  65,  45)),
    "Spaceport":      ("*", ( 85,  75, 155)),
    "Comms Tower":    ("R", (135,  95,  55)),
}

# Unit-type single letter labels
UNIT_LABEL = {
    UNIT_MECH:      "M",
    UNIT_VEHICLE:   "V",
    UNIT_AEROSPACE: "A",
    UNIT_INFANTRY:  "I",
    UNIT_DROPSHIP:  "D",
}

# When the strategic hex reaches this pixel radius, switch to drawing
# its 37-hex operational sub-grid inline (seamless zoom).
SUBHEX_ZOOM_THRESHOLD = 65

# Sub-hex radius as a fraction of parent hex radius. Tuned so the full
# radius-3 cluster fits CLEANLY inside the parent hex (geometry: furthest
# corner of the outermost sub-hex is at 6.083*r from center; must be ≤
# parent_edge_distance = R*sqrt(3)/2 ≈ 0.866R).
#   0.866 / 6.083 ≈ 0.1424  →  R/7.02.  Use 1/7.1 for a small margin.
SUBHEX_RATIO = 1.0 / 7.1

# Faint outlines at each level
STRAT_GUIDE  = (200, 200, 120)   # strategic hex boundary (yellow)
SUBHEX_GUIDE = (120, 200, 220)   # low-altitude hex boundary (cyan)


# ── Hierarchical coordinate helpers (module-level) ────────────────────────────

def pixel_to_hierarchical(px: float, py: float, hex_size: float,
                          ox: float, oy: float):
    """
    Convert a pixel to (strategic_hex, sub_hex_or_None, None).
    sub_hex is the operational-scale hex inside the strategic hex, only
    returned at zoom levels where the sub-grid is visible.
    Third element is always None (tactical tier removed).
    """
    from game.hex_grid import pixel_to_hex, hex_to_pixel, Hex, hex_distance
    from game.constants import OPERATIONAL_RADIUS

    strat = pixel_to_hex(px, py, hex_size, ox, oy)
    if hex_size < SUBHEX_ZOOM_THRESHOLD:
        return strat, None, None

    sub_size = hex_size * SUBHEX_RATIO
    scx, scy = hex_to_pixel(strat, hex_size, ox, oy)
    dx, dy   = px - scx, py - scy
    sub = pixel_to_hex(dx, dy, sub_size, 0, 0)
    if hex_distance(Hex(0, 0), sub) > OPERATIONAL_RADIUS:
        return strat, None, None

    return strat, sub.to_tuple(), None


def hierarchical_offset(sub_pos, tac_pos, hex_size: float):
    """Return (dx, dy) pixel offset from strategic hex center to sub_pos.
    tac_pos accepted for signature compat but ignored (tactical tier removed)."""
    from game.hex_grid import hex_to_pixel, Hex
    if sub_pos is None or hex_size < SUBHEX_ZOOM_THRESHOLD:
        return 0.0, 0.0
    sub_size = hex_size * SUBHEX_RATIO
    sx, sy   = hex_to_pixel(Hex.from_tuple(sub_pos), sub_size, 0, 0)
    return sx, sy

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
        surface:        pygame.Surface,
        rect:           pygame.Rect,
        campaign:       Campaign,
        hex_size:       float             = 20.0,
        pan:            Tuple[float, float] = (0.0, 0.0),
        scale:          str               = SCALE_STRATEGIC,
        op_hex:         Optional[Tuple[int, int]] = None,
        fog_set:        Optional[Set[Tuple[int, int]]] = None,
        explored_set:   Optional[Set[Tuple[int, int]]] = None,
        hover_hex:      Optional[Tuple[int, int]] = None,
        selected:       Optional[Tuple[int, int]] = None,
        highlight_hexes: Optional[Set[Tuple[int, int]]] = None,
        supply_set:     Optional[Set[str]] = None,   # unit IDs that are supplied
        contact_hexes:  Optional[Dict[Tuple[int, int], list]] = None,
        highlight_color: Tuple[int, int, int] = (80, 160, 255),
    ):
        self.surface         = surface
        self.rect            = rect
        self.campaign        = campaign
        self.hex_size        = hex_size
        self.pan             = pan
        self.scale           = scale
        self.op_hex          = op_hex
        self.fog_set         = fog_set
        self.explored_set    = explored_set
        self.hover           = hover_hex
        self.selected        = selected
        self.highlight_hexes  = highlight_hexes
        self.supply_set       = supply_set
        self.contact_hexes    = contact_hexes
        self.highlight_color  = highlight_color

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
        elif self.scale == SCALE_OPERATIONAL and self.op_hex is not None:
            for unit in self.campaign.units.values():
                if unit.position == self.op_hex and unit.status not in (STATUS_DESTROYED,):
                    # Units with no sub_position sit at the centre of the op map
                    sub = unit.sub_position if unit.sub_position is not None else (0, 0)
                    units_by_hex.setdefault(sub, []).append(unit)

        missions_by_hex: Dict[Tuple[int, int], list] = {}
        if self.scale == SCALE_STRATEGIC:
            for m in self.campaign.missions.values():
                missions_by_hex.setdefault(m.position, []).append(m)

        # If zoomed in far enough on the strategic map, draw sub-hexes inside
        # each strategic hex (the low-altitude hex grid). Parent hex appears as
        # a faint outline guide.
        show_subhexes = (self.scale == SCALE_STRATEGIC
                         and self.hex_size >= SUBHEX_ZOOM_THRESHOLD)

        # Group structures by hex
        structures_by_hex: Dict[Tuple[int, int], list] = {}
        if self.scale == SCALE_STRATEGIC:
            for s in self.campaign.structures.values():
                structures_by_hex.setdefault(s.position, []).append(s)

        if show_subhexes:
            for h, terrain in hexes:
                self._draw_subhexes(h, terrain)
            # Thin strategic-hex guide lines on top
            for h, _ in hexes:
                self._draw_hex_outline(h, STRAT_GUIDE, 2)
        else:
            for h, terrain in hexes:
                self._draw_hex_fill(h, terrain)
            for h, _ in hexes:
                self._draw_hex_border(h)

        # Movement-range highlight overlay
        if self.highlight_hexes:
            for h, _ in hexes:
                if h.to_tuple() in self.highlight_hexes:
                    self._draw_hex_highlight(h)

        # Territory control tint (semi-transparent faction color)
        if self.scale == SCALE_STRATEGIC:
            for h, _ in hexes:
                key = f"{h.q},{h.r}"
                fid = self.campaign.hex_control.get(key)
                if fid:
                    f = self.campaign.factions.get(fid)
                    if f:
                        self._draw_hex_territory(h, tuple(f.color))

        # Coastal transition shading
        if self.scale == SCALE_STRATEGIC:
            self._draw_coastal_edges(hexes, tmap)

        # Draw structures (below missions and units)
        for h, _ in hexes:
            key = h.to_tuple()
            if key in structures_by_hex:
                self._draw_structures(h, structures_by_hex[key])

        # Draw missions
        for h, terrain in hexes:
            key = h.to_tuple()
            if key in missions_by_hex:
                self._draw_mission_icon(h, missions_by_hex[key])

        # Draw objectives (diamond markers)
        if self.scale == SCALE_STRATEGIC:
            objectives_by_hex: Dict[Tuple[int, int], list] = {}
            for o in self.campaign.objectives.values():
                objectives_by_hex.setdefault(o.position, []).append(o)
            for h, _ in hexes:
                if h.to_tuple() in objectives_by_hex:
                    self._draw_objective_icons(h, objectives_by_hex[h.to_tuple()])

        # Hex note indicator dots
        if self.scale == SCALE_STRATEGIC and self.campaign.hex_notes:
            for h, _ in hexes:
                note_key = f"{h.q},{h.r}"
                if note_key in self.campaign.hex_notes:
                    cx_n, cy_n = self.hex_center(h)
                    dot_x = int(cx_n + self.hex_size * 0.42)
                    dot_y = int(cy_n - self.hex_size * 0.48)
                    dot_r = max(3, int(self.hex_size * 0.09))
                    pygame.draw.circle(self.surface, (255, 220, 50), (dot_x, dot_y), dot_r)
                    pygame.draw.circle(self.surface, (180, 140,  0), (dot_x, dot_y), dot_r, 1)

        # Draw units
        for h, terrain in hexes:
            key = h.to_tuple()
            if key in units_by_hex:
                self._draw_units(h, units_by_hex[key])

        # Contact hex warning borders
        if self.contact_hexes and self.scale == SCALE_STRATEGIC:
            for h, _ in hexes:
                if h.to_tuple() in self.contact_hexes:
                    self._draw_hex_outline(h, (220, 50, 50), 3)
                    cx_h, cy_h = self.hex_center(h)
                    r = max(4, int(self.hex_size * 0.12))
                    pygame.draw.line(self.surface, (255, 80, 80),
                                     (int(cx_h) - r, int(cy_h)), (int(cx_h) + r, int(cy_h)), 2)
                    pygame.draw.line(self.surface, (255, 80, 80),
                                     (int(cx_h), int(cy_h) - r), (int(cx_h), int(cy_h) + r), 2)

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
        """Render the 37 operational sub-hexes (500 m each) inside a strategic hex."""
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
        border_col = (45, 45, 55)

        for (sq, sr), terrain in sub_tmap.items():
            dx = sub_r * 1.5 * sq
            dy = sub_r * (sqrt3_2 * sq + sqrt3 * sr)
            cx = pcx + dx
            cy = pcy + dy
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

    def _draw_hex_highlight(self, h: Hex) -> None:
        pts = hex_corners(h, self.hex_size, self.ox, self.oy)
        r, g, b = self.highlight_color
        surf = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(surf, (r, g, b, 55), pts)
        self.surface.blit(surf, (0, 0))
        pygame.draw.polygon(self.surface, (r, g, b), pts, 1)

    def _draw_hex_territory(self, h: Hex, color: tuple) -> None:
        key = h.to_tuple()
        if self.fog_set is not None and key not in self.fog_set:
            if not (self.explored_set and key in self.explored_set):
                return
        pts = hex_corners(h, self.hex_size, self.ox, self.oy)
        surf = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        r, g, b = color[0], color[1], color[2]
        pygame.draw.polygon(surf, (r, g, b, 45), pts)
        self.surface.blit(surf, (0, 0))

    def _draw_objective_icons(self, h: Hex, objectives: list) -> None:
        from game.constants import OBJECTIVE_ACTIVE, OBJECTIVE_CAPTURED, OBJECTIVE_DENIED
        key = h.to_tuple()
        is_fog = (self.fog_set is not None and key not in self.fog_set)
        if is_fog:
            return
        cx, cy = self.hex_center(h)
        sz = min(max(5, int(self.hex_size * 0.25)), 16)
        n = len(objectives)
        for i, o in enumerate(objectives[:3]):
            ox = cx + (i - (n - 1) / 2) * (sz * 2 + 2)
            oy = cy - int(self.hex_size * 0.15)
            color = {OBJECTIVE_ACTIVE:   (255, 215,   0),
                     OBJECTIVE_CAPTURED: ( 60, 200,  80),
                     OBJECTIVE_DENIED:   (210,  50,  50)}.get(o.status, (180, 180, 180))
            pts = [(ox, oy - sz), (ox + sz, oy), (ox, oy + sz), (ox - sz, oy)]
            pygame.draw.polygon(self.surface, color, pts)
            pygame.draw.polygon(self.surface, (0, 0, 0), pts, 1)
            if o.faction_id:
                f = self.campaign.factions.get(o.faction_id)
                if f:
                    pygame.draw.polygon(self.surface, tuple(f.color), pts, 2)
            if self.hex_size >= 20 and o.vp_value:
                font = pygame.font.SysFont("monospace", max(7, sz - 1), bold=True)
                lbl = font.render(str(o.vp_value), True, (0, 0, 0))
                self.surface.blit(lbl, lbl.get_rect(center=(int(ox), int(oy))))

    def _draw_coastal_edges(self, hexes: list, tmap: dict) -> None:
        """Overlay water-wash triangles on coast/water hex edges that border a
        different moisture level, creating a visual shoreline gradient."""
        from game.hex_grid import HEX_DIRECTIONS
        WATER_SET = {TERRAIN_DEEP_WATER, TERRAIN_WATER}
        LAND_SET  = {TERRAIN_COAST, TERRAIN_PLAINS, TERRAIN_FOREST, TERRAIN_HILLS,
                     TERRAIN_MOUNTAINS, TERRAIN_URBAN, TERRAIN_INDUSTRIAL,
                     TERRAIN_DESERT, TERRAIN_ARCTIC, TERRAIN_VOLCANIC}
        overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        for h, terrain in hexes:
            key = h.to_tuple()
            if self.fog_set is not None and key not in self.fog_set:
                if not (self.explored_set and key in self.explored_set):
                    continue
            cx, cy  = self.hex_center(h)
            corners = hex_corners(h, self.hex_size, self.ox, self.oy)
            # hex_corners uses angle=π/3*i → corner order (pygame y-down):
            # 0=E, 1=SE, 2=SW, 3=W, 4=NW, 5=NE
            # HEX_DIRECTIONS[di]: edge between corners[di] and corners[(di+1)%6]
            # faces direction (6-di)%6  →  edge_i for direction di = (6-di)%6
            # wait: verified mapping: edge_i = di (corners[di]→corners[(di+1)%6])
            # faces direction (6-di)%6.  So for direction di → edge_i = (6-di)%6
            for di, d in enumerate(HEX_DIRECTIONS):
                nb = tmap.get((h.q + d.q, h.r + d.r))
                edge_i = (6 - di) % 6
                p1 = corners[edge_i]
                p2 = corners[(edge_i + 1) % 6]
                if terrain == TERRAIN_COAST and nb in WATER_SET:
                    pygame.draw.polygon(overlay, (50, 110, 190, 85),
                                        [(cx, cy), p1, p2])
                elif terrain in WATER_SET and nb in LAND_SET:
                    pygame.draw.polygon(overlay, (90, 155, 220, 65),
                                        [(cx, cy), p1, p2])
        self.surface.blit(overlay, (0, 0))

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

    def _draw_structures(self, h: Hex, structures: list) -> None:
        key    = h.to_tuple()
        is_fog = (self.fog_set is not None and key not in self.fog_set)
        if is_fog:
            return
        cx, cy = self.hex_center(h)
        sz     = min(max(16, int(self.hex_size * 0.55)), 44)
        for i, s in enumerate(structures[:3]):
            glyph, bg = STRUCTURE_GLYPH.get(s.structure_type, ("?", (120, 100, 80)))
            # Stack multiple structures horizontally
            sx = cx - (len(structures) - 1) * (sz + 2) // 2 + i * (sz + 2)
            sy = cy + int(self.hex_size * 0.30)
            r  = pygame.Rect(int(sx - sz), int(sy - sz // 2), sz * 2, sz)
            pygame.draw.rect(self.surface, bg, r, border_radius=2)
            # Faction-color border if owned
            if s.faction_id:
                f = self.campaign.factions.get(s.faction_id)
                if f:
                    pygame.draw.rect(self.surface, f.color, r, 1, border_radius=2)
            if sz >= 7:
                font = pygame.font.SysFont("monospace", max(7, sz - 2), bold=True)
                lbl  = font.render(glyph, True, (240, 240, 240))
                self.surface.blit(lbl, lbl.get_rect(center=(int(sx), int(sy))))

    def _draw_mission_icon(self, h: Hex, missions: list) -> None:
        key = h.to_tuple()
        is_fog = (self.fog_set is not None and key not in self.fog_set)
        if is_fog:
            return
        cx, cy = self.hex_center(h)
        r = min(max(4, int(self.hex_size * 0.28)), 18)
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
        if self.hex_size >= SUBHEX_ZOOM_THRESHOLD:
            radius = max(4, int(self.hex_size * SUBHEX_RATIO * 0.55))
        else:
            radius = min(max(4, int(self.hex_size * 0.32)), 22)

        # Font sized to the circle, not to hex_size — prevents giant "M" at high zoom
        unit_font = pygame.font.SysFont("monospace", max(7, int(radius * 1.1)), bold=True)

        for (gx, gy), g_units in groups.items():
            n = len(g_units)
            offsets = _unit_offsets(n, radius * 1.4)
            for i, unit in enumerate(g_units):
                ux = gx + offsets[i][0]
                uy = gy + offsets[i][1]
                faction = self.campaign.factions.get(unit.faction_id)
                fc = tuple(faction.color) if faction else (150, 150, 150)
                status_border = STATUS_COLORS.get(unit.status, (255, 255, 255))
                unsupplied = (self.supply_set is not None
                               and unit.id not in self.supply_set)
                _draw_unit_circle(self.surface, (ux, uy), radius, fc, status_border,
                                  UNIT_LABEL.get(unit.unit_type, "?"), unit_font,
                                  unit.status == STATUS_DESTROYED, unsupplied,
                                  unit.has_moved)

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
    surface:    pygame.Surface,
    center:     Tuple[float, float],
    radius:     int,
    fill:       tuple,
    border:     tuple,
    label:      str,
    font:       pygame.font.Font,
    dead:       bool = False,
    unsupplied: bool = False,
    has_moved:  bool = False,
) -> None:
    cx, cy = int(center[0]), int(center[1])
    dim = 0.5 if dead else (0.6 if has_moved else 1.0)
    alpha_fill = tuple(max(0, min(255, int(c * dim))) for c in fill)
    pygame.draw.circle(surface, alpha_fill, (cx, cy), radius)
    pygame.draw.circle(surface, border,     (cx, cy), radius, max(1, radius // 4))
    if unsupplied:
        pygame.draw.circle(surface, (255, 140, 0), (cx, cy), radius + 2, 2)
    if dead:
        pygame.draw.line(surface, (200, 40, 40), (cx - radius + 2, cy - radius + 2),
                         (cx + radius - 2, cy + radius - 2), 2)
    else:
        label_color = (255, 255, 255) if not has_moved else (160, 160, 160)
        txt = font.render(label, True, label_color)
        surface.blit(txt, txt.get_rect(center=(cx, cy)))
