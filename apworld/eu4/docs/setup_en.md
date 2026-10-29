# EU4 Windows setup

Requires Windows Archipelago 0.6.7 and non-Ironman EU4 1.37.5.0 with console
access and local text saves. Live EU4 acceptance is still pending.

1. Extract the player kit, use **Install APWorld** to install `eu4.apworld`, then
   fully restart Archipelago Launcher. No separate Python installation is needed.
2. Use Options Creator or edit the YAML; `starting_country` accepts any country's
   tag playable on 1444-11-11 (e.g. `byz`, `mng`), not its full name. Send it to the host.
   Obtain your generated
   `.apeu4.json` manifest after the host creates the seed. Never use OFFLINE-POC online.
3. Open **EU4 Client** (or **Open Patch** with the manifest). Select the manifest
   and EU4's Documents user folder, not its Steam installation.
4. Close EU4 and click **Installer le mod**. Enable **EU4 Archipelago** in a playset.
5. Start the configured country on 1444-11-11 without Ironman. Take the binding
   decision and save locally as text. Select that save in the client.
6. Enter the server and exact YAML player name, then **Se connecter**.
7. Save to report objectives. For incoming items, pause EU4, open its console,
   run `run eu4ap_sync.txt`, and save again to acknowledge rewards.
8. Apply the required Royal Charters, take the ratification decision, then save.

Options Creator shows 58 named countries alphabetically, with France preselected.
For an unlisted country choose Other country, expand Other country (advanced)
and replace the prefilled tag. `random` chooses a named country from the list.
Old tag-based YAMLs still work; listed names are also accepted. Country tags
are case-insensitive. Generation checks syntax, not
whether a country exists at the starting date. The start stays fixed to 1444-11-11
and switching countries during a campaign is unsupported.

Keep the client open while playing. Updates retain saves and `eu4ap/` campaign
state: back them up, close EU4/client, replace the package, restart AP and reinstall
the mod using the original manifest. The player kit's `docs/installation.md`
contains troubleshooting, removal instructions and links to validation protocols.
