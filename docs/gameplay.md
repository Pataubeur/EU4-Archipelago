# Gameplay and supported configuration

MVP countries: FRA, CAS, ENG, POR, HAB, BRA, POL and TUR. Choose the configured
tag manually at 1444-11-11. This set provides a bounded initial playtest scope,
including landlocked Brandenburg and Austria. No starting-development tables
or unverified geography-derived thresholds are used. Country formation/tag
switching is currently rejected by the bridge.

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
| starting_country | fra/cas/eng/por/hab/bra/pol/tur | Required player tag |
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
