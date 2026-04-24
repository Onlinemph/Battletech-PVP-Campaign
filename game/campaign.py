"""Campaign operations: creation, persistence, and turn management."""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from game.constants import DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT
from game.map_gen import generate_map, generate_operational_map
from game.models import Campaign, Faction, Unit, Mission, new_id
from game.constants import *

SAVES_DIR = Path(__file__).parent.parent / "saves"


# ── Factory ───────────────────────────────────────────────────────────────────

def new_campaign(
    name:        str,
    map_width:   int   = DEFAULT_MAP_WIDTH,
    map_height:  int   = DEFAULT_MAP_HEIGHT,
    seed:        int   = 0,
    water_ratio: float = 0.38,
) -> Campaign:
    import random
    if seed == 0:
        seed = random.randint(1, 999_999)

    terrain = generate_map(map_width, map_height, seed=seed, water_ratio=water_ratio)
    return Campaign(
        name=name,
        map_width=map_width,
        map_height=map_height,
        map_seed=seed,
        terrain_map=terrain,
    )


# ── Operational sub-map ───────────────────────────────────────────────────────

def get_operational_map(campaign: Campaign, strategic_hex: tuple) -> dict:
    """Return (or generate and cache) the operational sub-map for a strategic hex."""
    key = f"{strategic_hex[0]},{strategic_hex[1]}"
    if key not in campaign.op_maps:
        parent_terrain = campaign.terrain_map.get(strategic_hex, TERRAIN_PLAINS)
        campaign.op_maps[key] = generate_operational_map(
            parent_terrain, strategic_hex, campaign.map_seed
        )
    return campaign.op_maps[key]


# ── Persistence ───────────────────────────────────────────────────────────────

def save_campaign(campaign: Campaign, path: Optional[Path] = None) -> Path:
    SAVES_DIR.mkdir(exist_ok=True)
    if path is None:
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in campaign.name)
        path = SAVES_DIR / f"{safe}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(campaign.to_dict(), f, indent=2)
    return path


def load_campaign(path: Path) -> Campaign:
    with open(path, "r", encoding="utf-8") as f:
        return Campaign.from_dict(json.load(f))


def list_saves() -> list[Path]:
    SAVES_DIR.mkdir(exist_ok=True)
    return sorted(SAVES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def add_faction(campaign: Campaign, name: str, color: tuple, player_name: str = "") -> Faction:
    f = Faction.new(name, color, player_name)
    campaign.factions[f.id] = f
    return f


def add_unit(
    campaign:     Campaign,
    name:         str,
    faction_id:   str,
    unit_type:    str,
    position:     Optional[tuple] = None,
    vision_range: Optional[int]   = None,
) -> Unit:
    u = Unit.new(name, faction_id, unit_type)
    u.position = position
    if vision_range is not None:
        u.vision_range = vision_range
    campaign.units[u.id] = u
    return u


def add_mission(
    campaign:     Campaign,
    name:         str,
    mission_type: str,
    position:     tuple,
) -> Mission:
    m = Mission.new(name, mission_type, position, campaign.current_turn)
    campaign.missions[m.id] = m
    return m


def next_turn(campaign: Campaign) -> int:
    campaign.current_turn += 1
    return campaign.current_turn
