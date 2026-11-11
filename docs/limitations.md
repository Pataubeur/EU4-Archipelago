# Limitations and support boundary

- This is a release candidate awaiting EU4 acceptance. A generated native effect
  is not proof that it works in the engine. Real AP 0.6.7 generation and frozen
  Launcher startup have been exercised; see [validation.md](validation.md).
  **No 0.5.0 mechanic (game.log channel, inbox, fetters, keys, ambitions,
  DeathLink) has run in EU4 yet**: they are candidates gated by E1–E8.
- Ironman is **implemented as a candidate**: checks through `game.log` (E1),
  items through **live delivery codes** entered in game (E9). The mod is fixed for
  the whole campaign, so most items need neither a relaunch nor E2. Items without
  a code (server `/send`, DeathLinks beyond 20) use the relaunch inbox, which
  depends on E2 (an Ironman save still loads after the mod changes its checksum).
- Live deliveries are an **honour system**: codes are readable in the mod files
  and EU4 cannot verify reception. The client audits every claim and reports
  codes claimed before reception; it cannot undo them. Entering a code takes
  about five clicks per item.
- Binary saves are never parsed: their token table is not public. EU4 1.37.5
  compressed saves are binary even outside Ironman; the optional save of normal
  mode must be uncompressed (`compress_saves=no`). Achievements, cloud saves and
  EU4 multiplayer are unsupported; the mod changes the checksum, so Steam
  achievements are disabled. Use a separate launcher playset.
- The client must run while EU4 runs: EU4 truncates game.log at every launch.
  A yearly replay and the rescan decision recover a missed session. Two launches
  within the same minute share a log header and may be detected only if the file
  is shorter than before.
- EU4 1.37.5.0 is the engine test target, not a verified compatibility claim.
  Windows AP 0.6.7 is the supported test target and minimum package version.
  Mission identifiers are pinned to 1.37.5; another game version may rename them.
- No paid DLC is required. `owned_dlcs` must list the DLCs actually enabled:
  mission checks and DLC ambitions (Edge of Madness: El Dorado) depend on it,
  and a wrong declaration can make checks impossible. A no-DLC playtest is pending.
- Only the fixed 1444-11-11 start is supported, and `started_in` (bind decision)
  has no vanilla use: whether it rejects other dates is E8. Any country tag can
  be configured, but it must be playable at that date. Custom nations, random new
  worlds, total conversions and changing mods during the campaign are unsupported.
  Forming a nation is supported by design through the binding flag (E4 pending).
- AP logic mirrors the mod's guards but models neither game time nor the survival
  or strength of your country. Late calendar checks are excluded from progression
  by default (`exclude_long_checks`); dated achievements lose their deadline.
  Ambition difficulty and pacing (11–18 game years per hour measured on one
  player) are estimates, not playtest results.
- Relative development thresholds use variables set at binding (`export_to_variable`,
  `check_variable` comparing two variables): vanilla-attested syntax, untested here.
  Monthly income and navy thresholds are absolute and favour large countries.
- Negative colonist/diplomat/merchant modifiers may be clamped by the engine (E6).
- Classic `royal_charters` seeds keep 0.4 behaviour: console and text saves,
  no Ironman, tag changes rejected, fixed thresholds that loans can satisfy.
- Returning to an older save: in normal mode the client detects known regressions
  and stops; in Ironman it warns. Missing items are re-applied once in both modes.
  Do not branch the campaign or reuse one slot for two campaigns.
- Country flags are idempotency markers, not anti-cheat. EU4 console users can
  forge them, and game.log lines can be faked by anyone with file access.
- Only one EU4 user directory per active client. Keep `eu4ap/` (GUI state),
  manifest and save together when moving computers, with the client stopped.
  CLI users must also keep their explicitly selected SQLite database.
  The OS lock is per user directory, not a distributed/network filesystem lock.
- Very large saves (>256 MiB) and game.log growth over 64 MiB in one session are
  rejected. No game memory is accessed; only the process list is read.
- Item and location IDs are provisional and must be checked against community
  registries before a public release. The project is not an official AP World.
- Optional demo archives in `dist/demos/` are bound to OFFLINE-POC and cannot be
  used online. Changing mod definitions while EU4 is running is never done: the
  client writes the inbox only when `eu4.exe` is absent from the process list.
- The Launcher client uses AP's installed runtime. Only the optional developer
  CLI needs a source runtime; `dist/tools/` does not include AP dependencies.

Unverified hot reload is never used as a fallback. If an experiment fails, stop,
record the result and keep the failure visible; do not silently treat exports as
applied rewards.
