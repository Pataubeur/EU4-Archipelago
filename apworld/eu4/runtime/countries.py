"""Named country shortcuts for the 1444 selector, not an exhaustive game catalogue."""
from .data import COUNTRY_PRESETS, country_tag


# Display metadata only: no game scripts, history files or localization assets.
# Country availability and native gameplay still need in-game acceptance.
COUNTRY_NAMES = {
    "ARA": "Aragon", "HAB": "Austria", "AYU": "Ayutthaya", "AZT": "Aztec",
    "BAH": "Bahmanis", "BNG": "Bengal", "BOH": "Bohemia", "BRA": "Brandenburg",
    "BRI": "Brittany", "BUR": "Burgundy", "BYZ": "Byzantium", "CAS": "Castile",
    "CUS": "Cusco", "DAI": "Dai Viet", "DLH": "Delhi", "DAN": "Denmark",
    "ENG": "England", "ETH": "Ethiopia", "FRA": "France", "GEN": "Genoa",
    "GUJ": "Gujarat", "HUN": "Hungary", "JNP": "Jaunpur", "KHM": "Khmer",
    "KOR": "Korea", "LIT": "Lithuania", "LIV": "Livonian Order", "MAJ": "Majapahit",
    "MLC": "Malacca", "MAL": "Mali", "MLW": "Malwa", "MAM": "Mamluks",
    "MLO": "Milan", "MNG": "Ming", "KHA": "Mongolia", "MOR": "Morocco",
    "MOS": "Muscovy", "NAP": "Naples", "NOR": "Norway", "NOV": "Novgorod",
    "OIR": "Oirat", "ORI": "Orissa", "TUR": "Ottomans", "PAP": "Papal State",
    "POL": "Poland", "POR": "Portugal", "RYU": "Ryukyu", "SCO": "Scotland",
    "SER": "Serbia", "SON": "Songhai", "SWE": "Sweden", "SWI": "Switzerland",
    "TEU": "Teutonic Order", "TIM": "Timurids", "TUN": "Tunis", "VEN": "Venice",
    "VIJ": "Vijayanagar", "WAL": "Wallachia",
}

OTHER_COUNTRY = 8
TAG_OFFSET = 100


def country_choice_id(tag: str) -> int:
    """Keep legacy 0-7 values; all other tags have stable, order-independent IDs."""
    tag = country_tag(tag)
    if tag in COUNTRY_PRESETS:
        return COUNTRY_PRESETS.index(tag)
    return TAG_OFFSET + int(tag, 36)


def country_choice_tag(value: int) -> str:
    if type(value) is not int:
        raise ValueError("Starting country must be a country choice or tag")
    if 0 <= value < len(COUNTRY_PRESETS):
        return COUNTRY_PRESETS[value]
    number = value - TAG_OFFSET
    if not 36 ** 2 <= number < 36 ** 3:
        raise ValueError("Unknown starting-country choice")
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    tag = "".join(alphabet[(number // (36 ** power)) % 36] for power in (2, 1, 0))
    return country_tag(tag)


def named_country_tag(value: str) -> str:
    """Accept names/display labels as well as tags in player YAMLs."""
    key = value.strip().casefold().replace("_", " ")
    for tag, name in COUNTRY_NAMES.items():
        if key in (name.casefold(), f"{name} ({tag})".casefold()):
            return tag
    return country_tag(value)


def country_label(tag: str) -> str:
    name = COUNTRY_NAMES.get(tag)
    return f"{name} ({tag})" if name else tag
