# Required real-runtime acceptance experiment

Every item below is **pending**, not a reported result. Record exact EU4/AP
versions, DLC list, OS, mod checksum, logs, before/after saves and commands in
an ignored `local/validation/` directory. Never redistribute proprietary files.

## Phase 2: native PoC, before relying on world generation

1. Run `python scripts/prepare_poc.py` or create a manifest with
   `python scripts/eu4_client.py poc-manifest --output config/poc.apeu4.json`.
2. With EU4 stopped, install with `install-mod --manifest config/poc.apeu4.json
   --eu4-user-dir <your EU4 user directory>`.
3. Enable the mod, start FRA, 1444-11-11, non-Ironman, no other mods. Take the
   bind decision. Save locally as plaintext to `<save>`. Record whether the
   manifest binding flag appears under FRA/flags and EU4 error.log is clean.
4. Run `inspect --manifest config/poc.apeu4.json --state local/poc.sqlite3
   --save <save> --eu4-user-dir <userdir>`. No server is involved.
5. Satisfy Treasury: 100 ducats (or reach 1445), rescan, save and inspect again.
   Verify exactly the expected check ID is retained on repeated inspections.
   Let a game day pass without using rescan, save, and independently verify daily
   event scanning. For an older campaign upgraded from the monthly scanner,
   use rescan once to start the daily chain before this experiment.
6. Record treasury, queue a reward with `poc-reward --manifest
   config/poc.apeu4.json --state local/poc.sqlite3 --item "100 Ducats"`.
   Inspect to export. It must show pending, never confirmed yet.
7. In EU4, run `run eu4ap_sync.txt`. Verify treasury increases by exactly 100
   while paused. Run it again: no further increase. Save and inspect: confirmed.
8. While EU4 remains open, queue a SECOND reward, inspect to replace the file,
   then issue the SAME console command. Verify another 100, exactly once. This
   is the mandatory experiment establishing runtime `run` file rereading;
   it does not establish hot reload of event definitions.
9. Save, stop EU4 and client, relaunch/reload, inspect and run again. Confirm
   both flags persist and no ducats are added a third time. Repeat for monarch
   power, prestige and three Royal Charters, then ratification.
10. Read a zipped text save; compare to plaintext results. Try a deliberately
    older save: synchronization must block and invalidate the export. Restore
    the latest save; do not reset the state database to bypass the check.

If any native syntax fails, fix the generator, regenerate **while EU4 is
stopped**, and repeat using a fresh PoC campaign. An engine PoC failure means
phase 2 is incomplete, even if all Python tests pass.

## Phases 3–5: real Archipelago integration

1. Install eu4.apworld in AP 0.6.7. Run `python -m unittest worlds.eu4.test -v`
   from the AP source runtime. Run `python scripts/check_archipelago.py
   --ap-root <AP checkout>` from this repository for actual YAML generation.
2. Start the unmodified MultiServer with generated multidata. Install the real
   manifest mod, bind a fresh campaign, connect the client with the same manifest.
3. Complete one objective, save, verify the server accepts one location and
   sends the assigned item to its actual recipient. Do not assume the checked
   location contains an EU4 item in mixed-game seeds.
4. Complete a remote player's location containing an EU4 item (use the spoiler
   to choose it). Verify item index/ID/source are persisted by this client.
5. Apply, save and confirm the item; repeat the run command to test deduplication.
6. Stop/restart the AP server to test CommonClient reconnect. Complete an EU4
   objective while offline, save, reconnect and verify delayed reporting.
7. Restart the client without changing its DB/save. Verify ReceivedItems index-0
   replay adds no duplicate reward and acknowledged checks are not resent.
8. Receive and apply the required charters, ratify, save; verify server goal 30.
9. Repeat with two EU4 slots plus a different game, separate campaigns/user
   directories, then test BRA/HAB with only calendar checks and no paid DLC.

A synthetic-save demo, fake CommonContext or unit test cannot substitute for
these observations. Record all failures, including unsupported game syntax.
