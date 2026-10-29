from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, PerGameCommonOptions, Range


class StartingCountry(Choice):
    """Select this country manually in EU4 before binding the campaign."""
    display_name = "Starting Country"
    option_fra = 0
    option_cas = 1
    option_eng = 2
    option_por = 3
    option_hab = 4
    option_bra = 5
    option_pol = 6
    option_tur = 7
    default = 0


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
    goal_difficulty: GoalDifficulty
    location_count: LocationCount
    enable_economic_checks: EconomicChecks
    enable_technology_checks: TechnologyChecks
    reward_strength: RewardStrength
