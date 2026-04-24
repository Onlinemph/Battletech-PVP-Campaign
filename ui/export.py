"""PNG export of per-faction (or GM) map views with fog-of-war applied."""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pygame

from game.constants import SCALE_STRATEGIC
from game.hex_grid import Hex, hex_to_pixel
from game.models import Campaign
from game.vision import visible_hexes, visible_units, visible_missions
from game.campaign import update_explored
from ui.colors import BG, TEXT, TEXT_BRIGHT, PANEL_DARK, BORDER
from ui.renderer import MapRenderer

EXPORTS_DIR = Path(__file__).parent.parent / "exports"


def _fit_hex_size(campaign: Campaign, width: int, height: int, pad: int = 80) -> Tuple[float, float, float]:
    """Compute hex size and pan offset so entire strategic map fits in (width, height)."""
    # Compute bounding box of all terrain hexes in unit coordinates
    if not campaign.terrain_map:
        return 20.0, width / 2, height / 2
    xs, ys = [], []
    for key in campaign.terrain_map:
        h = Hex.from_tuple(key)
        px, py = hex_to_pixel(h, 1.0, 0, 0)
        xs.append(px); ys.append(py)
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max_x - min_x + 2        # +2 for hex margin
    span_y = max_y - min_y + 2
    avail_w = max(10, width  - pad * 2)
    avail_h = max(10, height - pad * 2 - 60)  # leave room for header
    size    = min(avail_w / span_x, avail_h / span_y)
    # After scaling, center the map
    cx_unit = (min_x + max_x) / 2
    cy_unit = (min_y + max_y) / 2
    pan_x   = width  / 2 - cx_unit * size
    pan_y   = height / 2 + 30 - cy_unit * size
    return size, pan_x, pan_y


def export_view(
    campaign:   Campaign,
    faction_id: Optional[str],
    width:      int = 1920,
    height:     int = 1080,
) -> Path:
    """
    Render the current strategic map for `faction_id` (None = GM view)
    and save as a PNG in exports/.
    Returns the saved file path.
    """
    EXPORTS_DIR.mkdir(exist_ok=True)

    pygame.font.init()
    surf = pygame.Surface((width, height))
    surf.fill(BG)

    # Header
    header_h = 50
    pygame.draw.rect(surf, PANEL_DARK, (0, 0, width, header_h))
    pygame.draw.line(surf, BORDER, (0, header_h), (width, header_h), 1)

    font_big  = pygame.font.SysFont("monospace", 22, bold=True)
    font_med  = pygame.font.SysFont("monospace", 14)

    faction_name = "GM — Full Situation"
    if faction_id is not None:
        f = campaign.factions.get(faction_id)
        if f:
            faction_name = f"{f.name}" + (f"  ({f.player_name})" if f.player_name else "")

    title = f"{campaign.name} — Turn {campaign.current_turn} — {faction_name}"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    surf.blit(font_big.render(title, True, TEXT_BRIGHT), (20, 12))
    ts_txt = font_med.render(stamp, True, TEXT)
    surf.blit(ts_txt, (width - ts_txt.get_width() - 20, 18))

    # Compute map layout
    size, pan_x, pan_y = _fit_hex_size(campaign, width, height)

    # Determine fog set + filtered units/missions
    if faction_id is None:
        fog_set        = None
        explored_set   = None
        units_save     = None
        missions_save  = None
    else:
        update_explored(campaign)
        fog_set        = visible_hexes(campaign, faction_id)
        explored_set   = campaign.explored_hexes.get(faction_id, set())
        visible        = visible_units(campaign, faction_id, fog_set)
        vis_missions   = {m.id: m for m in visible_missions(campaign, faction_id, fog_set)}
        units_save     = campaign.units
        missions_save  = campaign.missions
        campaign.units    = visible
        campaign.missions = vis_missions

    # Draw into a sub-rect
    map_rect = pygame.Rect(0, header_h, width, height - header_h)
    renderer = MapRenderer(
        surface      = surf,
        rect         = map_rect,
        campaign     = campaign,
        hex_size     = size,
        pan          = (pan_x, pan_y - header_h),
        scale        = SCALE_STRATEGIC,
        fog_set      = fog_set,
        explored_set = explored_set,
    )
    renderer.draw()

    # Legend
    _draw_legend(surf, campaign, width, height, faction_id)

    # Restore
    if units_save is not None:
        campaign.units    = units_save
    if missions_save is not None:
        campaign.missions = missions_save

    # Save
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in (faction_name.split("—")[0].strip()))
    fname     = f"{campaign.name}_T{campaign.current_turn}_{safe_name}_{datetime.now().strftime('%H%M%S')}.png"
    fname     = "".join(c if c.isalnum() or c in "-_." else "_" for c in fname)
    path      = EXPORTS_DIR / fname
    pygame.image.save(surf, str(path))
    return path


def _draw_legend(surf: pygame.Surface, campaign: Campaign, w: int, h: int,
                 faction_id: Optional[str]) -> None:
    """Small legend in the bottom-left with faction colors and unit counts."""
    font = pygame.font.SysFont("monospace", 13)
    bold = pygame.font.SysFont("monospace", 13, bold=True)
    x = 16
    y = h - 16 - (20 * (len(campaign.factions) + 2))
    pygame.draw.rect(surf, (0, 0, 0, 180),
                     pygame.Rect(x - 8, y - 4, 260, 20 * (len(campaign.factions) + 2) + 8))
    surf.blit(bold.render("Factions", True, TEXT_BRIGHT), (x, y)); y += 20
    for f in campaign.factions.values():
        pygame.draw.rect(surf, f.color, (x, y + 2, 14, 14))
        n_units = sum(1 for u in campaign.units.values() if u.faction_id == f.id)
        lbl = font.render(f"{f.name}  ({n_units} units)", True, TEXT)
        surf.blit(lbl, (x + 22, y))
        y += 20
    if faction_id is not None:
        surf.blit(font.render("Fog-of-war applied.", True, TEXT), (x, y))
