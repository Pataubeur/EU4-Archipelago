"""Feasibility experiment kit for the Ironman/progression design (development only).

This tool is NOT part of the APWorld or the player kit. It installs a separate
test mod, ``eu4ap_feasibility``, into the EU4 user directory, rewrites its inbox
between game launches, keeps copies of ``logs/game.log`` (EU4 overwrites it at
each launch), and summarises the ``EU4APX`` lines written by the native ``log``
effect. Protocols E1-E8 are described in docs/manual-validation.md.

The mission probe reads mission IDs from the local game installation at install
time. Only IDs are written, and only into the local user directory; no game file
is copied into this repository.

Examples (EU4 must be closed for install/inbox/uninstall):
    python scripts/feasibility_kit.py install --run R1 --tag BYZ --game-dir "E:/Steam/steamapps/common/Europa Universalis IV"
    python scripts/feasibility_kit.py inbox --run R1 --generation 2
    python scripts/feasibility_kit.py report --run R1
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apworld" / "eu4"))

from runtime.client import default_user_dir  # noqa: E402
from runtime.data import country_tag  # noqa: E402
from runtime.render import atomic_text  # noqa: E402

MOD = "eu4ap_feasibility"
PREFIX = "EU4APX"
ITEM_DUCATS = 11  # Distinctive amount: n items must add exactly 11*n ducats.
RUN_RE = re.compile(r"[A-Za-z0-9]{1,12}")
LINE_RE = re.compile(PREFIX + r" (?P<run>[A-Za-z0-9]+) (?P<kind>[A-Z_]+)(?: (?P<rest>.*))?$")


# --------------------------------------------------------------------- rendering

def _guard(flag: str, body: str) -> str:
    return f"\tif = {{\n\t\tlimit = {{ NOT = {{ has_country_flag = {flag} }} }}\n\t\tset_country_flag = {flag}\n{body}\t}}\n"


def inbox_effect(run: str, generation: int) -> str:
    """Generation N contains items 1..N; each is guarded by its own flag."""
    if generation < 1:
        raise ValueError("generation must be >= 1")
    parts = [f"# Generation {generation}. Rewritten only while EU4 is closed.\neu4apx_inbox = {{\n",
             _guard(f"eu4apx_gen_{generation}", f'\t\tlog = "{PREFIX} {run} GEN {generation}"\n')]
    for n in range(1, generation + 1):
        parts.append(_guard(f"eu4apx_item_{n}",
                            f"\t\tadd_treasury = {ITEM_DUCATS}\n"
                            f'\t\tlog = "{PREFIX} {run} ITEM {n} GEN {generation}"\n'))
    return "".join(parts) + "}\n"


def missions_effect(run: str, mission_ids: list[str]) -> str:
    parts = ["eu4apx_missions = {\n"]
    for mission in mission_ids:
        parts.append(f"\tif = {{\n\t\tlimit = {{ mission_completed = {mission} "
                     f"NOT = {{ has_country_flag = eu4apx_m_{mission} }} }}\n"
                     f"\t\tset_country_flag = eu4apx_m_{mission}\n"
                     f'\t\tlog = "{PREFIX} {run} MISSION {mission}"\n\t}}\n')
    return "".join(parts) + "}\n"


def mission_ids(game_dir: Path, tags: set[str]) -> list[str]:
    """IDs of missions whose series potential names one of ``tags`` (any DLC)."""
    found: set[str] = set()
    head = re.compile(r"([A-Za-z0-9_]+)\s*=\s*\{")

    def blocks(text: str):
        i = 0
        while (m := head.search(text, i)):
            j, depth = m.end(), 1
            while depth and j < len(text):
                depth += text[j] == "{"
                depth -= text[j] == "}"
                j += 1
            yield m.group(1), text[m.end():j - 1]
            i = j

    for path in sorted((game_dir / "missions").glob("*.txt")):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="cp1252", errors="replace"))
        for _series, body in blocks(text):
            potential = next((b for k, b in blocks(body) if k == "potential"), "")
            if set(re.findall(r"\btag\s*=\s*([A-Z][A-Z0-9]{2})\b", potential)) & tags:
                found.update(k for k, b in blocks(body) if re.search(r"\bicon\s*=", b))
    return sorted(found)


def render(run: str, form_tag: str, missions: list[str]) -> dict[str, tuple[str, str]]:
    """Relative path -> (content, encoding)."""
    r = run
    log = lambda text: f'log = "{PREFIX} {r} {text}"'  # noqa: E731
    events = f"""namespace = eu4apx
