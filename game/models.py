"""Data classes for all campaign entities."""
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from game.constants import *


def new_id() -> str:
    return str(uuid.uuid4())[:8]


# ── Roster ────────────────────────────────────────────────────────────────────

@dataclass
class RosterEntry:
    chassis:  str           # e.g. "Atlas AS7-D"
    pilot:    str           # pilot name
    tonnage:  int = 0
    status:   str = STATUS_ACTIVE
    notes:    str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "RosterEntry":
        return cls(**d)


# ── Unit ──────────────────────────────────────────────────────────────────────

@dataclass
class Unit:
    id:           str
    name:         str
    faction_id:   str
    unit_type:    str                           # UNIT_* constant
    status:       str = STATUS_ACTIVE
    # Strategic position (axial q,r); None = off-map/reserve
    position:     Optional[Tuple[int, int]] = None
    # Low-altitude sub-hex (local axial, relative to the strategic hex)
    sub_position: Optional[Tuple[int, int]] = None
    # Mapsheet tile (local axial, relative to the low-altitude sub-hex)
    tac_position: Optional[Tuple[int, int]] = None
    vision_range: int  = 2                      # strategic hexes
    repair_cost:  int  = 0                      # C-Bills to restore to active
    walk_mp:      int  = 4                      # BattleTech Walk movement points
    run_mp:       int  = 6                      # BattleTech Run movement points
    battle_value: int  = 0                      # MUL / TRO Battle Value for force balancing
    has_moved:    bool = False                   # True once moved this strategic phase
    group_id:     Optional[str] = None          # lance/group membership
    roster:       List[RosterEntry] = field(default_factory=list)
    notes:        str = ""

    @classmethod
    def new(cls, name: str, faction_id: str, unit_type: str) -> "Unit":
        vision = DEFAULT_VISION.get(unit_type, 2)
        return cls(id=new_id(), name=name, faction_id=faction_id,
                   unit_type=unit_type, vision_range=vision)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["roster"] = [r.to_dict() for r in self.roster]
        for f in ("position", "sub_position", "tac_position"):
            if d.get(f) is not None:
                d[f] = list(d[f])
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Unit":
        d = d.copy()
        d["roster"] = [RosterEntry.from_dict(r) for r in d.get("roster", [])]
        for f in ("position", "sub_position", "tac_position"):
            if d.get(f) is not None:
                d[f] = tuple(d[f])
        d.setdefault("walk_mp",      4)
        d.setdefault("run_mp",       6)
        d.setdefault("battle_value", 0)
        d.setdefault("has_moved",    False)
        return cls(**d)


# ── Faction ───────────────────────────────────────────────────────────────────

@dataclass
class Faction:
    id:          str
    name:        str
    color:       Tuple[int, int, int] = (180, 180, 180)
    player_name: str = ""
    resources:   int = 0                        # C-Bills / logistics points
    notes:       str = ""

    @classmethod
    def new(cls, name: str, color: Tuple[int, int, int], player_name: str = "") -> "Faction":
        return cls(id=new_id(), name=name, color=color, player_name=player_name)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["color"] = list(d["color"])
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Faction":
        d = d.copy()
        d["color"] = tuple(d["color"])
        return cls(**d)


# ── Mission ───────────────────────────────────────────────────────────────────

@dataclass
class Mission:
    id:                    str
    name:                  str
    mission_type:          str
    position:              Tuple[int, int]       # strategic hex (q, r)
    status:                str = MISSION_ACTIVE
    participating_factions: List[str] = field(default_factory=list)
    objectives:            List[str] = field(default_factory=list)
    rewards:               str = ""
    notes:                 str = ""
    turn_created:          int = 1
    turn_deadline:         Optional[int] = None

    @classmethod
    def new(cls, name: str, mission_type: str, position: Tuple[int, int], turn: int = 1) -> "Mission":
        return cls(id=new_id(), name=name, mission_type=mission_type,
                   position=position, turn_created=turn)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["position"] = list(d["position"])
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Mission":
        d = d.copy()
        d["position"] = tuple(d["position"])
        return cls(**d)


# ── Structure ─────────────────────────────────────────────────────────────────

