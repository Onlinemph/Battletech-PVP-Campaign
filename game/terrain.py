"""Terrain type definitions with display and gameplay properties."""
from dataclasses import dataclass
from typing import Dict, Tuple
from game.constants import *


@dataclass(frozen=True)
class TerrainDef:
    name:          str
    color:         Tuple[int, int, int]   # RGB for map display
    movement_cost: float                  # multiplier (1.0 = normal)
    cover:         int                    # 0–3 cover bonus
    elevation:     int                    # relative elevation level
    blocks_vision: bool
    passable:      bool
    symbol:        str                    # 1-char map symbol for text export


TERRAIN: Dict[str, TerrainDef] = {
    TERRAIN_DEEP_WATER: TerrainDef(
        "Deep Water",   (15,  50, 120),  99.0, 0, -2, False, False, "~"),
    TERRAIN_WATER: TerrainDef(
        "Water",        (40,  90, 180),   3.0, 0, -1, False, True,  "w"),
    TERRAIN_COAST: TerrainDef(
        "Coast",        (210,190, 130),   1.5, 0,  0, False, True,  "."),
    TERRAIN_PLAINS: TerrainDef(
        "Plains",       (110,160,  70),   1.0, 0,  1, False, True,  " "),
    TERRAIN_FOREST: TerrainDef(
        "Forest",       ( 30, 90,  30),   2.0, 2,  1, True,  True,  "T"),
    TERRAIN_HILLS: TerrainDef(
        "Hills",        (150,120,  60),   2.0, 1,  2, True,  True,  "h"),
    TERRAIN_MOUNTAINS: TerrainDef(
        "Mountains",    ( 90, 70,  60),   4.0, 2,  3, True,  True,  "M"),
    TERRAIN_URBAN: TerrainDef(
        "Urban",        (160,140, 140),   2.0, 3,  1, True,  True,  "U"),
    TERRAIN_INDUSTRIAL: TerrainDef(
        "Industrial",   (130, 90,  90),   2.0, 2,  1, True,  True,  "I"),
    TERRAIN_DESERT: TerrainDef(
        "Desert",       (210,175,  90),   1.5, 0,  1, False, True,  "d"),
    TERRAIN_ARCTIC: TerrainDef(
        "Arctic",       (215,230, 245),   2.5, 0,  1, False, True,  "A"),
    TERRAIN_VOLCANIC: TerrainDef(
        "Volcanic",     (100, 30,  10),   3.0, 0,  2, False, True,  "V"),
}


def terrain_color(terrain_id: str) -> Tuple[int, int, int]:
    return TERRAIN.get(terrain_id, TERRAIN[TERRAIN_PLAINS]).color


def terrain_name(terrain_id: str) -> str:
    return TERRAIN.get(terrain_id, TERRAIN[TERRAIN_PLAINS]).name
