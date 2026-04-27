"""
Pygame modal dialog widgets.
All dialogs are drawn on top of the screen each frame.
Call dialog.handle_event(event) and dialog.draw(surface).
Check dialog.done / dialog.result when finished.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pygame

from game.constants import (MISSION_STATUSES, STRUCTURE_TYPES, STRUCTURE_SUPPLY_RANGES,
                             COMBAT_OUTCOMES, OBJECTIVE_STATUSES)
from game.models import Mission, Faction, Objective
from ui.colors import (BG, PANEL_BG, PANEL_DARK, BORDER, BORDER_LT,
                        BTN_NORMAL, BTN_HOVER, BTN_ACTIVE, BTN_DANGER,
                        BTN_TEXT, TEXT, TEXT_DIM, TEXT_BRIGHT,
                        FACTION_PALETTE)


# ── Low-level widgets ─────────────────────────────────────────────────────────

class TextInput:
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font,
                 placeholder: str = "", value: str = ""):
        self.rect        = rect
        self.font        = font
        self.placeholder = placeholder
        self.value       = value
        self.active      = False
        self.cursor_vis  = True
        self._tick       = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if not self.active:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                self.active = False
            elif event.unicode and ord(event.unicode) >= 32:
                self.value += event.unicode

    def draw(self, surface: pygame.Surface) -> None:
        self._tick += 1
        if self._tick % 60 == 0:
            self.cursor_vis = not self.cursor_vis

        bg = (50, 50, 60) if self.active else (38, 38, 46)
        border = BORDER_LT if self.active else BORDER
        pygame.draw.rect(surface, bg, self.rect, border_radius=3)
        pygame.draw.rect(surface, border, self.rect, 1, border_radius=3)

        text = self.value or self.placeholder
        color = TEXT if self.value else TEXT_DIM
        rendered = self.font.render(text, True, color)
        surface.blit(rendered, (self.rect.x + 6, self.rect.y + (self.rect.height - rendered.get_height()) // 2))

        if self.active and self.cursor_vis and self.value:
            tw = self.font.size(self.value)[0]
            cx = self.rect.x + 6 + tw + 1
            cy = self.rect.y + 4
            pygame.draw.line(surface, TEXT, (cx, cy), (cx, self.rect.bottom - 4), 1)


class Button:
    def __init__(self, rect: pygame.Rect, label: str, font: pygame.font.Font,
                 color: tuple = BTN_NORMAL, danger: bool = False):
        self.rect    = rect
        self.label   = label
        self.font    = font
        self.color   = BTN_DANGER if danger else color
        self.hover   = False
        self.clicked = False

    def handle_event(self, event: pygame.event.Event) -> None:
        self.clicked = False
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.clicked = True

    def draw(self, surface: pygame.Surface) -> None:
        bg = BTN_HOVER if self.hover else self.color
        pygame.draw.rect(surface, bg, self.rect, border_radius=4)
        pygame.draw.rect(surface, BORDER_LT, self.rect, 1, border_radius=4)
        lbl = self.font.render(self.label, True, BTN_TEXT)
        surface.blit(lbl, lbl.get_rect(center=self.rect.center))


class DropDown:
    def __init__(self, rect: pygame.Rect, options: List[str], font: pygame.font.Font,
                 selected: int = 0):
        self.rect     = rect
        self.options  = options
        self.font     = font
        self.selected = selected
        self.open     = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if the event was consumed (should not be forwarded)."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if self.rect.collidepoint(event.pos):
            self.open = not self.open
            return True
        if self.open:
            for i, opt_rect in enumerate(self._option_rects()):
                if opt_rect.collidepoint(event.pos):
                    self.selected = i
                    self.open = False
                    return True
            # Click elsewhere while open: close and consume so widgets
            # hidden underneath the option list don't fire.
            self.open = False
            return True
        return False

    def _option_rects(self) -> List[pygame.Rect]:
        rects = []
        for i in range(len(self.options)):
            rects.append(pygame.Rect(
                self.rect.x, self.rect.bottom + i * self.rect.height,
                self.rect.width, self.rect.height
            ))
        return rects

    @property
    def value(self) -> str:
        return self.options[self.selected] if self.options else ""

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the closed (base) part only. Call draw_overlay() last to show open list."""
        pygame.draw.rect(surface, (45, 45, 55), self.rect, border_radius=3)
        pygame.draw.rect(surface, BORDER_LT, self.rect, 1, border_radius=3)
        lbl = self.font.render(self.value, True, TEXT)
        surface.blit(lbl, (self.rect.x + 6, self.rect.y + (self.rect.height - lbl.get_height()) // 2))
        # Arrow
        ax = self.rect.right - 14
        ay = self.rect.centery
        pygame.draw.polygon(surface, TEXT_DIM, [(ax, ay - 3), (ax + 7, ay - 3), (ax + 3, ay + 3)])

    def draw_overlay(self, surface: pygame.Surface) -> None:
        """Draw the expanded options list on top of everything else. No-op if closed."""
        if not self.open:
            return
        # Soft shadow
        shadow = pygame.Surface((self.rect.width + 6,
                                 self.rect.height * len(self.options) + 6), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 120))
        surface.blit(shadow, (self.rect.x + 2, self.rect.bottom + 2))
        for i, opt_rect in enumerate(self._option_rects()):
            bg = BTN_HOVER if i == self.selected else PANEL_DARK
            pygame.draw.rect(surface, bg, opt_rect)
            pygame.draw.rect(surface, BORDER, opt_rect, 1)
            lbl2 = self.font.render(self.options[i], True, TEXT)
            surface.blit(lbl2, (opt_rect.x + 6, opt_rect.y + (opt_rect.height - lbl2.get_height()) // 2))


class ColorSwatch:
    """Clickable color picker from a palette list."""
    def __init__(self, x: int, y: int, palette: list, cell: int = 20, cols: int = 5):
        self.palette  = palette
        self.cell     = cell
        self.cols     = cols
        self.x, self.y = x, y
        self.selected  = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, color in enumerate(self.palette):
                r = self._swatch_rect(i)
                if r.collidepoint(event.pos):
                    self.selected = i

    def _swatch_rect(self, i: int) -> pygame.Rect:
        col = i % self.cols
        row = i // self.cols
        return pygame.Rect(self.x + col * (self.cell + 3),
                           self.y + row * (self.cell + 3),
                           self.cell, self.cell)

    @property
    def color(self) -> tuple:
        return self.palette[self.selected]

    def draw(self, surface: pygame.Surface) -> None:
        for i, color in enumerate(self.palette):
            r = self._swatch_rect(i)
            pygame.draw.rect(surface, color, r, border_radius=2)
            if i == self.selected:
                pygame.draw.rect(surface, (255, 255, 255), r, 2, border_radius=2)


# ── Base dialog ───────────────────────────────────────────────────────────────

class Dialog:
    W = 480
    H = 320

    def __init__(self, title: str, screen_size: Tuple[int, int]):
        sw, sh   = screen_size
        self.rect = pygame.Rect((sw - self.W) // 2, (sh - self.H) // 2, self.W, self.H)
        self.title  = title
        self.done   = False
        self.result: Any = None

        pygame.font.init()
        self.font_h  = pygame.font.SysFont("monospace", 15, bold=True)
        self.font    = pygame.font.SysFont("monospace", 13)
        self.font_sm = pygame.font.SysFont("monospace", 11)

    def _draw_frame(self, surface: pygame.Surface) -> None:
        # Darken background
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        pygame.draw.rect(surface, PANEL_BG, self.rect, border_radius=6)
        pygame.draw.rect(surface, BORDER_LT, self.rect, 1, border_radius=6)
        # Title bar
        title_r = pygame.Rect(self.rect.x, self.rect.y, self.rect.width, 32)
        pygame.draw.rect(surface, PANEL_DARK, title_r,
                         border_top_left_radius=6, border_top_right_radius=6)
        pygame.draw.line(surface, BORDER, (title_r.left, title_r.bottom),
                         (title_r.right, title_r.bottom), 1)
        lbl = self.font_h.render(self.title, True, TEXT_BRIGHT)
        surface.blit(lbl, (self.rect.x + 12, self.rect.y + 8))

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)

    def label(self, surface: pygame.Surface, text: str, x: int, y: int,
              color: tuple = TEXT, bold: bool = False) -> None:
        f = pygame.font.SysFont("monospace", 13, bold=bold)
        s = f.render(text, True, color)
        surface.blit(s, (x, y))


# ── New Campaign dialog ───────────────────────────────────────────────────────

class NewCampaignDialog(Dialog):
    W, H = 500, 340

    def __init__(self, screen_size: Tuple[int, int]):
        super().__init__("New Campaign", screen_size)
        x, y = self.rect.x + 20, self.rect.y + 50

        self.inp_name    = TextInput(pygame.Rect(x + 130, y,      320, 28), self.font, "e.g. War of '39")
        self.inp_width   = TextInput(pygame.Rect(x + 130, y + 38, 100, 28), self.font, "60", "60")
        self.inp_height  = TextInput(pygame.Rect(x + 130, y + 76, 100, 28), self.font, "40", "40")
        self.inp_seed    = TextInput(pygame.Rect(x + 130, y + 114,150, 28), self.font, "random")
        self.inp_water   = TextInput(pygame.Rect(x + 130, y + 152, 80, 28), self.font, "0.38", "0.38")

        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Create", self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

        self._inputs = [self.inp_name, self.inp_width, self.inp_height, self.inp_seed, self.inp_water]

    def handle_event(self, event: pygame.event.Event) -> None:
        for inp in self._inputs:
            inp.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)

        if self.btn_cancel.clicked:
            self.done   = True
            self.result = None

        if self.btn_ok.clicked:
            try:
                name  = self.inp_name.value.strip() or "New Campaign"
                w     = int(self.inp_width.value  or 60)
                h     = int(self.inp_height.value or 40)
                seed  = int(self.inp_seed.value)  if self.inp_seed.value.strip() else 0
                water = float(self.inp_water.value or 0.38)
                self.result = dict(name=name, width=w, height=h, seed=seed, water=water)
                self.done   = True
            except ValueError:
                pass  # keep dialog open on bad input

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        labels = ["Campaign Name:", "Map Width (hexes):", "Map Height (hexes):",
                  "Seed (0=random):", "Water ratio (0-1):"]
        for i, lbl in enumerate(labels):
            self.label(surface, lbl, x, y + 7 + i * 38)
        for inp in self._inputs:
            inp.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)


# ── Add Faction dialog ────────────────────────────────────────────────────────

class AddFactionDialog(Dialog):
    W, H = 500, 320

    def __init__(self, screen_size: Tuple[int, int]):
        super().__init__("Add Faction", screen_size)
        x, y = self.rect.x + 20, self.rect.y + 50

        self.inp_name   = TextInput(pygame.Rect(x + 120, y,      320, 28), self.font, "e.g. House Davion")
        self.inp_player = TextInput(pygame.Rect(x + 120, y + 38, 320, 28), self.font, "player's real name")
        self.swatch     = ColorSwatch(x + 120, y + 82, FACTION_PALETTE)

        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Add",    self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        self.inp_name.handle_event(event)
        self.inp_player.handle_event(event)
        self.swatch.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)
        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_ok.clicked:
            name = self.inp_name.value.strip() or "Unnamed Faction"
            self.result = dict(name=name, player=self.inp_player.value.strip(),
                               color=self.swatch.color)
            self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, "Faction Name:", x, y + 7)
        self.label(surface, "Player Name:",  x, y + 45)
        self.label(surface, "Color:",        x, y + 90)
        self.inp_name.draw(surface)
        self.inp_player.draw(surface)
        self.swatch.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)


