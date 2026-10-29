"""Single catalog shared by the world, generated mod and external client."""
from __future__ import annotations

from dataclasses import dataclass

GAME = "Europa Universalis IV"
BASE_ID = 4_837_000  # Provisional community IDs, not an upstream allocation.
COUNTRIES = ("FRA", "CAS", "ENG", "POR", "HAB", "BRA", "POL", "TUR")


@dataclass(frozen=True)
class Objective:
    id: int
    name: str
    category: str
    trigger: str


# Stable IDs: never assign IDs from the position in a filtered pool.
OBJECTIVES = tuple(
    Objective(BASE_ID + n, f"Reach {1444 + n}", "calendar", f"is_year = {1444 + n}")
    for n in range(1, 21)
) + tuple(
    Objective(BASE_ID + 100 + i, f"Treasury: {amount} ducats", "economic", f"treasury = {amount}")
    for i, amount in enumerate((100, 250, 500, 1000))
) + tuple(
    Objective(BASE_ID + 200 + i, f"{kind.upper()} technology {level}", "technology", f"{kind}_tech = {level}")
    for i, (kind, level) in enumerate((
        ("adm", 4), ("dip", 4), ("mil", 4), ("adm", 5), ("dip", 5), ("mil", 5)))
)
BY_ID = {o.id: o for o in OBJECTIVES}

# Item name -> (stable id, native effect, baseline amount, classification).
ITEMS = {
    "Royal Charter": (BASE_ID + 1000, "", 0, "progression"),
    "100 Ducats": (BASE_ID + 1001, "add_treasury", 100, "filler"),
    "50 Administrative Power": (BASE_ID + 1002, "add_adm_power", 50, "useful"),
    "50 Diplomatic Power": (BASE_ID + 1003, "add_dip_power", 50, "useful"),
    "50 Military Power": (BASE_ID + 1004, "add_mil_power", 50, "useful"),
    "10 Prestige": (BASE_ID + 1005, "add_prestige", 10, "filler"),
}
ITEM_BY_ID = {v[0]: (k, *v[1:]) for k, v in ITEMS.items()}


def select_objectives(count: int, economic: bool, technology: bool) -> list[Objective]:
    if not 10 <= count <= 20:
        raise ValueError("location_count must be between 10 and 20")
    # Half the pool is always annual milestones; all-option-off remains viable.
    special = [o for o in OBJECTIVES if
               (economic and o.category == "economic") or
               (technology and o.category == "technology")]
    special = special[:count // 2]
    calendar = [o for o in OBJECTIVES if o.category == "calendar"]
    return calendar[:count - len(special)] + special
