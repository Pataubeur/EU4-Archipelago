from dataclasses import dataclass

import random

from Options import Choice, DefaultOnToggle, FreeText, PerGameCommonOptions, Range

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


class GoalDifficulty(Choice):
    """Number of Royal Charters required: easy=2, normal=3, hard=4."""
    display_name = "Goal Difficulty"
    option_easy = 2
    option_normal = 3
    option_hard = 4
    default = 3


class LocationCount(Range):
    """Number of objectives, including at least half calendar milestones."""
    display_name = "Location Count"
    range_start = 10
    range_end = 20
    default = 16


class EconomicChecks(DefaultOnToggle):
    """Include treasury milestones. Loans can satisfy these checks."""
    display_name = "Economic Checks"


class TechnologyChecks(DefaultOnToggle):
    """Include technology levels 4 and 5, without DLC or geography requirements."""
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
    goal_difficulty: GoalDifficulty
    location_count: LocationCount
    enable_economic_checks: EconomicChecks
    enable_technology_checks: TechnologyChecks
    reward_strength: RewardStrength

    @property
    def country_tag(self) -> str:
        if self.starting_country.value == OTHER_COUNTRY:
            return country_tag(self.custom_starting_country.value)
        return self.starting_country.tag