# ── Add Unit dialog ────────────────────────────────────────────────────────────

class AddUnitDialog(Dialog):
    W, H = 520, 450

    # Default walk/run MP by unit type (Aerospace uses thrust points as proxy)
    _DEFAULT_MP = {
        "BattleMech": (4, 6), "Vehicle": (4, 6),
        "Infantry": (1, 2), "Aerospace": (6, 9), "DropShip": (2, 3),
    }

    def __init__(self, screen_size: Tuple[int, int], factions: list, hex_pos: tuple):
        super().__init__(f"Add Unit at hex {hex_pos}", screen_size)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.hex_pos = hex_pos

        from game.constants import UNIT_TYPES, DEFAULT_VISION
        self.DEFAULT_VISION = DEFAULT_VISION

        self.inp_name    = TextInput(pygame.Rect(x + 130, y,       330, 28), self.font, "e.g. Alpha Lance")
        self.dd_faction  = DropDown( pygame.Rect(x + 130, y + 38,  240, 28), [f[0] for f in factions], self.font)
        self.dd_type     = DropDown( pygame.Rect(x + 130, y + 76,  200, 28), UNIT_TYPES, self.font)
        self.inp_walk    = TextInput(pygame.Rect(x + 130, y + 114,  60, 28), self.font, "4", "4")
        self.inp_run     = TextInput(pygame.Rect(x + 220, y + 114,  60, 28), self.font, "6", "6")
        self.inp_vision  = TextInput(pygame.Rect(x + 130, y + 152,  80, 28), self.font, "2", "2")
        self.inp_notes   = TextInput(pygame.Rect(x + 130, y + 190, 330, 28), self.font, "optional notes")
        self.inp_bv      = TextInput(pygame.Rect(x + 130, y + 228,  90, 28), self.font, "0", "0")

        self._faction_ids = [f[1] for f in factions]  # parallel list of IDs

        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Place",  self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.dd_faction.handle_event(event): return
        if self.dd_type.handle_event(event):
            # Auto-fill walk/run MP when type changes
            w, r = self._DEFAULT_MP.get(self.dd_type.value, (4, 6))
            self.inp_walk.value = str(w)
            self.inp_run.value  = str(r)
            return
        self.inp_name.handle_event(event)
        self.inp_walk.handle_event(event)
        self.inp_run.handle_event(event)
        self.inp_vision.handle_event(event)
        self.inp_notes.handle_event(event)
        self.inp_bv.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)
        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_ok.clicked:
            try:
                name       = self.inp_name.value.strip() or "New Unit"
                faction_id = self._faction_ids[self.dd_faction.selected] if self._faction_ids else ""
                unit_type  = self.dd_type.value
                w_def, r_def = self._DEFAULT_MP.get(unit_type, (4, 6))
                walk_mp    = int(self.inp_walk.value or w_def)
                run_mp     = int(self.inp_run.value  or r_def)
                vision     = int(self.inp_vision.value or self.DEFAULT_VISION.get(unit_type, 2))
                notes      = self.inp_notes.value.strip()
                bv         = int(self.inp_bv.value or 0)
                self.result = dict(name=name, faction_id=faction_id, unit_type=unit_type,
                                   walk_mp=walk_mp, run_mp=run_mp, battle_value=bv,
                                   vision=vision, notes=notes, position=self.hex_pos)
                self.done = True
            except (ValueError, IndexError):
                pass

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        labels = ["Unit Name:", "Faction:", "Unit Type:", "Walk / Run MP:", "Vision Range:", "Notes:", "Battle Value (BV):"]
        for i, lbl in enumerate(labels):
            self.label(surface, lbl, x, y + 7 + i * 38)
        self.inp_name.draw(surface)
        self.dd_faction.draw(surface)
        self.dd_type.draw(surface)
        self.inp_walk.draw(surface)
        self.label(surface, "/", x + 188, y + 121, color=(180, 180, 180))
        self.inp_run.draw(surface)
        self.inp_vision.draw(surface)
        self.inp_notes.draw(surface)
        self.inp_bv.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)
        self.dd_faction.draw_overlay(surface)
        self.dd_type.draw_overlay(surface)


