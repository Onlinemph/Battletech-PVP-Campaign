"""
Main Pygame application - the GM's campaign manager window.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Tuple

import pygame

from game.constants import (SCALE_STRATEGIC, SCALE_OPERATIONAL,
                             DEFAULT_VISION, UNIT_MECH,
                             HIGH_ALT_HEX_SIZE_M, LOW_ALT_HEX_SIZE_M)
from game.hex_grid import Hex, pixel_to_hex, hex_to_pixel, axial_to_offset
from game.models import Campaign
from game.terrain import terrain_name
from game.campaign import (new_campaign, save_campaign, load_campaign, list_saves,
                            add_faction, add_unit, add_mission, next_turn,
                            get_operational_map, log_event)

from ui.colors import BG, TEXT, TEXT_BRIGHT, TEXT_DIM, PANEL_DARK, BTN_ACTIVE, BTN_HOVER, BTN_NORMAL, BORDER_LT, BORDER
from ui.renderer import MapRenderer, pixel_to_hierarchical, SUBHEX_ZOOM_THRESHOLD, TACTICAL_ZOOM_THRESHOLD
from ui.chrome import (draw_toolbar, draw_sidebar, draw_statusbar,
                        TOOLBAR_H, STATUSBAR_H, SIDEBAR_W)
from ui.dialogs import (NewCampaignDialog, AddFactionDialog, AddUnitDialog,
                         AddMissionDialog, EditUnitDialog, LoadDialog,
                         ExportDialog, ConfirmDialog, ResolveMissionDialog)
from ui.export import export_view


ZOOM_LEVELS = [8, 12, 18, 26, 38, 55, 80, 120, 180, 260, 380, 540]


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
        self.scale       = SCALE_STRATEGIC
        self.op_hex: Optional[Tuple[int, int]] = None
        self.zoom_idx    = 3
        self.pan_x       = 0.0
        self.pan_y       = 0.0

        # Interaction state
        self.tool          = "select"     # select, move, add_unit, add_mission, delete
        self.selected_hex: Optional[Tuple[int, int]] = None
        self.selected_unit_id: Optional[str] = None
        self.faction_filter: Optional[str]   = None
        self.move_source_unit: Optional[str] = None  # when using move tool

        # Mouse pan
        self._drag_active  = False
        self._drag_start   = (0, 0)
        self._pan_start    = (0.0, 0.0)

        # Modal dialog
        self.dialog = None

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

    def _map_rect(self) -> pygame.Rect:
        return pygame.Rect(0, TOOLBAR_H,
                           self.width - SIDEBAR_W,
                           self.height - TOOLBAR_H - STATUSBAR_H)

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
                self._on_map_click(event.pos)
            elif event.button == 3:
                # Right-drag pan
                self._drag_active = True
                self._drag_start  = event.pos
                self._pan_start   = (self.pan_x, self.pan_y)
            elif event.button == 4:
                self._zoom(+1, event.pos)
            elif event.button == 5:
                self._zoom(-1, event.pos)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3:
                self._drag_active = False

        elif event.type == pygame.MOUSEMOTION:
            if self._drag_active:
                dx = event.pos[0] - self._drag_start[0]
                dy = event.pos[1] - self._drag_start[1]
                self.pan_x = self._pan_start[0] + dx
                self.pan_y = self._pan_start[1] + dy

    def _handle_key(self, event: pygame.event.Event) -> None:
        k = event.key
        step = 60
        if k == pygame.K_ESCAPE:
            if self.scale == SCALE_OPERATIONAL:
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
        elif k == pygame.K_s and (event.mod & pygame.KMOD_CTRL):
            self._handle_toolbar("save")

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

        if self.tool == "select":
            self.selected_hex     = coord
            hex_units = [u for u in self.campaign.units.values() if u.position == coord] \
                        if self.scale == SCALE_STRATEGIC else []
            self.selected_unit_id = hex_units[0].id if hex_units else None

        elif self.tool == "move":
            if self.move_source_unit is None:
                hex_units = [u for u in self.campaign.units.values() if u.position == coord]
                if hex_units:
                    self.move_source_unit  = hex_units[0].id
                    self.selected_unit_id  = hex_units[0].id
                    self._toast_msg(f"Move {hex_units[0].name}: click destination")
            else:
                u = self.campaign.units.get(self.move_source_unit)
                if u is not None:
                    u.position     = coord
                    u.sub_position = sub
                    u.tac_position = tac
                    detail = _fmt_coord(coord, sub, tac)
                    self._toast_msg(f"Moved {u.name} to {detail}")
                    log_event(self.campaign, "unit_moved",
                              f"{u.name} moved to ({coord[0]},{coord[1]})")
                self.move_source_unit = None

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

        elif self.tool == "delete":
            if self.scale != SCALE_STRATEGIC:
                return
            to_del = [uid for uid, u in self.campaign.units.items() if u.position == coord]
            if to_del:
                for uid in to_del:
                    del self.campaign.units[uid]
                self._toast_msg(f"Deleted {len(to_del)} unit(s)")

        self.selected_hex = coord

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
                next_turn(self.campaign)
                self._toast_msg(f"Advanced to turn {self.campaign.current_turn}")
        elif name == "add_faction":
            self.dialog = AddFactionDialog((self.width, self.height))
        elif name.startswith("tool_"):
            self.tool = name[5:]
            self.move_source_unit = None
        elif name == "view_strategic":
            self.scale = SCALE_STRATEGIC
            self.op_hex = None
        elif name == "view_operational":
            if self.selected_hex and self.scale == SCALE_STRATEGIC:
                self.op_hex = self.selected_hex
                self.scale  = SCALE_OPERATIONAL
                self.pan_x  = (self.width - SIDEBAR_W) / 2
                self.pan_y  = (self.height - TOOLBAR_H - STATUSBAR_H) / 2
                self._toast_msg(f"Drill-down into {self.selected_hex}")
            else:
                self._toast_msg("Select a strategic hex first")

    def _handle_sidebar(self, box) -> None:
        if box.name == "faction":
            self.faction_filter = None if self.faction_filter == box.data else box.data
        elif box.name == "unit":
            self.selected_unit_id = box.data
        elif box.name == "mission":
            m = self.campaign.missions.get(box.data)
            if m:
                self.dialog = ResolveMissionDialog(
                    (self.width, self.height), m, self.campaign.factions)
        elif box.name == "edit_unit":
            u = self.campaign.units.get(box.data)
            if u:
                self.dialog = EditUnitDialog((self.width, self.height), u)
        elif box.name == "delete_unit":
            self.dialog = ConfirmDialog((self.width, self.height),
                                         "Delete this unit?")
            self.dialog._delete_unit_id = box.data  # type: ignore[attr-defined]

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
            self._center_on((r["width"] // 2, r["height"] // 2))
            self._toast_msg(f"Created '{r['name']}' (seed {self.campaign.map_seed})")

        elif isinstance(d, LoadDialog):
            self.campaign = load_campaign(d.result)
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

        # Fog set if a faction filter is active (GM peeks at player view)
        fog_set = None
        if self.faction_filter is not None:
            from game.vision import visible_hexes
            fog_set = visible_hexes(self.campaign, self.faction_filter)

        renderer = MapRenderer(
            surface   = self.screen,
            rect      = rect,
            campaign  = self.campaign,
            hex_size  = self.hex_size,
            pan       = (self.pan_x, self.pan_y),
            scale     = self.scale,
            op_hex    = self.op_hex,
            fog_set   = fog_set,
            hover_hex = hover_hex,
            selected  = self.selected_hex,
        )
        renderer.draw()

        # Sidebar
        self._sidebar_boxes = draw_sidebar(
            self.screen, self.width - SIDEBAR_W, TOOLBAR_H,
            SIDEBAR_W, self.height - TOOLBAR_H - STATUSBAR_H,
            self.campaign, self.selected_hex, self.selected_unit_id,
            self.faction_filter, mouse_pos, self.scale, self.op_hex,
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
