"""Toolbar, sidebar, statusbar drawing."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pygame

from game.constants import (SCALE_STRATEGIC, SCALE_OPERATIONAL,
                             HIGH_ALT_HEX_SIZE_M, LOW_ALT_HEX_SIZE_M)
from game.hex_grid import axial_to_offset
from game.models import Campaign, Faction, Unit
from game.terrain import terrain_name
from ui.colors import (BG, PANEL_BG, PANEL_DARK, BORDER, BORDER_LT,
                        BTN_NORMAL, BTN_HOVER, BTN_ACTIVE, BTN_TEXT,
                        TEXT, TEXT_DIM, TEXT_BRIGHT, TEXT_WARN, TEXT_BAD)

TOOLBAR_H   = 46
STATUSBAR_H = 26
SIDEBAR_W   = 290


class Hitbox:
    """Named clickable rectangle for toolbar/sidebar."""
    __slots__ = ("name", "rect", "data")
    def __init__(self, name: str, rect: pygame.Rect, data=None):
        self.name = name
        self.rect = rect
        self.data = data


# ── Toolbar ───────────────────────────────────────────────────────────────────

def draw_toolbar(
    surface:      pygame.Surface,
    width:        int,
    active_tool:  str,
    scale:        str,
    turn:         int,
    campaign_name: str,
    hover_pos:    Tuple[int, int],
) -> List[Hitbox]:
    """
    Draw top toolbar. Returns list of clickable Hitboxes:
      new, load, save, export, next_turn,
      tool_select, tool_move, tool_add_unit, tool_add_mission,
      view_strategic, view_operational,
      add_faction, quit
    """
    pygame.draw.rect(surface, PANEL_DARK, (0, 0, width, TOOLBAR_H))
    pygame.draw.line(surface, BORDER, (0, TOOLBAR_H), (width, TOOLBAR_H), 1)

    font = pygame.font.SysFont("monospace", 13, bold=True)
    boxes: List[Hitbox] = []
    x = 6
    y = 7

    def btn(name: str, label: str, w: int = 70, active: bool = False, danger: bool = False):
        nonlocal x
        rect = pygame.Rect(x, y, w, TOOLBAR_H - 14)
        color = BTN_ACTIVE if active else (BTN_NORMAL if not danger else (140, 40, 40))
        if rect.collidepoint(hover_pos) and not active:
            color = BTN_HOVER
        pygame.draw.rect(surface, color, rect, border_radius=3)
        pygame.draw.rect(surface, BORDER_LT, rect, 1, border_radius=3)
        lbl = font.render(label, True, BTN_TEXT)
        surface.blit(lbl, lbl.get_rect(center=rect.center))
        boxes.append(Hitbox(name, rect))
        x += w + 4

    def sep():
        nonlocal x
        pygame.draw.line(surface, BORDER, (x + 2, y + 2), (x + 2, y + TOOLBAR_H - 16), 1)
        x += 8

    btn("new",  "New",  60)
    btn("load", "Load", 60)
    btn("save", "Save", 60)
    btn("export", "Export", 78)
    sep()

    # Tools
    btn("tool_select",       "Select",       70, active=(active_tool == "select"))
    btn("tool_move",         "Move",         62, active=(active_tool == "move"))
    btn("tool_add_unit",     "+Unit",        62, active=(active_tool == "add_unit"))
    btn("tool_add_mission",  "+Mission",     82, active=(active_tool == "add_mission"))
    btn("tool_delete",       "Delete",       66, active=(active_tool == "delete"))
    sep()

    btn("view_strategic",   "Strategic",   86, active=(scale == SCALE_STRATEGIC))
    btn("view_operational", "Operational", 98, active=(scale == SCALE_OPERATIONAL))
    sep()

    btn("add_faction", "+Faction", 82)
    sep()

    # Turn counter
    turn_rect = pygame.Rect(x, y, 110, TOOLBAR_H - 14)
    pygame.draw.rect(surface, (40, 40, 50), turn_rect, border_radius=3)
    pygame.draw.rect(surface, BORDER_LT, turn_rect, 1, border_radius=3)
    t_lbl = font.render(f"Turn {turn}", True, TEXT_BRIGHT)
    surface.blit(t_lbl, t_lbl.get_rect(center=turn_rect.center))
    x += 114

    btn("next_turn", "Next >>", 82)

    # Right-aligned: campaign name
    name_font = pygame.font.SysFont("monospace", 14, bold=True)
    name_surf = name_font.render(campaign_name, True, TEXT_WARN)
    surface.blit(name_surf, (width - name_surf.get_width() - 16, 14))

    return boxes


# ── Sidebar ───────────────────────────────────────────────────────────────────

def draw_sidebar(
    surface:      pygame.Surface,
    x:            int,
    y:            int,
    width:        int,
    height:       int,
    campaign:     Campaign,
    selected_hex: Optional[Tuple[int, int]],
    selected_unit_id: Optional[str],
    active_faction_filter: Optional[str],
    hover_pos:    Tuple[int, int],
    scale:        str,
    op_hex:       Optional[Tuple[int, int]],
) -> List[Hitbox]:
    """Right sidebar with factions, selected hex info, unit info."""
    rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, PANEL_BG, rect)
    pygame.draw.line(surface, BORDER, (x, y), (x, y + height), 1)

    font_h  = pygame.font.SysFont("monospace", 14, bold=True)
    font    = pygame.font.SysFont("monospace", 12)
    font_sm = pygame.font.SysFont("monospace", 11)

    boxes: List[Hitbox] = []
    cy = y + 10

    # ── Factions ─────────────────────────────────────────────────────────────
    surface.blit(font_h.render("FACTIONS", True, TEXT_BRIGHT), (x + 12, cy))
    cy += 22
    for f in campaign.factions.values():
        row = pygame.Rect(x + 8, cy, width - 16, 24)
        is_active = active_faction_filter == f.id
        bg = BTN_ACTIVE if is_active else (PANEL_DARK if row.collidepoint(hover_pos) else PANEL_DARK)
        if not is_active and row.collidepoint(hover_pos):
            bg = BTN_HOVER
        pygame.draw.rect(surface, bg, row, border_radius=3)
        pygame.draw.rect(surface, f.color, (row.x + 4, row.y + 4, 14, 16), border_radius=2)
        n_units = sum(1 for u in campaign.units.values() if u.faction_id == f.id)
        lbl = font.render(f"{f.name[:20]:20} [{n_units}]", True, TEXT)
        surface.blit(lbl, (row.x + 24, row.y + 6))
        boxes.append(Hitbox("faction", row, f.id))
        cy += 26
    if not campaign.factions:
        surface.blit(font_sm.render("(none yet — click +Faction)", True, TEXT_DIM), (x + 12, cy))
        cy += 18
    cy += 6

    # ── Selected hex ─────────────────────────────────────────────────────────
    pygame.draw.line(surface, BORDER, (x + 6, cy), (x + width - 6, cy), 1); cy += 6
    surface.blit(font_h.render("HEX INFO", True, TEXT_BRIGHT), (x + 12, cy)); cy += 22

    if selected_hex is None:
        surface.blit(font_sm.render("(no hex selected)", True, TEXT_DIM), (x + 12, cy))
        cy += 16
    else:
        col, row_idx = axial_to_offset(__import__("game.hex_grid", fromlist=["Hex"]).Hex.from_tuple(selected_hex))
        surface.blit(font.render(f"Axial:  q={selected_hex[0]}  r={selected_hex[1]}", True, TEXT), (x + 12, cy)); cy += 16
        surface.blit(font.render(f"Offset: col={col}  row={row_idx}", True, TEXT_DIM), (x + 12, cy)); cy += 16

        if scale == SCALE_STRATEGIC:
            terrain_id = campaign.terrain_map.get(selected_hex, "?")
            scale_m = HIGH_ALT_HEX_SIZE_M
        else:
            from game.campaign import get_operational_map
            tmap = get_operational_map(campaign, op_hex) if op_hex else {}
            terrain_id = tmap.get(selected_hex, "?")
            scale_m = LOW_ALT_HEX_SIZE_M
        surface.blit(font.render(f"Terrain: {terrain_name(terrain_id)}", True, TEXT), (x + 12, cy)); cy += 16
        surface.blit(font_sm.render(f"({scale_m/1000:.1f} km across)", True, TEXT_DIM), (x + 12, cy)); cy += 18

        # Units in this hex
        hex_units = [u for u in campaign.units.values() if u.position == selected_hex]
        if hex_units and scale == SCALE_STRATEGIC:
            surface.blit(font.render(f"Units ({len(hex_units)}):", True, TEXT_BRIGHT), (x + 12, cy)); cy += 16
            for u in hex_units:
                row = pygame.Rect(x + 14, cy, width - 28, 20)
                is_sel = u.id == selected_unit_id
                bg = BTN_ACTIVE if is_sel else (BTN_HOVER if row.collidepoint(hover_pos) else PANEL_DARK)
                pygame.draw.rect(surface, bg, row, border_radius=2)
                faction = campaign.factions.get(u.faction_id)
                fc = faction.color if faction else (150, 150, 150)
                pygame.draw.circle(surface, fc, (row.x + 10, row.y + 10), 5)
                lbl = font_sm.render(f"{u.name[:22]} [{u.unit_type[:4]}]", True, TEXT)
                surface.blit(lbl, (row.x + 20, row.y + 4))
                boxes.append(Hitbox("unit", row, u.id))
                cy += 22

        # Missions in this hex
        hex_missions = [m for m in campaign.missions.values() if m.position == selected_hex and scale == SCALE_STRATEGIC]
        if hex_missions:
            cy += 4
            surface.blit(font.render(f"Missions ({len(hex_missions)}):", True, TEXT_BRIGHT), (x + 12, cy)); cy += 16
            for m in hex_missions:
                row = pygame.Rect(x + 14, cy, width - 28, 20)
                bg = BTN_HOVER if row.collidepoint(hover_pos) else PANEL_DARK
                pygame.draw.rect(surface, bg, row, border_radius=2)
                lbl = font_sm.render(f"{m.mission_type[:8]}: {m.name[:18]}", True, TEXT)
                surface.blit(lbl, (row.x + 6, row.y + 4))
                boxes.append(Hitbox("mission", row, m.id))
                cy += 22

    cy += 6

    # ── Selected unit details ────────────────────────────────────────────────
    if selected_unit_id and selected_unit_id in campaign.units:
        u = campaign.units[selected_unit_id]
        pygame.draw.line(surface, BORDER, (x + 6, cy), (x + width - 6, cy), 1); cy += 6
        surface.blit(font_h.render("UNIT DETAIL", True, TEXT_BRIGHT), (x + 12, cy)); cy += 22
        faction = campaign.factions.get(u.faction_id)
        surface.blit(font.render(u.name[:30], True, TEXT_BRIGHT), (x + 12, cy)); cy += 16
        surface.blit(font_sm.render(f"Type: {u.unit_type}", True, TEXT), (x + 12, cy)); cy += 14
        if faction:
            surface.blit(font_sm.render(f"Faction: {faction.name}", True, TEXT), (x + 12, cy)); cy += 14
        status_color = TEXT_WARN if u.status != "active" else TEXT
        surface.blit(font_sm.render(f"Status: {u.status}", True, status_color), (x + 12, cy)); cy += 14
        surface.blit(font_sm.render(f"Vision: {u.vision_range} hex", True, TEXT), (x + 12, cy)); cy += 14
        surface.blit(font_sm.render(f"Roster: {len(u.roster)} element(s)", True, TEXT), (x + 12, cy)); cy += 16

        # Edit button
        edit_rect = pygame.Rect(x + 12, cy, 80, 22)
        bg = BTN_HOVER if edit_rect.collidepoint(hover_pos) else BTN_NORMAL
        pygame.draw.rect(surface, bg, edit_rect, border_radius=3)
        pygame.draw.rect(surface, BORDER_LT, edit_rect, 1, border_radius=3)
        surface.blit(font.render("Edit...", True, BTN_TEXT), (edit_rect.x + 16, edit_rect.y + 4))
        boxes.append(Hitbox("edit_unit", edit_rect, u.id))

        del_rect = pygame.Rect(x + 100, cy, 80, 22)
        bg = BTN_HOVER if del_rect.collidepoint(hover_pos) else (140, 40, 40)
        pygame.draw.rect(surface, bg, del_rect, border_radius=3)
        pygame.draw.rect(surface, BORDER_LT, del_rect, 1, border_radius=3)
        surface.blit(font.render("Delete", True, BTN_TEXT), (del_rect.x + 18, del_rect.y + 4))
        boxes.append(Hitbox("delete_unit", del_rect, u.id))
        cy += 28

    return boxes


# ── Statusbar ─────────────────────────────────────────────────────────────────

def draw_statusbar(
    surface:    pygame.Surface,
    x:          int, y: int, width: int,
    hover_hex:  Optional[Tuple[int, int]],
    terrain_name_str: str,
    hex_size:   float,
    scale:      str,
    op_hex:     Optional[Tuple[int, int]],
    tool:       str,
) -> None:
    pygame.draw.rect(surface, PANEL_DARK, (x, y, width, STATUSBAR_H))
    pygame.draw.line(surface, BORDER, (x, y), (x + width, y), 1)
    font = pygame.font.SysFont("monospace", 12)

    parts = []
    if hover_hex:
        parts.append(f"Hex ({hover_hex[0]},{hover_hex[1]})")
        if terrain_name_str:
            parts.append(terrain_name_str)
    parts.append(f"Zoom: {int(hex_size)}px")
    if scale == SCALE_OPERATIONAL and op_hex:
        parts.append(f"Operational view of strat hex ({op_hex[0]},{op_hex[1]})")
    else:
        from ui.renderer import SUBHEX_ZOOM_THRESHOLD, TACTICAL_ZOOM_THRESHOLD
        if hex_size >= TACTICAL_ZOOM_THRESHOLD:
            parts.append("Mapsheet tiles (500 m each)")
        elif hex_size >= SUBHEX_ZOOM_THRESHOLD:
            parts.append(f"Low-altitude hexes (each sub = {LOW_ALT_HEX_SIZE_M/1000:.1f} km)")
        else:
            parts.append(f"Strategic  (each hex = {HIGH_ALT_HEX_SIZE_M/1000:.0f} km)")
    parts.append(f"Tool: {tool}")

    txt = "  |  ".join(parts)
    surface.blit(font.render(txt, True, TEXT), (x + 10, y + 6))
