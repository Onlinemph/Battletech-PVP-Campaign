"""Fog-of-war, LOS, and supply calculations."""
from typing import Dict, Optional, Set, Tuple

from game.hex_grid import Hex, hex_range, hex_line, hex_distance
from game.models import Campaign, Unit
from game.constants import (STATUS_DESTROYED, STATUS_RETREATED,
                             TERRAIN_FOREST, UNIT_AEROSPACE,
                             UNIT_DROPSHIP, DROPSHIP_SUPPLY_RANGE, PHASE_NIGHT,
                             ELEVATION_VISION_DIV)
from game.terrain import TERRAIN


def visible_hexes(campaign: Campaign, faction_id: str) -> Set[Tuple[int, int]]:
    """
    Return the set of strategic hexes currently visible to faction_id.

    Rules:
    - Blocking terrain (blocks_vision=True) in intermediate hexes cuts LOS
      for ground units; aerospace ignore this.
    - Forest in the TARGET hex reduces effective range by 1 for all units
      (forest canopy conceals ground forces from both ground and air obs).
    """
    visible: Set[Tuple[int, int]] = set()
    for unit in campaign.units.values():
        if unit.faction_id != faction_id:
            continue
        if unit.status in (STATUS_DESTROYED, STATUS_RETREATED):
            continue
        if unit.position is None:
            continue
        center   = Hex.from_tuple(unit.position)
        is_aero  = unit.unit_type == UNIT_AEROSPACE
        vrange   = unit.vision_range
        # High-ground bonus: +1 vision per ELEVATION_VISION_DIV levels
        elev = campaign.elevation_map.get(unit.position, 3)
        vrange += elev // ELEVATION_VISION_DIV
        if campaign.current_phase == PHASE_NIGHT and not is_aero:
            vrange = max(0, vrange - 1)

        for h in hex_range(center, vrange):
            key  = h.to_tuple()
            dist = hex_distance(center, h)

            # LOS: check intermediate hexes for blocking terrain
            if dist > 1 and not is_aero:
                line    = hex_line(center, h)
                blocked = False
                for mid in line[1:-1]:
                    tdef = TERRAIN.get(campaign.terrain_map.get(mid.to_tuple(), ""))
                    if tdef and tdef.blocks_vision:
                        blocked = True
                        break
                if blocked:
                    continue

            # Forest concealment: target hex in forest → -1 effective range
            if dist > 0:
                target_terrain = campaign.terrain_map.get(key, "")
                if target_terrain == TERRAIN_FOREST and dist >= vrange:
                    continue

            visible.add(key)

    return visible


def get_contact_hexes(campaign: Campaign) -> Dict[Tuple[int, int], list]:
    """Return dict of hex → [faction_ids] for hexes with 2+ factions present."""
    hex_factions: Dict[Tuple[int, int], set] = {}
    for u in campaign.units.values():
        if u.position and u.status not in (STATUS_DESTROYED, STATUS_RETREATED):
            hex_factions.setdefault(u.position, set()).add(u.faction_id)
    return {pos: list(fids) for pos, fids in hex_factions.items() if len(fids) >= 2}


def visible_units(
    campaign:   Campaign,
    faction_id: str,
    vis_hexes:  Optional[Set[Tuple[int, int]]] = None,
) -> Dict[str, Unit]:
    """Own units always included; enemy units only if their hex is visible."""
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
    campaign:   Campaign,
    faction_id: str,
    vis_hexes:  Optional[Set[Tuple[int, int]]] = None,
) -> list:
    """Missions in vision range OR assigned to this faction."""
    if vis_hexes is None:
        vis_hexes = visible_hexes(campaign, faction_id)
    return [
        m for m in campaign.missions.values()
        if m.position in vis_hexes or faction_id in m.participating_factions
    ]


def visible_structures(
    campaign:   Campaign,
    faction_id: str,
    vis_hexes:  Optional[Set[Tuple[int, int]]] = None,
) -> dict:
    """Structures in visible hexes."""
    if vis_hexes is None:
        vis_hexes = visible_hexes(campaign, faction_id)
    return {s.id: s for s in campaign.structures.values() if s.position in vis_hexes}


def has_supply_sources(campaign: Campaign, faction_id: str) -> bool:
    """True if this faction has at least one active supply source."""
    for u in campaign.units.values():
        if (u.faction_id == faction_id and u.unit_type == UNIT_DROPSHIP
                and u.status not in (STATUS_DESTROYED, STATUS_RETREATED)
                and u.position is not None):
            return True
    for s in campaign.structures.values():
        if s.faction_id == faction_id and s.supply_range > 0:
            return True
    return False


def supplied_units(campaign: Campaign, faction_id: str) -> Set[str]:
    """Return IDs of units within supply range of a friendly source."""
    sources = []
    for u in campaign.units.values():
        if (u.faction_id == faction_id and u.unit_type == UNIT_DROPSHIP
                and u.position and u.status not in (STATUS_DESTROYED, STATUS_RETREATED)):
            sources.append((u.position, DROPSHIP_SUPPLY_RANGE))
    for s in campaign.structures.values():
        if s.faction_id == faction_id and s.supply_range > 0 and s.position:
            sources.append((s.position, s.supply_range))

    if not sources:
        return set()

    result: Set[str] = set()
    for uid, u in campaign.units.items():
        if u.faction_id != faction_id or u.position is None:
            continue
        center = Hex.from_tuple(u.position)
        for src_pos, src_range in sources:
            if hex_distance(center, Hex.from_tuple(src_pos)) <= src_range:
                result.add(uid)
                break
    return result
