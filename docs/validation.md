# Validation status — 2026-10-29

Release candidate **0.4.1** targets Windows Archipelago **0.6.7** and EU4
**1.37.5.0**. This is not yet an accepted live-game release.

## Named country selector — 0.4.1

- Starting Country is now a standard Choice dropdown with 58 alphabetically
  named shortcuts, displaying France (FRA) by default. Other country uses a
  prefilled tag in a separate collapsed advanced group. The shortlist is not
  an exhaustive set of all playable countries.
- **61 repository tests: 59 passed, two skipped**, no failures. Catalogue tests
  cover name/label resolution, unique stable IDs, legacy IDs and unlisted tags.
  The source-gated World tests additionally cover Other country and ignoring an
  inactive custom field; they are not counted as executed here.
- In `local/country-selector-041/`, the actual stock Windows 0.6.7 Options Creator
  executable displayed the named selector; a validation-only APWorld probe checked
  the France default, absence of the old TextChoice input, 58 labels plus Other,
  selected Ming through the real menu callback and exported YAML through the
  official action. Screenshots and JSON/YAML evidence are under `eu4-validation/`.
  Early probe attempts failed to inspect still-collapsed widgets; opening their
  panels fixed the test harness. These were probe setup failures, not game tests.
- Names from the shortlist (e.g. France) now work in player YAMLs. `random` chooses
  among the 58 names and excludes Other. Old raw tags and numeric shortcuts remain
  compatible, with unchanged manifests and campaign tokens.
- The repeatable `check_archipelago.py --frozen --options-creator` check passed
  against a new copy of the installed 0.6.7 runtime in
  `local/country-selector-041-final/`. It also generated a real seed from the
  UI-exported Ming YAML and validated the MNG manifest. The probe is installed
  only in the isolated test copy, never in the public `.apworld`.
- Eight additional stock-generator cases passed under its
  `eu4-validation/selection-cases/`: legacy name/ID (same old seed token), country
  name, display label, unlisted raw tag, Other with a custom tag, ignored inactive
  custom text, and rejection of an invalid active custom tag.

Engine acceptance and exhaustive country availability remain unverified.

## Free country selection — 0.4.0

Country selection now accepts any script-safe EU4 tag, with the same fixed
1444-11-11 start. The eight old shortcuts/numeric values remain available.
Country existence and 1444 playability are not inferred from syntactic validity.
The manifest schema and identity hashing are unchanged.

- The repository suite exercises the complete objective-option matrix for all
  eight presets plus BYZ, MNG, AZT and an alphanumeric tag (synthetic K00).
- **59 repository tests: 57 passed, two skipped** (PyYAML and AP source runtime
  unavailable), no failures. Compilation and public/tool/demo builds passed.
- Synthetic non-preset campaigns cover generated binding conditions, parsing,
  check reporting, pending rewards and acknowledgment, while rejecting a different
  player's country. Malformed tag/script input is rejected before rendering.
- The real Windows AP 0.6.7 generator emitted an MNG manifest in an isolated copy
  under `local/country-validation-040/`. The standard Launcher exported YAML and
  built the client UI. This is generator/UI evidence, not an EU4 playtest.
- The final package passed the same frozen checks with lowercase `byz` under
  `local/country-validation-040-final/`. Seven further stock-generator cases
  passed in its `eu4-validation/country-option-matrix/`: legacy `fra`, legacy
  numeric `0`, mixed-case `bYz`, custom `mng`, and rejection of `France`, `FRA }`
  and `1AB`. Legacy FRA generated the same seed token as the 0.3.1 build.
- AP-native tests cover old shortcut IDs, free-text normalization and invalid
  options; these remain source-runtime gated. The frozen generation test does
  exercise the real `TextChoice` API and World, without stubs.
- The offline CLI also accepts a non-preset tag and rejects malformed input
  without overwriting the preceding manifest. Existing PoC seed identity has a
  regression test against its original recorded token.

