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
10. Generate a non-legacy tag (e.g. BYZ, MNG or AZT) through Options
    Creator and the generator. Verify that the manifest and installed bind decision
    name the same country, bind it on 1444-11-11, then send a check, apply a reward,
    save and restart. Repeat across a small country, subject and low-technology
    start. Keep the fixed thresholds' balance observations separate from bridge
    correctness. Try a wrong country and a different starting date: binding must
    not succeed. A syntactically valid but nonexistent tag may pass generation;
    it must not bind any unrelated country. Keep old-manifest update coverage too.
11. In the named selector, confirm France is shown initially and select a different
    country by name. Export and generate its YAML, then install/bind the matching
    country. For an unlisted tag, select Other country and edit the advanced field;
    verify that returning to a named choice ignores the advanced tag. Do not claim
    the shortlist is the complete 1444 country roster.

A synthetic-save demo, fake CommonContext or unit test cannot substitute for
these observations. Record all failures, including unsupported game syntax.

## Feasibility experiments E1–E8 (progression and Ironman design)

These gate [design-progression.md](design-progression.md). They use a separate
test mod, never the seed mod. `scripts/feasibility_kit.py` installs it, rewrites
its inbox while EU4 is closed, keeps a copy of `game.log` before each rewrite
(EU4 overwrites that file at every launch) and summarises the `EU4APX` lines.
Evidence goes to `local/validation/feasibility/<run>/`.

Setup, once per run (EU4 closed):

```powershell
python scripts/feasibility_kit.py install --run R1 --tag BYZ --game-dir "<EU4 install>"
```

Create a launcher playset with **only** `EU4AP feasibility experiments`.
Normal launch options (no `-debug_mode`). Note DLC list and EU4 version.

| Id | Protocol | Pass criterion |
| --- | --- | --- |
| E1 `log` in Ironman | New **Ironman** game, BYZ 1444-11-11. Take *AP test: start experiment*. Unpause 2 months. Exit to menu. `report --run R1`. Repeat once in a normal game (run R2). | Lines `MODE ironman`, `START <name> 1444`, `TICK` with year and country name substituted. Fail if no line or raw `[GetYear]`. |
| E2 Ironman reload after mod change | After E1 (Ironman autosave on exit, EU4 closed): `inbox --run R1 --generation 2`. Relaunch with the same playset and **Continue** the Ironman game. | The save loads and stays Ironman. Record any checksum warning verbatim and with a screenshot. A refusal is a **documented failure** (design § 4.6), not something to work around. |
| E3 Inbox after relaunch | Continue E2 for 2 days. `report`. Then exit, relaunch, play 2 days without changing the inbox, `report` again. | `GEN 2`, `ITEM 2` exactly once; item 1 not reapplied; treasury +11 for item 2 only. Crash variant: after `ITEM 2` appears, kill `eu4.exe` before the next autosave, relaunch: `ITEM 2` appears once more and treasury matches one application. |
| E4 Flags after formation | Normal game, any country, start the experiment, then *AP test: change tag* (`change_tag = ROM` by default, `--form-tag` to change). Play 2 days, save as **uncompressed text**. | `FORM_BEFORE`/`FORM_AFTER`, then `FORMATION_FLAGS kept <new name>`; daily `TICK` continues. In the text save, `player=` is the new tag and `eu4apx_started` is under that tag's `flags`. Then repeat with a real formation decision (e.g. Spain) in a later run. |
| E5 on_actions merge | Start a **new** game (on_startup fires at game start). `report`. | Both `ONACTION A` and `ONACTION Z` = mod files with the same key are merged. Only `Z` = the last definition replaces earlier ones (then mods must not define vanilla on_action keys). Check `error.log` either way. |
| E6 Negative capacity modifiers | In a game where the country has ≥1 colonist (or after Exploration ideas), take *apply fetters*. Read colonists, diplomats, merchants in the UI; try to send one of each. Take *remove fetters*. | Record displayed totals (0 or negative?) and whether actions are blocked. Restored values after removal. |
| E7 `mission_completed` | Play the tested country until its first mission completes (the probe covers all its mission IDs and those of the formation tag). | `MISSION <id>` once for each completed mission, never for an uncompleted one or a mission from another tree. |
| E9 Live delivery codes | Normal **and** Ironman. `poc-manifest --schema 2 --save-mode ironman`, `install-mod`, list codes with `delivery-codes --manifest`. Bind, then take *receive a delivery*: enter a valid code, a wrong code, the same code twice, a trap code before 1450, and once while paused. | Each digit event shows; confirmation shows the code and the item name; valid code applies once with `CLAIM <code>`; others log `CLAIM_UNKNOWN` / `CLAIM_DUPLICATE` / `CLAIM_EARLY` and change nothing; the event chain works while paused; no `error.log` entry. Save/reload (normal) or exit/continue (Ironman) keeps the delivery flag. |
| E8 Remaining script checks | Not covered by the kit yet; add one decision per check before running: bind decision on a 1453 start (`started_in`), `check_variable` comparing two variables, `great_power_rank`, `has_won_war_against` inside `any_rival_country`, manual development without DLC, and game speed with a 150-condition weekly scan vs. none. | Each result recorded individually, including failures. |