# ── Add Mission dialog ─────────────────────────────────────────────────────────

class AddMissionDialog(Dialog):
    W, H = 500, 310

    def __init__(self, screen_size: Tuple[int, int], hex_pos: tuple):
        super().__init__(f"Place Mission at hex {hex_pos}", screen_size)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.hex_pos = hex_pos

        from game.constants import MISSION_TYPES
        self.inp_name  = TextInput(pygame.Rect(x + 130, y,      320, 28), self.font, "e.g. Strike Valhalla")
        self.dd_type   = DropDown( pygame.Rect(x + 130, y + 38, 200, 28), MISSION_TYPES, self.font)
        self.inp_notes = TextInput(pygame.Rect(x + 130, y + 76, 320, 28), self.font, "GM notes")

        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Place",  self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.dd_type.handle_event(event): return
        self.inp_name.handle_event(event)
        self.inp_notes.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)
        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_ok.clicked:
            self.result = dict(name=self.inp_name.value.strip() or "Mission",
                               mission_type=self.dd_type.value,
                               notes=self.inp_notes.value.strip(),
                               position=self.hex_pos)
            self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, "Mission Name:", x, y + 7)
        self.label(surface, "Type:",         x, y + 45)
        self.label(surface, "Notes:",        x, y + 83)
        self.inp_name.draw(surface)
        self.dd_type.draw(surface)
        self.inp_notes.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)
        self.dd_type.draw_overlay(surface)


# ── Edit Unit dialog ───────────────────────────────────────────────────────────

class EditUnitDialog(Dialog):
    W, H = 560, 520

    def __init__(self, screen_size: Tuple[int, int], unit, groups: dict = None):
        super().__init__(f"Edit Unit: {unit.name}", screen_size)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.unit = unit

        from game.constants import UNIT_STATUSES
        self.inp_name        = TextInput(pygame.Rect(x + 140, y,        370, 28), self.font, value=unit.name)
        self.dd_status       = DropDown( pygame.Rect(x + 140, y + 38,   200, 28), UNIT_STATUSES, self.font,
                                         selected=UNIT_STATUSES.index(unit.status) if unit.status in UNIT_STATUSES else 0)
        self.inp_repair_cost = TextInput(pygame.Rect(x + 140, y + 76,   100, 28), self.font,
                                         placeholder="0", value=str(unit.repair_cost) if unit.repair_cost else "")
        self.inp_bv          = TextInput(pygame.Rect(x + 300, y + 76,   100, 28), self.font,
                                         placeholder="0", value=str(unit.battle_value) if unit.battle_value else "")
        self.inp_vision      = TextInput(pygame.Rect(x + 140, y + 114,   80, 28), self.font, value=str(unit.vision_range))
        self.inp_notes       = TextInput(pygame.Rect(x + 140, y + 152,  370, 28), self.font, value=unit.notes)

        # Group assignment
        _groups = groups or {}
        self._group_ids   = [""] + [g.id for g in _groups.values()
                                    if g.faction_id == unit.faction_id]
        group_names       = ["(No Group)"] + [g.name for g in _groups.values()
                                               if g.faction_id == unit.faction_id]
        try:
            grp_idx = self._group_ids.index(unit.group_id or "")
        except ValueError:
            grp_idx = 0
        self.dd_group = DropDown(pygame.Rect(x + 140, y + 190, 220, 28), group_names, self.font,
                                 selected=grp_idx)

        # Roster section
        self.roster_entries: List[Dict] = [
            {"chassis": r.chassis, "pilot": r.pilot, "tonnage": str(r.tonnage),
             "status": r.status, "notes": r.notes}
            for r in unit.roster
        ]
        self._roster_scroll = 0
        self.roster_rect    = pygame.Rect(self.rect.x + 10, y + 238, self.rect.width - 20, 160)

        btn_y = self.rect.bottom - 48
        self.btn_ok       = Button(pygame.Rect(self.rect.right - 320, btn_y, 100, 32), "Save",   self.font)
        self.btn_roster   = Button(pygame.Rect(self.rect.right - 210, btn_y, 100, 32), "+Mech",  self.font)
        self.btn_cancel   = Button(pygame.Rect(self.rect.right - 100, btn_y,  90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.dd_status.handle_event(event): return
        if self.dd_group.handle_event(event):  return
        self.inp_name.handle_event(event)
        self.inp_repair_cost.handle_event(event)
        self.inp_bv.handle_event(event)
        self.inp_vision.handle_event(event)
        self.inp_notes.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_roster.handle_event(event)
        self.btn_cancel.handle_event(event)

        if self.btn_cancel.clicked:
            self.done = True; self.result = None

        if self.btn_roster.clicked:
            self.roster_entries.append({"chassis": "Unknown", "pilot": "Unknown",
                                        "tonnage": "0", "status": "active", "notes": ""})

        if self.btn_ok.clicked:
            from game.models import RosterEntry
            from game.constants import STATUS_ACTIVE
            try:
                self.unit.name         = self.inp_name.value.strip() or self.unit.name
                self.unit.status       = self.dd_status.value
                self.unit.repair_cost  = int(self.inp_repair_cost.value or 0)
                self.unit.battle_value = int(self.inp_bv.value or 0)
                self.unit.vision_range = int(self.inp_vision.value or 2)
                self.unit.notes        = self.inp_notes.value.strip()
                self.unit.group_id     = self._group_ids[self.dd_group.selected] or None
                self.unit.roster = [
                    RosterEntry(
                        chassis=e["chassis"], pilot=e["pilot"],
                        tonnage=int(e.get("tonnage", 0) or 0),
                        status=e.get("status", STATUS_ACTIVE),
                        notes=e.get("notes", ""),
                    )
                    for e in self.roster_entries
                ]
                self.result = self.unit
                self.done   = True
            except ValueError:
                pass

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, "Unit Name:",   x, y + 7)
        self.label(surface, "Status:",      x, y + 45)
        self.label(surface, "Repair Cost:", x, y + 83)
        self.label(surface, "BV:",          x + 260, y + 83)
        self.label(surface, "Vision:",      x, y + 121)
        self.label(surface, "Notes:",       x, y + 159)
        self.label(surface, "Group:",       x, y + 197)
        self.inp_name.draw(surface)
        self.dd_status.draw(surface)
        self.inp_repair_cost.draw(surface)
        self.inp_bv.draw(surface)
        self.inp_vision.draw(surface)
        self.inp_notes.draw(surface)
        self.dd_group.draw(surface)

        # Roster
        self.label(surface, "Roster:", x, y + 238, bold=True)
        pygame.draw.rect(surface, PANEL_DARK, self.roster_rect, border_radius=3)
        pygame.draw.rect(surface, BORDER, self.roster_rect, 1, border_radius=3)

        row_h = 22
        visible_rows = min(len(self.roster_entries), self.roster_rect.height // row_h)
        for i in range(visible_rows):
            e   = self.roster_entries[i + self._roster_scroll]
            ry  = self.roster_rect.y + 4 + i * row_h
            txt = f"{e['chassis'][:22]:22}  {e['pilot'][:16]:16}  {e['tonnage']:>3}t  {e['status']}"
            lbl = self.font_sm.render(txt, True, TEXT)
            surface.blit(lbl, (self.roster_rect.x + 4, ry))

        self.btn_ok.draw(surface)
        self.btn_roster.draw(surface)
        self.btn_cancel.draw(surface)
        self.dd_group.draw_overlay(surface)
        self.dd_status.draw_overlay(surface)


# ── Load Campaign dialog ───────────────────────────────────────────────────────

class LoadDialog(Dialog):
    W, H = 480, 360

    def __init__(self, screen_size: Tuple[int, int], saves: list):
        super().__init__("Load Campaign", screen_size)
        self.saves   = saves
        self.sel     = 0
        self.scroll  = 0
        self.list_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 44,
                                      self.rect.width - 20, self.rect.height - 100)

        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Load",   self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.list_rect.collidepoint(event.pos):
                row_h = 26
                idx = (event.pos[1] - self.list_rect.y) // row_h + self.scroll
                if 0 <= idx < len(self.saves):
                    self.sel = idx
            if event.button == 4:
                self.scroll = max(0, self.scroll - 1)
            if event.button == 5:
                self.scroll = min(max(0, len(self.saves) - 10), self.scroll + 1)

        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_ok.clicked and self.saves:
            self.result = self.saves[self.sel]
            self.done   = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        pygame.draw.rect(surface, PANEL_DARK, self.list_rect, border_radius=3)
        pygame.draw.rect(surface, BORDER, self.list_rect, 1, border_radius=3)
        row_h = 26
        vis   = self.list_rect.height // row_h
        for i in range(vis):
            idx = i + self.scroll
            if idx >= len(self.saves):
                break
            ry  = self.list_rect.y + i * row_h
            rr  = pygame.Rect(self.list_rect.x, ry, self.list_rect.width, row_h)
            if idx == self.sel:
                pygame.draw.rect(surface, BTN_ACTIVE, rr)
            lbl = self.font.render(str(self.saves[idx].stem), True, TEXT)
            surface.blit(lbl, (rr.x + 8, rr.y + 4))
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)


