# Development and release preparation

Players follow [installation.md](installation.md). These commands are for maintainers.
The shared runtime is only in `apworld/eu4/runtime/`; the optional Python package
and portable source ZIP expose it as `eu4_client`. Do not copy it to another source tree.
`mod/` is the checked-in offline rendering, not a mod for generated multiworlds.

## Local checks and build

The dependency-free tools work with Python 3.10+. The AP 0.6.7 source runtime
needs its own dependencies and supported Python (3.11.9 through 3.13.x on Windows),
as described in its [official source guide](https://github.com/ArchipelagoMW/Archipelago/blob/0.6.7/docs/running%20from%20source.md).

```powershell
python -m unittest discover -s tests -t . -v
python scripts/demo_bridge.py
python -m compileall -q apworld scripts tests
python scripts/build_apworld.py
```

Optional test extras: `python -m pip install -e '.[test]'`. Unittest discovers the
same repository tests as pytest; without PyYAML the YAML test explicitly skips.
Without `AP_ROOT` the real AP WorldTestBase suite explicitly skips. Never count
these skips as completed integration tests.

The build produces in `dist/release/`:

| Artifact | Distribution |
| --- | --- |
| `eu4.apworld` | Installable World and Launcher client, no extra runtime dependencies beyond AP |
| `example.yaml` | Player configuration, not a seed manifest |
| `RELEASE.json` | Release version, compatibility targets, candidate status and package hashes |
| `eu4-player-kit-0.4.1.zip` | Package, YAML, metadata, license and documentation for players |
| `SHA256SUMS` | SHA-256 of each file above, including the player ZIP |

`python scripts/build_apworld.py --include-tools --include-demos` additionally
builds `dist/tools/eu4-client-source.zip` (requires Python) and
`dist/demos/OFFLINE-ONLY-eu4-mod.zip` (cannot connect online), each with checksums.
The demo is freshly rendered in a temporary directory; stale files from `mod/`
are never silently packaged. `python scripts/prepare_poc.py` explicitly refreshes
the reference `mod/` and `config/poc.apeu4.json` when developing native scripts.

The builder uses fixed ZIP timestamps and sorted entries. Tests build twice,
compare hashes, inspect contents, verify checksums, extract and launch the optional
source CLI. Build into a new directory to prepare a release from a clean output:
`python scripts/build_apworld.py local/release-review`.
Old `dist/` files and user data are preserved; **publish only the five named
public files**, not `dist/` recursively. No command here publishes or pushes.

Release identity is `runtime/version.py`; Python packaging reads its `VERSION`.
Update `archipelago.json` and player documentation at the same time. The builder
rejects disagreement between runtime and World versions/minimum AP version.

## Official Archipelago conventions

The [AP 0.6.7 package specification](https://github.com/ArchipelagoMW/Archipelago/blob/0.6.7/docs/apworld%20specification.md)
defines the lowercase archive/module naming and metadata. The deterministic builder
emits `eu4/__init__.py`, relative World imports, bundled tutorial/runtime resources
and a root `archipelago.json`. Source metadata stays in `eu4/archipelago.json`;
container fields are added only during packaging, using container version 7 and
compatibility 7 from [APWorldContainer](https://github.com/ArchipelagoMW/Archipelago/blob/0.6.7/worlds/Files.py).
These container versions are separate from the World release version 0.4.1.
The official source Launcher also offers **Build APWorlds** for development;
our builder reproduces the pinned container layout while adding release artifacts.

Client registration uses the official [LauncherComponents API](https://github.com/ArchipelagoMW/Archipelago/blob/0.6.7/worlds/LauncherComponents.py):
`Component`, `.apeu4.json` suffix identification and `launch_subprocess`.
GUI imports are delayed until launch. The installed Windows runtime supplies
the GUI/network libraries; JSON campaign storage avoids the unavailable SQLite
module in that runtime. The optional source CLI retains SQLite.

## Check a Windows installation in isolation

After building, run from this repository (choose a work directory that does not exist):

```powershell
python scripts/check_archipelago.py --frozen --ap-root 'C:\Archipelago' --work-dir local/ap-release-check
```

The checker copies the installed runtime, excludes existing custom worlds,
profiles and output, installs the candidate into the copy's `custom_worlds`,
exports the official YAML template, generates a seed with `ArchipelagoGenerate.exe`,
validates the output manifest and starts/closes the actual Launcher GUI in smoke
mode. Its isolated profile never overwrites the user's client settings. Evidence,
package hash and explicit exclusions remain under `eu4-validation/` in that copy.
Pass `--country mng` (or another tag) to verify free-text country selection through
the real generator. The flag works with both source and frozen check modes.
Add `--options-creator` when the source installation includes
`ArchipelagoOptionsCreator.exe`. The isolated copy receives a validation-only
probe from `tests/frozen/selector_probe.py`: it checks the actual country dropdown,
France default, alphabetical labels, selects Ming, exports with the official UI
action and generates that exported YAML. The OS save dialog is redirected to
the evidence directory; no core sources or production World are patched.
This verifies UI startup, not manual button interactions or engine execution.
The source installation, original `local/` experiments and live saves are retained.

## Source runtime and optional CLI

Install the candidate `.apworld` in a prepared AP 0.6.7 source runtime's
`custom_worlds`. Use that runtime's Python for both checks:

```powershell
$env:AP_ROOT = 'C:\AP-source'
python -m unittest discover -s tests -t . -v
python scripts/check_archipelago.py --ap-root $env:AP_ROOT
```

The second command expects an already installed package. It invokes the real
`Generate.py` with the example YAML and validates the generated manifest.
`python -m unittest worlds.eu4.test -v` from the AP source root runs its native
WorldTestBase tests. No stub World API is used for these checks.

`StartingCountry` uses AP's [Choice API](https://github.com/ArchipelagoMW/Archipelago/blob/0.6.7/Options.py)
so normal UI selection has no adjacent empty input. `runtime/countries.py` is
the single source of named shortcuts and display labels. Legacy IDs 0-7 are
unchanged; other tags use stable base-36-derived integer IDs, independent of menu
sorting. Arbitrary tags in existing YAMLs still resolve through `.tag`.
The explicit Other country choice uses `custom_starting_country`, a FreeText
option in a collapsed advanced group. `EU4Options.country_tag` resolves the
active choice and ignores the advanced field for normal selections.
The shared `country_tag()` validator rejects script
syntax and malformed tags. Manifests require canonical uppercase tags without
normalizing existing identity fields; their schema/tokens are unchanged.
Tests cover the legacy presets, additional tags, binding generation, country
isolation and synthetic reward acknowledgment. Real Options tests also live in
`worlds.eu4.test`; the repository does not fake that API when AP is unavailable.

Host from that AP root with real YAMLs in a dedicated folder:

```powershell
python Generate.py --player_files_path 'C:\APPlayers' --outputpath 'C:\APOutput' --seed 12345 --multi 1 --spoiler 1
python MultiServer.py 'C:\APOutput\AP_<generated seed>.zip' --host 127.0.0.1 --port 38281
```

Distribute each player's `.apeu4.json` from the generated ZIP. The stock server
handles the seed without code changes. For a mixed-game seed, include the other
players' YAMLs and required Worlds. The source CLI is optional:

```powershell
python scripts/eu4_client.py install-mod --manifest 'C:\APOutput\player.apeu4.json' --eu4-user-dir 'C:\EU4-user'
python scripts/eu4_client.py connect --ap-root 'C:\AP-source' --server localhost:38281 --name EU4Player --manifest 'C:\APOutput\player.apeu4.json' --state local/campaign.sqlite3 --save 'C:\EU4-user\save games\campaign.eu4' --eu4-user-dir 'C:\EU4-user'
```

Extract the source-client ZIP and use `python -m eu4_client`, or install this
project with pip for `eu4-ap`. Online commands require AP's source runtime and
dependencies, not a similarly named PyPI package. Keep the CLI database when
moving or updating; do not interchange it with the GUI's JSON state.

## CI and acceptance gates

The optional GitHub Actions workflow runs unit/YAML/package checks on Windows,
prepares downloadable build artifacts, and can run the pinned upstream AP source
suite and real seed generation on manual request. It never creates a release.
This workspace has no Git metadata or configured remote; the workflow becomes
active only if this project is hosted on GitHub. Its hosted execution is unverified here.

Before a stable public release, execute [manual-validation.md](manual-validation.md):
real EU4 save parsing, two successive reward scripts without restarting, replay,
save/reload, daily scanning/migration, no-DLC play, reconnect and mixed-game delivery.
Also check the provisional item/location ID range with the AP community before
seeking official inclusion. Record failures and exact versions in the validation report.
