# EU4 Windows setup

Requires Windows Archipelago 0.6.7 and EU4 1.37.5.0, normal or Ironman.
Live EU4 acceptance of version 0.5.0 is still pending.

1. Extract the player kit, use **Install APWorld** to install `eu4.apworld`, then
   fully restart Archipelago Launcher. No separate Python installation is needed.
2. Use Options Creator or edit the YAML: country (`starting_country`, a tag such as
   `byz` or a listed name), `save_mode` (normal/ironman), `campaign_length`,
   `goal` (default mixed), `owned_dlcs` (the DLCs you run), fetters and traps.
   Send it to the host and obtain your generated `.apeu4.json` manifest.
   Never use OFFLINE-POC online.
3. Open **EU4 Client** (or **Open Patch** with the manifest). Select the manifest
   and EU4's Documents user folder, not its Steam installation.
4. Close EU4 and click **Installer le mod**. Enable **EU4 Archipelago** in a playset.
5. Start the configured country on 1444-11-11 in the chosen mode and take the
   binding decision.
6. Enter the server and exact YAML player name, then **Se connecter**. Keep the
   client open: it reads EU4's `game.log` and sends checks as they happen.
   The save field is optional (normal mode, uncompressed text saves only).
7. Received items: the client shows a 4-digit code for each; in EU4 take
   **Archipelago: receive a delivery**, enter it and confirm (live, also in
   Ironman). Items without a code apply after the next EU4 relaunch; in normal
   mode `run eu4ap_sync.txt` also works.
8. When the ambition, keys and seals are in place, take **ratify the victory**.

`goal: royal_charters` keeps the classic 0.4 mode (schema 1, console and text
saves, no Ironman). Options Creator shows 58 named countries alphabetically, with
France preselected; for an unlisted country choose Other country and set its tag.
Generation checks tag syntax, not whether a country exists at the starting date.
Forming a nation keeps the campaign (pending in-game confirmation).

Updates retain saves and `eu4ap/` campaign state: back them up, close EU4/client,
replace the package, restart AP and reinstall the mod using the original manifest.
The player kit's `docs/installation.md` contains troubleshooting and removal
instructions; `docs/gameplay.md` explains goals, fetters, keys and Ironman play.