@dataclass
class Structure:
    id:             str
    name:           str
    structure_type: str
    position:       Tuple[int, int]
    faction_id:     Optional[str] = None   # None = neutral / unowned
    status:         str = STATUS_ACTIVE
    supply_range:   int = 0
    notes:          str = ""

    @classmethod
    def new(cls, name: str, structure_type: str, position: Tuple[int, int],
            faction_id: Optional[str] = None, supply_range: int = 0) -> "Structure":
        return cls(id=new_id(), name=name, structure_type=structure_type,
                   position=position, faction_id=faction_id, supply_range=supply_range)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["position"] = list(d["position"])
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Structure":
        d = d.copy()
        d["position"] = tuple(d["position"])
        return cls(**d)


# ── Group ─────────────────────────────────────────────────────────────────────

@dataclass
class Group:
    id:         str
    name:       str
    faction_id: str
    notes:      str = ""

    @classmethod
    def new(cls, name: str, faction_id: str) -> "Group":
        return cls(id=new_id(), name=name, faction_id=faction_id)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name,
                "faction_id": self.faction_id, "notes": self.notes}

    @classmethod
    def from_dict(cls, d: dict) -> "Group":
        return cls(id=d["id"], name=d["name"],
                   faction_id=d["faction_id"], notes=d.get("notes", ""))


# ── Objective ─────────────────────────────────────────────────────────────────

@dataclass
class Objective:
    id:         str
    name:       str
    position:   Tuple[int, int]
    vp_value:   int           = 1
    status:     str           = OBJECTIVE_ACTIVE
    faction_id: Optional[str] = None   # who currently controls it
    notes:      str           = ""

    @classmethod
    def new(cls, name: str, position: tuple, vp_value: int = 1) -> "Objective":
        return cls(id=new_id(), name=name, position=tuple(position), vp_value=vp_value)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "position": list(self.position),
                "vp_value": self.vp_value, "status": self.status,
                "faction_id": self.faction_id, "notes": self.notes}

    @classmethod
    def from_dict(cls, d: dict) -> "Objective":
        return cls(id=d["id"], name=d["name"], position=tuple(d["position"]),
                   vp_value=d.get("vp_value", 1), status=d.get("status", OBJECTIVE_ACTIVE),
                   faction_id=d.get("faction_id"), notes=d.get("notes", ""))


# ── Campaign ──────────────────────────────────────────────────────────────────

