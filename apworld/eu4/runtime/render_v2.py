"""Schema-2 mod rendering: separate 'done' and 'check' flags, fetters, region keys,
an inbox applied by the daily event, and game.log lines for Ironman.

Every effect below is a candidate awaiting EU4 validation (experiments E1-E8).
Only files are added; no vanilla file is replaced.
"""
from __future__ import annotations

from .catalog import (AMBITIONS, DEV_TARGETS, FETTERS, ITEM_DEF_BY_ID, LOCATION_DEFS, MODIFIERS,
                      REGION_KEYS, goal_guards, location_guards)
from .manifest import Manifest

MAX_SEALS = 8          # Extra seals beyond this count have no further effect.
SCAN_DAYS, TICK_DAYS, REPLAY_DAYS = 7, 30, 365


def fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.3f}".rstrip("0")


def log(m: Manifest, text: str) -> str:
    return f'log = "EU4AP {m.token} {text}"'


def flag_limit(flags) -> str:
    return " ".join(f"has_country_flag = {f}" for f in flags)


def guard_flags(m: Manifest, guards) -> list[str]:
    return [m.level_flag(family, level) for family, level in guards]


def family_levels(family: str) -> int:
    if family == "seal":
        return MAX_SEALS
    if family.startswith("key:"):
        return 1
    return len(FETTERS[family].levels)


# ------------------------------------------------------------------------ items

def item_effect(m: Manifest, item_id: int) -> tuple[str, str]:
    """(effect script, extra limit) of one received item."""
    item = ITEM_DEF_BY_ID.get(item_id)
    if item is None:
        raise ValueError(f"Unsupported EU4 item ID {item_id}; export stopped")
    if item.kind in ("level", "seal"):
        family = item.family
        parts = []
        for level in range(1, family_levels(family) + 1):
            branch = "if" if level == 1 else "else_if"
            flag = m.level_flag(family, level)
            parts.append(f"{branch} = {{ limit = {{ NOT = {{ has_country_flag = {flag} }} }} "
                         f"set_country_flag = {flag} }}")
        return "\n".join(parts), ""
    if item.kind == "claims":
        claims = AMBITIONS[m.ambition].claims
        if not claims:
            return "add_prestige = 10", ""
        return (f"every_province = {{ limit = {{ {claims} NOT = {{ owned_by = ROOT }} }} "
                f"add_permanent_claim = ROOT }}"), ""
    if item.kind == "charter":
        return "add_prestige = 10", ""  # Royal Charters have no role in schema 2.
    amount = fmt(item.amount * (m.reward_strength if item.kind == "resource" else 1))
    return item.effect.replace("{amount}", amount), item.limit


def indent(text: str, spaces: int) -> str:
    return "\n".join(" " * spaces + line for line in text.splitlines())


DEATHLINK_EFFECT = "if = { limit = { stability = -1 } add_stability = -1 }\nadd_prestige = -10"


def deathlink_effect(m: Manifest) -> str:
    return f"set_country_flag = {cooldown_flag(m)}\n{DEATHLINK_EFFECT}"


def item_blocks(m: Manifest, items: list[tuple], deathlinks: int = 0) -> str:
    """Inbox/console blocks. An item with a live-delivery code is guarded by the
    code's flag, shared with the in-game claim: it is applied at most once,
    whichever path comes first."""
    from .deliveries import deathlink_code, match_deliveries
    codes = match_deliveries(m, items)
    chunks = []
    for row in items:
        index, item_id = row[0], row[1]
        effect, limit = item_effect(m, item_id)
        code = codes.get(index)
        guard = m.delivery_flag(code) if code else m.item_flag(index)
        extra = f"\n    set_country_flag = {m.item_flag(index)}" if code else ""
        name = ITEM_DEF_BY_ID[item_id].name
        chunks.append(f"""# Item index {index}: {name}{f' (code {code})' if code else ''}
if = {{
    limit = {{ NOT = {{ has_country_flag = {guard} }} {limit} }}
    set_country_flag = {guard}{extra}
{indent(effect, 4)}
    set_country_flag = {delivery_flag(m)}
    {log(m, f"ITEM {index}")}
}}""")
    for k in range(deathlinks):
        code = deathlink_code(m, k)
        flag = m.delivery_flag(code) if code else m.deathlink_flag(k)
        chunks.append(f"""# DeathLink received {k}{f' (code {code})' if code else ''}
if = {{
    limit = {{ NOT = {{ has_country_flag = {flag} }} }}
    set_country_flag = {flag}
{indent(deathlink_effect(m), 4)}
    set_country_flag = {delivery_flag(m)}
    {log(m, f"DEATHLINK {k}")}
}}""")
    return "\n".join(chunks)


