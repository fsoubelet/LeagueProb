import copy
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
            teams (List[Team]): list of teams competing in the league, as Team objects.
        """
        self.name = name.upper()
        self.season = season.lower().capitalize()
        self.teams: Dict[str, Team] = {team.name: team for team in teams}
        self.year = year
        self.gamepedia_url = (
            f"https://lol.gamepedia.com/{self.name}/{self.year}_Season/" f"{self.season}_Season"
        )
        self.matches_file = Path(f"{self.name.lower()}_matches.json")
        self.output_file = Path(f"{self.name.lower()}_output.md")
        self.standings = self.make_standings()

    def __str__(self):
        return f"{self.name} {self.season} {self.year}"

    def __repr__(self):
        return (
            f"League[{self.name} {self.season} {self.year}] | "
            f"Teams{list(team.name for team in self.teams.values())}"
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
        table = {team.name: team.record for team in self.teams.values()}
        # Sort in reversing order by wins (most to least) and minus losses (so least to top losses)
        return dict(sorted(table.items(), key=lambda item: (item[1][0], -item[1][1]), reverse=True))

    def make_standings(self) -> Dict[int, List[str]]:
        """
        Returns a dictionary of rankings and team names. The dictionary is equivalent to self.table
        but the keys are rankings (integers) and the values are list of team names for each
        ranking (since several teams can have the same record, they can have the same ranking).

        Returns:
            The standings dictionary.
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
        self._remove_team_from_standings(team_to_reset=team_name)

        logger.debug(f"Inserting team '{team_name}' into {self.name} standings at rank {standing}")
        if standing not in self.standings.keys():
            logger.trace(f"Standing {standing} wasn't present and will be created")
            self.standings[standing]: List[str] = []
        self.standings[standing].append(team_name)

        logger.trace("Re-sorting standings by rankings")
        self.standings = dict(sorted(self.standings.items()))

    def _remove_team_from_standings(self, team_to_reset: str) -> None:
        """Removes a team from the self.standings attribute.

        Args:
            team_to_reset (str): name of the team to remove.
        """
        for rank, teams in self.standings.items():
            if team_to_reset in teams:
                logger.debug(f"Removing {team_to_reset} from rank {rank} in the standings")
                teams.remove(team_to_reset)
                if not self.standings[rank]:
                    logger.trace(f"Rank {rank} now empty, removing it from the standings")
                    del self.standings[rank]
                return
        logger.debug(f"Team {team_to_reset} was not in the standings")

    def make_tiebreaker(self) -> None:
        """
        Tries to solve ties, first from head-to-head wins and then based on wins in the second
        half of the split. In case ties still happen aftwerwards, then actual tiebreaker matches
        would have to be played.
        """
        self._solve_ties_through_head_to_heads()
        self._solve_ties_through_wins_in_second_half()

    def _solve_ties_through_head_to_heads(self) -> None:
        """
        Goes through the standings and tries to solves ties by head-to-head wins. The
        head-to-head wins are calculated for teams tied for the same position, and they are
        ranked based on those head-to-head wins. In case ties still happen, the amount of wins
        in the second half of the split should be used to solve the ties.
        """
        logger.debug(f"Trying to solve head-to-heads for {self.name} {self.season} {self.year}")

        logger.trace("Copying standings dictionary")
        standings_copy = copy.deepcopy(self.standings)

        for rank, teams_at_this_rank in standings_copy.items():
            teams_h2h_wins: Dict[str, int] = {}
            if len(teams_at_this_rank) > 1:
                logger.trace(f"Several teams tied at rank {rank}, looking at head-to-head wins")
                for _, team_name in enumerate(teams_at_this_rank):
                    logger.trace(f"Getting head-to-head wins for team {team_name}")
                    other_teams: List[Team] = [
                        self.teams[other_team]
                        for other_team in teams_at_this_rank
                        if other_team != team_name
                    ]  # getting Team objects of other teams at this rank
                    teams_h2h_wins[team_name] = self.teams[team_name].head_to_head_wins(other_teams)

                logger.trace("Organizing head-to-head results by wins")
                # 'teams_by_records' also works with wins instead of records
                teams_h2h_wins: Dict[int, List[str]] = teams_by_records(teams_h2h_wins)

                logger.trace("Determining placings from head-to-heads")
                head_to_head_placing: Dict[int, List[str]] = {}
                place_teams_in_rankings(
                    teams_to_place_by_wins=teams_h2h_wins,
                    ranking_dict=head_to_head_placing,
                    next_rank=0,
                )

                logger.trace("Inserting teams back in standings")
                for placing, teams_at_this_placing in head_to_head_placing.items():
                    for team_name in teams_at_this_placing:
                        if placing == 0:
                            continue
                        self._remove_team_from_standings(team_name)
                        self._set_standing_for_team(team_name, rank + placing)

    def _solve_ties_through_wins_in_second_half(self) -> None:
        """
        Goes through the standings and tries to solves ties based on second half of split wins.
        Those wins are calculated for teams tied for the same position, and they are ranked based
        on those wins. In case ties still happen, an actual tiebreaker match should be played.
        """
        logger.debug(f"Trying to solve last ties for {self.name} {self.season} {self.year}")

        logger.trace("Copying standings dictionary")
        standings_copy = copy.deepcopy(self.standings)

        for rank, teams_at_this_rank in standings_copy.items():
            tied_teams: Dict[str, int] = {}
            if len(teams_at_this_rank) > 1:
                logger.trace(f"Several teams tied at rank {rank}, looking at head-to-head wins")
                for _, team_name in enumerate(teams_at_this_rank):
                    logger.trace(f"Getting second half of split wins for team {team_name}")
                    other_teams: List[Team] = [
                        self.teams[other_team]
                        for other_team in teams_at_this_rank
                        if other_team != team_name
                    ]  # getting Team objects of other teams at this rank
                    tied_teams[team_name] = self.teams[team_name].wins_in_second_half()

                logger.trace("Ranking tied teams by wins in second half")
                # 'teams_by_records' also works with wins instead of records
                teams_second_half_wins: Dict[int, List[str]] = teams_by_records(tied_teams)

                logger.trace("Determining placings from second half of split wins")
                wins_in_second_half_placing: Dict[int, List[str]] = {}
                place_teams_in_rankings(
                    teams_to_place_by_wins=teams_second_half_wins,
                    ranking_dict=wins_in_second_half_placing,
                    next_rank=0,
                )

                logger.trace("Inserting teams back in standings")
                for placing, teams_at_this_placing in wins_in_second_half_placing.items():
                    for team_name in teams_at_this_placing:
                        if placing == 0:
                            continue
                        self._remove_team_from_standings(team_name)
                        self._set_standing_for_team(team_name, rank + placing)


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


def place_teams_in_rankings(
    teams_to_place_by_wins: Dict[int, List[str]],
    ranking_dict: Dict[int, List[str]],
    next_rank: int = 1,
) -> None:
    """
    Inserts teams in ranking based on their amount of wins.

    Args:
        teams_to_place_by_wins (Dict[int, List[str]]): dict of teams organized by wins.
        ranking_dict (Dict[int, List[str]]): the rankings in which to place teams.
        next_rank (int): the rank at which to start inserting teams.
    """
    logger.trace("Inserting teams in rankings")
    next_rank = next_rank
    for wins, teams_with_these_wins in sorted(teams_to_place_by_wins.items(), reverse=True):
        rank = next_rank
        for team in teams_with_these_wins:
            logger.trace(f"Inserting {team} at rank {rank}")
            if not ranking_dict.get(rank):
                ranking_dict[rank]: List[str] = []
                ranking_dict[rank].append(team)
                next_rank += 1
