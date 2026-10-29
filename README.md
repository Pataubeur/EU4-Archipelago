# Europa Universalis IV × Archipelago

Play an EU4 country in an Archipelago multiworld. Objectives in your save send
checks; received items produce rewards applied through EU4's console.
**EU4 Client is included in the Archipelago Launcher.** Players need neither
this repository nor a separate Python installation.

**0.3.1 is a release candidate.** Windows Archipelago 0.6.7 is the supported test
target; EU4 1.37.5.0, non-Ironman, is the engine target. Packaging, synthetic-save
synchronization and real AP generation can be checked automatically.
**Live EU4 rewards, daily events and mixed-game play still need acceptance.**
Read the [validation report](docs/validation.md) before using an important campaign.

## Windows quick start

1. Download and extract `eu4-player-kit-0.3.1.zip` supplied by the maintainer.
   Build scripts do not publish a release.
2. Install [Archipelago 0.6.7](https://github.com/ArchipelagoMW/Archipelago/releases/tag/0.6.7).
   In its Launcher choose **Install APWorld**, select `eu4.apworld`, then fully
   restart it. **EU4 Client** should appear under Clients.
3. Edit `example.yaml`: set a unique `name` and choose your options. Send the YAML
   to your host, who also needs this `.apworld` to generate the seed.
4. Obtain your **generated `.apeu4.json` manifest** from the host. In **EU4 Client**,
   select it and your EU4 Documents user folder. With EU4 closed, click
   **Installer le mod**. The client creates the seed-specific mod.
5. Enable the mod in an EU4 playset. Start the configured country on 1444-11-11
   without Ironman. Take **Archipelago: bind this campaign** (or its French
   translation), then save to a dedicated local text `.eu4` file.
6. Select that save in the client, enter `hostname:port`, your YAML player name
   and optional password, then connect. Leave the client open while playing.
7. Save to send objectives. For rewards, pause, open EU4's console, enter
   `run eu4ap_sync.txt`, then **save again** to acknowledge them.

| File | Purpose |
| --- | --- |
| `eu4.apworld` | Install in AP; includes World, Launcher client and mod renderer |
| `example.yaml` | Player preferences submitted before seed generation |
| `AP_<token>_P<slot>.apeu4.json` | One player in one generated seed; supplied after generation |

`OFFLINE-POC` is a developer demonstration and cannot join a real seed.
There is no generic online mod ZIP: the client renders the mod from your manifest.
Use the standard Archipelago generator and server.

[Player guide, updates and troubleshooting](docs/installation.md) ·
[Gameplay](docs/gameplay.md) · [Known limits](docs/limitations.md) ·
[Manual acceptance protocol](docs/manual-validation.md)

## Build and contribute

Maintainers use Python 3.10+:

```powershell
python -m unittest discover -s tests -t . -v
python scripts/build_apworld.py
```

Public artifacts and SHA-256 checksums are in `dist/release/`. Optional source
client and offline demos are separate:
`python scripts/build_apworld.py --include-tools --include-demos`.
Existing files elsewhere in `dist/` are preserved; publish only the documented
files in `dist/release/`, never old root-level PoC archives or local data.

See [development and release checks](docs/development.md). Sources live in
`apworld/eu4/`, with one shared runtime in `apworld/eu4/runtime/`; `config/`
contains examples, `tests/` checks, `scripts/` tools and `docs/` guides.
`mod/` is a generated, checked-in offline reference; `dist/` and `local/` are
ignored outputs and local experiments. No user files are deleted for cleanup.

MIT licensed. Unofficial integration; no proprietary game files are distributed.