# ------------------------------------------------------------ live deliveries

def code_test(code: int) -> str:
    """Exact equality on an integer variable, as vanilla customizable localisation does."""
    return (f"check_variable = {{ which = eu4ap_code value = {code} }} "
            f"NOT = {{ check_variable = {{ which = eu4ap_code value = {code + 1} }} }}")


def deliveries_effect(m: Manifest) -> str:
    """eu4ap_claim applies the delivery whose code the player entered."""
    entries = [(code, *item_effect(m, item)) for code, item, _sender, _location in m.deliveries]
    entries += [(code, deathlink_effect(m), "") for code in m.deathlink_codes]
    parts = ["eu4ap_claim = {"]
    for n, (code, effect, limit) in enumerate(entries):
        branch = "if" if n == 0 else "else_if"
        flag = m.delivery_flag(code)
        early = (f"\n        else_if = {{ limit = {{ NOT = {{ {limit} }} }} {log(m, f'CLAIM_EARLY {code}')} }}"
                 if limit else "")
        parts.append(f"""    {branch} = {{
        limit = {{ {code_test(code)} }}
        if = {{ limit = {{ has_country_flag = {flag} }} {log(m, f"CLAIM_DUPLICATE {code}")} }}{early}
        else = {{
            set_country_flag = {flag}
{indent(effect, 12)}
            {log(m, f"CLAIM {code}")}
        }}
    }}""")
    parts.append(f"    else = {{ {log(m, 'CLAIM_UNKNOWN [Root.eu4ap_code.GetValue]')} }}" if entries
                 else f"    {log(m, 'CLAIM_UNKNOWN [Root.eu4ap_code.GetValue]')}")
    parts.append("    eu4ap_recompute = yes\n    eu4ap_promote = yes\n}")
    replay = ["eu4ap_replay_claims = {"]
    replay += [f"    if = {{ limit = {{ has_country_flag = {m.delivery_flag(code)} }} {log(m, f'CLAIM {code}')} }}"
               for code, *_ in entries]
    replay.append("}")
    return f"# Seed {m.token}: live deliveries, fixed for the whole campaign.\n" + "\n".join(parts + replay) + "\n"


def customizable_localisation(m: Manifest) -> str:
    texts = [f"""    text = {{
        localisation_key = eu4ap_dlv_done
        trigger = {{ OR = {{ {' '.join(f'AND = {{ {code_test(c)} has_country_flag = {m.delivery_flag(c)} }}'
                                      for c in all_codes(m))} }} }}
    }}""" if all_codes(m) else ""]
    texts += [f"""    text = {{
        localisation_key = eu4ap_dlv_{code}
        trigger = {{ {code_test(code)} }}
    }}""" for code in all_codes(m)]
    texts.append("    text = {\n        localisation_key = eu4ap_dlv_unknown\n    }")
    return ("defined_text = {\n    name = GetEU4APDelivery\n    random = no\n"
            + "\n".join(t for t in texts if t) + "\n}\n")


def all_codes(m: Manifest) -> list[int]:
    return [row[0] for row in m.deliveries] + list(m.deathlink_codes)


DIGIT_EVENTS = ((20, 1000), (21, 100), (22, 10), (23, 1))


def claim_events(m: Manifest) -> str:
    events = []
    for event_id, weight in DIGIT_EVENTS:
        following = event_id + 1
        options = []
        for digit in range(10):
            value = (f"set_variable = {{ which = eu4ap_code value = {digit * weight} }}" if weight == 1000
                     else f"change_variable = {{ which = eu4ap_code value = {digit * weight} }}")
            options.append(f"    option = {{ name = eu4ap.digit.{digit} {value} "
                           f"country_event = {{ id = eu4ap.{following} }} }}")
        options.append("    option = { name = eu4ap.claim.cancel }")
        events.append(f"""country_event = {{
    id = eu4ap.{event_id}
    title = eu4ap.{event_id}.t
    desc = eu4ap.{event_id}.d
    picture = DIPLOMACY_eventPicture
    is_triggered_only = yes
{chr(10).join(options)}
}}""")
    events.append(f"""country_event = {{
    id = eu4ap.24
    title = eu4ap.24.t
    desc = eu4ap.24.d
    picture = DIPLOMACY_eventPicture
    is_triggered_only = yes
    option = {{ name = eu4ap.24.a eu4ap_claim = yes }}
    option = {{ name = eu4ap.24.b country_event = {{ id = eu4ap.20 }} }}
    option = {{ name = eu4ap.claim.cancel }}
}}""")
    return "# Digit pad: the player enters the 4-digit code shown by the client.\n" + "\n".join(events) + "\n"