@dataclass
class Campaign:
    name:         str
    current_turn: int                            = 1
    map_width:    int                            = DEFAULT_MAP_WIDTH
    map_height:   int                            = DEFAULT_MAP_HEIGHT
    map_seed:      int                            = 0
    terrain_map:   Dict[Tuple[int, int], str]    = field(default_factory=dict)
    elevation_map: Dict[Tuple[int, int], int]    = field(default_factory=dict)
    factions:      Dict[str, Faction]            = field(default_factory=dict)
    units:        Dict[str, Unit]                = field(default_factory=dict)
    missions:     Dict[str, Mission]             = field(default_factory=dict)
    structures:   Dict[str, "Structure"]         = field(default_factory=dict)
    hex_notes:    Dict[str, str]                 = field(default_factory=dict)  # "q,r" → text
    gm_notes:     str                            = ""

    # Operational sub-maps cached by strategic hex key "q,r"
    op_maps:      Dict[str, Dict[Tuple[int,int], str]] = field(default_factory=dict)
    # Tactical (mapsheet-level) sub-maps keyed by "stratQ,stratR|subQ,subR"
    tac_maps:     Dict[str, Dict[Tuple[int,int], str]] = field(default_factory=dict)
    # Turn/event history: list of {"turn": int, "event": str, "detail": str}
    event_log:      List[Dict]                           = field(default_factory=list)
    # Per-faction set of hexes ever seen: faction_id → set of (q,r) tuples
    explored_hexes: Dict[str, Set[Tuple[int, int]]]      = field(default_factory=dict)
    # Territory control: "q,r" → faction_id
    hex_control:    Dict[str, str]                       = field(default_factory=dict)
    # Lance/unit groups
    groups:         Dict[str, "Group"]                   = field(default_factory=dict)
    # Campaign objectives with VP values
    objectives:     Dict[str, "Objective"]               = field(default_factory=dict)
    # Engagement records: list of combat dicts (capped at 200)
    combat_log:     List[Dict]                           = field(default_factory=list)
    # Current time of day within the day
    current_phase:   str                                 = PHASE_MORNING
    # Sub-turn index within the current strategic phase (0 to OP_TURNS_PER_PHASE-1)
    op_turn:         int                                 = 0
    # Hexes with multi-faction presence: "q,r" → [faction_id, ...]
    active_contacts: Dict[str, List[str]]                = field(default_factory=dict)
    # Index into factions.values() for whose turn it currently is (0 = first faction)
    active_faction_idx: int                              = 0

    def to_dict(self) -> dict:
        d: dict = {
            "name":         self.name,
            "current_turn": self.current_turn,
            "map_width":    self.map_width,
            "map_height":   self.map_height,
            "map_seed":     self.map_seed,
            "gm_notes":     self.gm_notes,
            "terrain_map":   {f"{k[0]},{k[1]}": v for k, v in self.terrain_map.items()},
            "elevation_map": {f"{k[0]},{k[1]}": v for k, v in self.elevation_map.items()},
            "factions":      {k: v.to_dict() for k, v in self.factions.items()},
            "units":        {k: v.to_dict() for k, v in self.units.items()},
            "missions":     {k: v.to_dict() for k, v in self.missions.items()},
            "structures":   {k: v.to_dict() for k, v in self.structures.items()},
            "hex_notes":    dict(self.hex_notes),
            "op_maps":      {
                mk: {f"{k[0]},{k[1]}": v for k, v in mv.items()}
                for mk, mv in self.op_maps.items()
            },
            "tac_maps":     {
                mk: {f"{k[0]},{k[1]}": v for k, v in mv.items()}
                for mk, mv in self.tac_maps.items()
            },
            "event_log":    list(self.event_log),
            "explored_hexes": {
                fid: [list(h) for h in hexes]
                for fid, hexes in self.explored_hexes.items()
            },
            "hex_control":  dict(self.hex_control),
            "groups":       {k: v.to_dict() for k, v in self.groups.items()},
            "objectives":   {k: v.to_dict() for k, v in self.objectives.items()},
            "combat_log":     list(self.combat_log),
            "current_phase":      self.current_phase,
            "op_turn":            self.op_turn,
            "active_contacts":    dict(self.active_contacts),
            "active_faction_idx": self.active_faction_idx,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Campaign":
        def parse_tmap(raw: dict) -> Dict[Tuple[int, int], str]:
            return {tuple(int(x) for x in k.split(",")): v  # type: ignore[return-value]
                    for k, v in raw.items()}

        def parse_emap(raw: dict) -> Dict[Tuple[int, int], int]:
            return {tuple(int(x) for x in k.split(",")): int(v)
                    for k, v in raw.items()}

        terrain_map = parse_tmap(d.get("terrain_map", {}))

        # Back-compat: generate elevation from terrain when loading old saves
        if "elevation_map" in d:
            elevation_map = parse_emap(d["elevation_map"])
        else:
            from game.map_gen import generate_elevation_map
            elevation_map = generate_elevation_map(terrain_map, d.get("map_seed", 0))

        return cls(
            name          = d["name"],
            current_turn  = d.get("current_turn", 1),
            map_width     = d.get("map_width",  DEFAULT_MAP_WIDTH),
            map_height    = d.get("map_height", DEFAULT_MAP_HEIGHT),
            map_seed      = d.get("map_seed", 0),
            gm_notes      = d.get("gm_notes", ""),
            terrain_map   = terrain_map,
            elevation_map = elevation_map,
            factions      = {k: Faction.from_dict(v) for k, v in d.get("factions", {}).items()},
            units        = {k: Unit.from_dict(v)    for k, v in d.get("units",    {}).items()},
            missions     = {k: Mission.from_dict(v)   for k, v in d.get("missions",   {}).items()},
            structures   = {k: Structure.from_dict(v) for k, v in d.get("structures", {}).items()},
            hex_notes    = d.get("hex_notes", {}),
            op_maps      = {
                mk: parse_tmap(mv)
                for mk, mv in d.get("op_maps", {}).items()
            },
            tac_maps     = {
                mk: parse_tmap(mv)
                for mk, mv in d.get("tac_maps", {}).items()
            },
            event_log      = d.get("event_log", []),
            explored_hexes = {
                fid: {tuple(h) for h in hexes}
                for fid, hexes in d.get("explored_hexes", {}).items()
            },
            hex_control  = d.get("hex_control", {}),
            groups          = {k: Group.from_dict(v) for k, v in d.get("groups", {}).items()},
            objectives      = {k: Objective.from_dict(v) for k, v in d.get("objectives", {}).items()},
            combat_log      = d.get("combat_log", []),
            current_phase      = d.get("current_phase", PHASE_MORNING),
            op_turn            = d.get("op_turn", 0),
            active_contacts    = d.get("active_contacts", {}),
            active_faction_idx = d.get("active_faction_idx", 0),
        )
