# Validation status — 2026-10-29

Release candidate **0.3.1** targets Windows Archipelago **0.6.7** and EU4
**1.37.5.0**. This is not yet an accepted live-game release.

## Executed during distribution preparation

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
The World, Python package and rendered mod use version 0.3.1; container version 7
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