def delivery_flag(m: Manifest) -> str:
    return f"eu4ap_{m.token}_delivery"


def cooldown_flag(m: Manifest) -> str:
    return f"eu4ap_{m.token}_dl_cooldown"


def inbox_text(m: Manifest, items: list[tuple], deathlinks: int = 0) -> str:
    replay = "\n".join(f"    if = {{ limit = {{ has_country_flag = {m.item_flag(row[0])} }} "
                       f"{log(m, f'ITEM {row[0]}')} }}" for row in items)
    return (f"# Seed {m.token}: every received item, each guarded by its own flag.\n"
            "# Rewritten by the client only while EU4 is closed; applied by the daily event.\n"
            f"eu4ap_inbox = {{\n{indent(item_blocks(m, items, deathlinks), 4)}\n}}\n"
            f"eu4ap_replay_items = {{\n{replay}\n}}\n")


def console_script(m: Manifest, items: list[tuple], deathlinks: int = 0) -> str:
    if m.save_mode == "ironman":
        return ("# Ironman campaign: the console is unavailable. Received items are installed\n"
                "# into the mod when EU4 is closed and applied the day after loading.\n")
    return (f"# Seed {m.token}; run eu4ap_sync.txt in the console, then keep playing.\n"
            f"if = {{\n    limit = {{ ai = no has_country_flag = {m.binding_flag} }}\n"
            f"{indent(item_blocks(m, items, deathlinks), 4)}\n"
            "    eu4ap_recompute = yes\n    eu4ap_promote = yes\n}\n")


# ---------------------------------------------------------------- scripted effects

def recompute_effect(m: Manifest) -> str:
    parts = []
    for key in m.fetters:
        levels = len(FETTERS[key].levels)
        names = [f"eu4ap_fetter_{key}_{n}" for n in range(levels)]
        branches = []
        for received in range(levels, -1, -1):
            keep = names[received] if received < levels else None
            body = " ".join(f"if = {{ limit = {{ has_country_modifier = {n} }} remove_country_modifier = {n} }}"
                            for n in names if n != keep)
            if keep:
                body += (f" if = {{ limit = {{ NOT = {{ has_country_modifier = {keep} }} }} "
                         f"add_country_modifier = {{ name = {keep} duration = -1 }} }}")
            condition = (f"has_country_flag = {m.level_flag(key, received)}" if received
                         else "always = yes")
            branch = "if" if received == levels else "else_if" if received else "else"
            limit = f"limit = {{ {condition} }} " if received else ""
            branches.append(f"    {branch} = {{ {limit}{body} }}")
        parts.append(f"    # Fetter {key}\n" + "\n".join(branches))
    return "eu4ap_recompute = {\n" + ("\n".join(parts) or "    # No fetter enabled") + "\n}\n"


