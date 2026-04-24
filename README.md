# BattleTech PVP Campaign Manager

A GM tool for running **double-blind** BattleTech PVP campaigns over a
procedurally-generated planet-scale hex map. Tracks factions, units
(with full per-mech/vehicle roster), missions, vision, and per-player
PNG exports that respect fog of war.

## Scale hierarchy

This follows the tabletop scale:

| Level               | Size across | Description                     |
|---------------------|-------------|---------------------------------|
| Battletech mapsheet | 500 m       | Standard tactical combat map    |
| Low-altitude hex    | 8.5 km      | 17 mapsheets                    |
| High-altitude hex   | 306 km      | 36 low-altitude hexes           |

The strategic map uses **high-altitude hexes**. You can drill down into
a single strategic hex to see its 37-hex operational sub-map
(low-altitude). Tactical combat happens on paper/VTT using actual BT
rules; this tool tracks the strategic/operational layer.

## Install & run

```bash
pip install -r requirements.txt
python main.py
```

## GM workflow

1. **New Campaign** — pick map size, seed, water ratio. A planet-scale
   terrain grid is generated with mountains, forests, deserts, arctic,
   coastlines, and scattered cities/industrial sites.
2. **+Faction** — add each player's faction; pick name, player name,
   display color.
3. **+Unit tool** — click a hex, assign faction/type/vision range. Each
   unit has a full roster (chassis, pilot, tonnage, status, notes) —
   edit via the sidebar *Edit…* button.
4. **+Mission tool** — place missions on the map.
5. **Move tool** — click a unit, then click destination hex.
6. **Export** — toolbar *Export* button dumps a PNG for any
   faction with **fog of war applied** (only hexes within their units'
   vision radius are visible; enemy units only show inside that
   radius). GM view exports the full situation.
7. **Save** — JSON save into `saves/`. Reload from splash or toolbar.
8. **Next Turn** — increments campaign turn counter. You can do
   whatever pacing you want.

## Interaction

| Input                     | Action                                    |
|---------------------------|-------------------------------------------|
| Left click                | Run active tool on hex                    |
| Right-drag                | Pan map                                   |
| WASD / arrow keys         | Pan map                                   |
| Scroll wheel / + / −      | Zoom                                      |
| ESC                       | Clear selection, or exit operational view |
| Ctrl+S                    | Save                                      |
| N                         | Next turn                                 |
| Click a faction (sidebar) | Peek at their fog-of-war view (GM only)   |
| Operational (toolbar)     | Drill into the currently selected hex     |
| Strategic (toolbar)       | Return to planet view                     |

## Double-blind usage

Before each turn:
1. GM reviews the situation, resolves moves/missions.
2. **Export** button → pick each faction → get a PNG that only shows
   what that faction's units can see.
3. Send each PNG to the respective player (Discord, email, whatever).
4. Players respond with orders; GM enters them.

Units out of vision become invisible in the export. Enemy units inside
your vision radius appear in the PNG. Terrain outside vision is
blacked out as fog.

## Files

```
main.py                  entry point
game/
  constants.py           scale & enum constants
  hex_grid.py            axial hex math, pixel conversion
  terrain.py             12 terrain types w/ display & gameplay props
  map_gen.py             FBM-noise procedural terrain
  models.py              Campaign, Faction, Unit, Mission, RosterEntry
  vision.py              visible_hexes / visible_units per faction
  campaign.py            create/save/load/turn ops, op-map caching
ui/
  colors.py              UI palette + 10-color faction palette
  renderer.py            Hex map renderer (draws fog-aware)
  chrome.py              Toolbar, sidebar, statusbar
  dialogs.py             Modal dialogs (NewCampaign, AddFaction, etc.)
  export.py              PNG export with header + legend + fog
  app.py                 App class: main loop & event handling
saves/                   JSON saves
exports/                 PNG exports
```

## Known limits / future work

- No persistent "explored" memory — faction sees only currently-in-range
  hexes each turn (not previously-seen). Easy to add by recording an
  `explored_hexes` set per faction on each `Next Turn`.
- Vision doesn't respect LOS blocking by mountains/forests at strategic
  scale (it's treated as radius-only); terrain data is already there.
- Operational (sub-hex) view only has terrain — units are only tracked
  at strategic scale currently.
- No undo. Save often.