# ── Export dialog ──────────────────────────────────────────────────────────────

class ExportDialog(Dialog):
    W, H = 460, 240

    def __init__(self, screen_size: Tuple[int, int], factions: list):
        super().__init__("Export Player View", screen_size)
        x, y = self.rect.x + 20, self.rect.y + 50
        names = ["[GM - All visible]"] + [f"{f.name} ({f.player_name})" for f in factions]
        self._ids   = [None] + [f.id for f in factions]
        self.dd     = DropDown(pygame.Rect(x + 140, y, 280, 28), names, self.font)
        self.inp_w  = TextInput(pygame.Rect(x + 140, y + 46, 100, 28), self.font, "1920", "1920")
        self.inp_h  = TextInput(pygame.Rect(x + 140, y + 84, 100, 28), self.font, "1080", "1080")

        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Export", self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.dd.handle_event(event): return
        self.inp_w.handle_event(event)
        self.inp_h.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)
        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_ok.clicked:
            try:
                w = int(self.inp_w.value or 1920)
                h = int(self.inp_h.value or 1080)
                self.result = dict(faction_id=self._ids[self.dd.selected], width=w, height=h)
                self.done = True
            except ValueError:
                pass

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, "View for faction:", x, y + 7)
        self.label(surface, "Image width:",      x, y + 53)
        self.label(surface, "Image height:",     x, y + 91)
        self.dd.draw(surface)
        self.inp_w.draw(surface)
        self.inp_h.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)
        self.dd.draw_overlay(surface)


# ── Confirmation dialog ────────────────────────────────────────────────────────

class ConfirmDialog(Dialog):
    W, H = 380, 170

    def __init__(self, screen_size: Tuple[int, int], message: str):
        super().__init__("Confirm", screen_size)
        self.message = message
        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Yes",    self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)
        if self.btn_cancel.clicked:
            self.done = True; self.result = False
        if self.btn_ok.clicked:
            self.result = True; self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        self.label(surface, self.message, self.rect.x + 20, self.rect.y + 55, bold=True)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)


# ── Resolve Mission dialog ────────────────────────────────────────────────────