def scan_effect(m: Manifest) -> str:
    parts = ["eu4ap_scan = {",
             "    export_to_variable = { which = eu4ap_dev_now value = total_development }"]
    for location in m.locations:
        done = m.done_flag(location)
        parts.append(f"    if = {{ limit = {{ NOT = {{ has_country_flag = {done} }} "
                     f"{LOCATION_DEFS[location].trigger} }} set_country_flag = {done} }}")
    ambition = AMBITIONS[m.ambition]
    parts.append(f"    if = {{\n        limit = {{ NOT = {{ has_country_flag = {m.ambition_flag} }} {ambition.goal} }}\n"
                 f"        set_country_flag = {m.ambition_flag}\n        {log(m, 'AMBITION')}\n    }}")
    for key in m.region_keys:
        scope = REGION_KEYS[key].scope
        held = m.level_flag(f"key:{key}", 1)
        parts.append(f"""    # Region key {key}: penalise new provinces until the key arrives.
    if = {{
        limit = {{ NOT = {{ has_country_flag = {held} }} }}
        every_owned_province = {{
            limit = {{ {scope} NOT = {{ has_province_flag = eu4ap_heartland }} NOT = {{ has_province_modifier = eu4ap_unratified }} }}
            add_province_modifier = {{ name = eu4ap_unratified duration = -1 }}
        }}
    }}
    else = {{
        every_owned_province = {{
            limit = {{ {scope} has_province_modifier = eu4ap_unratified }}
            remove_province_modifier = eu4ap_unratified
        }}
    }}""")
    if m.region_keys:
        parts.append("    every_province = { limit = { has_province_modifier = eu4ap_unratified "
                     "NOT = { owned_by = ROOT } } remove_province_modifier = eu4ap_unratified }")
    parts.append("    eu4ap_promote = yes\n}")
    return "\n".join(parts) + "\n"


def promote_effect(m: Manifest) -> str:
    parts = ["eu4ap_promote = {"]
    for location in m.locations:
        flags = guard_flags(m, location_guards(location, m))
        parts.append(f"    if = {{ limit = {{ has_country_flag = {m.done_flag(location)} "
                     f"NOT = {{ has_country_flag = {m.check_flag(location)} }} {flag_limit(flags)} }} "
                     f"set_country_flag = {m.check_flag(location)} {log(m, f'CHECK {location}')} }}")
    return "\n".join(parts) + "\n}\n"


def hello(m: Manifest) -> str:
    return (f"if = {{ limit = {{ ironman = yes }} {log(m, 'HELLO 2 ironman')} }} "
            f"else = {{ {log(m, 'HELLO 2 normal')} }}")


def replay_effect(m: Manifest) -> str:
    parts = ["eu4ap_replay = {", f"    {hello(m)}"]
    parts += [f"    if = {{ limit = {{ has_country_flag = {m.check_flag(i)} }} {log(m, f'CHECK {i}')} }}"
              for i in m.locations]
    parts += ["    eu4ap_replay_items = yes", "    eu4ap_replay_claims = yes",
              f"    if = {{ limit = {{ has_country_flag = {m.ambition_flag} }} {log(m, 'AMBITION')} }}",
              f"    if = {{ limit = {{ has_country_flag = {m.goal_flag} }} {log(m, 'GOAL')} }}", "}"]
    return "\n".join(parts) + "\n"


def setup_effect(m: Manifest) -> str:
    targets = "\n".join(
        f"    set_variable = {{ which = eu4ap_dev_{p} which = eu4ap_dev_start }}\n"
        f"    multiply_variable = {{ which = eu4ap_dev_{p} value = {fmt(p / 100)} }}" for p in DEV_TARGETS)
    return f"""eu4ap_setup = {{
    export_to_variable = {{ which = eu4ap_dev_start value = total_development }}
{targets}
    every_owned_province = {{ set_province_flag = eu4ap_heartland }}
    set_variable = {{ which = eu4ap_scan_days value = {SCAN_DAYS} }}
    set_variable = {{ which = eu4ap_tick_days value = {TICK_DAYS} }}
    set_variable = {{ which = eu4ap_replay_days value = {REPLAY_DAYS} }}
    eu4ap_recompute = yes
}}
"""