# Daily hidden chain: inbox, mission probe, monthly tick, formation probe.
country_event = {{
	id = eu4apx.1
	title = none
	desc = none
	picture = none
	hidden = yes
	is_triggered_only = yes
	immediate = {{
		if = {{
			limit = {{ ai = no has_country_flag = eu4apx_started }}
			eu4apx_inbox = yes
			eu4apx_missions = yes
			change_variable = {{ which = eu4apx_days value = 1 }}
			if = {{
				limit = {{ check_variable = {{ which = eu4apx_days value = 30 }} }}
				set_variable = {{ which = eu4apx_days value = 0 }}
				{log("TICK [GetYear] [Root.GetName]")}
			}}
			if = {{
				limit = {{ has_country_flag = eu4apx_formed NOT = {{ has_country_flag = eu4apx_formed_logged }} }}
				set_country_flag = eu4apx_formed_logged
				if = {{
					limit = {{ has_country_flag = eu4apx_pre_form has_country_flag = eu4apx_started }}
					{log("FORMATION_FLAGS kept [Root.GetName]")}
				}}
				else = {{
					{log("FORMATION_FLAGS lost [Root.GetName]")}
				}}
			}}
			country_event = {{ id = eu4apx.1 days = 1 }}
		}}
	}}
	option = {{ }}
}}
# E5: two mod files both define on_startup. Both lines => per-key merge.
country_event = {{
	id = eu4apx.10
	title = none
	desc = none
	picture = none
	hidden = yes
	is_triggered_only = yes
	trigger = {{ ai = no }}
	immediate = {{ {log("ONACTION A")} }}
	option = {{ }}
}}
country_event = {{
	id = eu4apx.11
	title = none
	desc = none
	picture = none
	hidden = yes
	is_triggered_only = yes
	trigger = {{ ai = no }}
	immediate = {{ {log("ONACTION Z")} }}
	option = {{ }}
}}
"""
    decisions = f"""country_decisions = {{
	eu4apx_start = {{
		potential = {{ ai = no NOT = {{ has_country_flag = eu4apx_started }} }}
		allow = {{ always = yes }}
		effect = {{
			set_country_flag = eu4apx_started
			if = {{
				limit = {{ ironman = yes }}
				{log("MODE ironman")}
			}}
			else = {{
				{log("MODE normal")}
			}}
			{log("START [Root.GetName] [GetYear]")}
			country_event = {{ id = eu4apx.1 days = 1 }}
		}}
		ai_will_do = {{ factor = 0 }}
	}}
	eu4apx_fetters_on = {{
		potential = {{ ai = no has_country_flag = eu4apx_started NOT = {{ has_country_modifier = eu4apx_no_colonist }} }}
		allow = {{ always = yes }}
		effect = {{
			add_country_modifier = {{ name = eu4apx_no_colonist duration = -1 }}
			add_country_modifier = {{ name = eu4apx_no_diplomat duration = -1 }}
			add_country_modifier = {{ name = eu4apx_no_merchant duration = -1 }}
			{log("FETTERS on")}
		}}
		ai_will_do = {{ factor = 0 }}
	}}
	eu4apx_fetters_off = {{
		potential = {{ ai = no has_country_modifier = eu4apx_no_colonist }}
		allow = {{ always = yes }}
		effect = {{
			remove_country_modifier = eu4apx_no_colonist
			remove_country_modifier = eu4apx_no_diplomat
			remove_country_modifier = eu4apx_no_merchant
			{log("FETTERS off")}
		}}
		ai_will_do = {{ factor = 0 }}
	}}
	eu4apx_form = {{
		potential = {{ ai = no has_country_flag = eu4apx_started NOT = {{ has_country_flag = eu4apx_formed }} }}
		allow = {{ NOT = {{ exists = {form_tag} }} }}
		effect = {{
			set_country_flag = eu4apx_pre_form
			{log("FORM_BEFORE [Root.GetName]")}
			change_tag = {form_tag}
			set_country_flag = eu4apx_formed
			{log("FORM_AFTER [Root.GetName]")}
		}}
		ai_will_do = {{ factor = 0 }}
	}}
}}
"""
    modifiers = """eu4apx_no_colonist = { colonists = -1 }
