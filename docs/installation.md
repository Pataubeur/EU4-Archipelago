# Windows player guide

## Compatibility and prerequisites

Use Windows Archipelago **0.6.7** and EU4 **1.37.5.0**, with a campaign starting
on 1444-11-11, in **normal** or **Ironman** mode (`save_mode` in your YAML).
EU4 is the intended engine target; live-game acceptance is pending, and Ironman
depends on experiments E1–E3 (see [validation.md](validation.md)). Other
versions, OSes and DLC combinations are unverified. No paid DLC is required;
declare the DLCs you run in `owned_dlcs`. Avoid other gameplay mods.

The release's `eu4.apworld` includes the World, Launcher GUI and mod renderer.
Archipelago supplies Python, Kivy and networking. **Players need no separate
Python, pip, Git, source checkout or compilation.** Start EU4 once to create its
user folder before installing the integration.

## Install Archipelago and prepare your player

1. Extract `eu4-player-kit-0.5.0.zip` supplied by the maintainer. If checksums
   accompany it, compare `Get-FileHash .\eu4-player-kit-0.5.0.zip -Algorithm SHA256`
   with the ZIP's line in `SHA256SUMS`.
2. Install [Archipelago 0.6.7](https://github.com/ArchipelagoMW/Archipelago/releases/tag/0.6.7).
   In its Launcher choose **Install APWorld**, select `eu4.apworld`, then close
   and reopen the Launcher. Alternatively copy it into the AP user folder's
   `custom_worlds` (use **Browse Files** to locate it). Keep the name `eu4.apworld`.
   Move duplicate EU4 packages outside AP search paths when updating.
3. Edit `example.yaml` in a text editor. Set a unique `name`, choose
   `starting_country` and the other options, preserving indentation. Set any
   playable starting country's tag, e.g. `byz`, `mng` or `azt`; case is ignored.
   Names from the menu, such as `France` or `Ming`, are also accepted. Send it to
   your host. **Generate Template Options** in the Launcher can also export EU4's
   complete template after package installation.
4. The host installs the same package and generates the multiworld. Obtain your
   `AP_<token>_P<slot>.apeu4.json` from its output ZIP, server address and password
   if needed. Keep the manifest for this campaign.

Alternatively open **Options Creator** in AP 0.6.7. **Starting Country** is a
dropdown with 58 alphabetically sorted named shortcuts and **France (FRA)**
selected by default. Choose the desired country and export the YAML; there is
no blank tag input next to the normal selection. For an unlisted country,
choose **Other country (advanced tag)**, expand **Other country (advanced)**
and change **Other Country Tag** from its prefilled `FRA` to the desired tag.
That advanced field is ignored for normal selections. The shortlist is not a
complete game-country catalogue. `random` chooses among its 58 named countries,
never the advanced entry. The generator checks tag
syntax but has no installed-game country catalogue: the country must actually
be playable in your EU4 installation on 1444-11-11. Incorrect or nonexistent
tags cannot bind a campaign or pass save-country validation.

The `.apworld` installs code; YAML selects preferences before generation; the
manifest identifies a generated seed and slot. They are not interchangeable.
`OFFLINE-POC` manifests and `OFFLINE-ONLY` archives are demonstrations rejected by
this GUI. Renaming a demonstration cannot make it an online manifest.

The generator machine needs this custom World installed. Do not assume the
public archipelago.gg generator accepts it. Hosts can use the standard local
**Generate** component with YAMLs in `Players`, then **Host** with the resulting
ZIP. No AP source changes or replacement server are required. Source and CLI
host instructions are in [development.md](development.md).

## Install the mod and bind the campaign

1. Open **EU4 Client** in Archipelago Launcher and select your generated manifest.
   **Open Patch** also recognizes `.apeu4.json`.
2. Verify the EU4 user folder, usually `Documents/Paradox Interactive/Europa
   Universalis IV`, containing `settings.txt` or `save games`. Windows Documents
   redirection, including OneDrive, is detected. This is separate from Steam's
   game installation. Use **Parcourir** for a custom `userdir.txt` location.
3. **Close EU4**, click **Installer le mod (EU4 fermé)** and wait for success.
   The client writes its generated files in `mod/eu4_archipelago/` and
   `mod/eu4_archipelago.mod`. For 0.5.0 manifests it refuses while `eu4.exe`
   runs (process list only) and keeps already received items in the inbox.
4. Add **EU4 Archipelago** to a dedicated Paradox launcher playset and enable it.
   Use one seed's mod at a time.
5. Start the manifest's country on 1444-11-11, in the mode chosen in your YAML
   (Ironman or not). In Decisions take **Archipelago: bind this campaign** /
   **lier cette campagne**. In normal mode you may also save locally as an
   **uncompressed** text file (`compress_saves=no`): EU4 1.37 compresses saves
   in binary form, which the client cannot read. Cloud-only saves are unsupported.

## Connect and play

Enter the server's `hostname:port`, exact YAML player name (not a country tag),
and optional password. The save field is optional for 0.5.0 manifests (normal
mode only; it adds rollback detection) and required for classic `royal_charters`
manifests. Click **Se connecter**. The client checks that the installed mod
matches the manifest. A mismatched seed, slot or campaign blocks synchronization:
correct the selected files instead of resetting progress.

Keep the client open while EU4 runs. It reads EU4's `logs/game.log`, where the
mod writes `EU4AP <token> …` lines: completed checks are sent as they happen,
without saving. EU4 overwrites this log at each launch; the mod replays its
state every game year and when you take **scan objectives now**, so a client
started late catches up.

Received items:

- **Live (normal and Ironman)**: the client's journal and summary show a 4-digit
  code for each received item (« À saisir en jeu »). In EU4 take **Archipelago:
  receive a delivery**, enter the code, check the item name and accept. The item
  applies immediately, without saving or relaunching.
- **Ironman, items without a code** (rare: server `/send`, extra DeathLinks): close EU4. The client installs every received item into the mod
  (`eu4ap_inbox.txt`) and shows « en attente du prochain relancement ». Relaunch
  EU4 and continue: items apply the next game day, once each, announced by an
  event. Relaunch at natural moments or when a key or seal waits.
- **Normal**: same relaunch path, or the fast path: pause, open the console and
  run `run eu4ap_sync.txt` (**Copier la commande EU4** copies it). Repeating it is
  harmless: every item has its own flag.

The client marks an item applied only when EU4 logs it (or a save contains its
flag), never because it wrote a file. Once the goal requirements are met, take
**ratify the victory**; the log reports it immediately. Chat supports `!help`,
`/help`, `/status`. **Déconnecter** stops the connection and retains progress.

## Update, reinstall or remove

Close EU4 and the client. Back up the latest save, original manifest and the
entire `<EU4 user folder>/eu4ap/` directory. Replace `eu4.apworld` through
**Install APWorld**, restart AP and select the **same manifest**. Reinstall the
mod while EU4 is closed and load the same save. Saves and
`eu4ap/<token>/campaign.json` are retained. Do not generate a new seed to update
an existing campaign.

Version 0.5.0 introduces manifest **schema 2** (ambitions, fetters, keys,
Ironman). Schema 1 manifests from 0.4.x keep their tokens, IDs and behaviour and
are still read; a campaign never changes schema. A YAML without a `goal` key now
generates the new default `mixed` goal; set `goal: royal_charters` for the classic
mode. Do not edit an existing manifest to switch countries or schema: generate a
new seed and use a new campaign instead.

A different manifest switches the active mod, backing up the previous mod to
`eu4ap/mod-backups/<token>-<timestamp>/`. To resume an old campaign, close EU4,
reinstall its original manifest and load its latest save. Client state is
separate per seed/slot. Never enable two generated AP mods together or run two
clients against the same EU4 user folder.

To uninstall, close both programs and remove the mod from the playset. Remove
`mod/eu4_archipelago.mod`, `mod/eu4_archipelago/` and AP's
`custom_worlds/eu4.apworld`. Keep saves, manifests and `eu4ap/` if you may resume.
Settings are in `%LOCALAPPDATA%/EU4Archipelago/client.json`; passwords are never
stored. Deleting that settings file only resets remembered paths. Deleting
`eu4ap/` loses rollback history: back it up first. The installer does not delete
saves, campaign state or unrelated files.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| No EU4 Client | Fully restart AP, check AP 0.6.7 and `custom_worlds/eu4.apworld`; move duplicate worlds outside search paths; inspect AP logs |
| Invalid manifest | Select the host's generated `.apeu4.json`, not YAML, `.apworld` or PoC |
| Invalid EU4 folder | Launch EU4 once; select its Documents user folder including any OneDrive/custom redirection |
| No binding decision | Check playset, selected country/date and EU4 `logs/error.log` |
| Save not bound / wrong seed | Bind and save with the matching mod and manifest |
| Binary/unreadable save | Clear the save field (0.5.0 uses game.log), or save uncompressed outside Ironman |
| Items « codes à saisir » | Take **receive a delivery** in EU4 and enter each code |
| « code inconnu » in game / client warning | Re-enter the code shown by the client; a claimed but unreceived code is reported, not undone |
| Items « sans code, au prochain relancement » | Close EU4; the client installs them; relaunch and play one day |
| Items installed but not applied | Load the bound campaign and unpause one day; check EU4 `logs/error.log` |
| No check sent | Keep the client open while EU4 runs; take **scan objectives now** to replay the state into game.log |
| « Le mod installé ne correspond pas » | Close EU4, select the right manifest, click **Installer le mod** |
| Mode warning (Ironman/normal) | The YAML `save_mode` differs from the game; logic (traps, delays) assumed the other mode |
| Reward pending (normal) | Run the console command or relaunch EU4, inspect EU4 error.log |
| Unknown native effect | Stop; retain engine version, logs and before/after saves; EU4 acceptance is pending |
| Server rejected / wrong slot | Check address, port, password, YAML name and manifest with the host |
| Rollback detected | Restore the latest synchronized save while keeping client state; do not reset state to bypass the check |
| Another process owns folder | Close the other client/installer; OS lock releases on exit |
| Access denied | Check writable user folder and Windows controlled-folder access permissions |

GUI campaign logs are beside `eu4ap/<token>/campaign.json`; AP logs are in its
user `logs` folder. Include versions and sanitized logs when reporting errors.
Keep private saves, manifests and passwords out of public reports.
See [validation.md](validation.md) for observed results and outstanding gates.
