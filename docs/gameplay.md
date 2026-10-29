# Gameplay and supported configuration

Choose any country playable on **1444-11-11**, using its EU4 tag in
`starting_country` (e.g. `fra`, `byz`, `mng`, `azt`). Select that country manually
in EU4. The existing FRA/CAS/ENG/POR/HAB/BRA/POL/TUR shortcuts and their numeric
values remain valid; arbitrary tags are also accepted and normalized to uppercase.
Options Creator shows a real dropdown with 58 alphabetical named shortcuts and
France selected by default. For a country outside that shortlist, choose
**Other country (advanced tag)** and set `custom_starting_country` under
**Other country (advanced)**. That field is ignored for named selections.
`random` draws from the 58 named countries, never the advanced entry.
Listed English names and display labels are also accepted in YAML, e.g. `Ming`
or `Byzantium (BYZ)`; arbitrary tags continue to work without the advanced field.

The generator validates tag syntax, not availability on the map: select a country
that is actually playable in the fixed 1444 start. No game files are required
for generation. No exhaustive country catalogue or starting-development tables
are bundled. Other start dates, custom nations and country formation/tag switching
remain outside the supported scope; a changed player tag is rejected by the bridge.
Opening tag selection does not establish that every country's engine behavior
or balance has been tested.

All locations are logically accessible without received items. You still need
to keep your country alive; AP's solver cannot guarantee survival in EU4.
Calendar checks unlock by reaching successive years, starting in 1445. At least
half the selected checks use this pool. Depending on options, treasury checks
(100/250/500/1000 ducats) and ADM/DIP/MIL levels 4–5 replace some annual checks.
Technology checks are taken in a fixed documented order after treasury checks,
up to half the pool. Both groups off yields only annual checks (up to 1464).
Dates are current-game-date thresholds, not campaign elapsed-time calculations.
Some treasury checks can be obtained immediately by large countries or through
loans. This is permitted in the MVP and is a balance limitation.
The same thresholds apply to all countries; small or low-technology starts may
take longer. Disable economic and/or technology checks for a calendar-only pool
when those objectives would be unsuitable. AP logic still does not model survival.

Take the binding decision once, then save. The hidden event scans every game day;
use the rescan decision and save for immediate reporting. Checks are automatic
after the client reads a save, not at the instant an unsaved objective occurs.
The online client checks file metadata every 250 ms and parses only changed
saves. Reading a large save and server latency still take time. After upgrading
an existing campaign from monthly scanning, take the rescan decision once to
start the daily event chain immediately; no new campaign or binding is needed.

Royal Charters are progression items. Collect 2/3/4 depending on difficulty,
apply them via the console, and take the ratification decision. Save to report
completion. Extra charters from common AP options have no further gameplay effect.
No locations depend on charters, so there is no charter-to-location cycle.

Other items are useful monarch power and filler ducats/prestige. Resources use
ordinary native effects. Strength `double` multiplies resource amounts by two;
item names retain baseline amounts. Existing game caps can waste prestige or
monarch power. These effects are implemented candidates awaiting real-game
verification; no discipline, colonization, legitimacy or permanent modifier
reward is advertised as implemented.

| YAML option | Supported values | Meaning |
| --- | --- | --- |
| starting_country | Any EU4 tag, e.g. fra/byz/mng/azt | Country playable on 1444-11-11; case-insensitive |
| custom_starting_country | A tag, default FRA | Used only when starting_country is other_country |
| goal_difficulty | easy/normal/hard | 2/3/4 Royal Charters |
| location_count | 10–20 | Pool size |
| enable_economic_checks | true/false | Treasury pool |
| enable_technology_checks | true/false | Technology pool |
| reward_strength | normal/double | Resource effect multiplier |

`starting_date` and `goal` are deliberately fixed, not inert YAML options.
Military/diplomatic/colonial checks and `progression_difficulty` are not yet
implemented and must not be added to the example YAML. More options should be
introduced only with matching game behavior and logic tests. Common AP options
come from PerGameCommonOptions. The example leaves accessibility at AP's default.