def daily_effect(m: Manifest) -> str:
    death = ""
    if m.death_link:
        seen = f"eu4ap_{m.token}_ruler_seen"
        death = f"""
    if = {{ limit = {{ has_country_flag = {cooldown_flag(m)} had_country_flag = {{ flag = {cooldown_flag(m)} days = 30 }} }}
        clr_country_flag = {cooldown_flag(m)} }}
    if = {{
        limit = {{ NOT = {{ has_ruler_flag = eu4ap_known_ruler }} }}
        set_ruler_flag = eu4ap_known_ruler
        if = {{ limit = {{ has_country_flag = {seen} NOT = {{ has_country_flag = {cooldown_flag(m)} }} }}
            {log(m, "DEATH [GetYear]")} }}
        set_country_flag = {seen}
    }}"""
    return f"""eu4ap_daily = {{
    eu4ap_inbox = yes
    eu4ap_recompute = yes
    eu4ap_promote = yes
    change_variable = {{ which = eu4ap_scan_days value = 1 }}
    if = {{ limit = {{ check_variable = {{ which = eu4ap_scan_days value = {SCAN_DAYS} }} }}
        set_variable = {{ which = eu4ap_scan_days value = 0 }}
        eu4ap_scan = yes
    }}
    change_variable = {{ which = eu4ap_tick_days value = 1 }}
    if = {{ limit = {{ check_variable = {{ which = eu4ap_tick_days value = {TICK_DAYS} }} }}
        set_variable = {{ which = eu4ap_tick_days value = 0 }}
        {log(m, "TICK [GetYear]")}
    }}
    change_variable = {{ which = eu4ap_replay_days value = 1 }}
    if = {{ limit = {{ check_variable = {{ which = eu4ap_replay_days value = {REPLAY_DAYS} }} }}
        set_variable = {{ which = eu4ap_replay_days value = 0 }}
        eu4ap_replay = yes
    }}
    if = {{ limit = {{ has_country_flag = {delivery_flag(m)} }}
        clr_country_flag = {delivery_flag(m)}
        country_event = {{ id = eu4ap.3 }}
    }}{death}
}}
"""


def effects_text(m: Manifest) -> str:
    return "\n".join([f"# Seed {m.token}: generated, do not edit.", setup_effect(m), daily_effect(m),
                      scan_effect(m), promote_effect(m), recompute_effect(m), replay_effect(m)])


# ------------------------------------------------------------- events, decisions

def start_daily(m: Manifest) -> str:
    flag = f"eu4ap_{m.token}_daily_scan"
    return (f"if = {{ limit = {{ NOT = {{ has_country_flag = {flag} }} }} "
            f"set_country_flag = {flag} country_event = {{ id = eu4ap.2 days = 1 }} }}")


def events_text(m: Manifest) -> str:
    hidden = """    title = none
    desc = none
    picture = none
    hidden = yes
    is_triggered_only = yes"""
    return f"""namespace = eu4ap
country_event = {{
    id = eu4ap.1
{hidden}
    immediate = {{ if = {{ limit = {{ ai = no has_country_flag = {m.binding_flag} }} {start_daily(m)} }} }}
    option = {{ }}
}}
# Daily chain: inbox, fetters, guarded checks; weekly scan; monthly tick; yearly replay.
country_event = {{
    id = eu4ap.2
{hidden}
    immediate = {{
        if = {{
            limit = {{ ai = no has_country_flag = {m.binding_flag} }}
            eu4ap_daily = yes
            country_event = {{ id = eu4ap.2 days = 1 }}
        }}
    }}
    option = {{ }}
}}
# Visible summary when deliveries from the multiworld have been applied.
country_event = {{
    id = eu4ap.3
    title = eu4ap.3.t
    desc = eu4ap.3.d
    picture = DIPLOMACY_eventPicture
    is_triggered_only = yes
    option = {{ name = eu4ap.3.a }}
}}
""" + claim_events(m)


def decisions_text(m: Manifest) -> str:
    allow = flag_limit([m.ambition_flag, *guard_flags(m, goal_guards(m))])
    extra = ""
    if AMBITIONS[m.ambition].decision == "pilgrimage":
        extra = f"""
    eu4ap_pilgrimage = {{
        potential = {{ ai = no has_country_flag = {m.binding_flag} NOT = {{ has_country_flag = eu4ap_golden_pilgrimage }} }}
        allow = {{ treasury = 3000 NOT = {{ num_of_loans = 1 }} is_bankrupt = no }}
        effect = {{
            add_treasury = -3000
            add_prestige = 25
            set_country_flag = eu4ap_golden_pilgrimage
        }}
        ai_will_do = {{ factor = 0 }}
    }}"""
    return f"""country_decisions = {{
    eu4ap_bind = {{
        potential = {{ ai = no tag = {m.country} NOT = {{ has_country_flag = eu4ap_bound }} }}
        allow = {{ started_in = 1444.11.11 }}
        effect = {{
            set_country_flag = eu4ap_bound
            set_country_flag = {m.binding_flag}
            eu4ap_setup = yes
            {hello(m)}
            eu4ap_scan = yes
            {start_daily(m)}
        }}
        ai_will_do = {{ factor = 0 }}
    }}
    eu4ap_rescan = {{
        potential = {{ ai = no has_country_flag = {m.binding_flag} }}
        allow = {{ always = yes }}
        effect = {{
            eu4ap_inbox = yes
            eu4ap_recompute = yes
            eu4ap_scan = yes
            eu4ap_replay = yes
            {start_daily(m)}
        }}
        ai_will_do = {{ factor = 0 }}
    }}
    eu4ap_claim_delivery = {{
        potential = {{ ai = no has_country_flag = {m.binding_flag} }}
        allow = {{ always = yes }}
        effect = {{ country_event = {{ id = eu4ap.20 }} }}
        ai_will_do = {{ factor = 0 }}
    }}
    eu4ap_ratify = {{
        potential = {{ ai = no has_country_flag = {m.binding_flag} NOT = {{ has_country_flag = {m.goal_flag} }} }}
        allow = {{ {allow} }}
        effect = {{
            set_country_flag = {m.goal_flag}
            {log(m, "GOAL")}
        }}
        ai_will_do = {{ factor = 0 }}
    }}{extra}
}}
"""


