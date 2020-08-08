from pathlib import Path
from typing import Dict, List

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
    def table(self) -> Dict[str, int]:
        """
        Dictionary of team names and their current amount of wins. The dictionary is ordered,
        from the team with the most wins (first) to the one with the least amount of wins (last)

        Returns:
            The self.table dictionary.
        """
        logger.debug(f"Returning ordered table for {self.name} {self.year} {self.season}")
        table = {team.name: team.wins for team in self.teams}
        return {
            name: wins
            for name, wins in sorted(table.items(), key=lambda item: item[1], reverse=True)
        }

    def make_standings(self) -> Dict[int, str]:
        """
        Returns a dictionary of ranking and team names. The dictionary is equivalent to self.table
        but the keys are rankings (integers) and the values are team names.

        Returns:
            The dictionary.
        """
        logger.debug(f"Getting current {self.name} {self.year} {self.season} standings")
        standings = {
            element[0]: element[1]
            for element in list(zip(range(1, len(self.table) + 1), self.table.keys()))
        }
        # TODO: tiebreaker
        # self.tiebreaker(standings)
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
    logger.debug("Constructing League object from gatheres Teams")
    return League(name, year, season, teams=teams_list)


def _get_dict_key(dictionary: dict, value):
    for key, val in dictionary.items():
        if val == value:
            return key
