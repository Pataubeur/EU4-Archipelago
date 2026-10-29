# Limitations and support boundary

- This is a release candidate awaiting EU4 acceptance. A generated native effect
  is not proof that it works in the engine. Real AP 0.6.7 generation and frozen
  Launcher startup have been exercised; see [validation.md](validation.md).
- Inbound rewards require `run eu4ap_sync.txt` and saving; outbound reporting
  requires a save. There is no fully automatic bidirectional bridge.
- EU4 1.37.5.0 is the engine test target, not a verified compatibility claim.
  Windows AP 0.6.7 is the supported test target and minimum package version.
  Other AP versions need the real integration suite before support is claimed.
- Ironman, binary saves, achievements, cloud saves and EU4 multiplayer are
  unsupported. The console requires non-Ironman; this mod changes the checksum
  and should not be used for achievements. Use a separate launcher playset.
- No paid gameplay DLC is intentionally required. This must still be checked
  with a no-DLC playtest. Do not infer DLC compatibility from mocks.
- Only the fixed 1444-11-11 start and eight listed tags are supported. Custom
  nations, random new worlds, total conversions, spectator play, tag changes
  and changing mods during the campaign are unsupported.
- No real save fixture is bundled. The parser has synthetic text/ZIP fixtures;
  a user-provided genuine save is necessary to establish format compatibility.
- Returning to an older save can lose already-applied rewards while AP checks
  remain completed. The client detects known regressions and stops. Same-date
  rollback before any recorded flag changed may be undetectable. Do not branch
  the campaign or reuse one slot for two campaigns.
- Country flags are idempotency markers, not anti-cheat. EU4 console users can
  forge them. Running an exported file against an unsaved branch before the
  client observes it lies outside the synchronization guarantee.
- Only one EU4 user directory per active client. Keep `eu4ap/` (GUI state),
  manifest and save together when moving computers, with the client stopped.
  CLI users must also keep their explicitly selected SQLite database.
  The OS lock is per user directory, not a distributed/network filesystem lock.
- Very large saves (>256 MiB) are rejected. Frequent full-save parsing can be
  expensive; no game memory is accessed. Parser CPU time may delay CLI responses.
- Item IDs are provisional and must be checked against community registries
  before a public release. The project is not an official AP World.
- Optional demo archives in `dist/demos/` are bound to OFFLINE-POC and cannot be
  used online. The Launcher client generates the real seed's mod before launch.
  Changing mod definitions while EU4 is running is unsupported.
- The Launcher client uses AP's installed runtime. Only the optional developer
  CLI needs a source runtime; `dist/tools/` does not include AP dependencies.

Unverified hot reload is never used as a fallback. If console `run` does not
read updated files in the tested game version, stop the experiment and record
the result; do not silently treat exports as applied rewards.
