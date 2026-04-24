"""Fog-of-war and visibility calculations."""
from typing import Dict, Optional, Set, Tuple

from game.hex_grid import Hex, hex_range
from game.models import Campaign, Unit
from game.constants import STATUS_DESTROYED, STATUS_RETREATED, TERRAIN_MOUNTAINS, TERRAIN_FOREST


def visible_hexes(campaign: Campaign, faction_id: str) -> Set[Tuple[int, int]]:
    """
    Return the set of strategic hexes currently visible to `faction_id`.
    Vision = union of hex_range(unit.position, unit.vision_range) for all
    active units belonging to that faction.
    """
    visible: Set[Tuple[int, int]] = set()
    for unit in campaign.units.values():
        if unit.faction_id != faction_id:
            continue
        if unit.status in (STATUS_DESTROYED, STATUS_RETREATED):
            continue
        if unit.position is None:
            continue
        center = Hex.from_tuple(unit.position)
        for h in hex_range(center, unit.vision_range):
            visible.add(h.to_tuple())
    return visible


def visible_units(
    campaign: Campaign,
    faction_id: str,
    vis_hexes: Optional[Set[Tuple[int, int]]] = None,
) -> Dict[str, Unit]:
    """
    Return units visible to `faction_id`:
    - Always includes own units.
    - Includes enemy units whose position is inside faction's vision.
    """
    if vis_hexes is None:
        vis_hexes = visible_hexes(campaign, faction_id)

    result: Dict[str, Unit] = {}
    for uid, unit in campaign.units.items():
        if unit.faction_id == faction_id:
            result[uid] = unit
        elif unit.position is not None and unit.position in vis_hexes:
            result[uid] = unit
    return result


def visible_missions(
    campaign: Campaign,
    faction_id: str,
    vis_hexes: Optional[Set[Tuple[int, int]]] = None,
) -> list:
    """Missions visible to a faction (in their vision or they participate)."""
    if vis_hexes is None:
        vis_hexes = visible_hexes(campaign, faction_id)

    result = []
    for mission in campaign.missions.values():
        if (mission.position in vis_hexes or
                faction_id in mission.participating_factions):
            result.append(mission)
    return result
