import copy
import itertools
import time
from functools import partial
from multiprocessing import Manager, Pool, Queue
from pathlib import Path
from typing import Dict, Iterator, List

from loguru import logger

from leagueprobs.league import League, get_league_from_matches
from leagueprobs.match import Match, get_matches_from_json
from leagueprobs.templates import EXPLANATION_TEMPLATE, OUTPUT_TEMPLATE
from leagueprobs.timing import timeit


class PossibilityHandler:
    """Class to figure the different possible scenarios of a given league."""

    def __init__(self, league: League, playoff_teams: int = 6) -> None:
        """
        Instantiate your PossibilityHandler class.

        Args:
            league (League): a League object for the league (name, season, year) to analyze.
            playoff_teams (int): number of teams in playoffs (number of playoff spots).
        """
        self.matches: List[Match] = get_matches_from_json(league.matches_file)
        self.finished_matches: List[Match] = [match for match in self.matches if match.result]
        self.upcomming_matches: List[Match] = [match for match in self.matches if not match.result]
        self.cumulated_outcomes: Dict[str, Dict[int, int]] = {}
        self.playoff_teams = playoff_teams
        self.league = league
        self.explanation = EXPLANATION_TEMPLATE.format(league_name=self.league.name)

    @logger.catch
    def run(self):
        logger.info(
            f"Figuring out possible scenarios for {self.league.name} {self.league.season} "
            f"{self.league.year}"
        )

        with timeit(lambda spanned: logger.info(f"Ran possible scenarios {spanned:.4f} seconds")):
            start_time = time.time()
            self.multiprocess_possibilities()
            finish_time = time.time()
            time_delta = finish_time - start_time

            self.create_output(time_delta)

    @logger.catch
    def multiprocess_possibilities(self):
        """Run every possible scenario."""
        possibilities: Iterator = itertools.product([0, 1], repeat=len(self.upcomming_matches))
        logger.debug(f"Multi-Processing {int(2 ** len(self.upcomming_matches))} possibilities now")

        with Manager() as manager:
            queue = manager.Queue()
            pool = Pool()
            func = partial(self.get_possibilities, queue)
            pool.map_async(func, possibilities)
            self._cumulate_results(queue)  # cumulate results while async multiprocessing them
            pool.close()
            pool.join()

    def get_possibilities(self, q: Queue, possibility: Iterator) -> None:
        """
        Generate all possible outcomes for upcoming matches, generate a League for each one,
        try to solve tiebreakers and add the final outcomes to the 'cumulated_outcomes' attribute.

        Args:
            q (Queue): your multiprocessing queue.
            possibility (Iterator): an iterator of possible outcomes for upcoming matches.

        Returns:
            Nothing.
        """
        upcoming_matches_copy: List[Match] = copy.deepcopy(self.upcomming_matches)
        self._set_upcoming_matches_outcomes(upcoming_matches_copy, possibility)

        logger.trace("Generating league state for these possible outcomes")
        generated_league: League = get_league_from_matches(
            name=self.league.name,
            year=self.league.year,
            season=self.league.season,
            matches=self.finished_matches + upcoming_matches_copy,
        )
        generated_league.make_tiebreaker()

        self._cumulate_outcome(q, generated_league.standings)

        # Good position to output possibilities for specific teams' outcomes
        # investigate_specific_scenario(
        #     league=generated_league,
        #     observed_team="YOURCHOICE",
        #     observed_ranking=10,
        #     upcoming_matches=upcoming_matches_copy,
        # )

    @staticmethod
    def _set_upcoming_matches_outcomes(upcomming_matches: List[Match], possibility: list) -> None:
        """
        Set outcomes of match objects based on the generated possibilities.

        Args:
            upcomming_matches (List[Match]): list of upcoming matches to set.
            possibility (list): generated possibile outcomes.

        Returns:
            Nothing, acts onto the upcoming matches in place.
        """
        for index, match in enumerate(upcomming_matches):
            logger.trace(
                f"Setting generated outcome for {match.week} {match.teams[0]}" f"-{match.teams[1]}"
            )
            upcomming_matches[index].result = (1, 0) if possibility[index] == 1 else (0, 1)

    @staticmethod
    def _cumulate_outcome(queue: Queue, standings: Dict[int, List[str]]) -> None:
        """
        For each team in the standings, find its ranking and add this to a cumulated ranking
        dictionary to be put into the multiprocessing queue.

        Args:
            queue (Queue): your multiprocessing queue.
            standings (Dict[int, List[str]]): a League object's standings, after tiebreakers.

        Returns:
            Nothing, puts back into the queue.
        """
        logger.trace("Cumulating outcomes from a scenario")

        cumulated_results: Dict[str, Dict[int, int]] = {}
        for standing, teams in standings.items():
            for team in teams:
                if not cumulated_results.get(team):
                    cumulated_results[team] = {}
                if not cumulated_results[team].get(standing):
                    cumulated_results[team][standing] = 1
                else:
                    cumulated_results[team][standing] += 1

        logger.trace("Putting oucome in queue")
        queue.put(cumulated_results)

    def _cumulate_results(self, queue: Queue) -> None:
        """
        Get the cumulated outcomes put into the queue and cumulate them for final results,
        to be put into the 'cumulated_outcomes' attribute.

        Args:
            queue (Queue): your multiprocessing queue.

        Returns:
            Nothing, acts on the PossibilityHandler's 'cumulated_outcomes' attribute.
        """
        logger.debug("Cumulating final results from queue")
        time.sleep(10)  # give producer some time to start

        while True:  # as long as the queue hasn't processes every job
            if queue.empty():
                print("EMPTY QUEUE")
                break

            logger.trace("Getting an scenario's outcome from the queue")
            # Result's keys are team names. Each team has for value a Dict[int, int] for its
            # different ranking outcomes. It has rankings as keys and as values the amount of
            # times this team gets each ranking.
            result: Dict[str, Dict[int, int]] = queue.get()

            for team, standings in result.items():
                if not self.cumulated_outcomes.get(team):
                    self.cumulated_outcomes[team]: Dict[int, int] = {}
                for ranking, amount in standings.items():
                    if not self.cumulated_outcomes[team].get(ranking):
                        self.cumulated_outcomes[team][ranking] = 0
                    self.cumulated_outcomes[team][ranking] += 1  # TODO: SHOULD BE AMOUNT???

    def create_output(self, process_time: float) -> None:
        """
        Compute and format odds for teams based on the 'cumulated_outcomes' attributes

        Args:
            process_time (float): the amount of time used to process all possibilities.

        Returns:
            Nothing, outputs a formatted summary to 'self.league.output_file'.
        """
        logger.info("Outputing standings probabilities")
        relative_rows: str = ""
        absolute_rows: str = ""

        for team, team_standings in sorted(
            self.cumulated_outcomes.items(), key=self.sort_result, reverse=True
        ):
            logger.trace(f"Getting odds for team '{team}'")
            team_relative_row: str = ""
            team_absolute_row: str = ""
            total = sum(team_standings.values())
            playoff_probability = 0
            for i in range(1, len(self.league.teams.keys())):
                if not team_standings.get(i):
                    team_standings[i] = 0
                if i <= self.playoff_teams:
                    playoff_probability += team_standings[i]
                team_relative_row = (
                    f"{team_relative_row} | {round(team_standings[i] / total * 100, 2)}"
                )
                team_absolute_row = f"{team_absolute_row} | {team_standings[i]:,}"
            team_relative_row = f"| {team} {team_relative_row} | {str(round(playoff_probability / total * 100, 2))} |"
            relative_rows = "".join([relative_rows, team_relative_row, "\n"])
            team_absolute_row = f"| {team} {team_absolute_row} | {total:,} |"
            absolute_rows = "".join([absolute_rows, team_absolute_row, "\n"])

        logger.debug("Formatting output")
        output = OUTPUT_TEMPLATE.format(
            explanation=self.explanation,
            relative_rows=relative_rows,
            absolute_rows=absolute_rows,
            process_time=round(process_time, 0),
        )

        with self.league.output_file.open("w") as f:
            f.write(output)
        logger.success(f"Output probabilities at '{self.league.output_file.absolute()}'")

    @staticmethod
    def sort_result(item):
        for i in range(1, 11):
            if not item[1].get(i):
                item[1][i] = 0

        return [item[1][i] for i in range(1, 11)]


@logger.catch
def investigate_specific_scenario(
    league: League, observed_team: str, observed_ranking: int, upcoming_matches: List[Match]
) -> None:
    """
    Given a generated league, looks if a specific team is in a specific position. If this is
    the case, then output the combination of scenarios that led to this result as a json file.

    Args:
        league (League): a League object of the generated league state.
        observed_team (str): name of the team to look for in a certain ranking.
        observed_ranking (int): ranking to see if the team is in.
        upcoming_matches (List[Match]): upcoming matches with generated outcomes.

    Returns:
        Nothing, outputs scenarios in a json file.
    """
    logger.trace(
        f"Investigating if {observed_team} finishes rank {observed_ranking} in this " f"scenario"
    )
    if (
        league.standings.get(observed_ranking)
        and observed_team in league.standings[observed_ranking]
    ):
        logger.info(
            f"Found a scenario where {observed_team} finishes rank {observed_ranking}! "
            f"Saving the scenario as json"
        )
        with Path(f"{observed_team}_rank_{observed_ranking}.json").open("a") as f:
            dict_matches = [match.__dict__ for match in upcoming_matches]
            json.dump(dict_matches, f)
