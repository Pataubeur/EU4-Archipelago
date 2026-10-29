# Feasibility and evidence (2026-10-19)

Historical research notes. Current installation, version targets and executed
checks are in [installation.md](installation.md) and [validation.md](validation.md).

Status: research-backed implementation candidate, **not validated in EU4**.
The working directory was empty except for IDE metadata. Python 3.10.2 is
available. Neither Archipelago nor EU4 was found in the standard paths checked;
this is not an exhaustive search of the user's disks. Shell network access is
denied. Research was performed with the web browsing tool.

## Sources reviewed

- [Adding games](https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/adding%20games.md),
  [World API](https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/world%20api.md),
  [protocol](https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/network%20protocol.md),
  [developer FAQ](https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/apworld_dev_faq.md).
- [APQuest](https://github.com/ArchipelagoMW/Archipelago/tree/main/worlds/apquest):
  region/item/location separation, option dataclass, slot data and completion rules.
- [CommonClient 0.6.6](https://github.com/ArchipelagoMW/Archipelago/blob/0.6.6/CommonClient.py):
  connection, authentication, replay and reconnect are delegated to CommonContext.
- [Factorio](https://github.com/ArchipelagoMW/Archipelago/tree/main/worlds/factorio):
  native RCON and game-side command bridge. EU4 has no equivalent documented API.
- [A Hat in Time client](https://github.com/ArchipelagoMW/Archipelago/blob/main/worlds/ahit/Client.py):
  separation between a game connection and the AP connection.
- [EU4 effect reference maintained by a mod author](https://github.com/vawser/EU4-Documentation/blob/master/effects.txt)
  and [trigger reference](https://github.com/vawser/EU4-Documentation/blob/master/triggers.txt).
  These document country flags, treasury/power effects, native script conditions
  and the console `run` workflow. They are community documentation, not an engine contract.
- Official wiki pages [Effects](https://eu4.paradoxwikis.com/Effects),
  [Console commands](https://eu4.paradoxwikis.com/Console_commands),
  [Conditions](https://eu4.paradoxwikis.com/Conditions),
  [Mod structure](https://eu4.paradoxwikis.com/Mod_structure) were requested but
  returned errors to the browsing tool. Their contents were **not** verified.

No existing EU4 Archipelago integration was identified in the searches performed.
This is not proof that none exists. Factorio's former file bridge is a useful
historical comparison, but its current RCON solution cannot be transplanted to EU4.

## Strategies

| Strategy | Feasibility | Latency | Persistence / desynchronization |
| --- | --- | --- | --- |
| Read plaintext saves | Implemented parser; real save validation pending | Save interval + 2 s polling | Country flags are the authority; read stable complete files only |
| Read zipped plaintext saves | Implemented `gamestate` reader | Same | Bounded decompression; reject binary/Ironman saves |
| Tail `game.log` via native `log` | Plausible, deferred | Immediate | Rotation, replay and unsaved state complicate confirmation |
| Generate mod before launch | Implemented seed-specific installer | Restart EU4 | No assumption of mod hot reload |
| Modify loaded events/decisions | Unverified; not used | Unknown | Engine caching must be tested, cannot promise hot reload |
| Console `run` effects file | Selected inbound candidate | User executes command | Per-item flags prevent replay in the same save lineage |
| Rewrite saves | Technically possible, rejected for MVP | Requires save/load | Corruption, encoding, simultaneous writer and lost state risks |
| Native HTTP/WebSocket/arbitrary file reader | No documented script mechanism found | N/A | Not assumed available |
| Memory/DLL/input automation | Excluded | N/A | Fragile and unnecessary for a manual console compromise |

## Selected vertical slice

Target EU4 **1.37.x**, 1444-11-11, non-Ironman, one human EU4 instance per AP
slot, no gameplay DLC requirement. Target AP **0.6.6** APIs; compatibility is
provisional until the real-runtime integration tests run. The offline bridge
supports Python 3.10+; use the Python required by your AP checkout for online work.

The client installs a seed-specific mod **before EU4 starts**. A decision binds
the selected country to a seed/team/slot token and starts a recurring hidden
daily event. That event records satisfied objectives as country flags. A
decision also permits an immediate rescan. The client polls a user-selected
local save and sends checks to AP without another user action after saving.

For incoming items, the client atomically writes `eu4ap_sync.txt` in the EU4 user
directory. The player pauses, opens the console, runs `run eu4ap_sync.txt`, then
saves. Each item has its own guarded effect and flag. An item is **confirmed
only when its flag appears in a parsed save**, never because a file was written.
Changing the file does not rely on hot reload of mod definitions. Whether `run`
reads a changed file on each execution is a required real-game test, not an
experimental result obtained here.

All progression items are Royal Charters. They unlock the final ratification
decision; no locations require them. All checks remain reachable in the AP
graph without received items. Physical campaign survival remains a gameplay
assumption, not a guarantee from the AP solver. Annual milestones provide a
safe path without conquest, ports, colonization, unions or DLC. Resource and
technology checks add variety when enabled; military and diplomacy pools are
deliberately absent from the MVP.

## Research and PoC exit criteria

Automated tests can establish parsing, generation, transactionality, identity
checks and protocol adapter behavior with fakes. They cannot establish that EU4
accepts the generated syntax or applies effects. Phase 2's **in-game** exit gate
therefore remains open. See `manual-validation.md` for the experiment that must
pass before calling this integration playable. Later phases are implemented as
testable candidates in parallel with this unresolved external validation.
