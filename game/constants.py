# BattleTech scale constants
MAPSHEET_SIZE_M = 500
LOW_ALT_HEX_MAPSHEETS = 17
HIGH_ALT_HEX_LOW_ALT = 36

LOW_ALT_HEX_SIZE_M = MAPSHEET_SIZE_M * LOW_ALT_HEX_MAPSHEETS   # 8,500 m
HIGH_ALT_HEX_SIZE_M = LOW_ALT_HEX_SIZE_M * HIGH_ALT_HEX_LOW_ALT  # 306,000 m

# Operational sub-map dimensions (low-altitude hexes per strategic hex)
OPERATIONAL_RADIUS = 3   # hex-radius, gives 37 hexes ≈ 36

# Tactical sub-map dimensions (mapsheets per low-altitude hex)
TACTICAL_RADIUS    = 2   # hex-radius, gives 19 hexes ≈ 17

SCALE_STRATEGIC   = "strategic"
SCALE_OPERATIONAL = "operational"

DEFAULT_MAP_WIDTH  = 60
DEFAULT_MAP_HEIGHT = 40

# ── Terrain ──────────────────────────────────────────────────────────────────
TERRAIN_DEEP_WATER  = "deep_water"
TERRAIN_WATER       = "water"
TERRAIN_COAST       = "coast"
TERRAIN_PLAINS      = "plains"
TERRAIN_FOREST      = "forest"
TERRAIN_HILLS       = "hills"
TERRAIN_MOUNTAINS   = "mountains"
TERRAIN_URBAN       = "urban"
TERRAIN_INDUSTRIAL  = "industrial"
TERRAIN_DESERT      = "desert"
TERRAIN_ARCTIC      = "arctic"
TERRAIN_VOLCANIC    = "volcanic"

ALL_TERRAIN = [
    TERRAIN_DEEP_WATER, TERRAIN_WATER, TERRAIN_COAST, TERRAIN_PLAINS,
    TERRAIN_FOREST, TERRAIN_HILLS, TERRAIN_MOUNTAINS, TERRAIN_URBAN,
    TERRAIN_INDUSTRIAL, TERRAIN_DESERT, TERRAIN_ARCTIC, TERRAIN_VOLCANIC,
]

# ── Units ─────────────────────────────────────────────────────────────────────
UNIT_MECH      = "BattleMech"
UNIT_VEHICLE   = "Vehicle"
UNIT_AEROSPACE = "Aerospace"
UNIT_INFANTRY  = "Infantry"
UNIT_DROPSHIP  = "DropShip"
UNIT_TYPES = [UNIT_MECH, UNIT_VEHICLE, UNIT_AEROSPACE, UNIT_INFANTRY, UNIT_DROPSHIP]

STATUS_ACTIVE    = "active"
STATUS_DESTROYED = "destroyed"
STATUS_RETREATED = "retreated"
STATUS_CRIPPLED  = "crippled"
STATUS_RESERVE   = "reserve"
STATUS_REPAIRING = "repairing"
UNIT_STATUSES = [STATUS_ACTIVE, STATUS_CRIPPLED, STATUS_RETREATED, STATUS_RESERVE,
                 STATUS_REPAIRING, STATUS_DESTROYED]

# Default vision range (strategic hexes) per unit type
DEFAULT_VISION = {
    UNIT_MECH:      2,
    UNIT_VEHICLE:   2,
    UNIT_AEROSPACE: 5,
    UNIT_INFANTRY:  1,
    UNIT_DROPSHIP:  3,
}

# ── Missions ──────────────────────────────────────────────────────────────────
MISSION_RAID      = "Raid"
MISSION_ASSAULT   = "Assault"
MISSION_PATROL    = "Patrol"
MISSION_GARRISON  = "Garrison"
MISSION_RECON     = "Recon"
MISSION_OBJECTIVE = "Hold Objective"
MISSION_RESCUE    = "Rescue"
MISSION_ESCORT    = "Escort"
MISSION_TYPES = [
    MISSION_RAID, MISSION_ASSAULT, MISSION_PATROL, MISSION_GARRISON,
    MISSION_RECON, MISSION_OBJECTIVE, MISSION_RESCUE, MISSION_ESCORT,
]

MISSION_ACTIVE    = "active"
MISSION_COMPLETED = "completed"
MISSION_FAILED    = "failed"
MISSION_PENDING   = "pending"
MISSION_STATUSES  = [MISSION_ACTIVE, MISSION_COMPLETED, MISSION_FAILED, MISSION_PENDING]

# ── Structures ────────────────────────────────────────────────────────────────
STRUCTURE_CITY      = "City"
STRUCTURE_TOWN      = "Town"
STRUCTURE_VILLAGE   = "Village"
STRUCTURE_BASE      = "Military Base"
STRUCTURE_FOB       = "FOB"
STRUCTURE_DEPOT     = "Supply Depot"
STRUCTURE_AIRFIELD  = "Airfield"
STRUCTURE_FACTORY   = "Factory"
STRUCTURE_SPACEPORT = "Spaceport"
STRUCTURE_COMMS     = "Comms Tower"
STRUCTURE_TYPES = [
    STRUCTURE_CITY, STRUCTURE_TOWN, STRUCTURE_VILLAGE,
    STRUCTURE_BASE, STRUCTURE_FOB, STRUCTURE_DEPOT,
    STRUCTURE_AIRFIELD, STRUCTURE_FACTORY, STRUCTURE_SPACEPORT, STRUCTURE_COMMS,
]
# Default supply radius (0 = not a supply source)
STRUCTURE_SUPPLY_RANGES = {
    STRUCTURE_CITY: 2, STRUCTURE_TOWN: 1, STRUCTURE_VILLAGE: 0,
    STRUCTURE_BASE: 5, STRUCTURE_FOB: 3, STRUCTURE_DEPOT: 4,
    STRUCTURE_AIRFIELD: 2, STRUCTURE_FACTORY: 2,
    STRUCTURE_SPACEPORT: 4, STRUCTURE_COMMS: 0,
}
DROPSHIP_SUPPLY_RANGE = 3

# ── Combat outcomes ──────────────────────────────────────────────────────────
OUTCOME_ATTACKER_WIN = "attacker_victory"
OUTCOME_DEFENDER_WIN = "defender_victory"
OUTCOME_DRAW         = "draw"
OUTCOME_WITHDRAWAL   = "mutual_withdrawal"
COMBAT_OUTCOMES = [OUTCOME_ATTACKER_WIN, OUTCOME_DEFENDER_WIN, OUTCOME_DRAW, OUTCOME_WITHDRAWAL]

# ── Objectives ────────────────────────────────────────────────────────────────
OBJECTIVE_ACTIVE   = "active"
OBJECTIVE_CAPTURED = "captured"
OBJECTIVE_DENIED   = "denied"
OBJECTIVE_STATUSES = [OBJECTIVE_ACTIVE, OBJECTIVE_CAPTURED, OBJECTIVE_DENIED]

# Default movement range (strategic hexes/turn)
DEFAULT_MOVE_RANGE = {
    UNIT_MECH:      3,
    UNIT_VEHICLE:   3,
    UNIT_AEROSPACE: 6,
    UNIT_INFANTRY:  2,
    UNIT_DROPSHIP:  2,
}
