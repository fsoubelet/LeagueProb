from pathlib import Path
from typing import Dict, List, Tuple

from loguru import logger

from leagueprobs.match import Match
from leagueprobs.teams import Team


class League:
    """Class to handle the specifics of a given league."""

    def __init__(self, name: str, year: int, season: str, teams: List[Team]) -> None:
        """Instantiate your league class.

        Args:
            name (str): the league's name (LEC / LCS / LCK / LPL)
            year (int): the year being played
            season (str): the season in the year (either spring or summer)
            teams (List[Team]): list of teams competing in the league.
        """
        self.name = name.upper()
        self.season = season.lower().capitalize()
        self.teams = teams
        self.year = year
        self.gamepedia_url = (
            f"https://lol.gamepedia.com/{self.name}/{self.year}_Season/" f"{self.season}_Season"
        )
        self.matches_file = Path(f"{self.name}_matches.json")
        self.output_file = Path(f"{self.name}_output.md")
        self.standings = self.make_standings()

    def __str__(self):
        return f"{self.name} {self.season} {self.year}"

    def __repr__(self):
        return (
            f"League[{self.name} {self.season} {self.year}] | "
            f"Teams{list(team.name for team in self.teams)}"
        )

    @property
    def table(self) -> Dict[str, Tuple[int, int]]:
        """
        Dictionary of team names and their current record. The dictionary is ordered, from the team
        with the most wins (first) to the one with the least amount of wins (last). In case of
        tie, the sorting is alphabetically on the team names but that's fine since table is not
        the standings.

        Returns:
            The self.table dictionary.
        """
        logger.trace(f"Getting ordered table for {self.name} {self.year} {self.season}")
        table = {team.name: team.record for team in self.teams}
        return {
            name: record
            for name, record in sorted(table.items(), key=lambda item: item[1][0], reverse=True)
        }

    def make_standings(self) -> Dict[int, List[str]]:
        """
        Returns a dictionary of rankings and team names. The dictionary is equivalent to self.table
        but the keys are rankings (integers) and the values are list of team names for each
        ranking (since several teams can have the same record, they can have the same ranking).

        Returns:
            The dictionary.
        """
        logger.debug(f"Getting current {self.name} {self.year} {self.season} standings")
        teams_by_wins = teams_by_records(self.table)

        standings: Dict[int, List[str]] = {}
        next_rank: int = 1
        for record, teams in teams_by_wins.items():
            insert_rank: int = next_rank
            logger.trace(f"Rank {insert_rank} corresponds to team record {record}")
            if not standings.get(insert_rank):
                logger.trace(f"Creating entry for rank {insert_rank}")
                standings[insert_rank] = []
            for team_name in teams:
                logger.trace(f"Team {team_name} inserted at rank {insert_rank}")
                standings[insert_rank].append(team_name)
                next_rank += 1
        return standings

    def _set_standing_for_team(self, team_name: str, standing: int) -> None:
        """
        Insert a team in a specific rank in the self.standings dictionary.

        Args:
            team_name (str): the team's name.
            standing (int): the rank at which to insert this team.
        """
        if team_name in self.standings.values():
            logger.debug(f"'{team_name}' already present in {self.name}.standings, removing")
            del self.standings[_get_dict_key(dictionary=self.standings, value=team_name)]
        logger.debug(
            f"Inserting team {team_name} into {self.name}.standings at standing" f" {standing}"
        )
        self.standings[standing] = team_name

    @staticmethod
    def tiebreaker(self) -> None:
        raise NotImplementedError


def get_league_from_matches(name: str, year: int, season: str, matches: List[Match]) -> League:
    """
    Returns a League when provided with the full list of its matches.

    Args:
        name (str): the league's name (LEC / LCS / LCK / LPL).
        year (int): the year being played.
        season (str): the season in the year (either spring or summer).
        matches: list of Match object for the league's season, as scraped from gamepedia.

    Returns:
        A League object.
    """
    logger.info(f"Building {name} {season.lower().capitalize()} {year} League from matches")
    league_teams: Dict[str, Team] = {}
    for match in matches:
        logger.trace(f"Parsing match {match}")
        for team in match.teams:  # Here team is the team's name as str
            logger.trace(f"{team} is a contender in match {match}")
            if not league_teams.get(team):
                logger.trace(f"Building team {team} with initial match {match}")
                league_teams[team] = Team(team, [match])
            else:
                logger.trace(f"Team {team} already built, adding {match} to its matches")
                league_teams[team].matches.append(match)

    teams_list: List[Team] = list(league_teams.values())
    logger.debug("Constructing League object from gathered Teams")
    return League(name, year, season, teams=teams_list)


def teams_by_records(league_table: Dict[str, Tuple[int, int]]) -> Dict[Tuple[int, int], List[str]]:
    """
    Return the league's table organized by records. The returned dictionary has team records as
    keys, and as values a list of the teams that have this record. The keys (records) are
    ordered, from the one with the most wins to the one with the least wins.

    Args:
        league_table (Dict[str, Tuple[int, int]]): a league's table.

    Returns:
        A dictionary.
    """
    teams_by_record: Dict[Tuple[int, int], List[str]] = {}

    logger.debug("Getting league table organized by wins")
    for team_name, team_record in league_table.items():
        if not teams_by_record.get(team_record):
            teams_by_record[team_record]: List[str] = []
        teams_by_record[team_record].append(team_name)
    return teams_by_record


def _get_dict_key(dictionary: dict, value):
    for key, val in dictionary.items():
        if val == value:
            return key