Live play across starting countries, fixed-threshold balance, subjects and
technology groups remain pending. The expanded protocol is in
[manual-validation.md](manual-validation.md).

## Earlier distribution preparation — 0.3.1

- The original suite ran 50 tests: 48 passed, two skipped (PyYAML and source
  `AP_ROOT` unavailable). Added regressions cover malformed/BOM manifests, GUI
  prerequisites, offline-manifest rejection and preservation on reinstall/seed switch.
- The final repository suite ran **54 tests: 52 passed, two skipped**, zero failures.
  `demo_bridge.py` passed its explicitly synthetic round trip; compileall passed.
  `prepare_poc.py` refreshed the reference mod to 0.3.1 and the public/tools/demo
  build completed. No engine behavior is inferred from these checks.
- A newly copied Windows AP 0.6.7 installation under
  `local/public-validation-031/` loaded the built `eu4.apworld` from `custom_worlds`.
  The final World/UI build was checked again under `local/public-validation-031-final/`.
- The unmodified installed Launcher exported `Europa Universalis IV.yaml` using
  **Generate Template Options**. The unmodified installed generator accepted the
  player YAML, filled a 16-location seed and emitted a real `.apeu4.json` inside
  the seed ZIP. Its manifest was parsed and validated by the shared runtime.
- The actual frozen Launcher started the EU4 client in its child process; Kivy
  built the UI and the smoke mode exited automatically. Logs, screenshot, widget
  geometry, package hash and result JSON are retained in `eu4-validation/`.
  UI startup does not establish that every manual interaction works.
- Packaging tests build twice with identical hashes, inspect archive layout and
  metadata, check every public checksum, reject demo content from the player kit,
  and extract/run the optional source client. Offline demos are separately rendered.

The package conforms to the pinned [official AP 0.6.7 specification](https://github.com/ArchipelagoMW/Archipelago/blob/0.6.7/docs/apworld%20specification.md)
and [APWorldContainer metadata](https://github.com/ArchipelagoMW/Archipelago/blob/0.6.7/worlds/Files.py).
The World, Python package and rendered mod now use version 0.4.1; container version 7
is a different protocol field. No AP sources or server were replaced.

## Earlier evidence retained, not rerun by the UI smoke test

The report from 2026-10-26 recorded a real, unmodified AP 0.6.7 server accepting
16 checks and delivering 16 items to the frozen client's Session, using a
synthetic bound text save. This establishes protocol transport for that earlier
build; it does not establish EU4 reward execution. Original evidence remains in
`local/launcher-test/`. No historical experiment is presented as a new EU4 test.

## Outstanding gates

| Gate | Status / next experiment |
| --- | --- |
| Real EU4 text and zipped saves | Pending; bind, save and inspect an actual campaign |
| Native effects and console file rereading | Pending; apply two separately exported rewards without restarting EU4, verify exact amounts and no duplicates |
| Daily scan and old campaign migration | Pending; check flags after a game day and after the migration rescan |
| Reload, rollback and victory in game | Pending; save/restart, reject an old save, ratify and observe AP completion |
| Manual GUI install/connect/update/uninstall | Pending end-to-end with EU4; synthetic preservation regressions pass |
| Mixed-game seed and remote hosting | Pending; confirm an actual foreign player's check delivers an EU4 item |
| Source WorldTestBase suite | Not executed here; `AP_ROOT` source environment unavailable |
| DLC/OS/version matrix | No-DLC play and versions beyond Windows AP 0.6.7 / EU4 target unverified |
| GitHub workflow | Prepared, not run on hosted infrastructure; this folder has no Git remote |

Follow the exact [manual protocol](manual-validation.md) and keep observations,
logs, manifests and before/after saves under ignored `local/validation/`.
Passing mocks or fabricating acknowledgment flags cannot close an engine gate.
The reproducible commands and release file list are in [development.md](development.md).
No release was published, no remote changes pushed, and existing local data was preserved.