class ResolveMissionDialog(Dialog):
    W, H = 520, 400

    def __init__(self, screen_size: Tuple[int, int], mission: Mission,
                 factions: Dict[str, Faction]):
        super().__init__(f"Mission: {mission.name}", screen_size)
        self.mission = mission
        self._faction_ids   = list(factions.keys())
        self._faction_names = [f.name for f in factions.values()]
        self._selected_factions: set = set(mission.participating_factions)
        self._faction_rects: List[pygame.Rect] = []

        x, y = self.rect.x + 20, self.rect.y + 50
        sel = MISSION_STATUSES.index(mission.status) if mission.status in MISSION_STATUSES else 0
        self.dd_status   = DropDown(pygame.Rect(x + 90, y,       380, 28), MISSION_STATUSES, self.font, selected=sel)
        self.inp_rewards = TextInput(pygame.Rect(x + 90, y + 38, 380, 26), self.font, value=mission.rewards)
        self.inp_notes   = TextInput(pygame.Rect(x + 90, y + 76, 380, 26), self.font, value=mission.notes)

        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Save",   self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.dd_status.handle_event(event):
            return
        self.inp_rewards.handle_event(event)
        self.inp_notes.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self._faction_rects):
                if r.collidepoint(event.pos):
                    fid = self._faction_ids[i]
                    if fid in self._selected_factions:
                        self._selected_factions.discard(fid)
                    else:
                        self._selected_factions.add(fid)

        if self.btn_cancel.clicked:
            self.done = True
            self.result = None
        if self.btn_ok.clicked:
            self.result = dict(
                status                = self.dd_status.value,
                rewards               = self.inp_rewards.value.strip(),
                notes                 = self.inp_notes.value.strip(),
                participating_factions= list(self._selected_factions),
            )
            self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50

        self.label(surface, "Status:",  x, y + 7)
        self.label(surface, "Rewards:", x, y + 45)
        self.label(surface, "Notes:",   x, y + 83)
        self.label(surface, "Factions:", x, y + 121, bold=True)

        self.dd_status.draw(surface)
        self.inp_rewards.draw(surface)
        self.inp_notes.draw(surface)

        # Faction toggle grid (2 columns)
        self._faction_rects = []
        col_w = (self.rect.width - 40) // 2
        fy = y + 138
        mouse_pos = pygame.mouse.get_pos()
        for i, (fid, fname) in enumerate(zip(self._faction_ids, self._faction_names)):
            col = i % 2
            row_i = i // 2
            r = pygame.Rect(x + col * col_w, fy + row_i * 22, col_w - 4, 19)
            self._faction_rects.append(r)
            is_sel = fid in self._selected_factions
            if is_sel:
                bg = BTN_ACTIVE
            elif r.collidepoint(mouse_pos):
                bg = BTN_HOVER
            else:
                bg = BTN_NORMAL
            pygame.draw.rect(surface, bg, r, border_radius=2)
            pygame.draw.rect(surface, BORDER_LT, r, 1, border_radius=2)
            surface.blit(self.font_sm.render(fname[:22], True, BTN_TEXT), (r.x + 4, r.y + 3))

        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)
        self.dd_status.draw_overlay(surface)


# ── Adjust Faction Funds dialog ───────────────────────────────────────────────

class AdjustFundsDialog(Dialog):
    W, H = 420, 220

    def __init__(self, screen_size: Tuple[int, int], faction_name: str, current: int):
        super().__init__(f"Adjust Funds: {faction_name}", screen_size)
        self.current = current
        x, y = self.rect.x + 20, self.rect.y + 50

        self.inp_amount = TextInput(pygame.Rect(x + 140, y,      220, 28), self.font,
                                    placeholder="e.g. 5000 or -2000")
        self.inp_reason = TextInput(pygame.Rect(x + 140, y + 38, 240, 28), self.font,
                                    placeholder="optional note")

        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y,  90, 32), "Apply",  self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y,  90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        self.inp_amount.handle_event(event)
        self.inp_reason.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)

        if self.btn_cancel.clicked:
            self.done = True; self.result = None

        if self.btn_ok.clicked:
            try:
                delta = int(self.inp_amount.value.replace(",", "").replace(" ", "") or 0)
            except ValueError:
                return
            self.result = dict(delta=delta, reason=self.inp_reason.value.strip())
            self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, f"Current: {self.current:,} C-Bills", x, y - 14, color=(140, 200, 140))
        self.label(surface, "Amount:",  x, y + 7)
        self.label(surface, "Reason:",  x, y + 45)
        self.label(surface, "(use negative to deduct)", x + 140, y + 60,
                   color=(120, 120, 130))
        self.inp_amount.draw(surface)
        self.inp_reason.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)


# ── Add Structure dialog ──────────────────────────────────────────────────────

class AddStructureDialog(Dialog):
    W, H = 520, 330

    def __init__(self, screen_size: Tuple[int, int], hex_pos: tuple,
                 factions: Dict[str, "Faction"]):
        super().__init__(f"Place Structure at hex {hex_pos}", screen_size)
        self.hex_pos  = hex_pos
        self._fac_ids = [""] + list(factions.keys())
        fac_names     = ["(Neutral)"] + [f.name for f in factions.values()]

        x, y = self.rect.x + 20, self.rect.y + 50
        self.inp_name     = TextInput(pygame.Rect(x + 140, y,       330, 28), self.font,
                                      placeholder="e.g. Fort Defiance")
        self.dd_type      = DropDown( pygame.Rect(x + 140, y + 38,  220, 28), STRUCTURE_TYPES, self.font)
        self.dd_faction   = DropDown( pygame.Rect(x + 140, y + 76,  220, 28), fac_names,       self.font)
        default_supply    = STRUCTURE_SUPPLY_RANGES.get(STRUCTURE_TYPES[0], 0)
        self.inp_supply   = TextInput(pygame.Rect(x + 140, y + 114,  80, 28), self.font,
                                      value=str(default_supply))
        self.inp_notes    = TextInput(pygame.Rect(x + 140, y + 152, 330, 28), self.font,
                                      placeholder="GM notes")
        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Place",  self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)
        self._last_type = STRUCTURE_TYPES[0]

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.dd_type.handle_event(event):    return
        if self.dd_faction.handle_event(event): return
        self.inp_name.handle_event(event)
        self.inp_supply.handle_event(event)
        self.inp_notes.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)

        # Auto-fill supply range when type changes
        if self.dd_type.value != self._last_type:
            self._last_type = self.dd_type.value
            self.inp_supply.value = str(STRUCTURE_SUPPLY_RANGES.get(self.dd_type.value, 0))

        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_ok.clicked:
            try:
                supply = int(self.inp_supply.value or 0)
            except ValueError:
                supply = 0
            self.result = dict(
                name           = self.inp_name.value.strip() or self.dd_type.value,
                structure_type = self.dd_type.value,
                faction_id     = self._fac_ids[self.dd_faction.selected] or None,
                supply_range   = supply,
                notes          = self.inp_notes.value.strip(),
                position       = self.hex_pos,
            )
            self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, "Name:",         x, y + 7)
        self.label(surface, "Type:",         x, y + 45)
        self.label(surface, "Owner:",        x, y + 83)
        self.label(surface, "Supply Range:", x, y + 121)
        self.label(surface, "Notes:",        x, y + 159)
        self.inp_name.draw(surface)
        self.inp_supply.draw(surface)
        self.inp_notes.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)
        self.dd_type.draw(surface)
        self.dd_faction.draw(surface)
        self.dd_type.draw_overlay(surface)
        self.dd_faction.draw_overlay(surface)


# ── Hex Note dialog ───────────────────────────────────────────────────────────

class HexNoteDialog(Dialog):
    W, H = 460, 190

    def __init__(self, screen_size: Tuple[int, int], hex_pos: tuple, existing: str = ""):
        super().__init__(f"GM Note — hex {hex_pos}", screen_size)
        self.hex_pos = hex_pos
        x, y = self.rect.x + 20, self.rect.y + 50
        self.inp_note   = TextInput(pygame.Rect(x, y, self.rect.width - 40, 28), self.font,
                                    placeholder="Secret note visible only in GM view",
                                    value=existing)
        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Save",   self.font)
        self.btn_clear  = Button(pygame.Rect(self.rect.right - 310, btn_y, 90, 32), "Clear",  self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        self.inp_note.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_clear.handle_event(event)
        self.btn_cancel.handle_event(event)
        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_clear.clicked:
            self.result = dict(text="", position=self.hex_pos)
            self.done = True
        if self.btn_ok.clicked:
            self.result = dict(text=self.inp_note.value.strip(), position=self.hex_pos)
            self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, "Note (GM eyes only):", x, y - 16, color=(200, 200, 100))
        self.inp_note.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_clear.draw(surface)
        self.btn_cancel.draw(surface)


