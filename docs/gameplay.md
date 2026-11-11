# Gameplay and supported configuration (0.5.0)

Design rationale and the full catalogue are in [design-progression.md](design-progression.md).
Every native effect below is an **implemented candidate awaiting EU4 validation**
(experiments E1–E8 and the 0.5.0 protocol in [manual-validation.md](manual-validation.md)).

## Choosing a country

Choose any country playable on **1444-11-11** with `starting_country` (tag such as
`fra`, `byz`, `mng`, or a listed name such as `Ming`). Options Creator shows 58
named shortcuts; **Other country (advanced tag)** plus `custom_starting_country`
covers any other tag. Generation validates tag syntax, not map availability.

## Goals

| `goal` | Victory decision requires |
| --- | --- |
| `mixed` (default) | the national ambition **and** N Seals of the Multiworld (`goal_difficulty`: 2/3/4) |
| `national_ambition` | the national ambition and its region keys / fetter levels |
| `great_power` | great power status with doubled development, Chancery 1 |
| `domination` | development ×2 (short), ×3 (standard) or ×5 (long) of your start, Imperial Court 2 |
| `royal_charters` | the classic 0.4 mode: 10–20 checks, Royal Charters only, unchanged schema 1 |

`national_ambition: auto` picks the country's dedicated ambition that fits the
campaign length and declared DLCs (e.g. BYZ standard → *Basileus*, BYZ long →
*Pentarchy*, FRA long → *Better than Napoleon*, POR short → *The Navigator*),
otherwise a generic one (*Regional Power*, *Great Power*, *At Every Continent*).
An explicit ambition that does not fit the country, length or DLCs stops
generation with an explanation. Ambitions are rewritten achievement conditions;
Steam achievements are never read. Once reached, an ambition stays reached.
Dated achievements lose their deadline (AP cannot guarantee game time); the
deadline survives as an always-excluded bonus check (*The Navigator: Before 1500*).

## Campaign length and checks

| `campaign_length` | Calendar | Checks (typical) | Estimated time |
| --- | --- | --- | --- |
| `short` | every 5 years, 1450–1500 | 29–39 | 4–6 h |
| `standard` | 1450–1575 | 61–78 | 8–12 h |
| `long` | 1450–1700 | 94–115 | 20 h+ |

Besides calendar checks: institutions, idea groups, empire rank, absolutism,
development **relative to your start** (+25 %, +50 %, ×2, ×3), cities of 30/50
development, allies, royal marriages, subjects, personal union, army tradition,
discipline, navy size, monthly income, trade share, debt-free reserves (loans no
longer validate treasury checks), discovering the New World, colonies, colonial
nations, continents, religious unity, prestige, stability, the first missions of
your country's tree (`mission_checks`, chosen by `owned_dlcs`), and the ambition's
milestones (priority locations).

`exclude_long_checks` (on by default) keeps progression items off long checks and
the last third of the calendar, where other players would wait hours.

## What the multiworld unlocks in your campaign

- **Fetters** (`fetters`, default colonial, admiralty, chancery, guilds; also
  academy, imperial_court, arsenal): permanent modifiers applied at binding and
  lifted level by level by *Progressive …* items. Example: Colonial License level
  0 is −1 colonist and −50 colonial growth. Their checks also require the level.
- **Region keys** (`region_keys`, on): each ambition region (Balkans, Anatolia,
  Mashriq, Egypt, Italy, …) needs its key. Without it, newly owned provinces
  there receive *Archipelago: Unratified Land* (−50 % taxes, production and
  manpower, +2 unrest) and its milestones stay locked. Provinces owned when you
  bind are never penalised.
- **Seals of the Multiworld**: required by the `mixed` victory.
- **Useful items**: Multiworld Decree (10-year modifier), Military Tradition,
  Fresh Recruits, Court Patronage, Peace Dividend, Missionary Zeal, monarch power,
  Ambition Claims (permanent claims on your ambition targets).
- **Filler**: Royal Treasury (0.25 year of income), Mandate of Legitimacy
  (or republican tradition/devotion), prestige. `reward_strength: double` doubles them.
- **Traps** (`trap_percentage`, default 0): stability, a small revolt, a
  diplomatic incident, inflation, an heir's death. Never before 1450, never
  fatal, and disabled in Ironman unless `ironman_traps`.
- **DeathLink** (`death_link`): a received death costs 1 stability (not below −2)
  and 10 prestige; your ruler changing sends one, with a 30-day loop guard.

## Normal and Ironman play

| | `save_mode: normal` | `save_mode: ironman` |
| --- | --- | --- |
| Checks sent | from `game.log` as they happen; saves add rollback detection | from `game.log` |
| Items received, live | delivery code entered in game | delivery code entered in game |
| Items received, other paths | console `run eu4ap_sync.txt`, or relaunch EU4 | relaunch EU4: applied the day after loading |
| Save in the client | optional (uncompressed text) | not used |

**Live deliveries.** At generation every item you will receive gets a 4-digit
code, written into the mod once (the mod never changes during the campaign).
When an item arrives, the client shows « Livraison reçue de Alice : Key: Anatolia
— code 4821 ». In EU4, even paused, take **Archipelago: receive a delivery**, pick
the four digits, check the item name on the confirmation screen and accept: the
effect applies at once. A code already received, unknown, or a trap before 1450
is refused with a log line. The game cannot know whether the server really sent
the item (honour system): the client audits every claim and reports a code
claimed before reception. Items without a code (an admin `/send`) and DeathLinks
beyond the 20 reserved codes arrive at the next relaunch. Both paths share the
same flag, so an item is never applied twice.

The mod also logs the actual mode; the client warns if it differs. The client
installs items into the mod's inbox only while EU4 is closed, as a safety net.
After a crash before the autosave, missing items are re-applied once automatically.

## Decisions

- **Archipelago: bind this campaign** — once, as the configured country on 1444-11-11.
- **Archipelago: receive a delivery** — digit pad for the codes shown by the client.
- **Archipelago: scan objectives now** — applies installed items, scans, replays state into the log.
- **Archipelago: ratify the victory** — available when the goal requirements are met.
- **Archipelago: golden pilgrimage** — Mali's ambition only.

A visible event announces deliveries. Purple *Archipelago* modifiers show the
remaining fetters and unratified provinces.

## Not modelled

AP logic mirrors the mod's guards exactly but does not model the survival or
military strength of your country, nor game time: a check reachable in logic can
remain hard in EU4. Formed nations (Rome, Spain, Prussia, …) keep the campaign
through the binding flag (to be confirmed in game, E4).
