# Windows player guide

## Compatibility and prerequisites

Use Windows Archipelago **0.6.7** and EU4 **1.37.5.0**, non-Ironman with console
access, a local text save and a campaign starting on 1444-11-11. EU4 is the
intended engine target; live-game acceptance is pending. Other versions, OSes
and DLC combinations are unverified. No paid DLC is deliberately required;
a no-DLC game still needs testing. Avoid other gameplay mods for initial tests.

The release's `eu4.apworld` includes the World, Launcher GUI and mod renderer.
Archipelago supplies Python, Kivy and networking. **Players need no separate
Python, pip, Git, source checkout or compilation.** Start EU4 once to create its
user folder before installing the integration.

## Install Archipelago and prepare your player

1. Extract `eu4-player-kit-0.3.1.zip` supplied by the maintainer. If checksums
   accompany it, compare `Get-FileHash .\eu4-player-kit-0.3.1.zip -Algorithm SHA256`
   with the ZIP's line in `SHA256SUMS`.
2. Install [Archipelago 0.6.7](https://github.com/ArchipelagoMW/Archipelago/releases/tag/0.6.7).
   In its Launcher choose **Install APWorld**, select `eu4.apworld`, then close
   and reopen the Launcher. Alternatively copy it into the AP user folder's
   `custom_worlds` (use **Browse Files** to locate it). Keep the name `eu4.apworld`.
   Move duplicate EU4 packages outside AP search paths when updating.
3. Edit `example.yaml` in a text editor. Set a unique `name`, choose
   `starting_country` and the other options, preserving indentation. Send it to
   your host. **Generate Template Options** in the Launcher can also export EU4's
   complete template after package installation.
4. The host installs the same package and generates the multiworld. Obtain your
   `AP_<token>_P<slot>.apeu4.json` from its output ZIP, server address and password
   if needed. Keep the manifest for this campaign.

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
   `mod/eu4_archipelago.mod`. It cannot verify that the game is stopped.
4. Add **EU4 Archipelago** to a dedicated Paradox launcher playset and enable it.
   Use one seed's mod at a time.
5. Start the manifest's country on 1444-11-11 without Ironman. In Decisions take
   **Archipelago: bind this campaign** / **lier cette campagne**. Save locally as
   text to a dedicated file such as `ap_campaign.eu4`. Initially disable save
   compression. Cloud-only and binary saves are unsupported.

## Connect and play

Select that `.eu4` in the client. Enter the server's `hostname:port`, exact YAML
player name (not a country tag), and optional password. Click **Se connecter**.
A mismatched seed, slot, country or campaign blocks synchronization: correct the
selected files instead of resetting progress.

Keep the client open. The mod records objectives every game day; save to send
them. The client checks file changes every 250 ms and parses only changed saves.
Use the rescan decision for an immediate scan. Older campaigns upgraded from the
monthly scanner need that decision once to start the daily chain.

Incoming rewards remain pending until you pause EU4, open its console and enter:

```text
run eu4ap_sync.txt
```

Then save to the watched path. Only item flags in the save acknowledge the
reward. **Copier la commande EU4** copies the command. Repeating it is designed
to be idempotent; verify this with the [acceptance protocol](manual-validation.md)
before trusting a valuable campaign. Console keys depend on keyboard layout.
Once all required Royal Charters are applied, take **ratify the royal charters**
and save to report victory. Chat supports `!help`, `/help`, `/status`.
**Déconnecter** stops the connection and retains progress.

## Update, reinstall or remove

Close EU4 and the client. Back up the latest save, original manifest and the
entire `<EU4 user folder>/eu4ap/` directory. Replace `eu4.apworld` through
**Install APWorld**, restart AP and select the **same manifest**. Reinstall the
mod while EU4 is closed and load the same save. Saves and
`eu4ap/<token>/campaign.json` are retained. Do not generate a new seed to update
an existing campaign.

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
| Binary/unreadable save | Disable Ironman and use a local text save, initially uncompressed |
| Reward pending | Run the console command, save to the watched path, inspect EU4 error.log |
| Unknown native effect | Stop; retain engine version, logs and before/after saves; EU4 acceptance is pending |
| Server rejected / wrong slot | Check address, port, password, YAML name and manifest with the host |
| Rollback detected | Restore the latest synchronized save while keeping client state; do not reset state to bypass the check |
| Another process owns folder | Close the other client/installer; OS lock releases on exit |
| Access denied | Check writable user folder and Windows controlled-folder access permissions |

GUI campaign logs are beside `eu4ap/<token>/campaign.json`; AP logs are in its
user `logs` folder. Include versions and sanitized logs when reporting errors.
Keep private saves, manifests and passwords out of public reports.
See [validation.md](validation.md) for observed results and outstanding gates.