# ── Add Group dialog ──────────────────────────────────────────────────────────

class AddGroupDialog(Dialog):
    W, H = 420, 240

    def __init__(self, screen_size: Tuple[int, int], factions: Dict[str, "Faction"]):
        super().__init__("New Lance / Group", screen_size)
        self._fac_ids   = list(factions.keys())
        fac_names       = [f.name for f in factions.values()]
        x, y = self.rect.x + 20, self.rect.y + 50
        self.inp_name   = TextInput(pygame.Rect(x + 110, y,      250, 28), self.font,
                                    placeholder="e.g. Assault Lance Alpha")
        self.dd_faction = DropDown( pygame.Rect(x + 110, y + 38, 220, 28), fac_names, self.font)
        self.inp_notes  = TextInput(pygame.Rect(x + 110, y + 76, 250, 28), self.font,
                                    placeholder="optional notes")
        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Add",    self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.dd_faction.handle_event(event): return
        self.inp_name.handle_event(event)
        self.inp_notes.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)
        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_ok.clicked:
            name = self.inp_name.value.strip()
            if not name or not self._fac_ids:
                return
            self.result = dict(name=name,
                               faction_id=self._fac_ids[self.dd_faction.selected],
                               notes=self.inp_notes.value.strip())
            self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, "Name:",   x, y + 7)
        self.label(surface, "Faction:", x, y + 45)
        self.label(surface, "Notes:",  x, y + 83)
        self.inp_name.draw(surface)
        self.inp_notes.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)
        self.dd_faction.draw(surface)
        self.dd_faction.draw_overlay(surface)


# ── Log Engagement dialog ─────────────────────────────────────────────────────

class LogEngagementDialog(Dialog):
    W, H = 540, 380

    def __init__(self, screen_size: Tuple[int, int], position: tuple,
                 factions: Dict[str, "Faction"]):
        super().__init__(f"Log Engagement at hex {position}", screen_size)
        self.position   = position
        self._fac_ids   = list(factions.keys())
        fac_names       = [f.name for f in factions.values()]
        x, y = self.rect.x + 20, self.rect.y + 50
        self.dd_attacker  = DropDown(pygame.Rect(x + 130, y,       220, 28), fac_names,      self.font)
        self.dd_defender  = DropDown(pygame.Rect(x + 130, y + 38,  220, 28), fac_names,      self.font)
        self.dd_outcome   = DropDown(pygame.Rect(x + 130, y + 76,  260, 28), COMBAT_OUTCOMES, self.font)
        self.inp_casualties = TextInput(pygame.Rect(x + 130, y + 114, 360, 28), self.font,
                                        placeholder="e.g. Atlas destroyed, 2 Mechs crippled")
        self.inp_notes    = TextInput(pygame.Rect(x + 130, y + 152, 360, 28), self.font,
                                      placeholder="narrative notes")
        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Log",    self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.dd_attacker.handle_event(event):  return
        if self.dd_defender.handle_event(event):  return
        if self.dd_outcome.handle_event(event):   return
        self.inp_casualties.handle_event(event)
        self.inp_notes.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)
        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_ok.clicked:
            if not self._fac_ids:
                return
            self.result = dict(
                position     = self.position,
                attacker_fid = self._fac_ids[self.dd_attacker.selected],
                defender_fid = self._fac_ids[self.dd_defender.selected],
                outcome      = self.dd_outcome.value,
                casualties   = self.inp_casualties.value.strip(),
                notes        = self.inp_notes.value.strip(),
            )
            self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, "Attacker:",   x, y + 7)
        self.label(surface, "Defender:",   x, y + 45)
        self.label(surface, "Outcome:",    x, y + 83)
        self.label(surface, "Casualties:", x, y + 121)
        self.label(surface, "Notes:",      x, y + 159)
        self.inp_casualties.draw(surface)
        self.inp_notes.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)
        self.dd_attacker.draw(surface)
        self.dd_defender.draw(surface)
        self.dd_outcome.draw(surface)
        self.dd_outcome.draw_overlay(surface)
        self.dd_defender.draw_overlay(surface)
        self.dd_attacker.draw_overlay(surface)


# ── Scenario Summary dialog ───────────────────────────────────────────────────

class ScenarioSummaryDialog(Dialog):
    """Shows the final force positions before handing off to tabletop BattleTech."""
    W, H = 580, 420

    def __init__(self, screen_size: Tuple[int, int], sub_pos: tuple,
                 op_hex: tuple, campaign, faction_ids: list):
        super().__init__(f"Battle Scenario  —  sub-hex {sub_pos}", screen_size)
        self._lines = self._build(sub_pos, op_hex, campaign, faction_ids)
        by = self.rect.bottom - 52
        self.btn_log   = Button(pygame.Rect(self.rect.x + 20, by, 160, 34), "Log Result...", self.font)
        self.btn_close = Button(pygame.Rect(self.rect.right - 130, by, 110, 34), "Close",
                                self.font, danger=True)

    @staticmethod
    def _build(sub_pos: tuple, op_hex: tuple, campaign, faction_ids: list) -> list:
        from game.hex_grid import Hex, hex_distance
        from game.constants import STATUS_DESTROYED, STATUS_RETREATED
        from game.campaign import get_operational_map
        from game.terrain import terrain_name

        op_map = get_operational_map(campaign, op_hex)
        terrain = terrain_name(op_map.get(sub_pos, "plains"))

        lines = [
            f"  Location : sub-hex {sub_pos} in strategic hex {op_hex}",
            f"  Terrain  : {terrain}",
            "",
        ]
        for fid in faction_ids:
            f = campaign.factions.get(fid)
            fname = f.name if f else fid
            units = [u for u in campaign.units.values()
                     if u.faction_id == fid and u.position == op_hex
                     and u.status not in (STATUS_DESTROYED, STATUS_RETREATED)]
            if not units:
                continue
            lines.append(f"  [{fname}]")
            for u in units:
                if u.sub_position is None:
                    role = "off-map"
                else:
                    d = hex_distance(Hex.from_tuple(sub_pos), Hex.from_tuple(u.sub_position))
                    role = "IN CONTACT" if d == 0 else "flanking" if d == 1 else "support"
                bv = f"BV {u.battle_value:,}" if u.battle_value else "BV ?"
                pos = f"sub{u.sub_position}" if u.sub_position else "(--)"
                lines.append(f"    {u.name[:20]:20s}  {pos}  {role}  [{bv}]")
            lines.append("")
        lines += [
            "  Set up the tabletop with attacking forces entering",
            "  from the edge nearest their sub-hex position.",
        ]
        return lines

    def handle_event(self, event: pygame.event.Event) -> None:
        self.btn_log.handle_event(event)
        self.btn_close.handle_event(event)
        if self.btn_log.clicked:
            self.result = {"action": "log"}
            self.done   = True
        if self.btn_close.clicked:
            self.result = {"action": "close"}
            self.done   = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        fy  = self.rect.y + 52
        fs  = pygame.font.SysFont("monospace", 12)
        fh  = pygame.font.SysFont("monospace", 13, bold=True)
        surface.blit(fh.render("FORCE POSITIONS", True, (255, 200, 80)), (self.rect.x + 20, fy))
        fy += 22
        for line in self._lines:
            col = (255, 180, 60) if line.strip().startswith("[") else \
                  (255, 80,  80) if "IN CONTACT" in line else \
                  (140, 200, 255) if line.strip().startswith("Set up") else \
                  (180, 200, 180)
            surface.blit(fs.render(line, True, col), (self.rect.x + 10, fy))
            fy += 15
        self.btn_log.draw(surface)
        self.btn_close.draw(surface)