eu4apx_no_diplomat = { diplomats = -1 }
eu4apx_no_merchant = { merchants = -1 }
"""
    english = """l_english:
 eu4apx_start_title:0 "§MAP test: start experiment§!"
 eu4apx_start_desc:0 "Starts the EU4APX feasibility experiment for this country."
 eu4apx_fetters_on_title:0 "§MAP test: apply fetters§!"
 eu4apx_fetters_on_desc:0 "Adds -1 colonist, -1 diplomat and -1 merchant."
 eu4apx_fetters_off_title:0 "§MAP test: remove fetters§!"
 eu4apx_fetters_off_desc:0 "Removes the test fetters."
 eu4apx_form_title:0 "§MAP test: change tag (formation)§!"
 eu4apx_form_desc:0 "Runs change_tag like a formation decision, to check country flags."
 eu4apx_no_colonist:0 "AP test: no colonist"
 eu4apx_no_diplomat:0 "AP test: no diplomat"
 eu4apx_no_merchant:0 "AP test: no merchant"
"""
    french = """l_french:
 eu4apx_start_title:0 "§MTest AP : démarrer l'expérience§!"
 eu4apx_start_desc:0 "Démarre l'expérience de faisabilité EU4APX pour ce pays."
 eu4apx_fetters_on_title:0 "§MTest AP : appliquer les entraves§!"
 eu4apx_fetters_on_desc:0 "Ajoute -1 colon, -1 diplomate et -1 marchand."
 eu4apx_fetters_off_title:0 "§MTest AP : retirer les entraves§!"
 eu4apx_fetters_off_desc:0 "Retire les entraves de test."
 eu4apx_form_title:0 "§MTest AP : changer de tag (formation)§!"
 eu4apx_form_desc:0 "Exécute change_tag comme une décision de formation, pour vérifier les flags du pays."
 eu4apx_no_colonist:0 "Test AP : aucun colon"
 eu4apx_no_diplomat:0 "Test AP : aucun diplomate"
 eu4apx_no_merchant:0 "Test AP : aucun marchand"
