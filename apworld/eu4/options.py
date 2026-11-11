from dataclasses import dataclass

import random

from Options import (Choice, DeathLink, DefaultOnToggle, FreeText, OptionSet, PerGameCommonOptions,
                     Range, Toggle)

from .runtime.catalog import AMBITIONS_LIST, DEFAULT_FETTERS, FETTERS, KNOWN_DLCS
from .runtime.data import country_tag
from .runtime.countries import (COUNTRY_NAMES, OTHER_COUNTRY, country_choice_id,
                                country_choice_tag, country_label, named_country_tag)


class StartingCountry(Choice):
    """Choose a country by name for the 1444-11-11 start. France is selected by default.

    For a country outside this shortlist, choose Other country and set its tag
    under Other country (advanced). Existing YAMLs can still use any valid tag.
    Random selects a named country from this list, never Other country.
    Select the same country manually in EU4; map availability is not verified here.
    """
    display_name = "Starting Country"
    # The AP metaclass reads these attributes at class creation. Alphabetical
    # names in the menu do not change the stable IDs of existing options.
    for _tag, _name in sorted(COUNTRY_NAMES.items(), key=lambda pair: pair[1].casefold()):
        locals()["option_" + _tag.lower()] = country_choice_id(_tag)
    option_other_country = OTHER_COUNTRY
    default = 0

    def __init__(self, value: int):
        if type(value) is not int:
            raise ValueError("Starting country must be a country choice or tag")
        if value != OTHER_COUNTRY:
            country_choice_tag(value)
        super().__init__(value)

    @classmethod
    def from_text(cls, text: str):
        if text.strip().casefold() == "random":
            return cls(country_choice_id(random.choice(tuple(COUNTRY_NAMES))))
        if text.strip().casefold().replace(" ", "_") == "other_country":
            return cls(OTHER_COUNTRY)
        return cls(country_choice_id(named_country_tag(text)))

    @classmethod
    def from_any(cls, value):
        if type(value) is int:
            return cls(value)
        if not isinstance(value, str):
            raise ValueError("Starting country must be a country choice or tag")
        return cls.from_text(value)

    @property
    def current_key(self) -> str:
        return "other_country" if self.value == OTHER_COUNTRY else self.tag.lower()

    @classmethod
    def get_option_name(cls, value: int) -> str:
        if value == OTHER_COUNTRY:
            return "Other country (advanced tag)"
        return country_label(country_choice_tag(value))

    @property
    def tag(self) -> str:
        if self.value == OTHER_COUNTRY:
            raise ValueError("Set the tag in Other country (advanced)")
        return country_choice_tag(self.value)


class CustomStartingCountry(FreeText):
    """Used only when Starting Country is Other country. Enter a three-character
    EU4 tag such as K00. Ignored for all named countries and existing tag YAMLs.
    The country must be playable on 1444-11-11; generation checks syntax only.
    """
    display_name = "Other Country Tag (only for Other country)"
    default = "FRA"


class SaveMode(Choice):
    """How you will play EU4. Normal: received items arrive with the console command
    `run eu4ap_sync.txt` or after relaunching EU4. Ironman: no console; items arrive
    the day after you relaunch EU4 and load your campaign. Traps are disabled in
    Ironman unless Ironman Traps is on. The mod also reports the actual mode."""
    display_name = "Save Mode"
    option_normal = 0
    option_ironman = 1
    default = 0


class CampaignLength(Choice):
    """Pacing: short ~4-6 h (calendar to 1500), standard ~8-12 h (to 1575),
    long 20 h+ (to 1700). Sets checks, thresholds and the automatic ambition."""
    display_name = "Campaign Length"
    option_short = 0
    option_standard = 1
    option_long = 2
    default = 1


class Goal(Choice):
    """Victory condition, ratified with an in-game decision.
    royal_charters: the classic 0.4 mode (10-20 checks, Royal Charters only).
    national_ambition: achieve your country's ambition (achievement-inspired).
    great_power: be a great power with doubled development.
    domination: multiply your starting development (x2/x3/x5 by length).
    mixed: the ambition AND Seals of the Multiworld (recommended)."""
    display_name = "Goal"
    option_royal_charters = 0
    option_national_ambition = 1
    option_great_power = 2
    option_domination = 3
    option_mixed = 4
    default = 4