# ── Operational Engagement dialog ─────────────────────────────────────────────

class OperationalEngagementDialog(Dialog):
    """Fires when two factions occupy the same op-scale sub-hex.
    Offers auto-resolve (BV-weighted 2d6) or manual logging."""
    W, H = 620, 460

    def __init__(self, screen_size: Tuple[int, int], sub_pos: tuple,
                 factions: Dict[str, "Faction"],
                 units_by_faction: Dict[str, list]):
        super().__init__(f"!! CONTACT !! Sub-hex {sub_pos}", screen_size)
        self._sub_pos = sub_pos
        self._factions = factions
        # Expect exactly two factions (may be more; take first two)
        fac_ids = list(units_by_faction.keys())
        self._fac_a_id   = fac_ids[0]
        self._fac_b_id   = fac_ids[1] if len(fac_ids) > 1 else fac_ids[0]
        self._fac_a_units = units_by_faction[self._fac_a_id]
        self._fac_b_units = units_by_faction.get(self._fac_b_id, [])
        self._fac_a_name  = factions[self._fac_a_id].name if self._fac_a_id in factions else self._fac_a_id
        self._fac_b_name  = factions[self._fac_b_id].name if self._fac_b_id in factions else self._fac_b_id
        self._fac_a_color = factions[self._fac_a_id].color if self._fac_a_id in factions else (180,180,180)
        self._fac_b_color = factions[self._fac_b_id].color if self._fac_b_id in factions else (180,180,180)

        self._resolved    = False
        self._result_lines: List[str] = []
        self._casualties: List[Tuple[str, str]] = []
        self._winner_fid: Optional[str] = None
        self._outcome_str = ""

        bx, by = self.rect.x + 20, self.rect.bottom - 52
        self.btn_auto    = Button(pygame.Rect(bx,       by, 130, 34), "Auto-Resolve", self.font)
        self.btn_manual  = Button(pygame.Rect(bx + 138, by, 130, 34), "Table Fight",  self.font)
        self.btn_apply   = Button(pygame.Rect(bx,       by, 130, 34), "Apply Result", self.font)
        self.btn_cancel  = Button(pygame.Rect(bx + 138, by, 110, 34), "Cancel",       self.font, danger=True)

    # ── resolution ──────────────────────────────────────────────────────────

    def _auto_resolve(self) -> None:
        import random
        from game.constants import (STATUS_DESTROYED, STATUS_RETREATED, STATUS_CRIPPLED,
                                    OUTCOME_ATTACKER_WIN, OUTCOME_DEFENDER_WIN, OUTCOME_DRAW)

        def _bv(units):
            return sum(u.battle_value if u.battle_value else 800 for u in units)

        a_bv = _bv(self._fac_a_units)
        b_bv = _bv(self._fac_b_units)
        total = max(1, a_bv + b_bv)
        a_ratio = a_bv / total

        a_roll  = random.randint(1, 6) + random.randint(1, 6)
        b_roll  = random.randint(1, 6) + random.randint(1, 6)
        bv_mod  = round((a_ratio - 0.5) * 4)
        a_score = a_roll + bv_mod
        b_score = b_roll - bv_mod

        if a_score > b_score:
            winner_name = self._fac_a_name
            self._winner_fid = self._fac_a_id
            loser_units  = self._fac_b_units
            winner_units = self._fac_a_units
            outcome = OUTCOME_ATTACKER_WIN
        elif b_score > a_score:
            winner_name = self._fac_b_name
            self._winner_fid = self._fac_b_id
            loser_units  = self._fac_a_units
            winner_units = self._fac_b_units
            outcome = OUTCOME_DEFENDER_WIN
        else:
            winner_name = "Draw"
            self._winner_fid = None
            loser_units  = self._fac_a_units + self._fac_b_units
            winner_units = []
            outcome = OUTCOME_DRAW

        self._outcome_str = outcome
        lines = [
            f"  {winner_name} wins  (A={a_score} vs B={b_score})",
            f"  BV — {self._fac_a_name}: {a_bv:,}  vs  {self._fac_b_name}: {b_bv:,}",
            "",
        ]
        casualties = []
        for u in loser_units:
            roll = random.randint(2, 12)
            if roll <= 4:
                casualties.append((u.id, STATUS_DESTROYED))
                lines.append(f"  X {u.name[:18]:18s} -> DESTROYED (roll {roll})")
            elif roll <= 7:
                casualties.append((u.id, STATUS_RETREATED))
                lines.append(f"  < {u.name[:18]:18s} -> RETREATED (roll {roll})")
            else:
                casualties.append((u.id, STATUS_CRIPPLED))
                lines.append(f"  ! {u.name[:18]:18s} -> CRIPPLED  (roll {roll})")
        for u in winner_units:
            roll = random.randint(2, 12)
            if roll <= 3:
                casualties.append((u.id, STATUS_CRIPPLED))
                lines.append(f"  ! {u.name[:18]:18s} -> CRIPPLED  (winner dmg, roll {roll})")
            else:
                lines.append(f"  . {u.name[:18]:18s} -> OK")

        self._result_lines = lines
        self._casualties   = casualties
        self._resolved     = True

    # ── events ──────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self._resolved:
            self.btn_auto.handle_event(event)
            self.btn_manual.handle_event(event)
            self.btn_cancel.handle_event(event)
            if self.btn_auto.clicked:
                self._auto_resolve()
            if self.btn_manual.clicked:
                self.result = {"action": "fight_manually",
                               "fac_a_id": self._fac_a_id, "fac_b_id": self._fac_b_id,
                               "sub_pos": self._sub_pos, "casualties": []}
                self.done = True
            if self.btn_cancel.clicked:
                self.done = True
        else:
            self.btn_apply.handle_event(event)
            self.btn_cancel.handle_event(event)
            if self.btn_apply.clicked:
                self.result = {
                    "action":    "auto_resolved",
                    "winner_fid": self._winner_fid,
                    "outcome":    self._outcome_str,
                    "fac_a_id":  self._fac_a_id,
                    "fac_b_id":  self._fac_b_id,
                    "sub_pos":   self._sub_pos,
                    "casualties": self._casualties,
                    "casualty_text": "; ".join(l.strip() for l in self._result_lines if l.strip()),
                }
                self.done = True
            if self.btn_cancel.clicked:
                self.done = True

    # ── drawing ─────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        rx, ry = self.rect.x, self.rect.y
        fw = self.rect.width

        if not self._resolved:
            # Two-column layout
            col_w = (fw - 48) // 2
            ax, bx = rx + 16, rx + 16 + col_w + 16

            def _draw_side(cx, fac_name, fac_color, units):
                y = ry + 52
                col_rect = pygame.Rect(cx, y - 4, col_w, self.rect.height - 100)
                pygame.draw.rect(surface, (25, 25, 35), col_rect, border_radius=4)
                pygame.draw.rect(surface, fac_color, col_rect, 1, border_radius=4)

                fn = pygame.font.SysFont("monospace", 13, bold=True)
                nm = fn.render(fac_name[:22], True, fac_color)
                surface.blit(nm, (cx + 8, y + 2)); y += 22

                bv_total = 0
                fsm = pygame.font.SysFont("monospace", 11)
                for u in units:
                    bv = u.battle_value or 0
                    bv_total += bv
                    bv_color = (160, 200, 160) if bv else (120, 120, 130)
                    bv_str   = f"{bv:,}" if bv else "?BV"
                    lbl = fsm.render(f"  {u.name[:18]}", True, (200, 200, 210))
                    surface.blit(lbl, (cx + 4, y)); y += 13
                    bv_lbl = fsm.render(f"    BV {bv_str}  [{u.unit_type[:3]}]", True, bv_color)
                    surface.blit(bv_lbl, (cx + 4, y)); y += 14

                pygame.draw.line(surface, fac_color, (cx + 8, y + 2), (cx + col_w - 8, y + 2), 1)
                y += 8
                tot = fn.render(f"Total BV: {bv_total:,}", True, fac_color)
                surface.blit(tot, (cx + 8, y))

            _draw_side(ax, self._fac_a_name, self._fac_a_color, self._fac_a_units)
            _draw_side(bx, self._fac_b_name, self._fac_b_color, self._fac_b_units)

            # vs label
            vs = pygame.font.SysFont("monospace", 18, bold=True).render("VS", True, (200, 60, 60))
            surface.blit(vs, vs.get_rect(center=(rx + fw // 2, ry + 140)))

            self.btn_auto.draw(surface)
            self.btn_manual.draw(surface)
            self.btn_cancel.draw(surface)

        else:
            # Result panel
            fy = ry + 52
            fs = pygame.font.SysFont("monospace", 12)
            fh = pygame.font.SysFont("monospace", 13, bold=True)
            wc = (100, 220, 100) if self._winner_fid else (200, 160, 60)
            surface.blit(fh.render("ENGAGEMENT RESULT", True, wc), (rx + 20, fy)); fy += 22
            for line in self._result_lines:
                col = (220, 80, 80) if line.strip().startswith("X") else \
                      (200, 160, 60) if line.strip().startswith(("<", "!")) else \
                      (100, 200, 120) if line.strip().startswith(".") else \
                      (180, 200, 255)
                surface.blit(fs.render(line, True, col), (rx + 20, fy)); fy += 14

            self.btn_apply.draw(surface)
            self.btn_cancel.draw(surface)


# ── Add Objective dialog ──────────────────────────────────────────────────────

class AddObjectiveDialog(Dialog):
    W, H = 460, 260

    def __init__(self, screen_size: Tuple[int, int], position: tuple):
        super().__init__(f"Place Objective at hex {position}", screen_size)
        self.position  = position
        x, y = self.rect.x + 20, self.rect.y + 50
        self.inp_name  = TextInput(pygame.Rect(x + 110, y,      300, 28), self.font,
                                   placeholder="e.g. Hilltop Firebase")
        self.inp_vp    = TextInput(pygame.Rect(x + 110, y + 38,  80, 28), self.font, value="1")
        self.inp_notes = TextInput(pygame.Rect(x + 110, y + 76, 300, 28), self.font,
                                   placeholder="optional notes")
        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Place",  self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        self.inp_name.handle_event(event)
        self.inp_vp.handle_event(event)
        self.inp_notes.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)
        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_ok.clicked:
            name = self.inp_name.value.strip() or "Objective"
            try:
                vp = max(0, int(self.inp_vp.value or 1))
            except ValueError:
                vp = 1
            self.result = dict(name=name, position=self.position,
                               vp_value=vp, notes=self.inp_notes.value.strip())
            self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, "Name:",     x, y + 7)
        self.label(surface, "VP Value:", x, y + 45)
        self.label(surface, "Notes:",    x, y + 83)
        self.inp_name.draw(surface)
        self.inp_vp.draw(surface)
        self.inp_notes.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)


