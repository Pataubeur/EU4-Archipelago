"""Schema-2 catalogue: the single source for generation, AP logic, the rendered
mod and the client. Every EU4 keyword used here exists in the vanilla 1.37.5
scripts (see docs/design-progression.md); behaviour inside this mod remains a
candidate awaiting EU4 validation.

IDs are stable and never derived from a position in a filtered pool:
calendar 2000-2099, generic 3000-3999, ambition milestones 10000-19999,
missions 20000+ (missions_1375.py). Items: legacy 1000-1005, new 1100+.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .data import BASE_ID, ITEMS as LEGACY_ITEMS, OBJECTIVES as LEGACY_OBJECTIVES
from .missions_1375 import MISSIONS

LENGTHS = ("short", "standard", "long")
HORIZON = {"short": 1500, "standard": 1575, "long": 1700}
MISSION_COUNT = {"short": 6, "standard": 12, "long": 18}
SAVE_MODES = ("normal", "ironman")
GOALS = ("national_ambition", "great_power", "domination", "mixed")
DEV_TARGETS = (125, 150, 200, 300, 500)  # Percent of starting development.

KNOWN_DLCS = (
    "American Dream", "Art of War", "Common Sense", "Conquest of Paradise", "Cradle of Civilization",
    "Dharma", "Domination", "El Dorado", "Emperor", "Golden Century", "King of Kings", "Leviathan",
    "Lions of the North", "Mandate of Heaven", "Mare Nostrum", "Origins", "Purple Phoenix",
    "Res Publica", "Rights of Man", "Rule Britannia", "Star and Crescent", "The Cossacks",
    "Third Rome", "Wealth of Nations", "Winds of Change",
)

Guard = tuple  # (family, level). Families: fetter keys, "key:<region>", "seal".


def length_index(length: str) -> int:
    return LENGTHS.index(length)


def late_year(length: str) -> int:
    """Calendar checks after this year are 'long': they can hold another player's
    progression for hours, so exclude_long_checks keeps progression off them."""
    return 1444 + 2 * (HORIZON[length] - 1444) // 3


# ------------------------------------------------------------------ fetters and keys

@dataclass(frozen=True)
class Fetter:
    item: str
    levels: tuple[dict, ...]  # Modifier of each missing-level state; len == item copies.
    title_en: str
    title_fr: str


FETTERS = {
    "colonial": Fetter("Progressive Colonial License", (
        {"colonists": -1, "global_colonial_growth": -50}, {"global_colonial_growth": -25}),
        "Colonial License", "Licence coloniale"),
    "admiralty": Fetter("Progressive Admiralty", (
        {"naval_forcelimit_modifier": -0.5}, {"naval_forcelimit_modifier": -0.25}),
        "Admiralty", "Amirauté"),
    "chancery": Fetter("Progressive Chancery", (
        {"diplomats": -1, "diplomatic_upkeep": -1}, {"diplomatic_upkeep": -1}),
        "Chancery", "Chancellerie"),
    "guilds": Fetter("Progressive Merchant Guilds", (
        {"merchants": -1, "trade_efficiency": -0.2}, {"trade_efficiency": -0.1}),
        "Merchant Guilds", "Guildes marchandes"),
    "academy": Fetter("Progressive Academy", (
        {"technology_cost": 0.3}, {"technology_cost": 0.2}, {"technology_cost": 0.1}),
        "Academy", "Académie"),
    "imperial_court": Fetter("Progressive Imperial Court", (
        {"core_creation": 0.5, "ae_impact": 0.5}, {"core_creation": 0.25, "ae_impact": 0.25}),
        "Imperial Court", "Cour impériale"),
    "arsenal": Fetter("Progressive Arsenal", (
        {"land_forcelimit_modifier": -0.33}, {"land_forcelimit_modifier": -0.15}),
        "Arsenal", "Arsenal"),
}
DEFAULT_FETTERS = ("admiralty", "chancery", "colonial", "guilds")


@dataclass(frozen=True)
class RegionKey:
    item: str
    scope: str  # Province-scope trigger selecting the key's provinces.
    name_fr: str


REGION_KEYS = {
    "anatolia": RegionKey("Key: Anatolia", "region = anatolia_region", "Anatolie"),
    "balkans": RegionKey("Key: Balkans", "region = balkan_region", "Balkans"),
    "baltic": RegionKey("Key: Baltic", "region = baltic_region", "Baltique"),
    "east_indies": RegionKey("Key: East Indies", "superregion = east_indies_superregion", "Indes orientales"),
    "egypt": RegionKey("Key: Egypt", "region = egypt_region", "Égypte"),
    "france": RegionKey("Key: France", "region = france_region", "France"),
    "iberia": RegionKey("Key: Iberia", "region = iberia_region", "Ibérie"),
    "india": RegionKey("Key: India", "superregion = india_superregion", "Inde"),
    "italy": RegionKey("Key: Italy", "region = italy_region", "Italie"),
    "low_countries": RegionKey("Key: Low Countries", "region = low_countries_region", "Pays-Bas"),
    "maghreb": RegionKey("Key: Maghreb", "region = maghreb_region", "Maghreb"),
    "mashriq": RegionKey("Key: Mashriq", "region = mashriq_region", "Machrek"),
    "north_german": RegionKey("Key: North Germany", "region = north_german_region", "Allemagne du Nord"),
    "russia": RegionKey("Key: Russia", "region = russia_region", "Russie"),
    "scandinavia": RegionKey("Key: Scandinavia", "region = scandinavia_region", "Scandinavie"),
    "south_german": RegionKey("Key: South Germany", "region = south_german_region", "Allemagne du Sud"),
}


def family_item(family: str) -> str:
    if family == "seal":
        return SEAL
    if family.startswith("key:"):
        return REGION_KEYS[family[4:]].item
    return FETTERS[family].item


# ------------------------------------------------------------------------- items

@dataclass(frozen=True)
class ItemDef:
    id: int
    name: str
    classification: str        # progression / useful / filler / trap
    kind: str                  # resource, level, seal, charter, trap
    effect: str = ""           # Country-scope script; {amount} is scaled by reward strength.
    amount: float = 0
    family: str = ""           # For level items.
    limit: str = ""            # Extra condition before applying (traps wait until 1450).


SEAL = "Seal of the Multiworld"
_new_items = [
    ItemDef(BASE_ID + 1100, SEAL, "progression", "seal", family="seal"),
    *[ItemDef(BASE_ID + 1110 + i, f.item, "progression", "level", family=key)
      for i, (key, f) in enumerate(FETTERS.items())],
    *[ItemDef(BASE_ID + 1200 + i, k.item, "progression", "level", family=f"key:{key}")
      for i, (key, k) in enumerate(REGION_KEYS.items())],
    ItemDef(BASE_ID + 1300, "Multiworld Decree", "useful", "resource",
            "add_country_modifier = { name = eu4ap_decree duration = 3650 }"),
    ItemDef(BASE_ID + 1301, "Royal Treasury", "filler", "resource", "add_years_of_income = {amount}", 0.25),
    ItemDef(BASE_ID + 1302, "Mandate of Legitimacy", "filler", "resource", (
        "if = { limit = { government = monarchy } add_legitimacy = {amount} }\n"
        "else_if = { limit = { government = republic } add_republican_tradition = {amount} }\n"
        "else_if = { limit = { government = theocracy } add_devotion = {amount} }\n"
        "else = { add_prestige = {amount} }"), 10),
    ItemDef(BASE_ID + 1303, "Military Tradition", "useful", "resource", "add_army_tradition = {amount}", 10),
    ItemDef(BASE_ID + 1304, "Fresh Recruits", "useful", "resource", "add_yearly_manpower = {amount}", 0.5),
    ItemDef(BASE_ID + 1305, "Court Patronage", "useful", "resource",
            "add_country_modifier = { name = eu4ap_court_patronage duration = 3650 }"),
    ItemDef(BASE_ID + 1306, "Peace Dividend", "useful", "resource", "add_war_exhaustion = -{amount}", 3),
    ItemDef(BASE_ID + 1307, "Missionary Zeal", "useful", "resource",
            "add_country_modifier = { name = eu4ap_missionary_zeal duration = 3650 }"),
    ItemDef(BASE_ID + 1308, "Ambition Claims", "useful", "claims"),
    ItemDef(BASE_ID + 1400, "Regency Crisis", "trap", "trap",
            "if = { limit = { stability = 0 } add_stability = -1 }", limit="is_year = 1450"),
    ItemDef(BASE_ID + 1401, "Peasant Revolt", "trap", "trap",
            "random_owned_province = { limit = { is_capital = no } "
            "spawn_rebels = { type = anti_tax_rebels size = 1 } }", limit="is_year = 1450"),
    ItemDef(BASE_ID + 1402, "Diplomatic Incident", "trap", "trap",
            "add_country_modifier = { name = eu4ap_diplomatic_incident duration = 1825 }", limit="is_year = 1450"),
    ItemDef(BASE_ID + 1403, "Inflation Spike", "trap", "trap", "add_inflation = 2", limit="is_year = 1450"),
    ItemDef(BASE_ID + 1404, "Sickly Heir", "trap", "trap",
            "if = { limit = { has_heir = yes NOT = { ruler_age = 50 } } kill_heir = { allow_new_heir = yes } }",
            limit="is_year = 1450"),
]
_legacy_items = [
    ItemDef(code, name, classification, "charter" if not effect else "resource",
            f"{effect} = {{amount}}" if effect else "", amount, family="charter" if not effect else "")
    for name, (code, effect, amount, classification) in LEGACY_ITEMS.items()
]
ALL_ITEMS = tuple(_legacy_items + _new_items)
ITEM_DEFS = {item.name: item for item in ALL_ITEMS}
ITEM_DEF_BY_ID = {item.id: item for item in ALL_ITEMS}
USEFUL_ITEMS = ("Multiworld Decree", "Military Tradition", "Fresh Recruits", "Court Patronage",
                "Peace Dividend", "Missionary Zeal", "50 Administrative Power",
                "50 Diplomatic Power", "50 Military Power")
FILLER_ITEMS = ("Royal Treasury", "Mandate of Legitimacy", "10 Prestige")
TRAP_ITEMS = tuple(i.name for i in _new_items if i.kind == "trap")
MODIFIERS = {
    "eu4ap_decree": ({"global_tax_modifier": 0.1, "production_efficiency": 0.1},
                     "Archipelago: Multiworld Decree", "Archipelago : décret du multiworld"),
    "eu4ap_court_patronage": ({"advisor_cost": -0.25}, "Archipelago: Court Patronage", "Archipelago : mécénat de cour"),
    "eu4ap_missionary_zeal": ({"missionaries": 1, "global_missionary_strength": 0.02},
                              "Archipelago: Missionary Zeal", "Archipelago : zèle missionnaire"),
    "eu4ap_diplomatic_incident": ({"ae_impact": 0.25}, "Archipelago: Diplomatic Incident",
                                  "Archipelago : incident diplomatique"),
    "eu4ap_unratified": ({"local_tax_modifier": -0.5, "local_production_efficiency": -0.5,
                          "local_manpower_modifier": -0.5, "local_unrest": 2},
                         "Archipelago: Unratified Land", "Archipelago : terre non ratifiée"),
}


# --------------------------------------------------------------------- locations

@dataclass(frozen=True)
class LocationDef:
    id: int
    name: str
    category: str
    trigger: str               # Country scope, ROOT = the bound player country.
    age: int = 1               # 1..4, used for AP regions and pacing.
    guards: tuple = ()         # ((family, level), ...)
    min_length: str = "short"
    long: bool = False         # Candidate for exclusion.
    priority: bool = False     # Ambition milestones.
    optional: bool = False     # Bonus with a game-date deadline: always excluded.


def _calendar(year: int) -> LocationDef:
    age = 1 if year < 1500 else 2 if year < 1600 else 3 if year < 1700 else 4
    length = next(n for n in LENGTHS if HORIZON[n] >= year) if year <= HORIZON["long"] else "long"
    return LocationDef(BASE_ID + 2000 + (year - 1450) // 5, f"Calendar: {year}", "calendar",
                       f"is_year = {year}", age, min_length=length)


CALENDAR = tuple(_calendar(year) for year in range(1450, HORIZON["long"] + 1, 5))

BASE_IDEAS = ("aristocracy_ideas", "plutocracy_ideas", "innovativeness_ideas", "religious_ideas",
              "spy_ideas", "diplomatic_ideas", "offensive_ideas", "defensive_ideas", "trade_ideas",
              "economic_ideas", "exploration_ideas", "maritime_ideas", "quality_ideas",
              "quantity_ideas", "expansion_ideas", "administrative_ideas", "humanist_ideas",
              "influence_ideas", "naval_ideas")
CONTINENTS = ("europe", "asia", "africa", "north_america", "south_america", "oceania")


def ideas(amount: int) -> str:
    groups = " ".join(f"full_idea_group = {g}" for g in BASE_IDEAS)
    return f"calc_true_if = {{ amount = {amount} {groups} }}"


def continents(amount: int) -> str:
    owned = " ".join(f"any_owned_province = {{ continent = {c} }}" for c in CONTINENTS)
    return f"calc_true_if = {{ amount = {amount} {owned} }}"


def dev_at_least(percent: int) -> str:
    return f"check_variable = {{ which = eu4ap_dev_now which = eu4ap_dev_{percent} }}"


NO_DEBT = "NOT = { num_of_loans = 1 } is_bankrupt = no"
NEW_WORLD = "OR = { north_america = { has_discovered = ROOT } south_america = { has_discovered = ROOT } }"


def _g(n: int, name: str, category: str, trigger: str, age: int, guards=(), length="short", long=False):
    return LocationDef(BASE_ID + 3000 + n, name, category, trigger, age, tuple(guards), length, long)


GENERIC = (
    _g(0, "Institution: Renaissance", "institution", "has_institution = renaissance", 1),
    _g(1, "Institution: Colonialism", "institution", "has_institution = colonialism", 1),
    _g(2, "Institution: Printing Press", "institution", "has_institution = printing_press", 2, length="standard"),
    _g(3, "Institution: Global Trade", "institution", "has_institution = global_trade", 2, length="standard"),
    _g(4, "Institution: Manufactories", "institution", "has_institution = manufactories", 3, length="long"),
    _g(10, "Ideas: First Group", "ideas", ideas(1), 1),
    _g(11, "Ideas: Three Groups", "ideas", ideas(3), 2, [("academy", 1)], "standard"),
    _g(12, "Ideas: Five Groups", "ideas", ideas(5), 3, [("academy", 2)], "long", True),
    _g(20, "Government: Empire Rank", "government", "government_rank = 3", 2, length="standard"),
    _g(21, "Government: Absolutism 50", "government", "absolutism = 50", 3, length="long", long=True),
    _g(30, "Development: +25%", "development", dev_at_least(125), 1),
    _g(31, "Development: +50%", "development", dev_at_least(150), 1),
    _g(32, "Development: Doubled", "development", dev_at_least(200), 2, [("imperial_court", 1)], "standard"),
    _g(33, "Development: Tripled", "development", dev_at_least(300), 3, [("imperial_court", 2)], "long", True),
    _g(34, "Development: City of 30", "development",
       "any_owned_province = { is_core = ROOT development = 30 }", 2, length="standard"),
    _g(35, "Development: City of 50", "development",
       "any_owned_province = { is_core = ROOT development = 50 }", 3, length="long", long=True),
    _g(40, "Diplomacy: Two Allies", "diplomacy", "num_of_allies = 2", 1, [("chancery", 1)]),
    _g(41, "Diplomacy: Four Allies", "diplomacy", "num_of_allies = 4", 2, [("chancery", 2)], "standard"),
    _g(42, "Diplomacy: Three Royal Marriages", "diplomacy", "num_of_royal_marriages = 3", 1),
    _g(43, "Diplomacy: First Subject", "diplomacy", "num_of_subjects = 1", 1, [("chancery", 1)]),
    _g(44, "Diplomacy: Three Subjects", "diplomacy", "num_of_subjects = 3", 2, [("chancery", 2)], "standard"),
    _g(45, "Diplomacy: Personal Union", "diplomacy", "personal_union = 1", 2, [("chancery", 2)], "standard"),
    _g(50, "Military: Army Tradition 50", "military", "army_tradition = 50", 1),
    _g(51, "Military: Army Tradition 80", "military", "army_tradition = 80", 2, [("arsenal", 1)], "standard"),
    _g(52, "Military: Victory over a Rival", "military",
       "any_rival_country = { ROOT = { has_won_war_against = { who = PREV max_years_since = 10 } } }", 1),
    _g(53, "Military: Discipline 105%", "military",
       "has_global_modifier_value = { which = discipline value = 0.05 }", 2, [("arsenal", 1)], "standard"),
    _g(54, "Military: Discipline 110%", "military",
       "has_global_modifier_value = { which = discipline value = 0.10 }", 3, [("arsenal", 2)], "long"),
    _g(60, "Navy: 20 Ships", "navy", "navy_size = 20", 1, [("admiralty", 1)]),
    _g(61, "Navy: 50 Ships", "navy", "navy_size = 50", 2, [("admiralty", 2)], "standard"),
    _g(70, "Economy: Monthly Income 15", "economy", "monthly_income = 15", 1, [("guilds", 1)]),
    _g(71, "Economy: Monthly Income 30", "economy", "monthly_income = 30", 2, [("guilds", 1)], "standard"),
    _g(72, "Economy: Monthly Income 60", "economy", "monthly_income = 60", 3, [("guilds", 2)], "long"),
    _g(73, "Economy: Trade-Driven Income", "economy", "trade_income_percentage = 0.3", 2, [("guilds", 1)], "standard"),
    _g(74, "Economy: Debt-Free Reserve", "economy", f"years_of_income = 0.5 {NO_DEBT}", 1),
    _g(75, "Economy: Royal Reserve", "economy", f"years_of_income = 1.5 {NO_DEBT}", 2, length="standard"),
    _g(80, "Exploration: Discover the New World", "exploration", NEW_WORLD, 1, [("admiralty", 1)]),
    _g(81, "Colonization: First Colony", "colonization", "num_of_colonies = 1", 1, [("colonial", 1)]),
    _g(82, "Colonization: Colonial Nation", "colonization",
       "any_subject_country = { is_colonial_nation = yes }", 2, [("colonial", 2)], "standard"),
    _g(83, "Colonization: Three Continents", "colonization", continents(3), 2, [("colonial", 1)], "standard"),
    _g(84, "Colonization: Five Continents", "colonization", continents(5), 3, [("colonial", 2)], "long", True),
    _g(90, "Religion: Religious Unity", "religion", "religious_unity = 1", 1),
    _g(91, "Prestige: 75", "prestige", "prestige = 75", 1),
    _g(92, "Stability: +3", "stability", "stability = 3", 1),
)


# --------------------------------------------------------------------- ambitions

@dataclass(frozen=True)
class Ambition:
    key: str
    index: int                  # Stable: milestone IDs are BASE+10000+100*index+n.
    name: str
    tags: tuple[str, ...]       # Empty: generic, any country.
    length: str                 # Minimum campaign length.
    goal: str                   # Country-scope trigger of the national goal.
    keys: tuple[str, ...] = ()
    goal_guards: tuple = ()     # Non-key guards (fetters).
    milestones: tuple = ()      # ((name, trigger, age, guards), ...)
    dlc: str = ""
    claims: str = ""            # Province-scope trigger for the Ambition Claims item.
    dated: bool = False         # Keys placed in sphere 1 (AP has no notion of game time).
    auto: bool = True           # Eligible for automatic selection.
    decision: str = ""          # Extra decision rendered for this ambition.

    def milestone_defs(self) -> tuple[LocationDef, ...]:
        """Milestones are (title, trigger, age, guards[, optional])."""
        return tuple(LocationDef(BASE_ID + 10_000 + 100 * self.index + n, f"{self.name}: {m[0]}",
                                 "ambition", m[1], m[2], tuple(m[3]), self.length,
                                 priority=not (len(m) > 4 and m[4]), optional=len(m) > 4 and m[4])
                     for n, m in enumerate(self.milestones))

    def all_goal_guards(self) -> tuple:
        return tuple((f"key:{k}", 1) for k in self.keys) + tuple(self.goal_guards)


def core(*provinces: int, extra: str = "") -> str:
    return " ".join(f"{p} = {{ owned_by = ROOT is_core = ROOT {extra}}}".replace("  ", " ") for p in provinces)


def areas(*names: str) -> str:
    return " ".join(f"{a}_area = {{ type = all owned_by = ROOT is_core = ROOT }}" for a in names)


def provinces_claim(*provinces: int) -> str:
    return "OR = { " + " ".join(f"province_id = {p}" for p in provinces) + " }"


def areas_claim(*names: str) -> str:
    return "OR = { " + " ".join(f"area = {a}_area" for a in names) + " }"


def count_in(region: str, value: int, extra: str = "is_core = ROOT") -> str:
    return f"num_of_owned_provinces_with = {{ value = {value} region = {region}_region {extra} }}"


K = lambda key: (f"key:{key}", 1)  # noqa: E731
BASILEUS_BALKANS = ("morea", "northern_greece", "albania", "macedonia", "bulgaria", "thrace")
BASILEUS_ANATOLIA = ("hudavendigar", "aydin", "germiyan", "kastamonu", "ankara", "karaman",
                     "rum", "cukurova", "dulkadir")
PENTARCHY = (118, 151, 358, 2313, 379)
SWE_COAST = {"scandinavia": (1, 2, 3, 6, 9, 11, 19, 25, 27, 28, 1930, 1981, 1982, 4113, 4165),
             "russia": (30, 33, 34), "baltic": (35, 36, 37, 38, 39, 40, 41, 42, 43, 1841, 1842, 1935),
             "north_german": (45, 46, 47, 48, 1858, 2994, 2995, 2996, 4746, 4745)}
ARA_PORTS = {"italy": (101, 112, 121), "balkans": (148, 151, 137), "anatolia": (317,),
             "maghreb": (336, 341, 354), "egypt": (358,), "iberia": (220,)}
HEREDITARY = ("government = monarchy NOT = { has_reform = elective_monarchy } "
              "NOT = { has_reform = polish_elective_monarchy } NOT = { has_reform = elective_monarchy_reform } "
              "NOT = { has_reform = polish_great_sejm }")
SUBJECT_GROUPS = (("eastern", ()), ("muslim", (("chancery", 1),)), ("dharmic", (("chancery", 1),)),
                  ("christian", (("chancery", 2),)), ("pagan", (("chancery", 2),)))

AMBITIONS_LIST = (
    Ambition("byz_basileus", 0, "Basileus", ("BYZ",), "standard",
             areas(*BASILEUS_BALKANS, *BASILEUS_ANATOLIA) + " NOT = { has_country_flag = byz_dishonoring_justinian }",
             ("balkans", "anatolia"), milestones=(
                 ("Greece", areas("morea", "northern_greece"), 1, [K("balkans")]),
                 ("Albania and Macedonia", areas("albania", "macedonia"), 2, [K("balkans")]),
                 ("Bulgaria and Thrace", areas("bulgaria", "thrace"), 2, [K("balkans")]),
                 ("Western Anatolia", areas("hudavendigar", "aydin", "germiyan"), 2, [K("anatolia")]),
                 ("Central Anatolia", areas("kastamonu", "ankara", "karaman"), 2, [K("anatolia")]),
                 ("Eastern Anatolia", areas("rum", "cukurova", "dulkadir"), 2, [K("anatolia")])),
             claims=areas_claim(*BASILEUS_BALKANS, *BASILEUS_ANATOLIA)),
    Ambition("byz_pentarchy", 1, "Pentarchy", ("BYZ",), "long",
             "religion = orthodox " + core(*PENTARCHY, extra="religion = orthodox ")
             + " NOT = { has_country_flag = byz_dishonoring_justinian }",
             ("anatolia", "mashriq", "egypt", "italy"), milestones=(
                 ("Constantinople Holds", "is_year = 1454 owns_core_province = 151", 1, []),
                 ("Foothold in Anatolia", "any_owned_province = { region = anatolia_region }", 1, [K("anatolia")]),
                 ("Antioch", core(2313), 2, [K("mashriq")]),
                 ("Jerusalem", core(379), 2, [K("mashriq")]),
                 ("Alexandria", core(358), 3, [K("egypt")]),
                 ("Rome", core(118), 3, [K("italy")])),
             claims=provinces_claim(*PENTARCHY)),
    Ambition("tur_sultan_of_rum", 2, "Sultan of Rum", ("TUR",), "long",
             "owns_core_province = 151 owns_core_province = 118 owns_core_province = 295",
             ("italy", "russia"), milestones=(
                 ("Constantinople", "owns_core_province = 151", 1, []),
                 ("Rome", "owns_core_province = 118", 2, [K("italy")]),
                 ("Moscow", "owns_core_province = 295", 3, [K("russia")])),
             claims=provinces_claim(118, 295)),
    Ambition("fra_better_than_napoleon", 3, "Better than Napoleon", ("FRA",), "long",
             "owns_core_province = 134 owns_core_province = 50 owns_core_province = 295",
             ("south_german", "north_german", "russia"), milestones=(
                 ("Vienna", "owns_core_province = 134", 2, [K("south_german")]),
                 ("Berlin", "owns_core_province = 50", 3, [K("north_german")]),
                 ("Moscow", "owns_core_province = 295", 3, [K("russia")])),
             claims=provinces_claim(134, 50, 295)),
    Ambition("eng_one_night_in_paris", 4, "One Night in Paris", ("ENG",), "short",
             "owns_core_province = 183", ("france",), milestones=(
                 ("French Lands in 1453", "is_year = 1453 any_owned_province = { region = france_region }", 1, []),
                 ("Paris", "owns = 183", 1, [K("france")])),
             claims=provinces_claim(183)),
    # The achievement's 1500 deadline cannot be guaranteed in a multiworld: the goal
    # drops it, and "Before 1500" is an always-excluded bonus milestone.
    Ambition("por_navigator", 5, "The Navigator", ("POR",), "short",
             "any_owned_province = { continent = africa } "
             "any_owned_province = { superregion = india_superregion } "
             "any_owned_province = { superregion = east_indies_superregion }",
             ("india", "east_indies"), dated=True, milestones=(
                 ("Africa", "any_owned_province = { continent = africa }", 1, []),
                 ("India", "any_owned_province = { superregion = india_superregion }", 1, [K("india")]),
                 ("East Indies", "any_owned_province = { superregion = east_indies_superregion }", 1,
                  [K("east_indies")]),
                 ("Before 1500", "NOT = { is_year = 1500 } any_owned_province = { continent = africa } "
                  "any_owned_province = { superregion = india_superregion } "
                  "any_owned_province = { superregion = east_indies_superregion }", 1,
                  [K("india"), K("east_indies")], True))),
    Ambition("cas_way_to_india", 6, "Way to India", ("CAS",), "short",
             "north_america = { has_discovered = ROOT } south_america = { has_discovered = ROOT }",
             goal_guards=(("admiralty", 1),), milestones=(
                 ("Atlantic Crossing", NEW_WORLD, 1, [("admiralty", 1)]),)),
    Ambition("spa_imperio_espanol", 7, "Imperio Espanol", ("CAS", "ARA"), "long",
             "tag = SPA " + " ".join(f"{p} = {{ country_or_non_sovereign_subject_holds = ROOT "
                                     "owner_is_colonial_nation = yes }" for p in (852, 835, 484, 808)),
             goal_guards=(("colonial", 2),), milestones=(
                 ("Form Spain", "tag = SPA", 2, []),
                 ("First Colonial Nation", "any_subject_country = { is_colonial_nation = yes }", 2,
                  [("colonial", 2)]))),
    Ambition("hab_pen_mightier", 8, "The Pen is Mightier", ("HAB",), "standard",
             "personal_union = 3", goal_guards=(("chancery", 2),), milestones=(
                 ("First Union", "personal_union = 1", 1, [("chancery", 1)]),
                 ("Second Union", "personal_union = 2", 2, [("chancery", 2)]))),
    Ambition("pol_one_king", 9, "One King to Rule", ("POL",), "long",
             HEREDITARY + " absolutism = 50", milestones=(
                 ("Hereditary Crown", HEREDITARY, 2, []),
                 ("Absolutism 25", "absolutism = 25", 3, []))),
    Ambition("pru_goosestep", 10, "A Fine Goosestep", ("BRA",), "long",
             "tag = PRU has_global_modifier_value = { which = discipline value = 0.25 }",
             goal_guards=(("arsenal", 2),), milestones=(
                 ("Form Prussia", "tag = PRU", 2, []),
                 ("Discipline 110%", "has_global_modifier_value = { which = discipline value = 0.10 }", 3,
                  [("arsenal", 1)]))),
    Ambition("mng_kow_tow", 11, "Kow-Tow", ("MNG",), "standard",
             " ".join(f"any_subject_country = {{ religion_group = {g} }}" for g, _ in SUBJECT_GROUPS),
             goal_guards=(("chancery", 2),), milestones=tuple(
                 (f"{g.capitalize()} Subject", f"any_subject_country = {{ religion_group = {g} }}", 2, list(gs))
                 for g, gs in SUBJECT_GROUPS)),
    Ambition("mal_golden_pilgrimage", 12, "Golden Pilgrimage", ("MAL",), "standard",
             "has_country_flag = eu4ap_golden_pilgrimage", decision="pilgrimage", milestones=(
                 ("Reserve of 1000 Ducats", f"treasury = 1000 {NO_DEBT}", 1, [("guilds", 1)]),
                 ("Reserve of 2000 Ducats", f"treasury = 2000 {NO_DEBT}", 2, [("guilds", 2)]))),
    Ambition("eth_prester_john", 13, "Prester John", ("ETH",), "long",
             "religion = coptic owns_core_province = 358 owns_core_province = 2313 owns_core_province = 151",
             ("egypt", "mashriq", "balkans"), milestones=(
                 ("Alexandria", "owns_core_province = 358", 2, [K("egypt")]),
                 ("Antioch", "owns_core_province = 2313", 3, [K("mashriq")]),
                 ("Constantinople", "owns_core_province = 151", 3, [K("balkans")])),
             claims=provinces_claim(358, 2313, 151)),
    Ambition("azt_edge_of_madness", 14, "Edge of Madness", ("AZT",), "standard",
             "had_country_flag = { flag = doom_reached_95 days = 7300 } NOT = { has_country_flag = doom_reached_100 }",
             dlc="El Dorado", milestones=(("Doom 95", "has_country_flag = doom_reached_95", 2, []),)),
    Ambition("swe_not_overpowered", 15, "Sweden is not Overpowered", ("SWE",), "standard",
             " ".join(f"owns_core_province = {p}" for ps in SWE_COAST.values() for p in ps),
             tuple(SWE_COAST), milestones=tuple(
                 (f"Baltic Coast: {r.replace('_', ' ').title()}",
                  " ".join(f"owns_core_province = {p}" for p in ps), 2, [K(r)])
                 for r, ps in SWE_COAST.items()),
             claims=provinces_claim(*(p for ps in SWE_COAST.values() for p in ps))),
    Ambition("dan_brick_by_brick", 16, "Brick by Brick", ("DAN",), "standard",
             "scandinavia_region = { type = all owned_by = ROOT is_core = ROOT }", ("scandinavia",), milestones=(
                 ("25 Scandinavian Cores", count_in("scandinavia", 25), 1, [K("scandinavia")]),
                 ("40 Scandinavian Cores", count_in("scandinavia", 40), 2, [K("scandinavia")]))),
    Ambition("ser_lazarus", 17, "Lazarus", ("SER",), "long",
             "balkan_region = { type = all owned_by = ROOT is_core = ROOT }", ("balkans",), milestones=(
                 ("15 Balkan Cores", count_in("balkan", 15), 1, [K("balkans")]),
                 ("35 Balkan Cores", count_in("balkan", 35), 2, [K("balkans")]))),
    Ambition("hun_take_that", 18, "Take that, von Habsburgs", ("HUN",), "standard",
             areas("inner_austria", "austria_proper", "carinthia", "tirol"), ("south_german",), milestones=tuple(
                 (title, areas(area), 2, [K("south_german")]) for title, area in (
                     ("Inner Austria", "inner_austria"), ("Austria Proper", "austria_proper"),
                     ("Carinthia", "carinthia"), ("Tirol", "tirol"))),
             claims=areas_claim("inner_austria", "austria_proper", "carinthia", "tirol")),
    Ambition("bur_inheritance", 19, "The Burgundian Inheritance", ("BUR",), "long",
             "FRA = { is_subject_of = ROOT } HAB = { is_subject_of = ROOT } "
             "low_countries_region = { type = all owned_by = ROOT is_core = ROOT }",
             ("low_countries",), goal_guards=(("chancery", 2),), milestones=(
                 ("Low Countries", "low_countries_region = { type = all owned_by = ROOT is_core = ROOT }", 2,
                  [K("low_countries")]),
                 ("France Subjugated", "FRA = { is_subject_of = ROOT }", 3, [("chancery", 2)]),
                 ("Austria Subjugated", "HAB = { is_subject_of = ROOT }", 3, [("chancery", 2)]))),
    Ambition("ara_consulate", 20, "Consulate of the Sea", ("ARA",), "long",
             " ".join(f"owns = {p}" for ps in ARA_PORTS.values() for p in ps),
             tuple(k for k in ARA_PORTS if k != "iberia"), milestones=tuple(
                 (f"Ports: {r.title()}", " ".join(f"owns = {p}" for p in ps), 2 if r != "iberia" else 1,
                  [] if r == "iberia" else [K(r)]) for r, ps in ARA_PORTS.items()),
             claims=provinces_claim(*(p for ps in ARA_PORTS.values() for p in ps))),
    Ambition("wal_dracula", 21, "Dracula's Revenge", ("WAL",), "long",
             "tag = RMN balkan_region = { type = all country_or_non_sovereign_subject_holds = ROOT }",
             ("balkans",), milestones=(
                 ("Form Romania", "tag = RMN", 2, []),
                 ("20 Balkan Provinces", count_in("balkan", 20, ""), 2, [K("balkans")]))),
    Ambition("tun_carthage", 22, "Sons of Carthage", ("TUN",), "standard",
             areas("sicily", "western_sicily", "baleares", "barbary_coast", "upper_andalucia")
             + " " + core(2986, 127, 4735, 221, 1750, 1749, 224, 4548), ("italy", "iberia"), milestones=(
                 ("Barbary Coast", areas("barbary_coast"), 1, []),
                 ("Sicily", areas("sicily", "western_sicily") + " " + core(2986, 127, 4735), 2, [K("italy")]),
                 ("Baleares and Andalusia", areas("baleares", "upper_andalucia") + " "
                  + core(221, 1750, 1749, 224, 4548), 2, [K("iberia")])),
             claims=areas_claim("sicily", "western_sicily", "baleares", "upper_andalucia")),
    # Generic goals (index >= 50): any country, no region key.
    Ambition("gen_regional_power", 50, "Regional Power", (), "short",
             f"government_rank = 2 {dev_at_least(150)}"),
    Ambition("gen_great_power", 51, "Great Power", (), "standard",
             f"is_great_power = yes {dev_at_least(200)}", goal_guards=(("chancery", 1),)),
    Ambition("gen_city_of_cities", 52, "City of Cities", (), "standard",
             "any_owned_province = { is_core = ROOT development = 40 }", auto=False),
    Ambition("gen_every_continent", 53, "At Every Continent", (), "long", continents(6),
             goal_guards=(("colonial", 2),)),
    Ambition("gen_emperor", 54, "Imperial Crown", (), "standard", "is_emperor = yes", auto=False),
    Ambition("gen_domination_short", 55, "Domination", (), "short", dev_at_least(200),
             goal_guards=(("imperial_court", 2),), auto=False),
    Ambition("gen_domination_standard", 56, "Domination", (), "standard", dev_at_least(300),
             goal_guards=(("imperial_court", 2),), auto=False),
    Ambition("gen_domination_long", 57, "Domination", (), "long", dev_at_least(500),
             goal_guards=(("imperial_court", 2),), auto=False),
)
AMBITIONS = {a.key: a for a in AMBITIONS_LIST}
GENERIC_BY_LENGTH = {"short": "gen_regional_power", "standard": "gen_great_power", "long": "gen_every_continent"}


def resolve_ambition(choice: str, tag: str, length: str, goal: str, dlcs) -> str:
    """Ambition used by a goal. Explicit choices must fit the country, length and DLCs."""
    if goal == "great_power":
        return "gen_great_power"
    if goal == "domination":
        return f"gen_domination_{length}"

    def fits(a: Ambition) -> bool:
        return (length_index(a.length) <= length_index(length) and (not a.dlc or a.dlc in dlcs)
                and (not a.tags or tag in a.tags))

    if choice and choice != "auto":
        ambition = AMBITIONS[choice]
        if not fits(ambition):
            raise ValueError(f"National ambition {choice} does not fit country {tag}, "
                             f"campaign length {length} or the declared DLCs")
        return choice
    dedicated = [a for a in AMBITIONS_LIST if a.tags and a.auto and fits(a)]
    if dedicated:
        return max(dedicated, key=lambda a: (length_index(a.length), -a.index)).key
    return GENERIC_BY_LENGTH[length]


# ---------------------------------------------------------------------- missions

def mission_locations() -> tuple[LocationDef, ...]:
    seen: dict[int, LocationDef] = {}
    for rows in MISSIONS.values():
        for code, mission, depth, _required, _excluded in rows:
            seen.setdefault(code, LocationDef(code, f"Mission: {mission}", "mission",
                                              f"mission_completed = {mission}", 1 if depth < 2 else 2))
    return tuple(sorted(seen.values(), key=lambda loc: loc.id))


def missions_for(tag: str, dlcs, count: int) -> list[int]:
    rows = [r for r in MISSIONS.get(tag, ())
            if (r[3] is None or r[3] in dlcs) and (r[4] is None or r[4] not in dlcs)]
    return [r[0] for r in sorted(rows, key=lambda r: (r[2], r[0]))[:count]]


# ------------------------------------------------------------------------ tables

MILESTONES = tuple(m for a in AMBITIONS_LIST for m in a.milestone_defs())
NEW_LOCATIONS = CALENDAR + GENERIC + MILESTONES + mission_locations()
ALL_LOCATIONS = tuple(
    LocationDef(o.id, o.name, o.category, o.trigger) for o in LEGACY_OBJECTIVES) + NEW_LOCATIONS
LOCATION_DEFS = {loc.id: loc for loc in ALL_LOCATIONS}


def location_groups() -> dict[str, set[str]]:
    groups: dict[str, set[str]] = {}
    for loc in NEW_LOCATIONS:
        groups.setdefault(loc.category.capitalize(), set()).add(loc.name)
        if loc.long:
            groups.setdefault("Long checks", set()).add(loc.name)
    return groups


def item_groups() -> dict[str, set[str]]:
    return {"Region Keys": {k.item for k in REGION_KEYS.values()},
            "Fetters": {f.item for f in FETTERS.values()},
            "Traps": set(TRAP_ITEMS)}


def effective_guards(guards, manifest) -> tuple:
    """Guards that exist in this slot: disabled fetters/keys impose nothing."""
    kept = []
    for family, level in guards:
        if family == "seal" or (family.startswith("key:") and family[4:] in manifest.region_keys) \
                or family in manifest.fetters:
            kept.append((family, level))
    return tuple(kept)


def location_guards(location_id: int, manifest) -> tuple:
    return effective_guards(LOCATION_DEFS[location_id].guards, manifest)


def goal_guards(manifest) -> tuple:
    """Everything the ratify decision checks, besides the ambition itself."""
    guards = list(effective_guards(AMBITIONS[manifest.ambition].all_goal_guards(), manifest))
    if manifest.goal == "mixed":
        guards.append(("seal", manifest.charters_required))
    return tuple(guards)