def modifiers_text(m: Manifest) -> str:
    blocks = []
    for key, fetter in FETTERS.items():
        for n, values in enumerate(fetter.levels):
            body = " ".join(f"{k} = {fmt(v)}" for k, v in values.items())
            blocks.append(f"eu4ap_fetter_{key}_{n} = {{ {body} }}")
    for name, (values, _en, _fr) in MODIFIERS.items():
        body = " ".join(f"{k} = {fmt(v)}" for k, v in values.items())
        blocks.append(f"{name} = {{ {body} }}")
    return "\n".join(blocks) + "\n"


def localisation(m: Manifest, language: str) -> str:
    fr = language == "french"
    ambition = AMBITIONS[m.ambition]
    lines = [f"l_{language}:"]

    def add(key: str, text: str) -> None:
        lines.append(f' {key}:0 "{text}"')

    seals = (f" et {m.charters_required} Sceaux du multiworld" if fr else
             f" and {m.charters_required} Seals of the Multiworld") if m.goal == "mixed" else ""
    if fr:
        add("eu4ap_bind_title", "§MArchipelago : lier cette campagne§!")
        add("eu4ap_bind_desc", "Lie ce pays au joueur Archipelago du mod installé et pose les entraves de départ.")
        add("eu4ap_rescan_title", "§MArchipelago : vérifier les objectifs§!")
        add("eu4ap_rescan_desc", "Applique les objets installés, vérifie les objectifs et réécrit l'état dans le journal du jeu.")
        add("eu4ap_ratify_title", "§MArchipelago : ratifier la victoire§!")
        add("eu4ap_ratify_desc", f"Exige l'ambition « {ambition.name} »{seals} et les clés ou paliers associés.")
        add("eu4ap_pilgrimage_title", "§MArchipelago : pèlerinage d'or§!")
        add("eu4ap_pilgrimage_desc", "Dépense 3000 ducats sans emprunt pour accomplir le pèlerinage d'or.")
        add("eu4ap.3.t", "Archipelago : livraisons du multiworld")
        add("eu4ap.3.d", "Des objets envoyés par les autres joueurs du multiworld viennent d'arriver. "
                         "Les modificateurs « Archipelago » indiquent les entraves restantes.")
        add("eu4ap.3.a", "Excellent.")
        add("eu4ap_claim_delivery_title", "§MArchipelago : réceptionner une livraison§!")
        add("eu4ap_claim_delivery_desc", "Saisissez le code à 4 chiffres affiché par le client Archipelago pour "
                                         "recevoir immédiatement un objet du multiworld.")
        for event_id, label in ((20, "premier"), (21, "deuxième"), (22, "troisième"), (23, "dernier")):
            add(f"eu4ap.{event_id}.t", f"Archipelago : code de livraison ({label} chiffre)")
            add(f"eu4ap.{event_id}.d", f"Choisissez le {label} chiffre du code affiché par le client.")
        add("eu4ap.24.t", "Archipelago : confirmer la livraison")
        add("eu4ap.24.d", "Code [Root.eu4ap_code.GetValue] : [Root.GetEU4APDelivery]")
        add("eu4ap.24.a", "Recevoir cette livraison")
        add("eu4ap.24.b", "Corriger le code")
        add("eu4ap.claim.cancel", "Annuler")
        add("eu4ap_dlv_unknown", "code inconnu. Vérifiez le code affiché par le client.")
        add("eu4ap_dlv_done", "livraison déjà reçue.")
    else:
        add("eu4ap_bind_title", "§MArchipelago: bind this campaign§!")
        add("eu4ap_bind_desc", "Binds this country to the installed Archipelago slot and applies the starting fetters.")
        add("eu4ap_rescan_title", "§MArchipelago: scan objectives now§!")
        add("eu4ap_rescan_desc", "Applies installed items, scans objectives and writes the state to the game log.")
        add("eu4ap_ratify_title", "§MArchipelago: ratify the victory§!")
        add("eu4ap_ratify_desc", f"Requires the ambition '{ambition.name}'{seals} and its keys or levels.")
        add("eu4ap_pilgrimage_title", "§MArchipelago: golden pilgrimage§!")
        add("eu4ap_pilgrimage_desc", "Spend 3000 ducats without loans to complete the golden pilgrimage.")
        add("eu4ap.3.t", "Archipelago: deliveries from the multiworld")
        add("eu4ap.3.d", "Items sent by the other players of the multiworld have arrived. "
                         "Modifiers named 'Archipelago' show the remaining fetters.")
        add("eu4ap.3.a", "Excellent.")
        add("eu4ap_claim_delivery_title", "§MArchipelago: receive a delivery§!")
        add("eu4ap_claim_delivery_desc", "Enter the 4-digit code shown by the Archipelago client to receive "
                                         "an item from the multiworld immediately.")
        for event_id, label in ((20, "first"), (21, "second"), (22, "third"), (23, "last")):
            add(f"eu4ap.{event_id}.t", f"Archipelago: delivery code ({label} digit)")
            add(f"eu4ap.{event_id}.d", f"Choose the {label} digit of the code shown by the client.")
        add("eu4ap.24.t", "Archipelago: confirm the delivery")
        add("eu4ap.24.d", "Code [Root.eu4ap_code.GetValue]: [Root.GetEU4APDelivery]")
        add("eu4ap.24.a", "Receive this delivery")
        add("eu4ap.24.b", "Correct the code")
        add("eu4ap.claim.cancel", "Cancel")
        add("eu4ap_dlv_unknown", "unknown code. Check the code shown by the client.")
        add("eu4ap_dlv_done", "delivery already received.")
    for digit in range(10):
        add(f"eu4ap.digit.{digit}", str(digit))
    for code, item, _sender, _location in m.deliveries:
        add(f"eu4ap_dlv_{code}", ITEM_DEF_BY_ID[item].name)
    for code in m.deathlink_codes:
        add(f"eu4ap_dlv_{code}", "DeathLink")
    for key, fetter in FETTERS.items():
        total = len(fetter.levels)
        for n in range(total):
            title = fetter.title_fr if fr else fetter.title_en
            text = (f"§MArchipelago : {title}, palier {n}/{total}§!" if fr
                    else f"§MArchipelago: {title}, level {n}/{total}§!")
            add(f"eu4ap_fetter_{key}_{n}", text)
    for name, (_values, en, french) in MODIFIERS.items():
        add(name, f"§M{french if fr else en}§!")
    return "\n".join(lines) + "\n"


def mod_files(m: Manifest, items: list[tuple] = (), deathlinks: int = 0) -> dict[str, tuple[str, str]]:
    """Relative path -> (content, encoding) for a schema-2 manifest."""
    return {
        "common/scripted_effects/eu4ap_effects.txt": (effects_text(m), "utf-8"),
        "common/scripted_effects/eu4ap_inbox.txt": (inbox_text(m, list(items), deathlinks), "utf-8"),
        "common/scripted_effects/eu4ap_deliveries.txt": (deliveries_effect(m), "utf-8"),
        "customizable_localization/eu4ap_customizable_localization.txt": (customizable_localisation(m), "utf-8"),
        "common/event_modifiers/eu4ap_modifiers.txt": (modifiers_text(m), "utf-8"),
        "events/eu4ap_events.txt": (events_text(m), "utf-8"),
        "decisions/eu4ap_decisions.txt": (decisions_text(m), "utf-8"),
        "localisation/eu4ap_l_english.yml": (localisation(m, "english"), "utf-8-sig"),
        "localisation/eu4ap_l_french.yml": (localisation(m, "french"), "utf-8-sig"),
    }
