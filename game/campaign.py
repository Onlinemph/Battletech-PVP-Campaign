"""Campaign operations: creation, persistence, and turn management."""
import heapq
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from game.constants import DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT
from game.map_gen import generate_map, generate_elevation_map, generate_operational_map, generate_tactical_map
from game.models import Campaign, Faction, Unit, Mission, Structure, Group, Objective, new_id
from game.constants import *


# ── Movement helpers (BT 4-hour phase math) ──────────────────────────────────

def walk_mp_to_move_points(walk_mp: int) -> float:
    """Float movement budget in plains-hex equivalents per strategic phase.
    Formula: walk_mp × 86.4 km/8h ÷ HOURS_PER_PHASE ÷ 18 km/hex."""
    return walk_mp * 86.4 / HOURS_PER_PHASE / 18


def walk_mp_to_strategic(walk_mp: int) -> int:
    """Strategic hexes per phase through open plains (rounded)."""
    return max(1, round(walk_mp_to_move_points(walk_mp)))


def walk_mp_to_op_range(walk_mp: int) -> int:
    """Operational hexes per sub-turn for pre-battle positioning (gameplay-scaled)."""
    return max(1, walk_mp // 2)


def strategic_reachable(campaign, position: tuple, walk_mp: int,
                        unit_type: str = "BattleMech") -> set:
    """Dijkstra flood-fill: all strategic hexes reachable within one phase.
    Terrain costs from TERRAIN_MOVE_COST; Aerospace/DropShip ignore terrain."""
    budget = walk_mp_to_move_points(walk_mp)
    if budget <= 0:
        return {position}

    from game.hex_grid import Hex, hex_range, hex_neighbors

    # Aerospace and DropShip fly over everything — simple radius
    if unit_type in (UNIT_AEROSPACE, UNIT_DROPSHIP):
        r = max(1, round(budget))
        return {h.to_tuple() for h in hex_range(Hex.from_tuple(position), r)}

    elev_map  = campaign.elevation_map
    dist = {position: 0.0}
    heap = [(0.0, position)]
    reachable = {position}
    while heap:
        cost, pos = heapq.heappop(heap)
        if cost > dist.get(pos, float("inf")) + 1e-9:
            continue
        cur_elev = elev_map.get(pos, 3)
        for nb in hex_neighbors(Hex.from_tuple(pos)):
            nb_t = nb.to_tuple()
            terrain = campaign.terrain_map.get(nb_t, TERRAIN_PLAINS)
            entry_cost = TERRAIN_MOVE_COST.get(terrain)
            if entry_cost is None:
                continue  # impassable (deep water, etc.)
            # Slope penalty: steep grades cost extra; cliffs are impassable
            delta = abs(elev_map.get(nb_t, 3) - cur_elev)
            if delta >= SLOPE_IMPASSABLE:
                continue
            entry_cost += delta * SLOPE_COST_PER_LEVEL
            new_cost = cost + entry_cost
            if new_cost <= budget + 1e-9 and new_cost < dist.get(nb_t, float("inf")) - 1e-9:
                dist[nb_t] = new_cost
                reachable.add(nb_t)
                heapq.heappush(heap, (new_cost, nb_t))
    return reachable

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

    terrain   = generate_map(map_width, map_height, seed=seed, water_ratio=water_ratio)
    elevation = generate_elevation_map(terrain, seed)
    return Campaign(
        name=name,
        map_width=map_width,
        map_height=map_height,
        map_seed=seed,
        terrain_map=terrain,
        elevation_map=elevation,
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


def get_tactical_map(campaign: Campaign, strategic_hex: tuple, sub_hex: tuple) -> dict:
    """Return (or generate and cache) the mapsheet-level sub-map for one low-alt hex."""
    key = f"{strategic_hex[0]},{strategic_hex[1]}|{sub_hex[0]},{sub_hex[1]}"
    if key not in campaign.tac_maps:
        op_map = get_operational_map(campaign, strategic_hex)
        parent_terrain = op_map.get(sub_hex, TERRAIN_PLAINS)
        campaign.tac_maps[key] = generate_tactical_map(
            parent_terrain, key, campaign.map_seed
        )
    return campaign.tac_maps[key]


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
    log_event(campaign, "faction_added", f"Faction added: {f.name}")
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
    log_event(campaign, "unit_added", f"Unit added: {u.name} [{u.unit_type}]")
    return u


def add_structure(
    campaign:       Campaign,
    name:           str,
    structure_type: str,
    position:       tuple,
    faction_id:     Optional[str] = None,
    supply_range:   int = 0,
) -> "Structure":
    s = Structure.new(name, structure_type, position, faction_id, supply_range)
    campaign.structures[s.id] = s
    owner = campaign.factions[faction_id].name if faction_id and faction_id in campaign.factions else "neutral"
    log_event(campaign, "structure_built",
              f"{s.structure_type} '{s.name}' placed ({owner})")
    return s


def add_mission(
    campaign:     Campaign,
    name:         str,
    mission_type: str,
    position:     tuple,
) -> Mission:
    m = Mission.new(name, mission_type, position, campaign.current_turn)
    campaign.missions[m.id] = m
    log_event(campaign, "mission_created", f"Mission created: {m.name} ({m.mission_type})")
    return m


def add_group(campaign: Campaign, name: str, faction_id: str) -> Group:
    g = Group.new(name, faction_id)
    campaign.groups[g.id] = g
    log_event(campaign, "group_added", f"Group added: {g.name}")
    return g


def add_objective(campaign: Campaign, name: str, position: tuple,
                  vp_value: int = 1) -> Objective:
    o = Objective.new(name, position, vp_value)
    campaign.objectives[o.id] = o
    log_event(campaign, "objective_placed", f"Objective '{o.name}' ({o.vp_value} VP)")
    return o


def log_combat(campaign: Campaign, position: tuple, attacker_fid: str,
               defender_fid: str, outcome: str,
               casualties: str = "", notes: str = "") -> dict:
    entry = {
        "id":           new_id(),
        "turn":         campaign.current_turn,
        "position":     list(position),
        "attacker_fid": attacker_fid,
        "defender_fid": defender_fid,
        "outcome":      outcome,
        "casualties":   casualties,
        "notes":        notes,
    }
    campaign.combat_log.append(entry)
    if len(campaign.combat_log) > 200:
        campaign.combat_log = campaign.combat_log[-200:]
    atk = campaign.factions.get(attacker_fid)
    dfn = campaign.factions.get(defender_fid)
    log_event(campaign, "combat_resolved",
              f"{atk.name if atk else '?'} vs {dfn.name if dfn else '?'} -> {outcome}")
    return entry


def next_phase(campaign: Campaign) -> tuple:
    """Advance Morning→Afternoon→Night→next Day Morning.
    End-of-day hooks run only on night→morning transition."""
    idx = PHASES.index(campaign.current_phase) if campaign.current_phase in PHASES else 0
    if idx + 1 < len(PHASES):
        campaign.current_phase = PHASES[idx + 1]
    else:
        campaign.current_phase = PHASE_MORNING
        update_explored(campaign)
        _log_supply_warnings(campaign)
        _update_territory(campaign)
        _process_income(campaign)
        campaign.current_turn += 1

    for u in campaign.units.values():
        u.has_moved = False

    _detect_contacts(campaign)
    _detect_sensor_contacts(campaign)
    abbr = PHASE_ABBR.get(campaign.current_phase, "??")
    log_event(campaign, f"phase_{campaign.current_phase}",
              f"Day {campaign.current_turn} · {abbr} begins")
    return campaign.current_turn, campaign.current_phase


def next_turn(campaign: Campaign) -> int:
    """Advance a full day (3 phases). Kept for backward compatibility."""
    for _ in range(3):
        next_phase(campaign)
    return campaign.current_turn


def next_op_turn(campaign: Campaign) -> tuple:
    """Advance one 1-hour operational sub-turn.
    After OP_TURNS_PER_PHASE sub-turns, the strategic phase advances automatically.
    Returns (day, phase, op_turn_index)."""
    campaign.op_turn += 1
    if campaign.op_turn >= OP_TURNS_PER_PHASE:
        campaign.op_turn = 0
        next_phase(campaign)
    else:
        _detect_op_contacts(campaign)
        log_event(campaign, "op_turn_advanced",
                  f"Hour {campaign.op_turn}/{OP_TURNS_PER_PHASE} of "
                  f"Day {campaign.current_turn} · "
                  f"{PHASE_ABBR.get(campaign.current_phase, '?')}")
    return campaign.current_turn, campaign.current_phase, campaign.op_turn


def _detect_op_contacts(campaign: Campaign) -> None:
    """Detect units from opposing factions sharing the same sub_position in a strategic hex."""
    sub_factions: dict = {}
    for u in campaign.units.values():
        if (u.position and u.sub_position
                and u.status not in (STATUS_DESTROYED, STATUS_RETREATED)):
            key = (u.position, u.sub_position)
            sub_factions.setdefault(key, set()).add(u.faction_id)
    for key, fids in sub_factions.items():
        if len(fids) >= 2:
            strat, sub = key
            names = [campaign.factions[f].name if f in campaign.factions else f
                     for f in fids]
            log_event(campaign, "op_contact",
                      f"Tactical contact at ({strat[0]},{strat[1]}) "
                      f"sub({sub[0]},{sub[1]}): {' vs '.join(names)}")


def _detect_contacts(campaign: Campaign) -> None:
    """Detect hexes shared by 2+ factions and log new contacts."""
    hex_factions: dict = {}
    for u in campaign.units.values():
        if u.position and u.status not in (STATUS_DESTROYED, STATUS_RETREATED):
            hex_factions.setdefault(u.position, set()).add(u.faction_id)

    new_contacts: dict = {}
    for pos, fids in hex_factions.items():
        if len(fids) >= 2:
            key = f"{pos[0]},{pos[1]}"
            new_contacts[key] = list(fids)

    for key, fids in new_contacts.items():
        if key not in campaign.active_contacts:
            names = [campaign.factions[f].name if f in campaign.factions else f
                     for f in fids]
            q, r = (int(x) for x in key.split(","))
            log_event(campaign, "contact_detected",
                      f"Contact ({q},{r}): {' vs '.join(names)}")

    campaign.active_contacts = new_contacts


def _detect_sensor_contacts(campaign: Campaign) -> None:
    """Log when faction A can see an enemy unit in a different hex."""
    from game.vision import visible_hexes
    faction_ids = list(campaign.factions.keys())
    reported: set = set()
    for i, fid_a in enumerate(faction_ids):
        vis_a = visible_hexes(campaign, fid_a)
        for fid_b in faction_ids[i + 1:]:
            for u in campaign.units.values():
                if (u.faction_id == fid_b and u.position is not None
                        and u.position in vis_a
                        and u.status not in (STATUS_DESTROYED, STATUS_RETREATED)):
                    pair_key = tuple(sorted([fid_a, fid_b]))
                    if pair_key not in reported:
                        fa = campaign.factions.get(fid_a)
                        fb = campaign.factions.get(fid_b)
                        log_event(campaign, "sensor_contact",
                                  f"{fa.name if fa else fid_a} sensors detect "
                                  f"{fb.name if fb else fid_b}")
                        reported.add(pair_key)
                    break


def _log_supply_warnings(campaign: Campaign) -> None:
    from game.vision import supplied_units, has_supply_sources
    for faction_id in campaign.factions:
        if not has_supply_sources(campaign, faction_id):
            continue
        sup = supplied_units(campaign, faction_id)
        for uid, u in campaign.units.items():
            if (u.faction_id == faction_id and u.position is not None
                    and uid not in sup):
                log_event(campaign, "supply_warning",
                          f"{u.name} is out of supply range")


def update_explored(campaign: Campaign) -> None:
    """Snapshot each faction's current visibility into their explored set."""
    from game.vision import visible_hexes
    for faction_id in campaign.factions:
        vis = visible_hexes(campaign, faction_id)
        if faction_id not in campaign.explored_hexes:
            campaign.explored_hexes[faction_id] = set()
        campaign.explored_hexes[faction_id].update(vis)


def compute_daily_income(campaign: Campaign, faction_id: str) -> dict:
    """Return {income, maintenance, net} for a faction for one day."""
    income = 0
    for key, fid in campaign.hex_control.items():
        if fid == faction_id:
            q, r = (int(x) for x in key.split(","))
            terrain = campaign.terrain_map.get((q, r), "")
            income += TERRAIN_INCOME.get(terrain, 0)
    for s in campaign.structures.values():
        if s.faction_id == faction_id and s.status == STATUS_ACTIVE:
            income += STRUCTURE_INCOME.get(s.structure_type, 0)
    maintenance = sum(
        UNIT_MAINTENANCE.get(u.unit_type, 0)
        for u in campaign.units.values()
        if u.faction_id == faction_id
        and u.status not in (STATUS_DESTROYED, STATUS_RETREATED)
    )
    return {"income": income, "maintenance": maintenance, "net": income - maintenance}


def _process_income(campaign: Campaign) -> None:
    """Apply daily income and maintenance to all factions at end of day."""
    for faction_id, f in campaign.factions.items():
        bd = compute_daily_income(campaign, faction_id)
        f.resources += bd["net"]
        sign = "+" if bd["net"] >= 0 else ""
        log_event(campaign, "income",
                  f"{f.name}: +{bd['income']:,} income  "
                  f"-{bd['maintenance']:,} maint  "
                  f"= {sign}{bd['net']:,} C-Bills")


def _update_territory(campaign: Campaign) -> None:
    """Auto-capture hexes occupied exclusively by one faction's active units.
    Also auto-captures any objectives on those hexes."""
    from typing import Set as _Set
    occupied: dict = {}
    for u in campaign.units.values():
        if u.position and u.status not in (STATUS_DESTROYED, STATUS_RETREATED):
            occupied.setdefault(u.position, set()).add(u.faction_id)
    for pos, fids in occupied.items():
        key = f"{pos[0]},{pos[1]}"
        if len(fids) == 1:
            fid = next(iter(fids))
            if campaign.hex_control.get(key) != fid:
                campaign.hex_control[key] = fid
                f = campaign.factions.get(fid)
                log_event(campaign, "territory_captured",
                          f"{f.name if f else fid} captured ({pos[0]},{pos[1]})")
            # Auto-capture any objectives sitting in this uncontested hex
            for o in campaign.objectives.values():
                if o.position == pos and o.faction_id != fid:
                    o.faction_id = fid
                    o.status     = OBJECTIVE_CAPTURED
                    f = campaign.factions.get(fid)
                    log_event(campaign, "objective_captured",
                              f"{f.name if f else fid} seized '{o.name}' ({o.vp_value} VP)")


def log_event(campaign: Campaign, event: str, detail: str) -> None:
    campaign.event_log.append({
        "turn":   campaign.current_turn,
        "phase":  campaign.current_phase,
        "event":  event,
        "detail": detail,
    })
    if len(campaign.event_log) > 100:
        campaign.event_log = campaign.event_log[-100:]
