"""
Main Pygame application - the GM's campaign manager window.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import pygame

from game.constants import (SCALE_STRATEGIC, SCALE_OPERATIONAL,
                             DEFAULT_VISION, UNIT_MECH,
                             HIGH_ALT_HEX_SIZE_M, LOW_ALT_HEX_SIZE_M,
                             DEFAULT_MOVE_RANGE, OP_TURNS_PER_PHASE,
                             STATUS_ACTIVE, STATUS_RESERVE,
                             STATUS_DESTROYED, STATUS_RETREATED,
                             TERRAIN_PLAINS, TERRAIN_FOREST, TERRAIN_HILLS,
                             TERRAIN_MOUNTAINS, TERRAIN_URBAN, TERRAIN_INDUSTRIAL,
                             TERRAIN_DESERT, TERRAIN_ARCTIC, TERRAIN_WATER,
                             TERRAIN_COAST, TERRAIN_DEEP_WATER, TERRAIN_VOLCANIC)
from game.hex_grid import Hex, pixel_to_hex, hex_to_pixel, axial_to_offset, hex_range
from game.models import Campaign
from game.terrain import terrain_name
from game.campaign import (new_campaign, save_campaign, load_campaign, list_saves,
                            add_faction, add_unit, add_mission, next_turn, next_phase,
                            next_op_turn, get_operational_map, log_event, add_structure,
                            add_group, add_objective, log_combat,
                            walk_mp_to_strategic, walk_mp_to_op_range,
                            strategic_reachable, operational_reachable,
                            compute_daily_income)
from game.vision import visible_hexes, supplied_units, has_supply_sources, get_contact_hexes

from ui.colors import BG, TEXT, TEXT_BRIGHT, TEXT_DIM, PANEL_DARK, BTN_ACTIVE, BTN_HOVER, BTN_NORMAL, BORDER_LT, BORDER
from ui.renderer import MapRenderer, pixel_to_hierarchical, SUBHEX_ZOOM_THRESHOLD
from ui.chrome import (draw_toolbar, draw_sidebar, draw_statusbar,
                        TOOLBAR_H, STATUSBAR_H, SIDEBAR_W)
from ui.dialogs import (NewCampaignDialog, AddFactionDialog, AddUnitDialog,
                         AddMissionDialog, EditUnitDialog, LoadDialog,
                         ExportDialog, ConfirmDialog, ResolveMissionDialog,
                         AdjustFundsDialog, AddStructureDialog, HexNoteDialog,
                         AddGroupDialog, LogEngagementDialog,
                         AddObjectiveDialog, ResolveObjectiveDialog,
                         OperationalEngagementDialog, ScenarioSummaryDialog)
from ui.export import export_view


ZOOM_LEVELS = [8, 12, 18, 26, 38, 55, 80, 120, 180]


class App:
    def __init__(self, width: int = 1366, height: int = 820):
        pygame.init()
        pygame.display.set_caption("BattleTech PVP Campaign Manager")
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        self.clock  = pygame.time.Clock()
        self.width  = width
        self.height = height

        self.campaign: Optional[Campaign] = None

        # View state
        self.scale             = SCALE_STRATEGIC
        self.op_hex: Optional[Tuple[int, int]] = None
        self.zoom_idx          = 3
        self._pre_op_zoom_idx  = 3   # saved strategic zoom when drilling into operational
        self.pan_x             = 0.0
        self.pan_y             = 0.0

        # Interaction state
        self.tool          = "select"     # select, move, add_unit, add_mission, delete
        self.selected_hex: Optional[Tuple[int, int]] = None
        self.selected_unit_id: Optional[str] = None
        self.faction_filter: Optional[str]   = None
        self.move_source_unit: Optional[str] = None  # when using move tool
        self.deploy_unit_id:  Optional[str] = None  # reserve unit being deployed
        self.gm_force_move:   bool          = False  # bypass range/moved checks

        # Mouse pan
        self._drag_active        = False
        self._drag_start         = (0, 0)
        self._pan_start          = (0.0, 0.0)
        self._right_click_start: Optional[tuple] = None

        # Paint tool state
        self.paint_terrain   = "plains"
        self.paint_elevation = 5
        self._paint_dragging = False

        # Operational minigame state
        self.op_turn_moved: set = set()   # unit IDs that moved this op-turn
        self.op_engagement: dict = {}     # sub_pos → {"sub_pos","factions","turn_moved"}
        self.op_place_unit_id: Optional[str] = None   # unit awaiting sub-hex placement

        # Right-click context menu
        self._ctx_menu: Optional[dict] = None   # {pos, hex_pos, items: [(label,fn)]}

        # Keybinding help overlay
        self._show_help = False

        # Terrain palette hitboxes (rebuilt each frame when paint tool active)
        self._palette_boxes: list = []

        # Modal dialog
        self.dialog = None

        # Undo stack (session-only JSON snapshots, max 10)
        self._phase_undo_stack: list = []

        # Message toast
        self._toast      = ""
        self._toast_time = 0

        # Cached hitboxes for click dispatch
        self._toolbar_boxes: list = []
        self._sidebar_boxes: list = []

    # ── lifecycle ────────────────────────────────────────────────────────────

    def run(self) -> None:
        self._show_main_menu()
        while True:
            self._handle_events()
            self._draw()
            pygame.display.flip()
            self.clock.tick(60)

    def quit(self) -> None:
        pygame.quit()
        sys.exit(0)

    # ── helpers ──────────────────────────────────────────────────────────────

    @property
    def hex_size(self) -> float:
        return ZOOM_LEVELS[self.zoom_idx]

    def _toast_msg(self, text: str) -> None:
        self._toast = text
        self._toast_time = pygame.time.get_ticks()

    def _center_on(self, hex_pos: Tuple[int, int]) -> None:
        """Center the viewport on a given hex."""
        h = Hex.from_tuple(hex_pos)
        cx, cy = hex_to_pixel(h, self.hex_size, 0, 0)
        self.pan_x = (self.width - SIDEBAR_W) / 2 - cx
        self.pan_y = (self.height - TOOLBAR_H - STATUSBAR_H) / 2 - cy

    def _enter_operational(self, hex_pos: Tuple[int, int]) -> None:
        """Switch to operational scale for hex_pos, auto-zooming to fit the sub-map."""
        from game.constants import OPERATIONAL_RADIUS
        self._pre_op_zoom_idx = self.zoom_idx   # remember strategic zoom for return trip
        self.op_hex = hex_pos
        self.scale  = SCALE_OPERATIONAL
        # Pick the zoom level that best fits OPERATIONAL_RADIUS hexes in the viewport
        map_short = min(self.width - SIDEBAR_W, self.height - TOOLBAR_H - STATUSBAR_H)
        target = map_short * 0.72 / (OPERATIONAL_RADIUS * 3)
        self.zoom_idx = min(range(len(ZOOM_LEVELS)), key=lambda i: abs(ZOOM_LEVELS[i] - target))
        self.pan_x = (self.width - SIDEBAR_W) / 2
        self.pan_y = (self.height - TOOLBAR_H - STATUSBAR_H) / 2

    def _map_rect(self) -> pygame.Rect:
        return pygame.Rect(0, TOOLBAR_H,
                           self.width - SIDEBAR_W,
                           self.height - TOOLBAR_H - STATUSBAR_H)

    def _group_walk_mp(self, unit) -> int:
        """Return effective walk_mp — minimum across active ground members of unit's group.
        Aerospace and DropShips don't constrain formation ground speed.
        Falls back to DEFAULT_MOVE_RANGE when walk_mp is 0 (non-walking unit types)."""
        _GROUND = (UNIT_MECH, "Vehicle", "Infantry")
        def _effective(u) -> int:
            return u.walk_mp if u.walk_mp > 0 else DEFAULT_MOVE_RANGE.get(u.unit_type, 3)
        if not unit.group_id:
            return _effective(unit)
        members = [u for u in self.campaign.units.values()
                   if u.group_id == unit.group_id
                   and u.status not in (STATUS_DESTROYED, STATUS_RETREATED)
                   and u.unit_type in _GROUND]
        if not members:
            return _effective(unit)
        return min(_effective(u) for u in members)

    # ── main menu (blank state) ──────────────────────────────────────────────

    def _show_main_menu(self) -> None:
        # Nothing special; if no campaign is loaded, draw() shows a splash.
        pass

    # ── event handling ───────────────────────────────────────────────────────

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()

            elif event.type == pygame.VIDEORESIZE:
                self.width, self.height = event.w, event.h
                self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)

            # Dialog absorbs all input while open
            elif self.dialog is not None:
                self.dialog.handle_event(event)
                if self.dialog.done:
                    self._finish_dialog()

            elif self.campaign is None:
                # Only menu actions
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_menu_click(event.pos)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.quit()

            else:
                self._handle_game_event(event)

    def _handle_menu_click(self, pos: Tuple[int, int]) -> None:
        # Simple centered buttons in splash screen
        cx = self.width // 2
        cy = self.height // 2
        new_r  = pygame.Rect(cx - 110, cy - 20,  220, 44)
        load_r = pygame.Rect(cx - 110, cy + 36,  220, 44)
        quit_r = pygame.Rect(cx - 110, cy + 92,  220, 44)
        if new_r.collidepoint(pos):
            self.dialog = NewCampaignDialog((self.width, self.height))
        elif load_r.collidepoint(pos):
            saves = list_saves()
            if saves:
                self.dialog = LoadDialog((self.width, self.height), saves)
            else:
                self._toast_msg("No saves found in saves/")
        elif quit_r.collidepoint(pos):
            self.quit()

    def _handle_game_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._handle_key(event)
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Dismiss context menu on any click
            if self._ctx_menu is not None:
                for label, fn in self._ctx_menu.get("items", []):
                    r = self._ctx_menu.get("_rects", {}).get(label)
                    if r and r.collidepoint(event.pos):
                        fn()
                        self._ctx_menu = None
                        return
                self._ctx_menu = None
                return

            # Terrain / elevation palette clicks
            if self.tool == "paint_terrain":
                for pb in self._palette_boxes:
                    if pb.rect.collidepoint(event.pos):
                        self.paint_terrain = pb.data
                        self._toast_msg(f"Paint: {pb.data}")
                        return
            elif self.tool == "paint_elevation":
                for pb in self._palette_boxes:
                    if pb.rect.collidepoint(event.pos):
                        self.paint_elevation = pb.data
                        self._toast_msg(f"Elevation: {pb.data}")
                        return

            # Toolbar
            for box in self._toolbar_boxes:
                if box.rect.collidepoint(event.pos):
                    self._handle_toolbar(box.name)
                    return
            # Sidebar
            sx = self.width - SIDEBAR_W
            if event.pos[0] >= sx:
                for box in self._sidebar_boxes:
                    if box.rect.collidepoint(event.pos):
                        self._handle_sidebar(box)
                        return
                return
            # Map area
            if event.button == 1:
                self._paint_dragging = (self.tool in ("paint_terrain", "paint_elevation"))
                self._on_map_click(event.pos)
            elif event.button == 3:
                self._drag_active = True
                self._drag_start  = event.pos
                self._pan_start   = (self.pan_x, self.pan_y)
                self._right_click_start = event.pos
            elif event.button == 4:
                self._zoom(+1, event.pos)
            elif event.button == 5:
                self._zoom(-1, event.pos)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._paint_dragging = False
            elif event.button == 3:
                self._drag_active = False
                if self._right_click_start is not None:
                    dx = event.pos[0] - self._right_click_start[0]
                    dy = event.pos[1] - self._right_click_start[1]
                    if abs(dx) < 6 and abs(dy) < 6:
                        # Tiny movement — show context menu
                        self._show_context_menu(event.pos)
                self._right_click_start = None

        elif event.type == pygame.MOUSEMOTION:
            if self._drag_active:
                dx = event.pos[0] - self._drag_start[0]
                dy = event.pos[1] - self._drag_start[1]
                self.pan_x = self._pan_start[0] + dx
                self.pan_y = self._pan_start[1] + dy
            elif self._paint_dragging:
                rect = self._map_rect()
                if rect.collidepoint(event.pos):
                    self._on_map_click(event.pos)

    def _handle_key(self, event: pygame.event.Event) -> None:
        k = event.key
        step = 60
        if k == pygame.K_ESCAPE:
            self._show_help = False
            self._ctx_menu  = None
            if self.gm_force_move:
                self.gm_force_move    = False
                self.move_source_unit = None
                self._toast_msg("GM force-move cancelled")
            elif self.deploy_unit_id:
                self.deploy_unit_id = None
                self._toast_msg("Deploy cancelled")
            elif self.scale == SCALE_OPERATIONAL:
                self.scale = SCALE_STRATEGIC
                self.op_hex = None
            else:
                self.selected_hex = None
                self.selected_unit_id = None
                self.move_source_unit = None
        elif k in (pygame.K_LEFT,  pygame.K_a):
            self.pan_x += step
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.pan_x -= step
        elif k in (pygame.K_UP,    pygame.K_w):
            self.pan_y += step
        elif k in (pygame.K_DOWN,  pygame.K_s):
            self.pan_y -= step
        elif k in (pygame.K_PLUS, pygame.K_EQUALS):
            self._zoom(+1, (self.width // 2, self.height // 2))
        elif k == pygame.K_MINUS:
            self._zoom(-1, (self.width // 2, self.height // 2))
        elif k == pygame.K_n:
            self._handle_toolbar("next_turn")
        elif k == pygame.K_z and (event.mod & pygame.KMOD_CTRL):
            self._handle_toolbar("revert_phase")
        elif k == pygame.K_s and (event.mod & pygame.KMOD_CTRL):
            self._handle_toolbar("save")
        elif event.unicode == "?":
            self._show_help = not self._show_help

    def _zoom(self, delta: int, around: Tuple[int, int]) -> None:
        old_size = self.hex_size
        new_idx  = max(0, min(len(ZOOM_LEVELS) - 1, self.zoom_idx + delta))
        if new_idx == self.zoom_idx:
            return
        # Keep hex under cursor at the same screen position
        rect = self._map_rect()
        mx, my = around[0] - rect.x, around[1] - rect.y
        scale = ZOOM_LEVELS[new_idx] / old_size
        self.pan_x = mx - (mx - self.pan_x) * scale
        self.pan_y = my - (my - self.pan_y) * scale
        self.zoom_idx = new_idx

    # ── map click ────────────────────────────────────────────────────────────

    def _on_map_click(self, pos: Tuple[int, int]) -> None:
        rect   = self._map_rect()
        ox, oy = rect.x + self.pan_x, rect.y + self.pan_y

        # Capture all three levels when zoomed in enough
        strat, sub, tac = pixel_to_hierarchical(pos[0], pos[1], self.hex_size, ox, oy)
        coord  = strat.to_tuple()

        tmap = self._current_terrain_map()
        if coord not in tmap:
            return

        # Operational placement mode: place an unpositioned unit on a sub-hex
        if self.op_place_unit_id and self.scale == SCALE_OPERATIONAL:
            u = self.campaign.units.get(self.op_place_unit_id)
            if u:
                u.sub_position = coord
                if u.status == STATUS_RESERVE:
                    u.status = STATUS_ACTIVE
                self._toast_msg(f"Placed {u.name} at {coord}")
            self.op_place_unit_id = None
            return

        # Deploy mode: place a reserve unit on the clicked hex
        if self.deploy_unit_id:
            u = self.campaign.units.get(self.deploy_unit_id)
            if u:
                u.position     = coord
                u.sub_position = sub if sub else None
                u.has_moved    = True
                if u.status == STATUS_RESERVE:
                    u.status = STATUS_ACTIVE
                log_event(self.campaign, "unit_deployed",
                          f"{u.name} deployed to ({coord[0]},{coord[1]})")
                self.selected_unit_id = u.id
                self.selected_hex     = coord
                self._toast_msg(f"Deployed {u.name} to ({coord[0]},{coord[1]})")
            self.deploy_unit_id = None
            return

        if self.tool == "select":
            self.selected_hex     = coord
            hex_units = [u for u in self.campaign.units.values() if u.position == coord] \
                        if self.scale == SCALE_STRATEGIC else []
            self.selected_unit_id = hex_units[0].id if hex_units else None

        elif self.tool == "move":
            if self.scale == SCALE_OPERATIONAL:
                # Operational move: pick unit by sub_position, then set destination sub_position
                if self.move_source_unit is None:
                    op_units = [u for u in self.campaign.units.values()
                                if u.position == self.op_hex and u.sub_position == coord
                                and u.status not in (STATUS_DESTROYED, STATUS_RETREATED)]
                    if not op_units:
                        op_units = [u for u in self.campaign.units.values()
                                    if u.position == self.op_hex
                                    and u.status not in (STATUS_DESTROYED, STATUS_RETREATED)]
                    if op_units:
                        # Filter to active faction if possible
                        af_idx = self.campaign.active_faction_idx % max(1, len(self.campaign.factions))
                        af_id  = list(self.campaign.factions.keys())[af_idx] if self.campaign.factions else None
                        af_units = [u for u in op_units if u.faction_id == af_id] if af_id else []
                        chosen = (af_units or op_units)[0]
                        # Check move limit: per-engagement tracker or global op_turn_moved
                        eng = self._unit_engagement(chosen)
                        moved_set = eng["turn_moved"] if eng else self.op_turn_moved
                        if chosen.id in moved_set and not self.gm_force_move:
                            ctx = "positioning turn" if eng else "op-turn"
                            self._toast_msg(f"{chosen.name} already moved this {ctx}")
                            return
                        self.move_source_unit = chosen.id
                        self.selected_unit_id = chosen.id
                        self._toast_msg(f"Op-move {chosen.name}: click destination")
                else:
                    u = self.campaign.units.get(self.move_source_unit)
                    if u is not None:
                        dest_sub = sub if sub is not None else coord
                        u.sub_position = dest_sub
                        if not self.gm_force_move:
                            # Track in destination engagement if one exists there,
                            # otherwise fall back to the source engagement or op_turn_moved
                            dest_eng = self.op_engagement.get(dest_sub)
                            src_eng  = self._unit_engagement(u) if u.sub_position else None
                            if dest_eng:
                                dest_eng["turn_moved"].add(u.id)
                            elif src_eng:
                                src_eng["turn_moved"].add(u.id)
                            else:
                                self.op_turn_moved.add(u.id)
                        self._toast_msg(f"Moved {u.name} to sub {dest_sub}")
                        log_event(self.campaign, "unit_moved",
                                  f"{u.name} op-move to sub({dest_sub[0]},{dest_sub[1]})")
                        # Check for contact at destination
                        self._check_op_contact(dest_sub)
                    self.move_source_unit = None
                    self.gm_force_move    = False
            else:
                if self.move_source_unit is None:
                    hex_units = [u for u in self.campaign.units.values() if u.position == coord]
                    if hex_units:
                        u = hex_units[0]
                        if u.has_moved:
                            self._toast_msg(f"{u.name} already moved this phase")
                            return
                        self.move_source_unit = u.id
                        self.selected_unit_id = u.id
                        self._toast_msg(f"Move {u.name}: click destination")
                else:
                    u = self.campaign.units.get(self.move_source_unit)
                    if u is not None:
                        u.position     = coord
                        u.sub_position = sub
                        u.tac_position = tac
                        if not self.gm_force_move:
                            u.has_moved = True
                        detail = _fmt_coord(coord, sub, tac)
                        gm_tag = " [GM]" if self.gm_force_move else ""
                        self._toast_msg(f"Moved {u.name} to {detail}{gm_tag}")
                        log_event(self.campaign, "unit_moved",
                                  f"{u.name} moved to ({coord[0]},{coord[1]}){gm_tag}")
                    self.move_source_unit = None
                    self.gm_force_move    = False

        elif self.tool == "add_unit":
            if not self.campaign.factions:
                self._toast_msg("Add a faction first (+Faction).")
                return
            faction_list = [(f.name, f.id) for f in self.campaign.factions.values()]
            d = AddUnitDialog((self.width, self.height), faction_list, coord)
            d._sub_pos = sub   # type: ignore[attr-defined]
            d._tac_pos = tac   # type: ignore[attr-defined]
            self.dialog = d

        elif self.tool == "add_mission":
            self.dialog = AddMissionDialog((self.width, self.height), coord)

        elif self.tool == "add_structure":
            if self.scale != SCALE_STRATEGIC:
                return
            self.dialog = AddStructureDialog(
                (self.width, self.height), coord, self.campaign.factions)

        elif self.tool == "add_objective":
            if self.scale != SCALE_STRATEGIC:
                return
            self.dialog = AddObjectiveDialog((self.width, self.height), coord)

        elif self.tool == "delete":
            if self.scale != SCALE_STRATEGIC:
                return
            to_del = [uid for uid, u in self.campaign.units.items() if u.position == coord]
            if to_del:
                for uid in to_del:
                    del self.campaign.units[uid]
                self._toast_msg(f"Deleted {len(to_del)} unit(s)")

        elif self.tool == "paint_terrain":
            tmap = self._current_terrain_map()
            if coord in tmap:
                tmap[coord] = self.paint_terrain
                key = f"{coord[0]},{coord[1]}"
                self.campaign.op_maps.pop(key, None)
            return  # don't update selected_hex while painting

        elif self.tool == "paint_elevation":
            if self.scale == SCALE_STRATEGIC and coord in self.campaign.terrain_map:
                self.campaign.elevation_map[coord] = self.paint_elevation
            return

        self.selected_hex = coord

    def _check_op_contact(self, sub_pos: tuple) -> None:
        """Add an engagement entry when opposing factions share sub_pos."""
        if not self.op_hex or not self.campaign:
            return
        if sub_pos in self.op_engagement:
            return  # already tracking this contact point
        by_faction: dict = {}
        for uid, u in self.campaign.units.items():
            if (u.position == self.op_hex and u.sub_position == sub_pos
                    and u.status not in (STATUS_DESTROYED, STATUS_RETREATED)):
                by_faction.setdefault(u.faction_id, []).append(u)
        if len(by_faction) >= 2:
            fac_ids = list(by_faction.keys())
            self.op_engagement[sub_pos] = {
                "sub_pos":    sub_pos,
                "factions":   fac_ids,
                "turn_moved": set(),
            }
            names = [self.campaign.factions[f].name if f in self.campaign.factions else f
                     for f in fac_ids[:2]]
            n = len(self.op_engagement)
            self._toast_msg(f"Contact! {' vs '.join(names)} at sub{sub_pos} "
                            f"({n} engagement{'s' if n > 1 else ''} active)")
            log_event(self.campaign, "op_contact",
                      f"Engagement: {' vs '.join(names)} at sub{sub_pos}")

    def _unit_engagement(self, unit) -> Optional[dict]:
        """Return the engagement entry for a unit's sub_position, or None."""
        if unit.sub_position:
            return self.op_engagement.get(unit.sub_position)
        return None

    def _current_terrain_map(self) -> dict:
        if self.scale == SCALE_OPERATIONAL and self.op_hex is not None:
            return get_operational_map(self.campaign, self.op_hex)
        return self.campaign.terrain_map

    # ── toolbar / sidebar dispatch ───────────────────────────────────────────

    def _handle_toolbar(self, name: str) -> None:
        if name == "new":
            self.dialog = NewCampaignDialog((self.width, self.height))
        elif name == "load":
            saves = list_saves()
            if saves:
                self.dialog = LoadDialog((self.width, self.height), saves)
            else:
                self._toast_msg("No saves found")
        elif name == "save":
            if self.campaign:
                path = save_campaign(self.campaign)
                self._toast_msg(f"Saved: {path.name}")
        elif name == "export":
            if self.campaign:
                factions = list(self.campaign.factions.values())
                self.dialog = ExportDialog((self.width, self.height), factions)
        elif name == "next_turn":
            if self.campaign:
                snap = json.dumps(self.campaign.to_dict())
                self._phase_undo_stack.append(snap)
                if len(self._phase_undo_stack) > 10:
                    self._phase_undo_stack.pop(0)
                if self.scale == SCALE_OPERATIONAL:
                    day, phase, op_t = next_op_turn(self.campaign)
                    abbr = {"morning": "AM", "afternoon": "PM", "night": "**"}.get(phase, phase)
                    self._toast_msg(f"Hour {op_t+1}/{OP_TURNS_PER_PHASE} — Day {day} {abbr}")
                    self.op_turn_moved.clear()
                    for eng in self.op_engagement.values():
                        eng["turn_moved"] = set()
                    # Advance active faction so the other side moves next op-turn
                    if self.campaign.factions:
                        n = len(self.campaign.factions)
                        self.campaign.active_faction_idx = (self.campaign.active_faction_idx + 1) % n
                else:
                    day, phase = next_phase(self.campaign)
                    abbr = {"morning": "AM", "afternoon": "PM", "night": "**"}.get(phase, phase)
                    self._toast_msg(f"Day {day} · {abbr}")
                from game.campaign import SAVES_DIR
                save_campaign(self.campaign, SAVES_DIR / "autosave.json")
        elif name == "revert_phase":
            if self.campaign and self._phase_undo_stack:
                snap = self._phase_undo_stack.pop()
                self.campaign = Campaign.from_dict(json.loads(snap))
                self._toast_msg("Reverted to previous phase")
        elif name == "add_faction":
            self.dialog = AddFactionDialog((self.width, self.height))
        elif name == "add_group":
            if not self.campaign.factions:
                self._toast_msg("Add a faction first.")
                return
            self.dialog = AddGroupDialog((self.width, self.height), self.campaign.factions)
        elif name.startswith("tool_"):
            self.tool = name[5:]
            self.move_source_unit = None
        elif name == "view_strategic":
            self.zoom_idx = self._pre_op_zoom_idx   # restore zoom from before drill-down
            if self.op_hex:
                self._center_on(self.op_hex)
            self.scale  = SCALE_STRATEGIC
            self.op_hex = None
        elif name == "view_operational":
            if self.selected_hex and self.scale == SCALE_STRATEGIC:
                self._enter_operational(self.selected_hex)
                self._toast_msg(f"Drill-down into {self.selected_hex}")
            else:
                self._toast_msg("Select a strategic hex first")

    def _handle_sidebar(self, box) -> None:
        if box.name == "faction":
            self.faction_filter = None if self.faction_filter == box.data else box.data
        elif box.name == "unit":
            self.selected_unit_id = box.data
            u = self.campaign.units.get(box.data)
            if u and u.position:
                self._center_on(u.position)
        elif box.name == "mission":
            m = self.campaign.missions.get(box.data)
            if m:
                self.dialog = ResolveMissionDialog(
                    (self.width, self.height), m, self.campaign.factions)
        elif box.name == "edit_unit":
            u = self.campaign.units.get(box.data)
            if u:
                self.dialog = EditUnitDialog((self.width, self.height), u,
                                             self.campaign.groups)
        elif box.name == "delete_unit":
            self.dialog = ConfirmDialog((self.width, self.height), "Delete this unit?")
            self.dialog._delete_unit_id = box.data  # type: ignore[attr-defined]
        elif box.name == "adjust_funds":
            f = self.campaign.factions.get(box.data)
            if f:
                self.dialog = AdjustFundsDialog((self.width, self.height), f.name, f.resources)
                self.dialog._faction_id = box.data  # type: ignore[attr-defined]
        elif box.name == "group":
            g = self.campaign.groups.get(box.data)
            if g:
                self._toast_msg(f"Group: {g.name}")
        elif box.name == "objective":
            o = self.campaign.objectives.get(box.data)
            if o:
                self.dialog = ResolveObjectiveDialog(
                    (self.width, self.height), o, self.campaign.factions)
        elif box.name == "log_combat":
            if self.campaign.factions:
                pos = self.selected_hex or (0, 0)
                self.dialog = LogEngagementDialog(
                    (self.width, self.height), pos, self.campaign.factions)
            else:
                self._toast_msg("Add factions first.")
        elif box.name == "structure":
            s = self.campaign.structures.get(box.data)
            if s:
                self._toast_msg(f"Structure: {s.name} ({s.structure_type})")
        elif box.name == "delete_structure":
            self.dialog = ConfirmDialog((self.width, self.height), "Delete this structure?")
            self.dialog._delete_struct_id = box.data  # type: ignore[attr-defined]
        elif box.name == "edit_note":
            note_key = box.data
            existing = self.campaign.hex_notes.get(note_key, "")
            try:
                q, r = (int(x) for x in note_key.split(","))
            except ValueError:
                return
            self.dialog = HexNoteDialog((self.width, self.height), (q, r), existing)
        elif box.name == "contact_hex":
            pos = box.data
            self.selected_hex = pos
            if self.scale == SCALE_STRATEGIC:
                self._enter_operational(pos)
                self._toast_msg(f"Contact! Drilling into hex ({pos[0]},{pos[1]})")
        elif box.name == "engage_next_turn":
            sp = box.data
            if sp in self.op_engagement:
                self.op_engagement[sp]["turn_moved"] = set()
                self._toast_msg(f"Positioning turn reset for sub{sp} — maneuver again")
        elif box.name == "engage_commit":
            sp = box.data
            if sp in self.op_engagement:
                eng = self.op_engagement[sp]
                self.dialog = ScenarioSummaryDialog(
                    (self.width, self.height),
                    sp, self.op_hex, self.campaign, eng["factions"],
                )
        elif box.name == "reset_all_moves":
            for u in self.campaign.units.values():
                u.has_moved = False
            self._toast_msg("All unit moves reset")
        elif box.name == "reset_move":
            u = self.campaign.units.get(box.data)
            if u:
                u.has_moved = False
                self._toast_msg(f"{u.name} move reset by GM")
        elif box.name == "force_move_unit":
            u = self.campaign.units.get(box.data)
            if u:
                self.move_source_unit = u.id
                self.gm_force_move    = True
                self._toast_msg(f"GM: move {u.name} anywhere — click destination")
        elif box.name == "land_unit":
            u = self.campaign.units.get(box.data)
            if u:
                self.deploy_unit_id = box.data
                self._toast_msg(f"Land {u.name} — click a hex to place")
        elif box.name == "end_turn":
            factions = list(self.campaign.factions.values())
            if factions:
                self.campaign.active_faction_idx = (
                    self.campaign.active_faction_idx + 1) % len(factions)
                nf = factions[self.campaign.active_faction_idx]
                self._toast_msg(f"{nf.name}'s turn")
        elif box.name in ("reserve_unit", "orbit_unit"):
            self.selected_unit_id = box.data
        elif box.name == "deploy_unit":
            u = self.campaign.units.get(box.data)
            if u:
                self.deploy_unit_id = box.data
                self._toast_msg(f"Deploy {u.name} — click a hex to place")
        elif box.name == "op_place_unit":
            if self.op_place_unit_id == box.data:
                self.op_place_unit_id = None   # toggle off
            else:
                self.op_place_unit_id = box.data
                u = self.campaign.units.get(box.data)
                name = u.name if u else box.data
                self._toast_msg(f"Click the map to place {name}")
        elif box.name == "pay_repair":
            u = self.campaign.units.get(box.data)
            if u:
                f = self.campaign.factions.get(u.faction_id)
                if f and f.resources >= u.repair_cost:
                    f.resources -= u.repair_cost
                    u.status = "active"
                    log_event(self.campaign, "unit_repaired",
                              f"{u.name} repaired ({u.repair_cost:,} C-Bills)")
                    self._toast_msg(f"{u.name} repaired — {u.repair_cost:,} C-Bills deducted")
                    u.repair_cost = 0
                elif f:
                    self._toast_msg(f"Insufficient funds: need {u.repair_cost:,}, have {f.resources:,}")

    # ── dialog completion ────────────────────────────────────────────────────

    def _finish_dialog(self) -> None:
        d = self.dialog
        self.dialog = None
        if d is None or d.result is None:
            return

        if isinstance(d, NewCampaignDialog):
            r = d.result
            self.campaign = new_campaign(r["name"], r["width"], r["height"],
                                          r["seed"], r["water"])
            self._phase_undo_stack.clear()
            self._center_on((r["width"] // 2, r["height"] // 2))
            self._toast_msg(f"Created '{r['name']}' (seed {self.campaign.map_seed})")

        elif isinstance(d, LoadDialog):
            self.campaign = load_campaign(d.result)
            self._phase_undo_stack.clear()
            self._center_on((self.campaign.map_width // 2, self.campaign.map_height // 2))
            self._toast_msg(f"Loaded: {d.result.name}")

        elif isinstance(d, AddFactionDialog):
            r = d.result
            f = add_faction(self.campaign, r["name"], r["color"], r["player"])
            self._toast_msg(f"Added faction: {f.name}")

        elif isinstance(d, AddUnitDialog):
            r = d.result
            u = add_unit(self.campaign, r["name"], r["faction_id"], r["unit_type"],
                         position=r["position"], vision_range=r["vision"])
            u.notes        = r.get("notes", "")
            u.walk_mp      = r.get("walk_mp",      4)
            u.run_mp       = r.get("run_mp",       6)
            u.battle_value = r.get("battle_value", 0)
            u.sub_position = getattr(d, "_sub_pos", None)
            u.tac_position = getattr(d, "_tac_pos", None)
            self.selected_unit_id = u.id
            self._toast_msg(f"Added unit: {u.name} at {_fmt_coord(u.position, u.sub_position, u.tac_position)}")

        elif isinstance(d, AddMissionDialog):
            r = d.result
            m = add_mission(self.campaign, r["name"], r["mission_type"], r["position"])
            m.notes = r.get("notes", "")
            self._toast_msg(f"Placed mission: {m.name}")

        elif isinstance(d, EditUnitDialog):
            self._toast_msg("Unit updated")

        elif isinstance(d, ResolveMissionDialog):
            r = d.result
            m = d.mission
            m.status                 = r["status"]
            m.rewards                = r["rewards"]
            m.notes                  = r["notes"]
            m.participating_factions = r["participating_factions"]
            log_event(self.campaign, "mission_resolved",
                      f"'{m.name}' -> {m.status}")
            self._toast_msg(f"Mission '{m.name}' updated: {m.status}")

        elif isinstance(d, AdjustFundsDialog):
            fid = getattr(d, "_faction_id", None)
            f   = self.campaign.factions.get(fid) if fid else None
            if f:
                r = d.result
                f.resources += r["delta"]
                verb   = "added to" if r["delta"] >= 0 else "deducted from"
                reason = f" ({r['reason']})" if r["reason"] else ""
                log_event(self.campaign, "funds_adjusted",
                          f"{abs(r['delta']):,} C-Bills {verb} {f.name}{reason}")
                self._toast_msg(f"{f.name}: {f.resources:,} C-Bills")

        elif isinstance(d, AddGroupDialog):
            r = d.result
            g = add_group(self.campaign, r["name"], r["faction_id"])
            g.notes = r.get("notes", "")
            self._toast_msg(f"Group added: {g.name}")

        elif isinstance(d, LogEngagementDialog):
            r = d.result
            log_combat(self.campaign, r["position"], r["attacker_fid"], r["defender_fid"],
                       r["outcome"], r["casualties"], r["notes"])
            self._toast_msg(f"Combat logged: {r['outcome']}")
            sp = getattr(d, "_from_engagement_sp", None)
            if sp is not None:
                self.op_engagement.pop(sp, None)

        elif isinstance(d, ScenarioSummaryDialog):
            sp = getattr(d, "_sub_pos", None)
            if d.result and d.result.get("action") == "log":
                pos = sp or self.op_hex or (0, 0)
                dlg = LogEngagementDialog(
                    (self.width, self.height), pos, self.campaign.factions)
                dlg._from_engagement_sp = sp  # type: ignore[attr-defined]
                self.dialog = dlg
            else:
                self.op_engagement.pop(sp, None)

        elif isinstance(d, AddObjectiveDialog):
            r = d.result
            o = add_objective(self.campaign, r["name"], r["position"], r["vp_value"])
            o.notes = r.get("notes", "")
            self._toast_msg(f"Objective placed: {o.name} ({o.vp_value} VP)")

        elif isinstance(d, ResolveObjectiveDialog):
            r = d.result
            o = d.objective
            o.status     = r["status"]
            o.faction_id = r["faction_id"]
            o.notes      = r["notes"]
            log_event(self.campaign, "objective_resolved",
                      f"'{o.name}' -> {o.status}")
            self._toast_msg(f"Objective '{o.name}' updated")

        elif isinstance(d, AddStructureDialog):
            r = d.result
            s = add_structure(self.campaign, r["name"], r["structure_type"],
                              r["position"], r["faction_id"], r["supply_range"])
            s.notes = r.get("notes", "")
            self._toast_msg(f"Placed: {s.name}")

        elif isinstance(d, HexNoteDialog):
            r = d.result
            key = f"{r['position'][0]},{r['position'][1]}"
            if r["text"]:
                self.campaign.hex_notes[key] = r["text"]
            else:
                self.campaign.hex_notes.pop(key, None)
            self._toast_msg("Note saved." if r["text"] else "Note cleared.")

        elif isinstance(d, ExportDialog):
            r = d.result
            path = export_view(self.campaign, r["faction_id"], r["width"], r["height"])
            self._toast_msg(f"Exported: {path.name}")

        elif isinstance(d, ConfirmDialog):
            uid = getattr(d, "_delete_unit_id", None)
            if d.result and uid and uid in self.campaign.units:
                unit_name = self.campaign.units[uid].name
                del self.campaign.units[uid]
                log_event(self.campaign, "unit_deleted", f"Unit deleted: {unit_name}")
                if self.selected_unit_id == uid:
                    self.selected_unit_id = None
                self._toast_msg("Unit deleted")
            sid = getattr(d, "_delete_struct_id", None)
            if d.result and sid and sid in self.campaign.structures:
                s = self.campaign.structures.pop(sid)
                log_event(self.campaign, "structure_deleted", f"Structure deleted: {s.name}")
                self._toast_msg(f"Deleted: {s.name}")

        elif isinstance(d, OperationalEngagementDialog):
            r = d.result
            if r is None:
                return
            if r["action"] == "fight_manually":
                # Re-open the manual log dialog so the GM can record the result
                self.dialog = LogEngagementDialog(
                    (self.width, self.height),
                    r.get("sub_pos", self.op_hex or (0, 0)),
                    self.campaign.factions,
                )
                return
            # Auto-resolved: apply casualties
            destroyed, retreated, crippled = [], [], []
            for uid, new_status in r.get("casualties", []):
                u = self.campaign.units.get(uid)
                if u:
                    u.status = new_status
                    if new_status == STATUS_RETREATED:
                        retreated.append(u.name)
                    elif new_status == STATUS_DESTROYED:
                        destroyed.append(u.name)
                    else:
                        crippled.append(u.name)
            log_combat(
                self.campaign,
                self.op_hex or (0, 0),
                r["fac_a_id"], r["fac_b_id"],
                r["outcome"],
                r.get("casualty_text", ""),
                "",
            )
            parts = []
            if destroyed: parts.append(f"Destroyed: {', '.join(destroyed)}")
            if retreated: parts.append(f"Retreated: {', '.join(retreated)}")
            if crippled:  parts.append(f"Crippled: {', '.join(crippled)}")
            self._toast_msg(f"Engagement resolved — {'; '.join(parts) if parts else 'No casualties'}")

    # ── drawing ──────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.screen.fill(BG)
        if self.campaign is None:
            self._draw_splash()
        else:
            self._draw_game()
        self._draw_toast()
        if self.dialog:
            self.dialog.draw(self.screen)

    def _draw_splash(self) -> None:
        font_t = pygame.font.SysFont("monospace", 34, bold=True)
        font_s = pygame.font.SysFont("monospace", 16)
        title  = font_t.render("BattleTech PVP Campaign Manager", True, TEXT_BRIGHT)
        sub    = font_s.render("GM tool — double-blind strategic map", True, TEXT_DIM)
        self.screen.blit(title, title.get_rect(center=(self.width // 2, self.height // 2 - 100)))
        self.screen.blit(sub,   sub.get_rect(center=(self.width // 2, self.height // 2 - 60)))

        cx, cy = self.width // 2, self.height // 2
        for label, rect in (
            ("New Campaign", pygame.Rect(cx - 110, cy - 20, 220, 44)),
            ("Load Campaign", pygame.Rect(cx - 110, cy + 36, 220, 44)),
            ("Quit",          pygame.Rect(cx - 110, cy + 92, 220, 44)),
        ):
            hover = rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(self.screen, BTN_HOVER if hover else BTN_NORMAL, rect, border_radius=5)
            pygame.draw.rect(self.screen, BORDER_LT, rect, 1, border_radius=5)
            lbl = font_s.render(label, True, TEXT)
            self.screen.blit(lbl, lbl.get_rect(center=rect.center))

    def _draw_game(self) -> None:
        mouse_pos = pygame.mouse.get_pos()

        # Toolbar
        self._toolbar_boxes = draw_toolbar(
            self.screen, self.width, self.tool, self.scale,
            self.campaign.current_turn, self.campaign.name, mouse_pos,
            phase=self.campaign.current_phase,
            has_undo=bool(self._phase_undo_stack),
            op_turn=self.campaign.op_turn,
        )

        # Map
        rect = self._map_rect()
        hover_hex = None
        if rect.collidepoint(mouse_pos):
            h = pixel_to_hex(mouse_pos[0], mouse_pos[1], self.hex_size,
                             rect.x + self.pan_x, rect.y + self.pan_y)
            tmap = self._current_terrain_map()
            if h.to_tuple() in tmap:
                hover_hex = h.to_tuple()

        # Fog set if a faction filter is active (GM peeks at player view).
        # Only applies at strategic scale — operational sub-hexes use a different
        # coordinate space and all units in the op-hex can see the whole sub-map.
        fog_set = None
        if self.faction_filter is not None and self.scale == SCALE_STRATEGIC:
            fog_set = visible_hexes(self.campaign, self.faction_filter)

        # Movement range highlight when a source unit is selected in move mode
        highlight_hexes = None
        highlight_color = (80, 160, 255)   # default blue
        if self.tool == "move" and self.move_source_unit:
            u = self.campaign.units.get(self.move_source_unit)
            if u:
                if self.gm_force_move:
                    # GM override: highlight entire map in orange
                    highlight_hexes = set(self._current_terrain_map().keys())
                    highlight_color = (255, 140, 40)
                else:
                    eff_walk = self._group_walk_mp(u)
                    if self.scale == SCALE_STRATEGIC and u.position is not None:
                        highlight_hexes = strategic_reachable(
                            self.campaign, u.position, eff_walk, u.unit_type
                        )
                    elif self.scale == SCALE_OPERATIONAL and u.sub_position is not None:
                        op_range = walk_mp_to_op_range(eff_walk)
                        if u.sub_position in self.op_engagement:
                            op_range = max(1, op_range // 2)   # tighter range during engagement
                            highlight_color = (255, 160, 60)   # amber = tactical positioning
                        highlight_hexes = operational_reachable(
                            self.campaign, self.op_hex, u.sub_position,
                            op_range, u.unit_type
                        )

        # Vision highlight: selected unit in select tool shows its LOS in green
        if (highlight_hexes is None
                and self.tool == "select"
                and self.selected_unit_id
                and self.scale == SCALE_STRATEGIC):
            u = self.campaign.units.get(self.selected_unit_id)
            if u and u.position:
                from game.vision import unit_visible_hexes
                highlight_hexes = unit_visible_hexes(self.campaign, u)
                highlight_color = (60, 210, 100)

        # Supply indicators: orange ring on units out of supply range
        supply_set = None
        if self.scale == SCALE_STRATEGIC and self.campaign.factions:
            if any(has_supply_sources(self.campaign, fid)
                   for fid in self.campaign.factions):
                supply_set = set()
                for fid in self.campaign.factions:
                    supply_set.update(supplied_units(self.campaign, fid))

        # Contact hexes for red-border overlay and sidebar alert
        contact_hexes = (get_contact_hexes(self.campaign)
                         if self.scale == SCALE_STRATEGIC else None)

        engagement_sub = set(self.op_engagement.keys()) if self.op_engagement else None

        renderer = MapRenderer(
            surface         = self.screen,
            rect            = rect,
            campaign        = self.campaign,
            hex_size        = self.hex_size,
            pan             = (self.pan_x, self.pan_y),
            scale           = self.scale,
            op_hex          = self.op_hex,
            fog_set         = fog_set,
            hover_hex       = hover_hex,
            selected        = self.selected_hex,
            highlight_hexes  = highlight_hexes,
            highlight_color  = highlight_color,
            supply_set       = supply_set,
            contact_hexes    = contact_hexes,
            engagement_hexes = engagement_sub,
        )
        renderer.draw()

        # Hover tooltip — unit names above cursor
        if hover_hex and self.scale == SCALE_STRATEGIC:
            tip_units = [u for u in self.campaign.units.values()
                         if u.position == hover_hex
                         and (fog_set is None or hover_hex in fog_set)]
            if tip_units:
                self._draw_hover_tooltip(mouse_pos, tip_units)

        # Sidebar
        self._sidebar_boxes = draw_sidebar(
            self.screen, self.width - SIDEBAR_W, TOOLBAR_H,
            SIDEBAR_W, self.height - TOOLBAR_H - STATUSBAR_H,
            self.campaign, self.selected_hex, self.selected_unit_id,
            self.faction_filter, mouse_pos, self.scale, self.op_hex,
            op_turn_moved=self.op_turn_moved,
            op_engagement=self.op_engagement if self.op_engagement else None,
            op_place_unit_id=self.op_place_unit_id,
            fog_set=fog_set,
        )

        # Statusbar
        tname = ""
        if hover_hex:
            tmap = self._current_terrain_map()
            tname = terrain_name(tmap.get(hover_hex, ""))
        draw_statusbar(
            self.screen, 0, self.height - STATUSBAR_H, self.width,
            hover_hex, tname, self.hex_size, self.scale, self.op_hex, self.tool,
        )

        # Terrain / elevation palette (above statusbar, only when paint tool active)
        if self.tool == "paint_terrain":
            self._draw_terrain_palette()
        elif self.tool == "paint_elevation":
            self._draw_elevation_palette()

        # Overlays (drawn last, on top of everything)
        if self._ctx_menu:
            self._draw_context_menu()
        if self._show_help:
            self._draw_help_overlay()
        if self.deploy_unit_id:
            self._draw_deploy_banner()
        if self.gm_force_move:
            self._draw_gm_move_banner()

    def _draw_deploy_banner(self) -> None:
        u = self.campaign.units.get(self.deploy_unit_id) if self.deploy_unit_id else None
        if not u:
            return
        font = pygame.font.SysFont("monospace", 13, bold=True)
        text = f"DEPLOY  {u.name}  —  click a hex to place   [Esc] to cancel"
        tw, th = font.size(text)
        map_r = self._map_rect()
        bw = tw + 24
        bx = map_r.x + (map_r.width - bw) // 2
        by = map_r.y + 10
        bg = pygame.Surface((bw, th + 10), pygame.SRCALPHA)
        bg.fill((20, 80, 20, 220))
        self.screen.blit(bg, (bx, by))
        pygame.draw.rect(self.screen, (80, 200, 80),
                         pygame.Rect(bx, by, bw, th + 10), 1, border_radius=4)
        self.screen.blit(font.render(text, True, (180, 255, 180)), (bx + 12, by + 5))

    def _draw_gm_move_banner(self) -> None:
        u = self.campaign.units.get(self.move_source_unit) if self.move_source_unit else None
        if not u:
            return
        font = pygame.font.SysFont("monospace", 13, bold=True)
        text = f"GM MOVE  {u.name}  —  click any hex   [Esc] to cancel"
        tw, th = font.size(text)
        map_r = self._map_rect()
        bw = tw + 24
        bx = map_r.x + (map_r.width - bw) // 2
        by = map_r.y + 10
        bg = pygame.Surface((bw, th + 10), pygame.SRCALPHA)
        bg.fill((80, 40, 0, 220))
        self.screen.blit(bg, (bx, by))
        pygame.draw.rect(self.screen, (255, 140, 40),
                         pygame.Rect(bx, by, bw, th + 10), 1, border_radius=4)
        self.screen.blit(font.render(text, True, (255, 200, 120)), (bx + 12, by + 5))

    def _draw_hover_tooltip(self, pos: Tuple[int, int], units: list) -> None:
        font = pygame.font.SysFont("monospace", 11, bold=True)
        lines = []
        for u in units[:5]:
            f = self.campaign.factions.get(u.faction_id)
            fname = f.name[:10] if f else "?"
            lines.append((f"{u.name[:16]} [{u.unit_type[:4]}]", f.color if f else (150, 150, 150)))
        if not lines:
            return
        pad, lh = 6, 14
        w = max(font.size(t)[0] for t, _ in lines) + pad * 2
        h = len(lines) * lh + pad
        tx = min(pos[0] + 14, self.width - w - 4)
        ty = max(pos[1] - h - 8, TOOLBAR_H + 4)
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((15, 15, 25, 210))
        self.screen.blit(bg, (tx, ty))
        pygame.draw.rect(self.screen, (80, 80, 100), pygame.Rect(tx, ty, w, h), 1, border_radius=3)
        for i, (text, color) in enumerate(lines):
            surf = font.render(text, True, color)
            self.screen.blit(surf, (tx + pad, ty + pad // 2 + i * lh))

    # ── context menu ─────────────────────────────────────────────────────────

    def _show_context_menu(self, pos: Tuple[int, int]) -> None:
        """Build a context menu for the hex under the cursor."""
        rect   = self._map_rect()
        if not rect.collidepoint(pos):
            return
        ox, oy = rect.x + self.pan_x, rect.y + self.pan_y
        h = pixel_to_hex(pos[0], pos[1], self.hex_size, ox, oy)
        coord = h.to_tuple()
        tmap = self._current_terrain_map()
        if coord not in tmap:
            return

        items: list = []

        # Select
        def _select():
            self.selected_hex = coord
        items.append(("Select hex", _select))

        # Drill-down
        if self.scale == SCALE_STRATEGIC:
            def _drill(c=coord):
                self._enter_operational(c)
                self._toast_msg(f"Drilling into {c}")
            items.append(("Drill down", _drill))

        # Move selected unit here
        if self.selected_unit_id and self.campaign:
            u = self.campaign.units.get(self.selected_unit_id)
            if u:
                def _move_here(unit=u, c=coord):
                    unit.position = c
                    log_event(self.campaign, "unit_moved",
                              f"{unit.name} moved to ({c[0]},{c[1]})")
                    self._toast_msg(f"Moved {unit.name} to {c}")
                items.append((f"Move {u.name[:12]} here", _move_here))

        # Add unit
        if self.campaign and self.campaign.factions and self.scale == SCALE_STRATEGIC:
            def _add_unit():
                faction_list = [(f.name, f.id) for f in self.campaign.factions.values()]
                self.dialog = AddUnitDialog((self.width, self.height), faction_list, coord)
            items.append(("Add unit", _add_unit))

        # Hex note
        if self.campaign:
            def _note():
                key = f"{coord[0]},{coord[1]}"
                existing = self.campaign.hex_notes.get(key, "")
                self.dialog = HexNoteDialog((self.width, self.height), coord, existing)
            label = "Edit note" if f"{coord[0]},{coord[1]}" in self.campaign.hex_notes else "Add note"
            items.append((label, _note))

        self._ctx_menu = {"pos": pos, "hex_pos": coord, "items": items, "_rects": {}}

    def _draw_context_menu(self) -> None:
        if not self._ctx_menu:
            return
        m    = self._ctx_menu
        font = pygame.font.SysFont("monospace", 12, bold=True)
        pad  = 8
        lh   = 20
        items = m["items"]
        w = max((font.size(lbl)[0] for lbl, _ in items), default=80) + pad * 2
        h = len(items) * lh + pad
        px, py = m["pos"]
        # Clamp to screen
        px = min(px, self.width  - SIDEBAR_W - w - 4)
        py = min(py, self.height - STATUSBAR_H - h - 4)
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((20, 22, 34, 230))
        self.screen.blit(bg, (px, py))
        pygame.draw.rect(self.screen, (100, 100, 140), pygame.Rect(px, py, w, h), 1, border_radius=3)
        mouse = pygame.mouse.get_pos()
        rects = {}
        for i, (label, fn) in enumerate(items):
            r = pygame.Rect(px, py + pad // 2 + i * lh, w, lh)
            if r.collidepoint(mouse):
                pygame.draw.rect(self.screen, (50, 60, 100), r)
            surf = font.render(label, True, (210, 210, 230))
            self.screen.blit(surf, (r.x + pad, r.y + 3))
            rects[label] = r
        m["_rects"] = rects

    # ── terrain palette ──────────────────────────────────────────────────────

    _PAINT_TERRAINS = [
        TERRAIN_PLAINS, TERRAIN_FOREST, TERRAIN_HILLS, TERRAIN_MOUNTAINS,
        TERRAIN_COAST,  TERRAIN_WATER,  TERRAIN_DEEP_WATER,
        TERRAIN_DESERT, TERRAIN_ARCTIC, TERRAIN_URBAN, TERRAIN_INDUSTRIAL,
        TERRAIN_VOLCANIC,
    ]

    def _draw_terrain_palette(self) -> None:
        """Draw a row of terrain swatches above the statusbar when paint tool active."""
        from game.terrain import TERRAIN, terrain_name
        font   = pygame.font.SysFont("monospace", 10, bold=True)
        sw, sh = 52, 18
        gap    = 3
        total  = len(self._PAINT_TERRAINS) * (sw + gap) - gap
        start_x = (self.width - SIDEBAR_W - total) // 2
        y = self.height - STATUSBAR_H - sh - 4
        self._palette_boxes = []
        for i, tid in enumerate(self._PAINT_TERRAINS):
            tdef = TERRAIN.get(tid)
            if not tdef:
                continue
            x = start_x + i * (sw + gap)
            r = pygame.Rect(x, y, sw, sh)
            is_sel = (tid == self.paint_terrain)
            pygame.draw.rect(self.screen, tdef.color, r, border_radius=2)
            if is_sel:
                pygame.draw.rect(self.screen, (255, 255, 255), r, 2, border_radius=2)
            else:
                pygame.draw.rect(self.screen, (60, 60, 80), r, 1, border_radius=2)
            lbl = font.render(tdef.name[:6], True, (255, 255, 255))
            self.screen.blit(lbl, lbl.get_rect(center=r.center))
            from ui.chrome import Hitbox
            self._palette_boxes.append(Hitbox(f"palette_{tid}", r, tid))

    # ── elevation palette ────────────────────────────────────────────────────

    # Hypsometric colors matching the renderer's shading bands (0=deep water → 10=peak)
    _ELEV_COLORS = [
        ( 20,  60, 180),  # 0 deep water
        ( 40,  90, 200),  # 1 water
        ( 60, 140,  80),  # 2 lowlands
        ( 80, 160,  70),  # 3 plains
        (140, 170,  60),  # 4 mid green
        (180, 160,  50),  # 5 mid yellow
        (200, 130,  40),  # 6 highland
        (190, 100,  30),  # 7 upper highland
        (160,  80,  40),  # 8 mountain brown
        (180, 180, 180),  # 9 high rock
        (240, 240, 255),  # 10 peak / snow
    ]

    def _draw_elevation_palette(self) -> None:
        """Draw elevation swatches 0–10 above the statusbar when elevation tool active."""
        from ui.chrome import Hitbox
        font  = pygame.font.SysFont("monospace", 10, bold=True)
        sw, sh = 38, 22
        gap   = 3
        total = 11 * (sw + gap) - gap
        start_x = (self.width - SIDEBAR_W - total) // 2
        y = self.height - STATUSBAR_H - sh - 4
        self._palette_boxes = []
        for elev in range(11):
            x = start_x + elev * (sw + gap)
            r = pygame.Rect(x, y, sw, sh)
            color  = self._ELEV_COLORS[elev]
            is_sel = (elev == self.paint_elevation)
            pygame.draw.rect(self.screen, color, r, border_radius=2)
            border = (255, 255, 255) if is_sel else (60, 60, 80)
            pygame.draw.rect(self.screen, border, r, 2 if is_sel else 1, border_radius=2)
            lbl_c = (255, 255, 255) if elev <= 8 else (30, 30, 30)
            self.screen.blit(font.render(str(elev), True, lbl_c),
                             font.render(str(elev), True, lbl_c).get_rect(center=r.center))
            self._palette_boxes.append(Hitbox(f"palette_elev_{elev}", r, elev))

    # ── keybinding help overlay ──────────────────────────────────────────────

    def _draw_help_overlay(self) -> None:
        lines = [
            ("KEYBOARD SHORTCUTS", None),
            ("", None),
            ("Arrow / WASD",        "Pan map"),
            ("+  /  -",             "Zoom in / out"),
            ("N",                   "Next phase"),
            ("Ctrl+Z",              "Undo phase"),
            ("Ctrl+S",              "Save"),
            ("Escape",              "Back / deselect"),
            ("?",                   "Toggle this help"),
            ("", None),
            ("MOUSE", None),
            ("Left-click",          "Use current tool"),
            ("Right-click",         "Context menu"),
            ("Right-drag",          "Pan map"),
            ("Scroll wheel",        "Zoom"),
            ("", None),
            ("TOOLS", None),
            ("Select",              "Click hex → info"),
            ("Move",                "Click unit then dest"),
            ("Paint",               "Click/drag terrain"),
            ("Delete",              "Click unit to remove"),
        ]
        font_h = pygame.font.SysFont("monospace", 14, bold=True)
        font   = pygame.font.SysFont("monospace", 12)
        pad    = 16
        lh     = 18
        w      = 340
        h      = len(lines) * lh + pad * 2
        x = (self.width - SIDEBAR_W - w) // 2
        y = (self.height - h) // 2
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((10, 12, 22, 230))
        self.screen.blit(bg, (x, y))
        pygame.draw.rect(self.screen, (120, 120, 160), pygame.Rect(x, y, w, h), 1, border_radius=4)
        for i, (key, desc) in enumerate(lines):
            cy = y + pad + i * lh
            if desc is None:
                surf = font_h.render(key, True, (200, 180, 100)) if key else None
            else:
                k_surf = font.render(key, True, (160, 200, 255))
                d_surf = font.render(desc, True, (200, 200, 210))
                self.screen.blit(k_surf, (x + pad, cy))
                self.screen.blit(d_surf, (x + pad + 140, cy))
                continue
            if surf:
                self.screen.blit(surf, (x + pad, cy))

    def _draw_toast(self) -> None:
        if not self._toast:
            return
        age = pygame.time.get_ticks() - self._toast_time
        if age > 3000:
            self._toast = ""
            return
        alpha = max(0, min(255, int(255 * (1 - max(0, age - 2000) / 1000))))
        font = pygame.font.SysFont("monospace", 14, bold=True)
        surf = font.render(self._toast, True, TEXT_BRIGHT)
        bg_r = pygame.Rect(0, 0, surf.get_width() + 24, surf.get_height() + 14)
        bg_r.bottomleft = (20, self.height - STATUSBAR_H - 10)
        bg = pygame.Surface(bg_r.size, pygame.SRCALPHA)
        bg.fill((20, 20, 30, alpha))
        self.screen.blit(bg, bg_r.topleft)
        pygame.draw.rect(self.screen, (100, 100, 120, alpha), bg_r, 1, border_radius=3)
        self.screen.blit(surf, (bg_r.x + 12, bg_r.y + 7))


def _fmt_coord(strat, sub, tac) -> str:
    """Human-friendly rendering of a hierarchical coordinate."""
    s = f"({strat[0]},{strat[1]})"
    if sub is not None:
        s += f" · sub({sub[0]},{sub[1]})"
    if tac is not None:
        s += f" · tile({tac[0]},{tac[1]})"
    return s
