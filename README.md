# Europa Universalis IV × Archipelago

Play an EU4 country in an Archipelago multiworld: pursue an achievement-inspired
national ambition while other players lift your fetters, unlock your regions and
send Seals of the Multiworld. Normal and Ironman campaigns are supported by design.
**EU4 Client is included in the Archipelago Launcher.** Players need neither
this repository nor a separate Python installation.

**0.5.0 is a release candidate.** Windows Archipelago 0.6.7 is the supported test
target; EU4 1.37.5.0 (normal or Ironman) is the engine target. Packaging, synthetic
synchronization and real AP generation are checked automatically.
**No 0.5.0 mechanic has been validated in EU4 yet** (experiments E1–E8, notably
whether an Ironman save reloads after the mod changes).
Read the [validation report](docs/validation.md) before using an important campaign.

## Windows quick start

1. Download and extract `eu4-player-kit-0.5.0.zip` supplied by the maintainer.
   Build scripts do not publish a release.
2. Install [Archipelago 0.6.7](https://github.com/ArchipelagoMW/Archipelago/releases/tag/0.6.7).
   In its Launcher choose **Install APWorld**, select `eu4.apworld`, then fully
   restart it. **EU4 Client** should appear under Clients.
3. Open **Options Creator**, select **Europa Universalis IV**, enter a unique
   player name and choose your country/options. Export the YAML and send it to
   your host, who also needs this `.apworld` to generate the seed. Editing
   `example.yaml` remains an alternative; `starting_country` accepts tags such
   as `fra`, `byz` and `mng` for countries playable on 1444-11-11.
4. Obtain your **generated `.apeu4.json` manifest** from the host. In **EU4 Client**,
   select it and your EU4 Documents user folder. With EU4 closed, click
   **Installer le mod**. The client creates the seed-specific mod.
5. Enable the mod in an EU4 playset. Start the configured country on 1444-11-11
   in the mode of your YAML (`save_mode`). Take **Archipelago: bind this campaign**
   (or its French translation).
6. In the client enter `hostname:port`, your YAML player name and optional
   password, then connect. Leave the client open while EU4 runs: it reads
   `game.log` and sends checks as they happen. A save is optional (normal mode).
7. Received items: the client shows a 4-digit code per item; take **Archipelago:
   receive a delivery** in EU4 and enter it (live, also in Ironman). Rare items
   without a code arrive at the next relaunch. Ratify the victory with its decision.

| File | Purpose |
| --- | --- |
| `eu4.apworld` | Install in AP; includes World, Launcher client and mod renderer |
| `example.yaml` | Player preferences submitted before seed generation |
| `AP_<token>_P<slot>.apeu4.json` | One player in one generated seed; supplied after generation |

`OFFLINE-POC` is a developer demonstration and cannot join a real seed.
There is no generic online mod ZIP: the client renders the mod from your manifest.
Use the standard Archipelago generator and server.

In **Options Creator**, choose a country from the alphabetical list of 58 named
shortcuts, such as **France (FRA)** (the default), **Byzantium (BYZ)** or **Ming (MNG)**.
For an unlisted country select **Other country (advanced tag)**, expand
**Other country (advanced)** and enter its tag. Old tag-based YAMLs remain valid.
The list is a shortlist, not an exhaustive game catalogue. Generation checks
the tag's syntax, not whether the country exists
on the starting map. Select an existing playable country on **1444-11-11**.
Other start dates remain unsupported. Forming a nation (Rome, Spain, Prussia…)
keeps the campaign through its binding flag, pending in-game confirmation.

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