class NationalAmbition(Choice):
    """auto picks the dedicated ambition of your country that fits the campaign
    length and declared DLCs, else a generic one. An explicit choice must fit the
    country, length and DLCs, or generation stops with an explanation."""
    display_name = "National Ambition"
    option_auto = 0
    for _ambition in AMBITIONS_LIST:
        locals()["option_" + _ambition.key] = _ambition.index + 1
    default = 0


class OwnedDLCs(OptionSet):
    """DLCs ENABLED in your EU4 launcher. They select mission trees and DLC-only
    ambitions. Declaring a DLC you do not run makes some checks impossible."""
    display_name = "Owned DLCs"
    valid_keys = frozenset(KNOWN_DLCS)
    default = frozenset()


class Fetters(OptionSet):
    """Progressive handicaps applied at binding and lifted by items found in the
    multiworld: colonial, admiralty, chancery, guilds, academy, imperial_court, arsenal."""
    display_name = "Fetters"
    valid_keys = frozenset(FETTERS)
    default = frozenset(DEFAULT_FETTERS)


class RegionKeys(DefaultOnToggle):
    """Ambition regions need a key item: without it, newly owned provinces there
    are 'unratified' (heavy penalties) and their checks stay locked."""
    display_name = "Region Keys"


class MissionChecks(DefaultOnToggle):
    """Include the first missions of your country's tree (by declared DLCs)."""
    display_name = "Mission Checks"


class ExcludeLongChecks(DefaultOnToggle):
    """Never place progression items on long or difficult checks, including the
    last third of the calendar: other players would wait hours for them."""
    display_name = "Exclude Long Checks"


class TrapPercentage(Range):
    """Percentage of filler replaced by mild traps (never fatal, not before 1450)."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 30
    default = 0


class IronmanTraps(Toggle):
    """Allow traps in Ironman, where they arrive grouped after a relaunch."""
    display_name = "Ironman Traps"


class GoalDifficulty(Choice):
    """Number of Royal Charters (royal_charters goal) or Seals of the Multiworld
    (mixed goal) required: easy=2, normal=3, hard=4."""
    display_name = "Goal Difficulty"
    option_easy = 2
    option_normal = 3
    option_hard = 4
    default = 3


class LocationCount(Range):
    """royal_charters goal only: number of objectives, at least half calendar milestones."""
    display_name = "Location Count"
    range_start = 10
    range_end = 20
    default = 16


class EconomicChecks(DefaultOnToggle):
    """royal_charters goal only: include treasury milestones. Loans can satisfy these checks."""
    display_name = "Economic Checks"


class TechnologyChecks(DefaultOnToggle):
    """royal_charters goal only: include technology levels 4 and 5."""
    display_name = "Technology Checks"


class RewardStrength(Choice):
    """Scale resources; charters remain unchanged. Names describe baseline amounts."""
    display_name = "Reward Strength"
    option_normal = 1
    option_double = 2
    default = 1


@dataclass
class EU4Options(PerGameCommonOptions):
    starting_country: StartingCountry
    custom_starting_country: CustomStartingCountry
    save_mode: SaveMode
    campaign_length: CampaignLength
    goal: Goal
    national_ambition: NationalAmbition
    goal_difficulty: GoalDifficulty
    location_count: LocationCount
    enable_economic_checks: EconomicChecks
    enable_technology_checks: TechnologyChecks
    reward_strength: RewardStrength
    owned_dlcs: OwnedDLCs
    fetters: Fetters
    region_keys: RegionKeys
    mission_checks: MissionChecks
    exclude_long_checks: ExcludeLongChecks
    trap_percentage: TrapPercentage
    ironman_traps: IronmanTraps
    death_link: DeathLink

    @property
    def country_tag(self) -> str:
        if self.starting_country.value == OTHER_COUNTRY:
            return country_tag(self.custom_starting_country.value)
        return self.starting_country.tag
