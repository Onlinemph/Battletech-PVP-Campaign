# BattleTech scale constants — two tiers
STRATEGIC_HEX_M   = 18_000   # 18 km per strategic hex (high-altitude overview)
OPERATIONAL_HEX_M =    500   # 500 m per operational hex (= one BT mapsheet)

# Keep backward-compat aliases used by chrome.py sidebar
HIGH_ALT_HEX_SIZE_M = STRATEGIC_HEX_M
LOW_ALT_HEX_SIZE_M  = OPERATIONAL_HEX_M

# Operational sub-map radius (low-altitude hexes visible when drilling into a strategic hex)
OPERATIONAL_RADIUS = 3   # hex-radius → 37 hexes
# Tactical (mapsheet) sub-map radius — radius 2 = 19 hexes, one per BT mapsheet tile
TACTICAL_RADIUS    = 2   # hex-radius → 19 hexes

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
STATUS_INORBIT   = "in_orbit"
UNIT_STATUSES = [STATUS_ACTIVE, STATUS_CRIPPLED, STATUS_RETREATED, STATUS_RESERVE,
                 STATUS_REPAIRING, STATUS_INORBIT, STATUS_DESTROYED]

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

# ── Day/Phase system ──────────────────────────────────────────────────────────
PHASE_MORNING   = "morning"
PHASE_AFTERNOON = "afternoon"
PHASE_NIGHT     = "night"
PHASES          = [PHASE_MORNING, PHASE_AFTERNOON, PHASE_NIGHT]
PHASE_ABBR      = {PHASE_MORNING: "AM", PHASE_AFTERNOON: "PM", PHASE_NIGHT: "**"}
PHASE_COLOR     = {
    PHASE_MORNING:   (255, 180,  60),
    PHASE_AFTERNOON: (220, 140,  30),
    PHASE_NIGHT:     ( 80, 100, 190),
}

# Operational sub-turns per strategic phase (4h phase ÷ 1h sub-turns)
OP_TURNS_PER_PHASE = 4

# Hours of travel covered per strategic phase (shorter = fewer hexes moved per phase)
HOURS_PER_PHASE = 4

# Default movement range (strategic hexes/turn) — legacy fallback for Aerospace/DropShip
DEFAULT_MOVE_RANGE = {
    UNIT_MECH:      3,
    UNIT_VEHICLE:   3,
    UNIT_AEROSPACE: 6,
    UNIT_INFANTRY:  2,
    UNIT_DROPSHIP:  2,
}

# ── Economy ───────────────────────────────────────────────────────────────────

# C-Bills generated per controlled hex per day
TERRAIN_INCOME = {
    TERRAIN_URBAN:       50_000,
    TERRAIN_INDUSTRIAL:  75_000,
    TERRAIN_PLAINS:       5_000,
    TERRAIN_HILLS:        4_000,
    TERRAIN_FOREST:       3_000,
    TERRAIN_MOUNTAINS:    2_000,
    TERRAIN_COAST:        3_000,
    TERRAIN_DESERT:       1_000,
    TERRAIN_ARCTIC:       1_000,
    TERRAIN_VOLCANIC:         0,
    TERRAIN_WATER:            0,
    TERRAIN_DEEP_WATER:       0,
}

# Additional C-Bills per owned structure per day
STRUCTURE_INCOME = {
    STRUCTURE_CITY:      200_000,
    STRUCTURE_TOWN:       50_000,
    STRUCTURE_VILLAGE:    10_000,
    STRUCTURE_FACTORY:   150_000,
    STRUCTURE_SPACEPORT: 100_000,
    STRUCTURE_BASE:       10_000,
    STRUCTURE_FOB:         5_000,
    STRUCTURE_DEPOT:      20_000,
    STRUCTURE_AIRFIELD:   25_000,
    STRUCTURE_COMMS:       5_000,
}

# C-Bills maintenance cost per unit per day
UNIT_MAINTENANCE = {
    UNIT_MECH:      10_000,
    UNIT_VEHICLE:    5_000,
    UNIT_AEROSPACE: 15_000,
    UNIT_INFANTRY:   2_000,
    UNIT_DROPSHIP:  20_000,
}

# ── Terrain movement costs (strategic Dijkstra) ───────────────────────────────
# Cost in "plains-hex equivalents" to enter that terrain type. None = impassable.
TERRAIN_MOVE_COST = {
    TERRAIN_PLAINS:     1.0,
    TERRAIN_COAST:      1.0,
    TERRAIN_FOREST:     1.5,
    TERRAIN_HILLS:      1.5,
    TERRAIN_DESERT:     1.5,
    TERRAIN_ARCTIC:     2.0,
    TERRAIN_MOUNTAINS:  3.0,
    TERRAIN_URBAN:      1.5,
    TERRAIN_INDUSTRIAL: 1.5,
    TERRAIN_VOLCANIC:   3.0,
    TERRAIN_WATER:      3.0,      # mechs wade (very slow)
    TERRAIN_DEEP_WATER: None,     # impassable
}

# ── Operational movement costs (500 m hexes, tighter than strategic) ──────────
# None = impassable at operational scale (water too deep to cross in one sub-turn)
OP_TERRAIN_COST = {
    TERRAIN_PLAINS:     1.0,
    TERRAIN_COAST:      1.0,
    TERRAIN_FOREST:     2.0,
    TERRAIN_HILLS:      2.0,
    TERRAIN_DESERT:     1.5,
    TERRAIN_ARCTIC:     2.5,
    TERRAIN_MOUNTAINS:  None,     # cliff walls, impassable at operational scale
    TERRAIN_URBAN:      1.5,
    TERRAIN_INDUSTRIAL: 1.5,
    TERRAIN_VOLCANIC:   None,
    TERRAIN_WATER:      None,
    TERRAIN_DEEP_WATER: None,
}

# ── Elevation ─────────────────────────────────────────────────────────────────
ELEVATION_MIN = 0
ELEVATION_MAX = 10

# Extra movement cost per elevation-unit of difference between adjacent hexes
SLOPE_COST_PER_LEVEL = 0.4
# Elevation delta that is treated as an impassable cliff
SLOPE_IMPASSABLE     = 5
# Elevation levels required for +1 vision range bonus
ELEVATION_VISION_DIV = 3

# Integer elevation range (min, max inclusive) generated per terrain type
TERRAIN_ELEVATION_RANGE = {
    TERRAIN_DEEP_WATER:  (0, 0),
    TERRAIN_WATER:       (0, 1),
    TERRAIN_COAST:       (1, 2),
    TERRAIN_PLAINS:      (2, 4),
    TERRAIN_DESERT:      (2, 4),
    TERRAIN_ARCTIC:      (2, 6),
    TERRAIN_FOREST:      (3, 5),
    TERRAIN_HILLS:       (4, 6),
    TERRAIN_URBAN:       (2, 4),
    TERRAIN_INDUSTRIAL:  (2, 4),
    TERRAIN_MOUNTAINS:   (6, 9),
    TERRAIN_VOLCANIC:    (5, 9),
}