"""
    return {
        "descriptor.mod": (descriptor(), "utf-8"),
        "events/eu4apx_events.txt": (events, "utf-8"),
        "decisions/eu4apx_decisions.txt": (decisions, "utf-8"),
        "common/event_modifiers/eu4apx_modifiers.txt": (modifiers, "utf-8"),
        "common/on_actions/eu4apx_a_on_actions.txt": ("on_startup = { events = { eu4apx.10 } }\n", "utf-8"),
        "common/on_actions/eu4apx_z_on_actions.txt": ("on_startup = { events = { eu4apx.11 } }\n", "utf-8"),
        "common/scripted_effects/eu4apx_missions.txt": (missions_effect(run, missions), "utf-8"),
        "common/scripted_effects/eu4apx_inbox.txt": (inbox_effect(run, 1), "utf-8"),
        "localisation/eu4apx_l_english.yml": (english, "utf-8-sig"),
        "localisation/eu4apx_l_french.yml": (french, "utf-8-sig"),
    }


def descriptor() -> str:
    return ('name="EU4AP feasibility experiments"\nversion="0.0.1"\n'
            'supported_version="v1.37.5.0"\ntags={ "Gameplay" }\n')


# ----------------------------------------------------------------- log analysis

@dataclass
class RunReport:
    modes: list[str] = field(default_factory=list)
    starts: list[str] = field(default_factory=list)
    generations: list[int] = field(default_factory=list)
    items: Counter = field(default_factory=Counter)
    missions: list[str] = field(default_factory=list)
    ticks: list[str] = field(default_factory=list)
    formation: list[str] = field(default_factory=list)
    on_actions: Counter = field(default_factory=Counter)
    fetters: list[str] = field(default_factory=list)


def parse_log(text: str, run: str) -> RunReport:
    """Parse complete lines only; a final line without newline may still be written."""
    report = RunReport()
    lines = text.split("\n")
    if not text.endswith("\n"):
        lines = lines[:-1]
    for raw in lines:
        index = raw.find(PREFIX + " ")
        if index < 0:
            continue
        match = LINE_RE.match(raw[index:].rstrip("\r"))
        if not match or match.group("run") != run:
            continue
        kind, rest = match.group("kind"), (match.group("rest") or "").strip()
        if kind == "MODE":
            report.modes.append(rest)
        elif kind == "START":
            report.starts.append(rest)
        elif kind == "GEN" and rest.isdecimal():
            report.generations.append(int(rest))
        elif kind == "ITEM" and rest.split(" ")[0].isdecimal():
            report.items[int(rest.split(" ")[0])] += 1
        elif kind == "MISSION":
            report.missions.append(rest)
        elif kind == "TICK":
            report.ticks.append(rest)
        elif kind in ("FORM_BEFORE", "FORM_AFTER", "FORMATION_FLAGS"):
            report.formation.append(f"{kind} {rest}".strip())
        elif kind == "ONACTION":
            report.on_actions[rest] += 1
        elif kind == "FETTERS":
            report.fetters.append(rest)
    return report


SESSION_RE = re.compile(r"^Time:.*$", re.M)


def merge_sessions(texts: list[str]) -> str:
    """One text per EU4 launch: copies of the same session keep the longest one.

    game.log is truncated at each launch and starts with a ``Time:`` header.
    A copy taken mid-session is a prefix of a later copy of that session.
    """
    sessions: dict[str, str] = {}
    order: list[str] = []
    for text in texts:
        text = text.replace("\r\n", "\n")
        header = SESSION_RE.search(text[:2000])
        key = header.group() if header else f"unknown-{len(order)}"
        if key not in sessions:
            order.append(key)
            sessions[key] = text
        elif len(text) > len(sessions[key]):
            sessions[key] = text
    # Only the newest copy of a session may end with a partial line.
    return "".join(s if s.endswith("\n") or s is sessions[order[-1]] else s + "\n"
                   for s in (sessions[k] for k in order))


def read_logs(paths: list[Path]) -> str:
    return merge_sessions([p.read_bytes().decode("cp1252", errors="replace") for p in paths])


def format_report(report: RunReport, generation: int | None) -> str:
    duplicates = {k: v for k, v in report.items.items() if v > 1}
    lines = [
        f"E1 log effect: {'OK' if report.modes or report.ticks else 'NO EU4APX LINE FOUND'}; modes={report.modes}",
        f"   starts={report.starts}; ticks={len(report.ticks)} last={report.ticks[-1] if report.ticks else '-'}",
        f"E3 inbox: generations applied={report.generations}; items={dict(sorted(report.items.items()))}",
        f"   items applied more than once in these logs: {duplicates or 'none'}"
        + ("  (expected only after a crash before autosave)" if duplicates else ""),
    ]
    if generation is not None:
        missing = [n for n in range(1, generation + 1) if n not in report.items]
        lines.append(f"   installed generation={generation}; items never logged: {missing or 'none'}")
    lines += [
        f"E4 formation: {report.formation or 'not attempted'}",
        f"E5 on_actions: {dict(report.on_actions) or 'no ONACTION line (on_startup fires on new games only)'}",
        f"E6 fetters: {report.fetters or 'not toggled'} (check colonists/diplomats/merchants in the UI)",
        f"E7 missions completed: {report.missions or 'none yet'}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------- commands

def eu4_running() -> bool:
    if os.name != "nt":
        return False
    result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq eu4.exe", "/NH"],
                            capture_output=True, text=True, check=False)
    return "eu4.exe" in result.stdout.lower()


def require_closed() -> None:
    if eu4_running():
        raise SystemExit("EU4 is running. Close it first: definitions are never changed while it runs.")


def evidence_dir(run: str) -> Path:
    return ROOT / "local" / "validation" / "feasibility" / run


def snapshot_log(user_dir: Path, run: str, label: str) -> Path | None:
    source = user_dir / "logs" / "game.log"
    if not source.is_file():
        return None
    target = evidence_dir(run) / f"game-{datetime.now():%Y%m%dT%H%M%S}-{label}.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def checked_run(value: str) -> str:
    if not RUN_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("run must be 1-12 letters/digits")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-dir", type=Path, default=None, help="EU4 user directory (Documents)")
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install", help="Install the test mod (EU4 closed)")
    install.add_argument("--run", type=checked_run, required=True)
    install.add_argument("--tag", required=True, help="Country played in the test, e.g. BYZ or FRA")
    install.add_argument("--form-tag", default="ROM", help="Tag used by the change_tag test decision")
    install.add_argument("--game-dir", type=Path, help="EU4 install, for the mission ID probe")
    inbox = sub.add_parser("inbox", help="Rewrite the inbox with items 1..N (EU4 closed)")
    inbox.add_argument("--run", type=checked_run, required=True)
    inbox.add_argument("--generation", type=int, required=True)
    report = sub.add_parser("report", help="Summarise EU4APX lines from saved and current logs")
    report.add_argument("--run", type=checked_run, required=True)
    sub.add_parser("uninstall", help="Remove the test mod (EU4 closed)")
    args = parser.parse_args(argv)

    user_dir = args.user_dir or default_user_dir()
    root = user_dir / "mod" / MOD
    if args.command == "install":
        require_closed()
        tag = country_tag(args.tag)
        form = country_tag(args.form_tag)
        missions = mission_ids(args.game_dir, {tag, form}) if args.game_dir else []
        for relative, (content, encoding) in render(args.run, form, missions).items():
            atomic_text(root / relative, content, encoding)
        atomic_text(user_dir / "mod" / f"{MOD}.mod", descriptor() + f'path="{root.resolve().as_posix()}"\n')
        atomic_text(evidence_dir(args.run) / "generation.txt", "1\n")
        print(f"Installed {root} (run {args.run}, {len(missions)} mission IDs probed, inbox generation 1).")
        print("Enable ONLY this mod in a separate playset, then follow docs/manual-validation.md.")
    elif args.command == "inbox":
        require_closed()
        if not root.is_dir():
            raise SystemExit("Test mod not installed")
        saved = snapshot_log(user_dir, args.run, f"before-gen{args.generation}")
        atomic_text(root / "common/scripted_effects/eu4apx_inbox.txt", inbox_effect(args.run, args.generation))
        atomic_text(evidence_dir(args.run) / "generation.txt", f"{args.generation}\n")
        print(f"Inbox generation {args.generation} written; previous game.log kept at {saved}.")
    elif args.command == "report":
        saved = sorted(evidence_dir(args.run).glob("game-*.log"))
        current = user_dir / "logs" / "game.log"
        paths = saved + ([current] if current.is_file() else [])
        if not paths:
            raise SystemExit("No game.log found")
        generation_file = evidence_dir(args.run) / "generation.txt"
        generation = int(generation_file.read_text().strip()) if generation_file.is_file() else None
        print(f"Logs read: {len(paths)} (saved copies + current game.log)")
        print(format_report(parse_log(read_logs(paths), args.run), generation))
        print(f"Cross-check in game: each applied item adds exactly {ITEM_DUCATS} ducats.")
    elif args.command == "uninstall":
        require_closed()
        shutil.rmtree(root, ignore_errors=True)
        (user_dir / "mod" / f"{MOD}.mod").unlink(missing_ok=True)
        print("Test mod removed. Evidence under local/validation/feasibility/ is kept.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