After all runs: `python scripts/feasibility_kit.py uninstall`, then record each
result (pass/fail/inconclusive, with log excerpts) in [validation.md](validation.md).
A missing `EU4APX` line is a result, not a reason to switch to a different channel
without documenting it.

## 0.5.0 acceptance: every mechanic, normal and Ironman

Prerequisite: E1 and E2 recorded (pass or documented failure). Generate two real
seeds with AP 0.6.7: **A** = BYZ, `standard`, `save_mode: normal`, all fetters,
`trap_percentage: 30`, `death_link: true`; **B** = the same with
`save_mode: ironman`. Keep `game.log` copies (`feasibility_kit.py` copies them
into `local/validation/`), the client log beside `campaign.json`, the manifest
and before/after saves. Each line is pending until observed in **both** A and B,
except where marked.

| Mechanic | Procedure | Expected |
| --- | --- | --- |
| Install / mismatch | Install A with EU4 running, then closed; connect with B's manifest selected after installing A | Refused while running; installed when closed; mismatch refused before connecting |
| Bind and HELLO | Take the bind decision | `EU4AP <token> HELLO 2 normal` (A) / `ironman` (B); no mode warning; starting fetter modifiers shown in purple; no error in `logs/error.log` |
| Starting fetters | Inspect colonists, diplomats, merchants, naval and land force limits, technology cost | Values reduced as listed in gameplay.md (record clamping, E6) |
| done / check separation | Reach 1450 (free) and *Two Allies* without Chancery | 1450 → `CHECK` the next day. Allies: no `CHECK`; after Chancery 1 arrives, `CHECK` even if the alliance has ended |
| Live delivery (A and B) | Another player sends an item; enter the code shown by the client in game | Applied immediately (no save, no relaunch); client shows it applied and removes the code; claiming a code not yet received is reported |
| Claim then relaunch (B) | Claim an item, exit and relaunch with the inbox installed | Not applied a second time |
| Inbox (B) | Receive two items while EU4 runs; close EU4 | Client shows 2 « en attente du prochain relancement », then « installés »; after relaunch and one day: two `ITEM` lines, recap event, treasury/modifiers changed once |
| Console fast path (A only) | Receive an item; `run eu4ap_sync.txt` twice; relaunch | One application; the relaunch inbox does not apply it again |
| Crash repair (B) | After an `ITEM` line, kill `eu4.exe` before the autosave; relaunch | The item is applied again exactly once; client warns only if the year moved back > 1 |
| Fetter levels | Receive both Progressive Colonial License | Level 1 modifier replaces level 0; final level removes it; no duplicate modifiers |
| Region keys | Conquer an Anatolian province before `Key: Anatolia`; then receive it | Unratified Land on the new province only (not on Constantinople/Morea); removed within a week of the key; the AI owner of a lost province keeps no penalty |
| Relative development | Bind, then develop or conquer +25 % | `Development: +25%` check (variables set at binding, E8) |
| Weekly scan / rescan | Fulfil a check and wait < 7 days; take the rescan decision | Check after at most 7 days; immediately with rescan; rescan replays all CHECK/ITEM lines |
| Late client | Play a session with the client closed, then start it | State recovered at the next yearly replay or rescan |
| Missions | Complete a first-row BYZ mission (base tree, no DLC declared) | `CHECK` for its Mission location |
| Ambition | Use the console (A only) to grant the 15 Basileus areas, or play | Ambition flag and `AMBITION` line; ratify available only with both keys and 3 seals; `GOAL` sent, AP goal 30 |
| Formation (A only) | Form a nation (or `change_tag` via E4), save as text | Client keeps synchronising; the save parser follows the new tag |
| Traps | Receive a trap before 1450 (A) | Applied on 1450-01-01, not before; never below −1 stability |
| Ironman traps (B) | Same seed option without `ironman_traps` | No trap in the item pool (spoiler) |
| DeathLink | Ruler dies; another player sends a death | One DeathLink sent per ruler change; received one costs 1 stability and 10 prestige; no loop within 30 days |
| Pace | Note real time per in-game decade from TICK lines | Record years/hour per country to recalibrate `campaign_length` |

A synthetic test, a fake CommonContext or a fabricated log line cannot close any
of these lines. Record failures verbatim, including unsupported script syntax
reported in EU4's `logs/error.log`.
