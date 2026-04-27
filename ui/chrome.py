"""Toolbar, sidebar, statusbar drawing."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pygame

from game.constants import (SCALE_STRATEGIC, SCALE_OPERATIONAL,
                             HIGH_ALT_HEX_SIZE_M, LOW_ALT_HEX_SIZE_M,
                             PHASE_COLOR, PHASE_ABBR, PHASE_MORNING,
                             OP_TURNS_PER_PHASE,
                             STATUS_DESTROYED, STATUS_RETREATED, STATUS_INORBIT,
                             STATUS_CRIPPLED, ELEVATION_VISION_DIV)
from game.hex_grid import axial_to_offset
from game.models import Campaign, Faction, Unit
from game.terrain import terrain_name
from ui.colors import (BG, PANEL_BG, PANEL_DARK, BORDER, BORDER_LT,
                        BTN_NORMAL, BTN_HOVER, BTN_ACTIVE, BTN_DANGER, BTN_TEXT,
                        TEXT, TEXT_DIM, TEXT_BRIGHT, TEXT_WARN, TEXT_BAD, TEXT_GOOD)

TOOLBAR_H   = 46
STATUSBAR_H = 26
SIDEBAR_W   = 290


def _mission_status_color(status: str) -> tuple:
    return {
        "active":    ( 40, 160, 255),
        "completed": ( 60, 200,  80),
        "failed":    (210,  50,  50),
        "pending":   (200, 160,  40),
    }.get(status, (120, 120, 130))


def _event_icon(event: str) -> str:
    return {
        "turn_advanced":      ">>",
        "faction_added":      "[F]",
        "unit_added":         "[U]",
        "unit_moved":         "~>",
        "unit_deleted":       "[X]",
        "unit_repaired":      "[W]",
        "mission_created":    "[M]",
        "mission_resolved":   "[R]",
        "funds_adjusted":     "[$]",
        "structure_built":    "[S]",
        "structure_deleted":  "[S]",
        "supply_warning":     "[!]",
        "territory_captured":  "[T]",
        "group_added":         "[G]",
        "combat_resolved":     "[C]",
        "objective_placed":    "[*]",
        "objective_resolved":  "[*]",
        "phase_morning":       "[AM]",
        "phase_afternoon":     "[PM]",
        "phase_night":         "[**]",
        "contact_detected":    "[!!]",
        "sensor_contact":      "[~]",
        "op_turn_advanced":    "[h]",
        "op_contact":          "[X]",
        "income":              "[$]",
    }.get(event, "  ")


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
    phase:        str = PHASE_MORNING,
    has_undo:     bool = False,
    op_turn:      int  = 0,
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
    btn("tool_select",        "Select",  64, active=(active_tool == "select"))
    btn("tool_move",          "Move",    54, active=(active_tool == "move"))
    btn("tool_add_unit",      "+Unit",   56, active=(active_tool == "add_unit"))
    btn("tool_add_mission",   "+Miss",   58, active=(active_tool == "add_mission"))
    btn("tool_add_structure", "+Bldg",   58, active=(active_tool == "add_structure"))
    btn("tool_add_objective", "+Obj",    52, active=(active_tool == "add_objective"))
    btn("tool_paint_terrain",   "Paint",  56, active=(active_tool == "paint_terrain"))
    btn("tool_paint_elevation", "Elev",  48, active=(active_tool == "paint_elevation"))
    btn("add_group",            "+Grp",  52)
    btn("tool_delete",        "Del",     46, active=(active_tool == "delete"))
    sep()

    btn("view_strategic",   "Strat",  56, active=(scale == SCALE_STRATEGIC))
    btn("view_operational", "Op",     44, active=(scale == SCALE_OPERATIONAL))
    sep()

    btn("add_faction", "+Fac", 54)
    sep()

    # Day / Phase / Op-turn counter
    phase_color = PHASE_COLOR.get(phase, (120, 120, 130))
    abbr        = PHASE_ABBR.get(phase, "??")
    if scale == SCALE_OPERATIONAL:
        turn_label = f"D{turn} {abbr}  H{op_turn+1}/{OP_TURNS_PER_PHASE}"
        turn_w     = 164
        next_label = "Hr >>"
        next_w     = 64
    else:
        turn_label = f"Day {turn}  ·  {abbr}"
        turn_w     = 148
        next_label = "Next >>"
        next_w     = 74
    turn_rect = pygame.Rect(x, y, turn_w, TOOLBAR_H - 14)
    pygame.draw.rect(surface, (40, 40, 50), turn_rect, border_radius=3)
    pygame.draw.rect(surface, phase_color, turn_rect, 1, border_radius=3)
    t_lbl = font.render(turn_label, True, phase_color)
    surface.blit(t_lbl, t_lbl.get_rect(center=turn_rect.center))
    x += turn_w + 4

    btn("next_turn",    next_label, next_w)
    btn("revert_phase", "Undo",     54, danger=(not has_undo))

    # Campaign name right-aligned — only drawn if it won't overlap buttons
    name_font = pygame.font.SysFont("monospace", 13, bold=True)
    short_name = campaign_name[:18] + "…" if len(campaign_name) > 18 else campaign_name
    name_surf  = name_font.render(short_name, True, TEXT_WARN)
    name_x = width - name_surf.get_width() - 10
    if name_x > x + 6:
        surface.blit(name_surf, (name_x, 14))

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
    op_turn_moved: Optional[set] = None,
    op_engagement: Optional[dict] = None,
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

    # ── Active Turn ───────────────────────────────────────────────────────────
    faction_list = list(campaign.factions.values())
    if faction_list:
        af_idx = campaign.active_faction_idx % len(faction_list)
        af = faction_list[af_idx]
        banner = pygame.Rect(x + 6, cy, width - 12, 26)
        pygame.draw.rect(surface, (30, 50, 30), banner, border_radius=3)
        pygame.draw.rect(surface, af.color, banner, 1, border_radius=3)
        pygame.draw.rect(surface, af.color, (banner.x + 4, banner.y + 5, 14, 16), border_radius=2)
        lbl = font.render(f"  {af.name[:14]}'s Turn", True, af.color)
        surface.blit(lbl, (banner.x + 22, banner.y + 6))
        et_r = pygame.Rect(banner.right - 78, banner.y + 4, 72, 18)
        et_bg = BTN_HOVER if et_r.collidepoint(hover_pos) else BTN_NORMAL
        pygame.draw.rect(surface, et_bg, et_r, border_radius=2)
        surface.blit(font_sm.render("End Turn →", True, BTN_TEXT), (et_r.x + 4, et_r.y + 3))
        boxes.append(Hitbox("end_turn", et_r))
        cy += 32
        rst_all_r = pygame.Rect(x + 6, cy, width - 12, 18)
        rst_bg = BTN_HOVER if rst_all_r.collidepoint(hover_pos) else BTN_NORMAL
        pygame.draw.rect(surface, rst_bg, rst_all_r, border_radius=2)
        surface.blit(font_sm.render("↺ Reset All Moves", True, BTN_TEXT),
                     (rst_all_r.x + 8, rst_all_r.y + 3))
        boxes.append(Hitbox("reset_all_moves", rst_all_r))
        cy += 22

    # ── Operational / Engagement panel ───────────────────────────────────────
    if scale == SCALE_OPERATIONAL and op_hex is not None:
        from game.hex_grid import Hex, hex_distance
        _moved = op_turn_moved or set()
        _eng   = op_engagement or {}

        hex_units = [u for u in campaign.units.values()
                     if u.position == op_hex
                     and u.status not in (STATUS_DESTROYED,)]
        by_faction: dict = {}
        for u in hex_units:
            by_faction.setdefault(u.faction_id, []).append(u)

        if _eng:
            # ── ENGAGEMENT MODE — one section per active contact ──────────
            n_eng = len(_eng)
            pygame.draw.line(surface, (200, 40, 40), (x + 6, cy), (x + width - 6, cy), 2); cy += 6
            hdr = f"⚔ ENGAGEMENT{'S' if n_eng > 1 else ''}  ({n_eng})"
            surface.blit(font_h.render(hdr, True, (255, 80, 80)), (x + 12, cy)); cy += 18

            for sp, eng in _eng.items():
                emv = eng.get("turn_moved", set())
                # Sub-header for this contact point
                sp_lbl = font_sm.render(f"sub({sp[0]},{sp[1]})", True, (255, 160, 80))
                surface.blit(sp_lbl, (x + 12, cy)); cy += 13

                # Units relative to this contact hex
                for fid, units in by_faction.items():
                    f  = campaign.factions.get(fid)
                    fc = f.color if f else (90, 90, 90)
                    total_bv = sum(u.battle_value for u in units if u.battle_value)
                    fname = (f.name[:12] if f else fid[:8]) + (f" BV{total_bv:,}" if total_bv else "")
                    surface.blit(font_sm.render(fname, True, fc), (x + 14, cy)); cy += 12
                    for u in units:
                        if u.sub_position is None:
                            continue
                        d     = hex_distance(Hex.from_tuple(sp), Hex.from_tuple(u.sub_position))
                        role  = "●" if d == 0 else "→" if d == 1 else "⋯"
                        r_col = (255, 80, 80) if d == 0 else (255, 180, 60) if d == 1 else (140, 180, 200)
                        moved = u.id in emv
                        row   = pygame.Rect(x + 8, cy, width - 16, 16)
                        bg    = (24, 24, 30) if moved else (BTN_HOVER if row.collidepoint(hover_pos) else PANEL_DARK)
                        pygame.draw.rect(surface, bg, row, border_radius=2)
                        mv_s  = "✓" if moved else " "
                        st_s  = "!" if u.status == STATUS_CRIPPLED else " "
                        sub_s = f"({u.sub_position[0]},{u.sub_position[1]})"
                        lbl   = font_sm.render(f"{mv_s}{st_s}{u.name[:11]} {sub_s}", True,
                                               TEXT_DIM if moved else TEXT)
                        surface.blit(lbl, (row.x + 4, row.y + 2))
                        rl = font_sm.render(role, True, r_col)
                        surface.blit(rl, (row.right - rl.get_width() - 4, row.y + 2))
                        boxes.append(Hitbox("unit", row, u.id))
                        cy += 17

                # Per-engagement action buttons (carry sp as data)
                btn_w = (width - 20) // 2
                nxt_r = pygame.Rect(x + 8,          cy, btn_w - 2, 20)
                cmt_r = pygame.Rect(x + 8 + btn_w,  cy, btn_w - 2, 20)
                nxt_bg = BTN_HOVER if nxt_r.collidepoint(hover_pos) else BTN_NORMAL
                cmt_bg = (50, 90, 50) if cmt_r.collidepoint(hover_pos) else (35, 65, 35)
                pygame.draw.rect(surface, nxt_bg, nxt_r, border_radius=3)
                pygame.draw.rect(surface, BORDER_LT, nxt_r, 1, border_radius=3)
                pygame.draw.rect(surface, cmt_bg, cmt_r, border_radius=3)
                pygame.draw.rect(surface, (80, 180, 80), cmt_r, 1, border_radius=3)
                surface.blit(font_sm.render("↺ Pos.Turn", True, BTN_TEXT), (nxt_r.x + 4, nxt_r.y + 4))
                surface.blit(font_sm.render("⚔ Lock In", True, (140, 235, 140)), (cmt_r.x + 4, cmt_r.y + 4))
                boxes.append(Hitbox("engage_next_turn", nxt_r, sp))
                boxes.append(Hitbox("engage_commit",    cmt_r, sp))
                cy += 24

        else:
            # ── NORMAL OP UNITS panel ─────────────────────────────────────
            pygame.draw.line(surface, (80, 80, 100), (x + 6, cy), (x + width - 6, cy), 1); cy += 6
            surface.blit(font_h.render("OP UNITS", True, TEXT_BRIGHT), (x + 12, cy)); cy += 18

            if not hex_units:
                surface.blit(font_sm.render("(no units in this hex)", True, TEXT_DIM), (x + 12, cy))
                cy += 14
            else:
                for fid, units in by_faction.items():
                    f  = campaign.factions.get(fid)
                    fc = f.color if f else (90, 90, 90)
                    total_bv = sum(u.battle_value for u in units if u.battle_value)
                    bv_str = f"  BV {total_bv:,}" if total_bv else ""
                    surface.blit(font_sm.render((f.name[:16] if f else fid[:12]) + bv_str, True, fc),
                                 (x + 12, cy)); cy += 13
                    for u in units:
                        row   = pygame.Rect(x + 8, cy, width - 16, 17)
                        moved = u.id in _moved
                        bg    = (24, 24, 30) if moved else (BTN_HOVER if row.collidepoint(hover_pos) else PANEL_DARK)
                        pygame.draw.rect(surface, bg, row, border_radius=2)
                        sub_s = f"({u.sub_position[0]},{u.sub_position[1]})" if u.sub_position else "(--)"
                        mv_s  = "✓" if moved else " "
                        st_s  = "!" if u.status == STATUS_CRIPPLED else " "
                        lbl   = font_sm.render(f"{mv_s}{st_s}{u.name[:14]} {sub_s}", True,
                                               TEXT_DIM if moved else TEXT)
                        surface.blit(lbl, (row.x + 4, row.y + 3))
                        boxes.append(Hitbox("unit", row, u.id))
                        cy += 18
                cy += 4

            # Sub-hex contact indicator
            contacts_at: dict = {}
            for u in hex_units:
                if u.sub_position:
                    contacts_at.setdefault(u.sub_position, set()).add(u.faction_id)
            contested = [(sp, fids) for sp, fids in contacts_at.items() if len(fids) >= 2]
            if contested:
                pygame.draw.line(surface, (200, 50, 50), (x + 6, cy), (x + width - 6, cy), 1); cy += 4
                surface.blit(font_sm.render("CONTACT!", True, (255, 80, 80)), (x + 12, cy)); cy += 13
                for sp, fids in contested:
                    names = [campaign.factions[f].name[:8] if f in campaign.factions else f[:6]
                             for f in fids]
                    surface.blit(font_sm.render(f"  sub{sp}: {' vs '.join(names)}", True, (255, 120, 120)),
                                 (x + 12, cy)); cy += 12
                cy += 4

    # ── Factions ─────────────────────────────────────────────────────────────
    surface.blit(font_h.render("FACTIONS", True, TEXT_BRIGHT), (x + 12, cy))
    cy += 22
    for f in campaign.factions.values():
        row = pygame.Rect(x + 8, cy, width - 16, 24)
        is_active = active_faction_filter == f.id
        bg = BTN_ACTIVE if is_active else (BTN_HOVER if row.collidepoint(hover_pos) else PANEL_DARK)
        pygame.draw.rect(surface, bg, row, border_radius=3)
        pygame.draw.rect(surface, f.color, (row.x + 4, row.y + 4, 14, 16), border_radius=2)
        n_units = sum(1 for u in campaign.units.values() if u.faction_id == f.id)
        lbl = font.render(f"{f.name[:16]:16} [{n_units}]", True, TEXT)
        surface.blit(lbl, (row.x + 24, row.y + 6))
        boxes.append(Hitbox("faction", row, f.id))
        cy += 26

        # Resources line with adjust button
        res_color = TEXT_GOOD if f.resources >= 0 else TEXT_BAD
        surface.blit(font_sm.render(f"  C-Bills: {f.resources:,}", True, res_color), (x + 24, cy + 1))
        adj_rect = pygame.Rect(x + width - 52, cy, 44, 15)
        adj_bg = BTN_HOVER if adj_rect.collidepoint(hover_pos) else BTN_NORMAL
        pygame.draw.rect(surface, adj_bg, adj_rect, border_radius=2)
        surface.blit(font_sm.render("[+/-]", True, BTN_TEXT), (adj_rect.x + 2, adj_rect.y + 1))
        boxes.append(Hitbox("adjust_funds", adj_rect, f.id))
        cy += 16
        # Daily income projection
        from game.campaign import compute_daily_income
        bd = compute_daily_income(campaign, f.id)
        net_color = TEXT_GOOD if bd["net"] >= 0 else TEXT_BAD
        inc_k  = bd["income"]      // 1000
        mnt_k  = bd["maintenance"] // 1000
        sign   = "+" if bd["net"] >= 0 else ""
        net_k  = bd["net"]         // 1000
        daily  = f"  +{inc_k}k / -{mnt_k}k = {sign}{net_k}k/day"
        surface.blit(font_sm.render(daily, True, net_color), (x + 24, cy + 1))
        cy += 14
        # Total Battle Value
        total_bv = sum(u.battle_value for u in campaign.units.values()
                       if u.faction_id == f.id
                       and u.status not in (STATUS_DESTROYED, STATUS_RETREATED))
        surface.blit(font_sm.render(f"  BV: {total_bv:,}", True, TEXT_DIM), (x + 24, cy + 1))
        cy += 13

    if not campaign.factions:
        surface.blit(font_sm.render("(none yet — click +Faction)", True, TEXT_DIM), (x + 12, cy))
        cy += 18
    cy += 4

    # ── Contact report ───────────────────────────────────────────────────────
    contacts = campaign.active_contacts
    if contacts:
        pygame.draw.line(surface, (200, 50, 50), (x + 6, cy), (x + width - 6, cy), 1); cy += 6
        surface.blit(font_h.render("!! CONTACT !!", True, (255, 80, 80)), (x + 12, cy)); cy += 20
        for key, fids in list(contacts.items())[:4]:
            q, r = (int(n) for n in key.split(","))
            row = pygame.Rect(x + 8, cy, width - 16, 20)
            bg  = BTN_HOVER if row.collidepoint(hover_pos) else (60, 20, 20)
            pygame.draw.rect(surface, bg, row, border_radius=2)
            names = [campaign.factions[f].name[:8] if f in campaign.factions else f[:8]
                     for f in fids]
            lbl = font_sm.render(f"({q},{r}) {' vs '.join(names)}", True, (255, 120, 120))
            surface.blit(lbl, (row.x + 8, row.y + 4))
            boxes.append(Hitbox("contact_hex", row, (q, r)))
            cy += 22
        cy += 4

    # ── Groups ───────────────────────────────────────────────────────────────
    pygame.draw.line(surface, BORDER, (x + 6, cy), (x + width - 6, cy), 1); cy += 6
    surface.blit(font_h.render("GROUPS", True, TEXT_BRIGHT), (x + 12, cy)); cy += 20
    if not campaign.groups:
        surface.blit(font_sm.render("(no groups — use +Group)", True, TEXT_DIM), (x + 12, cy))
        cy += 16
    else:
        for g in campaign.groups.values():
            n_members = sum(1 for u in campaign.units.values() if u.group_id == g.id)
            row = pygame.Rect(x + 8, cy, width - 16, 20)
            bg = BTN_HOVER if row.collidepoint(hover_pos) else PANEL_DARK
            pygame.draw.rect(surface, bg, row, border_radius=2)
            gf = campaign.factions.get(g.faction_id)
            fc = gf.color if gf else (90, 90, 90)
            pygame.draw.circle(surface, fc, (row.x + 10, row.y + 10), 4)
            lbl = font_sm.render(f"{g.name[:20]} ({n_members}u)", True, TEXT)
            surface.blit(lbl, (row.x + 20, row.y + 4))
            boxes.append(Hitbox("group", row, g.id))
            cy += 22
    cy += 4

    # ── Reserves (off-map units) ──────────────────────────────────────────────
    _TYPE_ABBR = {"BattleMech": "M", "Vehicle": "V", "Aerospace": "A",
                  "Infantry": "I", "DropShip": "D"}
    reserve_units = [u for u in campaign.units.values()
                     if u.position is None and u.status != STATUS_DESTROYED]
    if reserve_units:
        pygame.draw.line(surface, BORDER, (x + 6, cy), (x + width - 6, cy), 1); cy += 6
        surface.blit(font_h.render("RESERVES", True, TEXT_BRIGHT), (x + 12, cy)); cy += 20
        for u in reserve_units:
            row = pygame.Rect(x + 8, cy, width - 16, 20)
            bg  = BTN_HOVER if row.collidepoint(hover_pos) else PANEL_DARK
            pygame.draw.rect(surface, bg, row, border_radius=2)
            fac = campaign.factions.get(u.faction_id)
            fc  = fac.color if fac else (90, 90, 90)
            pygame.draw.circle(surface, fc, (row.x + 10, row.y + 10), 4)
            abbr = _TYPE_ABBR.get(u.unit_type, "?")
            lbl  = font_sm.render(f"{u.name[:16]} [{abbr}]", True, TEXT)
            surface.blit(lbl, (row.x + 20, row.y + 4))
            # Deploy button — registered BEFORE row hitbox so it wins collision check
            dep_r  = pygame.Rect(row.right - 52, row.y + 2, 48, 16)
            dep_bg = (30, 100, 30) if dep_r.collidepoint(hover_pos) else BTN_NORMAL
            pygame.draw.rect(surface, dep_bg, dep_r, border_radius=2)
            surface.blit(font_sm.render("Deploy", True, BTN_TEXT), (dep_r.x + 4, dep_r.y + 2))
            boxes.append(Hitbox("deploy_unit", dep_r, u.id))
            boxes.append(Hitbox("reserve_unit", row,   u.id))
            cy += 22
        cy += 4

    # ── In Orbit ──────────────────────────────────────────────────────────────
    orbit_units = [u for u in campaign.units.values()
                   if u.status == STATUS_INORBIT]
    if orbit_units:
        pygame.draw.line(surface, BORDER, (x + 6, cy), (x + width - 6, cy), 1); cy += 6
        surface.blit(font_h.render("IN ORBIT", True, (120, 160, 255)), (x + 12, cy)); cy += 20
        for u in orbit_units:
            row = pygame.Rect(x + 8, cy, width - 16, 20)
            bg  = BTN_HOVER if row.collidepoint(hover_pos) else (20, 20, 50)
            pygame.draw.rect(surface, bg, row, border_radius=2)
            fac = campaign.factions.get(u.faction_id)
            fc  = fac.color if fac else (90, 90, 90)
            pygame.draw.circle(surface, fc, (row.x + 10, row.y + 10), 4)
            abbr = _TYPE_ABBR.get(u.unit_type, "?")
            lbl  = font_sm.render(f"{u.name[:16]} [{abbr}]", True, (180, 200, 255))
            surface.blit(lbl, (row.x + 20, row.y + 4))
            land_r  = pygame.Rect(row.right - 48, row.y + 2, 44, 16)
            land_bg = (20, 60, 120) if land_r.collidepoint(hover_pos) else BTN_NORMAL
            pygame.draw.rect(surface, land_bg, land_r, border_radius=2)
            surface.blit(font_sm.render("Land", True, BTN_TEXT), (land_r.x + 6, land_r.y + 2))
            boxes.append(Hitbox("land_unit",   land_r, u.id))
            boxes.append(Hitbox("orbit_unit",  row,    u.id))
            cy += 22
        cy += 4

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
        if scale == SCALE_STRATEGIC and campaign.elevation_map:
            elev = campaign.elevation_map.get(selected_hex, 3)
            elev_bar = "█" * elev + "░" * (10 - elev)
            surface.blit(font_sm.render(f"Elev: {elev:2d}/10  {elev_bar}", True, (160, 200, 255)), (x + 12, cy)); cy += 14
        if scale_m >= 1000:
            scale_str = f"{scale_m // 1000} km across"
        else:
            scale_str = f"{scale_m} m across (1 mapsheet)"
        surface.blit(font_sm.render(f"({scale_str})", True, TEXT_DIM), (x + 12, cy)); cy += 16

        # Territory control
        if scale == SCALE_STRATEGIC:
            ctrl_key = f"{selected_hex[0]},{selected_hex[1]}"
            ctrl_fid = campaign.hex_control.get(ctrl_key)
            if ctrl_fid and ctrl_fid in campaign.factions:
                cf = campaign.factions[ctrl_fid]
                pygame.draw.rect(surface, cf.color, pygame.Rect(x + 12, cy + 3, 8, 8))
                surface.blit(font_sm.render(f"Controlled by: {cf.name}", True, TEXT), (x + 26, cy))
            else:
                surface.blit(font_sm.render("Control: Uncontrolled", True, TEXT_DIM), (x + 12, cy))
            cy += 16

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
                lbl = font_sm.render(f"{u.name[:16]} [{u.unit_type[:4]}]", True, TEXT)
                surface.blit(lbl, (row.x + 20, row.y + 4))
                if u.has_moved:
                    mv_surf = font_sm.render("✓moved", True, (200, 160, 60))
                    surface.blit(mv_surf, (row.right - mv_surf.get_width() - 4, row.y + 4))
                elif u.walk_mp:
                    mp_surf = font_sm.render(f"{u.walk_mp}/{u.run_mp}", True, (140, 200, 140))
                    surface.blit(mp_surf, (row.right - mp_surf.get_width() - 4, row.y + 4))
                boxes.append(Hitbox("unit", row, u.id))
                cy += 22

        # Structures in this hex
        hex_structs = [s for s in campaign.structures.values()
                       if s.position == selected_hex and scale == SCALE_STRATEGIC]
        if hex_structs:
            cy += 4
            surface.blit(font.render(f"Structures ({len(hex_structs)}):", True, TEXT_BRIGHT), (x + 12, cy)); cy += 16
            for s in hex_structs:
                row = pygame.Rect(x + 14, cy, width - 28, 20)
                bg = BTN_HOVER if row.collidepoint(hover_pos) else PANEL_DARK
                pygame.draw.rect(surface, bg, row, border_radius=2)
                f_color = campaign.factions[s.faction_id].color if s.faction_id and s.faction_id in campaign.factions else (90, 90, 90)
                pygame.draw.rect(surface, f_color, pygame.Rect(row.x + 2, row.y + 2, 4, 16), border_radius=1)
                lbl = font_sm.render(f"{s.structure_type[:10]}: {s.name[:12]}", True, TEXT)
                surface.blit(lbl, (row.x + 10, row.y + 4))
                # Delete button registered BEFORE row so it takes priority on click
                del_r = pygame.Rect(row.right - 20, row.y + 2, 18, 16)
                del_bg = (180, 40, 40) if del_r.collidepoint(hover_pos) else (100, 30, 30)
                pygame.draw.rect(surface, del_bg, del_r, border_radius=2)
                surface.blit(font_sm.render("X", True, (255, 100, 100)), (del_r.x + 5, del_r.y + 2))
                boxes.append(Hitbox("delete_structure", del_r, s.id))
                boxes.append(Hitbox("structure", row, s.id))
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
                pygame.draw.rect(surface, _mission_status_color(m.status),
                                 pygame.Rect(row.x + 2, row.y + 2, 4, 16), border_radius=1)
                lbl = font_sm.render(f"{m.mission_type[:8]}: {m.name[:16]}", True, TEXT)
                surface.blit(lbl, (row.x + 10, row.y + 4))
                boxes.append(Hitbox("mission", row, m.id))
                cy += 22

        # GM hex note
        note_key = f"{selected_hex[0]},{selected_hex[1]}"
        note = campaign.hex_notes.get(note_key, "")
        cy += 4
        note_btn = pygame.Rect(x + 14, cy, width - 28, 18)
        nb_bg = BTN_HOVER if note_btn.collidepoint(hover_pos) else BTN_NORMAL
        pygame.draw.rect(surface, nb_bg, note_btn, border_radius=2)
        note_lbl = font_sm.render("Edit Note" if note else "+ Add Note", True, BTN_TEXT)
        surface.blit(note_lbl, (note_btn.x + 6, note_btn.y + 3))
        boxes.append(Hitbox("edit_note", note_btn, note_key))
        cy += 20
        if note:
            for chunk in (note[:34], note[34:68]):
                if chunk:
                    surface.blit(font_sm.render(chunk, True, TEXT_WARN), (x + 14, cy))
                    cy += 13

    cy += 4

    # ── Objectives & VP ──────────────────────────────────────────────────────
    if campaign.objectives or campaign.factions:
        pygame.draw.line(surface, BORDER, (x + 6, cy), (x + width - 6, cy), 1); cy += 6
        surface.blit(font_h.render("OBJECTIVES & VP", True, TEXT_BRIGHT), (x + 12, cy)); cy += 20

        # VP standings, highest first
        for f in sorted(campaign.factions.values(),
                        key=lambda f: -sum(o.vp_value for o in campaign.objectives.values()
                                           if o.faction_id == f.id)):
            vp = sum(o.vp_value for o in campaign.objectives.values() if o.faction_id == f.id)
            pygame.draw.rect(surface, f.color, pygame.Rect(x + 12, cy + 3, 8, 8))
            lbl = font_sm.render(f"{f.name[:14]}  {vp} VP", True, TEXT)
            surface.blit(lbl, (x + 26, cy))
            cy += 16

        # Objectives in selected hex
        if selected_hex and scale == SCALE_STRATEGIC:
            hex_objs = [o for o in campaign.objectives.values() if o.position == selected_hex]
            if hex_objs:
                cy += 2
                surface.blit(font_sm.render(f"Objectives here ({len(hex_objs)}):", True, TEXT_BRIGHT),
                             (x + 12, cy)); cy += 15
                for o in hex_objs:
                    row = pygame.Rect(x + 14, cy, width - 28, 20)
                    bg = BTN_HOVER if row.collidepoint(hover_pos) else PANEL_DARK
                    pygame.draw.rect(surface, bg, row, border_radius=2)
                    oc = {"active": (255, 215, 0), "captured": (60, 200, 80),
                          "denied": (210, 50, 50)}.get(o.status, (150, 150, 150))
                    pygame.draw.rect(surface, oc, pygame.Rect(row.x + 2, row.y + 2, 4, 16), border_radius=1)
                    lbl = font_sm.render(f"{o.name[:18]}  {o.vp_value}VP", True, TEXT)
                    surface.blit(lbl, (row.x + 10, row.y + 4))
                    boxes.append(Hitbox("objective", row, o.id))
                    cy += 22
        cy += 2

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
        from game.constants import STATUS_REPAIRING
        status_color = TEXT_WARN if u.status != "active" else TEXT
        surface.blit(font_sm.render(f"Status: {u.status}", True, status_color), (x + 12, cy)); cy += 14
        if u.has_moved:
            surface.blit(font_sm.render("Moved this phase", True, (200, 160, 60)), (x + 12, cy))
            rst_r = pygame.Rect(x + width - 82, cy - 1, 70, 16)
            rst_bg = BTN_HOVER if rst_r.collidepoint(hover_pos) else BTN_NORMAL
            pygame.draw.rect(surface, rst_bg, rst_r, border_radius=2)
            surface.blit(font_sm.render("Reset", True, BTN_TEXT), (rst_r.x + 10, rst_r.y + 2))
            boxes.append(Hitbox("reset_move", rst_r, u.id))
            cy += 14
        if u.status == STATUS_REPAIRING and u.repair_cost:
            faction_res = campaign.factions[u.faction_id].resources if u.faction_id in campaign.factions else 0
            can_afford  = faction_res >= u.repair_cost
            cost_color  = TEXT_GOOD if can_afford else TEXT_BAD
            surface.blit(font_sm.render(f"Repair cost: {u.repair_cost:,} C-Bills", True, cost_color),
                         (x + 12, cy)); cy += 14
            surface.blit(font_sm.render(f"Faction has: {faction_res:,} C-Bills", True, TEXT_DIM),
                         (x + 12, cy)); cy += 14
        elev_bonus = campaign.elevation_map.get(u.position, 3) // ELEVATION_VISION_DIV if u.position else 0
        vision_lbl = f"Vision: {u.vision_range}" + (f" +{elev_bonus} (elev)" if elev_bonus else "") + " hex"
        surface.blit(font_sm.render(vision_lbl, True, (60, 210, 100)), (x + 12, cy)); cy += 14
        bv_color = TEXT_WARN if u.battle_value == 0 else TEXT
        bv_label = f"BV: {u.battle_value:,}" if u.battle_value else "BV: (not set)"
        surface.blit(font_sm.render(bv_label, True, bv_color), (x + 12, cy)); cy += 14
        if u.group_id and u.group_id in campaign.groups:
            g = campaign.groups[u.group_id]
            surface.blit(font_sm.render(f"Group: {g.name}", True, TEXT_WARN), (x + 12, cy)); cy += 14
        surface.blit(font_sm.render(f"Roster: {len(u.roster)} element(s)", True, TEXT), (x + 12, cy)); cy += 16

        # Edit / Delete / Pay & Repair buttons
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

        fm_rect = pygame.Rect(x + 188, cy, 90, 22)
        fm_bg = BTN_HOVER if fm_rect.collidepoint(hover_pos) else (70, 40, 10)
        pygame.draw.rect(surface, fm_bg, fm_rect, border_radius=3)
        pygame.draw.rect(surface, (200, 120, 40), fm_rect, 1, border_radius=3)
        surface.blit(font_sm.render("GM Move", True, (255, 180, 80)), (fm_rect.x + 10, fm_rect.y + 5))
        boxes.append(Hitbox("force_move_unit", fm_rect, u.id))

        if u.status == STATUS_REPAIRING:
            repair_rect = pygame.Rect(x + 12, cy + 28, 130, 22)
            faction_res = campaign.factions[u.faction_id].resources if u.faction_id in campaign.factions else 0
            can_afford  = faction_res >= u.repair_cost
            rep_bg = BTN_HOVER if repair_rect.collidepoint(hover_pos) else (BTN_ACTIVE if can_afford else BTN_DANGER)
            pygame.draw.rect(surface, rep_bg, repair_rect, border_radius=3)
            pygame.draw.rect(surface, BORDER_LT, repair_rect, 1, border_radius=3)
            surface.blit(font_sm.render("Pay & Repair", True, BTN_TEXT), (repair_rect.x + 8, repair_rect.y + 5))
            boxes.append(Hitbox("pay_repair", repair_rect, u.id))
            cy += 28

        cy += 28

    # ── Recent events ────────────────────────────────────────────────────────
    pygame.draw.line(surface, BORDER, (x + 6, cy), (x + width - 6, cy), 1); cy += 6
    surface.blit(font_h.render("RECENT EVENTS", True, TEXT_BRIGHT), (x + 12, cy)); cy += 20

    recent = list(reversed(campaign.event_log[-8:]))
    if not recent:
        surface.blit(font_sm.render("(no events yet)", True, TEXT_DIM), (x + 12, cy))
        cy += 16
    else:
        for entry in recent:
            abbr = PHASE_ABBR.get(entry.get("phase", PHASE_MORNING), "  ")
            surface.blit(font_sm.render(f"D{entry['turn']}{abbr}", True, TEXT_DIM), (x + 12, cy))
            icon   = _event_icon(entry["event"])
            detail = entry["detail"][:30]
            surface.blit(font_sm.render(f"{icon} {detail}", True, TEXT), (x + 44, cy))
            cy += 15

    # ── Combat log ───────────────────────────────────────────────────────────
    pygame.draw.line(surface, BORDER, (x + 6, cy), (x + width - 6, cy), 1); cy += 6
    surface.blit(font_h.render("COMBAT LOG", True, TEXT_BRIGHT), (x + 12, cy)); cy += 20

    if selected_hex and scale == SCALE_STRATEGIC:
        hex_combats = [e for e in reversed(campaign.combat_log)
                       if tuple(e["position"]) == selected_hex][:3]
    else:
        hex_combats = list(reversed(campaign.combat_log[-3:]))

    if not hex_combats:
        surface.blit(font_sm.render("(no combats recorded)", True, TEXT_DIM), (x + 12, cy))
        cy += 16
    else:
        for e in hex_combats:
            atk = campaign.factions.get(e["attacker_fid"])
            dfn = campaign.factions.get(e["defender_fid"])
            line1 = f"T{e['turn']} {(atk.name if atk else '?')[:8]} vs {(dfn.name if dfn else '?')[:8]}"
            line2 = f"  -> {e['outcome'][:22]}"
            surface.blit(font_sm.render(line1, True, TEXT), (x + 12, cy)); cy += 13
            surface.blit(font_sm.render(line2, True, TEXT_DIM), (x + 12, cy)); cy += 14

    log_btn = pygame.Rect(x + 14, cy, width - 28, 18)
    lb_bg = BTN_HOVER if log_btn.collidepoint(hover_pos) else BTN_NORMAL
    pygame.draw.rect(surface, lb_bg, log_btn, border_radius=2)
    surface.blit(font_sm.render("+ Log Combat", True, BTN_TEXT), (log_btn.x + 6, log_btn.y + 3))
    boxes.append(Hitbox("log_combat", log_btn, None))
    cy += 22

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
        from ui.renderer import SUBHEX_ZOOM_THRESHOLD
        if hex_size >= SUBHEX_ZOOM_THRESHOLD:
            parts.append(f"Operational  (each hex = {LOW_ALT_HEX_SIZE_M} m / 1 mapsheet)")
        else:
            parts.append(f"Strategic  (each hex = {HIGH_ALT_HEX_SIZE_M // 1000} km)")
    parts.append(f"Tool: {tool}")

    txt = "  |  ".join(parts)
    surface.blit(font.render(txt, True, TEXT), (x + 10, y + 6))
