"""UI color palette."""

# Background / chrome
BG          = ( 28,  28,  32)
PANEL_BG    = ( 38,  38,  44)
PANEL_DARK  = ( 25,  25,  30)
BORDER      = ( 70,  70,  80)
BORDER_LT   = (100, 100, 115)

# Text
TEXT        = (220, 220, 220)
TEXT_DIM    = (140, 140, 150)
TEXT_BRIGHT = (255, 255, 255)
TEXT_WARN   = (255, 200,  80)
TEXT_BAD    = (220,  60,  60)
TEXT_GOOD   = ( 80, 200,  80)

# Buttons
BTN_NORMAL  = ( 55,  55,  65)
BTN_HOVER   = ( 75,  75,  90)
BTN_ACTIVE  = ( 40,  90, 160)
BTN_DANGER  = (140,  40,  40)
BTN_TEXT    = (210, 210, 220)

# Map
FOG         = ( 18,  18,  22)          # unexplored hex
FOG_KNOWN   = ( 35,  35,  42)          # previously seen (future)
GRID_LINE   = ( 60,  60,  70)
GRID_HOVER  = (200, 200, 100)
SELECTED    = (255, 220,  50)
MISSION_CLR = (255, 160,  40)
MISSION_BDR = (200, 120,  20)

# Altitude overlay tints (for elevation indicator)
ALT_LOW     = ( 80, 130,  80)
ALT_HIGH    = (200, 180, 160)

# Faction default palette (cycled when adding factions)
FACTION_PALETTE = [
    (220,  60,  60),   # red
    ( 60, 130, 220),   # blue
    ( 60, 200,  80),   # green
    (220, 180,  40),   # yellow
    (200,  80, 220),   # purple
    ( 40, 200, 200),   # cyan
    (220, 120,  40),   # orange
    (160, 200,  80),   # lime
    (200,  80, 120),   # pink
    (100, 160, 220),   # sky
]