# ── Resolve Objective dialog ──────────────────────────────────────────────────

class ResolveObjectiveDialog(Dialog):
    W, H = 480, 300

    def __init__(self, screen_size: Tuple[int, int], objective: Objective,
                 factions: Dict[str, "Faction"]):
        super().__init__(f"Objective: {objective.name}", screen_size)
        self.objective  = objective
        self._fac_ids   = [""] + list(factions.keys())
        fac_names       = ["(None)"] + [f.name for f in factions.values()]
        x, y = self.rect.x + 20, self.rect.y + 50
        try:
            status_idx = OBJECTIVE_STATUSES.index(objective.status)
        except ValueError:
            status_idx = 0
        try:
            fac_idx = self._fac_ids.index(objective.faction_id or "")
        except ValueError:
            fac_idx = 0
        self.dd_status  = DropDown(pygame.Rect(x + 110, y,      200, 28), OBJECTIVE_STATUSES, self.font,
                                   selected=status_idx)
        self.dd_faction = DropDown(pygame.Rect(x + 110, y + 38, 220, 28), fac_names, self.font,
                                   selected=fac_idx)
        self.inp_notes  = TextInput(pygame.Rect(x + 110, y + 76, 320, 28), self.font,
                                    value=objective.notes)
        btn_y = self.rect.bottom - 48
        self.btn_ok     = Button(pygame.Rect(self.rect.right - 210, btn_y, 90, 32), "Save",   self.font)
        self.btn_cancel = Button(pygame.Rect(self.rect.right - 110, btn_y, 90, 32), "Cancel", self.font, danger=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.dd_status.handle_event(event):  return
        if self.dd_faction.handle_event(event): return
        self.inp_notes.handle_event(event)
        self.btn_ok.handle_event(event)
        self.btn_cancel.handle_event(event)
        if self.btn_cancel.clicked:
            self.done = True; self.result = None
        if self.btn_ok.clicked:
            fid = self._fac_ids[self.dd_faction.selected] or None
            self.result = dict(status=self.dd_status.value,
                               faction_id=fid,
                               notes=self.inp_notes.value.strip())
            self.done = True

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_frame(surface)
        x, y = self.rect.x + 20, self.rect.y + 50
        self.label(surface, "Status:",      x, y + 7)
        self.label(surface, "Controlled by:", x, y + 45)
        self.label(surface, "Notes:",       x, y + 83)
        self.inp_notes.draw(surface)
        self.btn_ok.draw(surface)
        self.btn_cancel.draw(surface)
        self.dd_status.draw(surface)
        self.dd_faction.draw(surface)
        self.dd_faction.draw_overlay(surface)
        self.dd_status.draw_overlay(surface)
