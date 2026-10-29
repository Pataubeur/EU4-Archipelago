"""Generate native effects; no runtime mod definition replacement is required."""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .data import BY_ID, ITEM_BY_ID
from .manifest import Manifest
from .version import VERSION, EU4_VERSION


def atomic_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding=encoding, newline="\n") as output:
        output.write(text)
        output.flush()
        os.fsync(output.fileno())
    temp.replace(path)


def scan_effect(m: Manifest) -> str:
    parts = ["eu4ap_scan = {"]
    for location in m.locations:
        flag = m.check_flag(location)
        parts.append(f"""    if = {{
        limit = {{ NOT = {{ has_country_flag = {flag} }} {BY_ID[location].trigger} }}
        set_country_flag = {flag}
    }}""")
    return "\n".join(parts) + "\n}\n"


def reward_script(m: Manifest, items: list[tuple]) -> str:
    chunks = [f"# Seed {m.token}; run eu4ap_sync.txt, then save.\n",
              f"if = {{\n    limit = {{ ai = no has_country_flag = {m.binding_flag} }}"]
    for index, item, _location, _player, _flags, _status in items:
        if item not in ITEM_BY_ID:
            raise ValueError(f"Unsupported EU4 item ID {item}; export stopped")
        name, effect, amount, _classification = ITEM_BY_ID[item]
        if effect:
            body = f"        {effect} = {amount * m.reward_strength}\n"
        else:
            body = ""
            for n in range(m.charters_required):
                branch = "if" if n == 0 else "else_if"
                flag = m.charter_flag(n)
                body += (f"        {branch} = {{\n"
                         f"            limit = {{ NOT = {{ has_country_flag = {flag} }} }}\n"
                         f"            set_country_flag = {flag}\n        }}\n")
        flag = m.item_flag(index)
        chunks.append(f"""    # Item index {index}: {name}
    if = {{
        limit = {{ NOT = {{ has_country_flag = {flag} }} }}
{body}        set_country_flag = {flag}
    }}""")
    chunks.append("    eu4ap_scan = yes\n}\n")
    return "\n".join(chunks)


def install_mod(m: Manifest, user_dir: Path) -> Path:
    """Install only our generated files. Must run while EU4 is stopped."""
    root = user_dir / "mod" / "eu4_archipelago"
    # Keep a recoverable copy before changing the active seed. Saves and client
    # progress are never part of this generated mod directory.
    previous = root / "eu4ap_manifest.json"
    if root.exists():
        old = Manifest.read(previous) if previous.is_file() else None
        if old != m:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = user_dir / "eu4ap" / "mod-backups" / f"{old.token if old else 'unknown'}-{stamp}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(root, backup)
    root.mkdir(parents=True, exist_ok=True)
    descriptor = ('name="EU4 Archipelago"\n'
                  f'version="{VERSION}"\nsupported_version="{EU4_VERSION}"\n'
                  'tags={ "Gameplay" }\n')
    atomic_text(root / "descriptor.mod", descriptor)
    atomic_text(user_dir / "mod" / "eu4_archipelago.mod",
                descriptor + f'path="{root.resolve().as_posix()}"\n')
    atomic_text(root / "common/scripted_effects/eu4ap_effects.txt", scan_effect(m))
    daily_flag = f"eu4ap_{m.token}_daily_scan"
    start_daily = f"""if = {{
                limit = {{ NOT = {{ has_country_flag = {daily_flag} }} }}
                set_country_flag = {daily_flag}
                country_event = {{ id = eu4ap.2 days = 1 }}
            }}"""
    atomic_text(root / "events/eu4ap_events.txt", f"""namespace = eu4ap
# Legacy monthly events queued in existing saves start the daily chain once.
country_event = {{
    id = eu4ap.1
    title = none
    desc = none
    picture = none
    hidden = yes
    is_triggered_only = yes
    immediate = {{
        if = {{
            limit = {{ ai = no has_country_flag = {m.binding_flag} }}
            eu4ap_scan = yes
            {start_daily}
        }}
    }}
    option = {{ }}
}}
country_event = {{
    id = eu4ap.2
    title = none
    desc = none
    picture = none
    hidden = yes
    is_triggered_only = yes
    immediate = {{
        if = {{
            limit = {{ ai = no has_country_flag = {m.binding_flag} }}
            eu4ap_scan = yes
            country_event = {{ id = eu4ap.2 days = 1 }}
        }}
    }}
    option = {{ }}
}}
""")
    charter_limit = " ".join(f"has_country_flag = {m.charter_flag(n)}" for n in range(m.charters_required))
    atomic_text(root / "decisions/eu4ap_decisions.txt", f"""country_decisions = {{
    eu4ap_bind = {{
        potential = {{ ai = no tag = {m.country} NOT = {{ has_country_flag = eu4ap_bound }} }}
        allow = {{ started_in = 1444.11.11 }}
        effect = {{
            set_country_flag = eu4ap_bound
            set_country_flag = {m.binding_flag}
            eu4ap_scan = yes
            {start_daily}
        }}
        ai_will_do = {{ factor = 0 }}
    }}
    eu4ap_rescan = {{
        potential = {{ ai = no has_country_flag = {m.binding_flag} }}
        allow = {{ always = yes }}
        effect = {{
            eu4ap_scan = yes
            {start_daily}
        }}
        ai_will_do = {{ factor = 0 }}
    }}
    eu4ap_ratify = {{
        potential = {{ ai = no has_country_flag = {m.binding_flag}
            NOT = {{ has_country_flag = {m.goal_flag} }} }}
        allow = {{ {charter_limit} }}
        effect = {{ set_country_flag = {m.goal_flag} }}
        ai_will_do = {{ factor = 0 }}
    }}
}}
""")
    atomic_text(root / "localisation/eu4ap_l_english.yml", '''l_english:
 eu4ap_bind_title:0 "§MArchipelago: bind this campaign§!"
 eu4ap_bind_desc:0 "Bind this country to the installed Archipelago slot. Save after binding."
 eu4ap_rescan_title:0 "§MArchipelago: scan objectives now§!"
 eu4ap_rescan_desc:0 "Record completed objectives, then save to synchronize with the client."
 eu4ap_ratify_title:0 "§MArchipelago: ratify the royal charters§!"
 eu4ap_ratify_desc:0 "Complete the Multiworld goal after receiving all required Royal Charters. Save to report victory."
''', encoding="utf-8-sig")
    atomic_text(root / "localisation/eu4ap_l_french.yml", '''l_french:
 eu4ap_bind_title:0 "§MArchipelago : lier cette campagne§!"
 eu4ap_bind_desc:0 "Liez ce pays au joueur Archipelago configuré dans le mod installé. Sauvegardez après avoir lié la campagne."
 eu4ap_rescan_title:0 "§MArchipelago : vérifier les objectifs§!"
 eu4ap_rescan_desc:0 "Enregistrez les objectifs accomplis, puis sauvegardez pour synchroniser la campagne avec le client."
 eu4ap_ratify_title:0 "§MArchipelago : ratifier les chartes royales§!"
 eu4ap_ratify_desc:0 "Accomplissez l'objectif du multiworld après avoir reçu toutes les chartes royales requises. Sauvegardez pour signaler la victoire."
''', encoding="utf-8-sig")
    m.write(root / "eu4ap_manifest.json")
    return root
