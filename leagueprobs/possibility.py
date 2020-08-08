import copy
import itertools
import time
from functools import partial
from multiprocessing import Manager, Pool, Queue
from pathlib import Path
from typing import Dict, List

from loguru import logger

from leagueprobs.leagues import League
from leagueprobs.match import Match, get_matches_from_json
from leagueprobs.teams import Team


class PossibilityHandler:
    template_file = Path("output_template.txt")

    def __init__(self, league: League):
        self.matches: List[Match] = get_matches_from_json(league.matches_file)
        self.finished_matches: List[Match] = [match for match in self.matches if match.result]
        self.upcomming_matches: List[Match] = [match for match in self.matches if not match.result]
        self.cumulated_outcomes = {}
        self.league = league

    def run(self):
        logger.info("Starting possibilities run")
        start_time = time.time()

        self.multiprocess_possibilities()

        finish_time = time.time()
        time_delta = finish_time - start_time

        self.create_output(time_delta)

    def multiprocess_possibilities(self):
        """Get results"""
        possibilities = itertools.product([0, 1], repeat=len(self.upcomming_matches))

        logger.debug(f"Multi-Processing {len(list(possibilities))} possibilities now")
        with Manager() as manager:
            q = manager.Queue()
            p = Pool()
            func = partial(self.get_possibilities, q)
            p.map_async(func, possibilities)
            self.cumulate_results(q)  # cumulate results while async multiprocessing them
            p.close()
            p.join()

    def get_possibilities(self, q: Queue, possibility: List):
        logger.debug("Getting possibilities")
        prediction = copy.deepcopy(self.upcomming_matches)
        self.get_outcome(prediction, possibility)
        league = self.league.from_matches(self.finished_matches + prediction)
        league.create_standings()
        self.cumulate_outcome(q, league.standings)

        # good position to output possibilities for specific teams e.g.:
        # if lec.standings.get(10):
        #     if 'G2' in lec.standings[10]:
        #         dict_matches = [match.__dict__ for match in prediction]
        #         with open('src/g8_10.json', 'a') as f:
        #             json.dump(dict_matches, f)

    @staticmethod
    def get_outcome(upcomming_matches: List[Match], possibility: List):
        logger.debug(f"Getting outcome for {len(list(upcomming_matches))} upcoming matches")
        for i, match in enumerate(upcomming_matches):
            logger.debug(f"Getting outcome for {match.teams[0]}-{match.teams[1]}")
            upcomming_matches[i].result = [1, 0] if possibility[i] == 1 else [0, 1]

    @staticmethod
    def cumulate_outcome(q: Queue, standings: Dict):
        logger.debug("Cumulating outcomes")
        cumulated_results = {}
        for standing, teams in standings.items():
            for team in teams:
                if not cumulated_results.get(team):
                    cumulated_results[team] = {}
                if not cumulated_results[team].get(standing):
                    cumulated_results[team][standing] = 1
                else:
                    cumulated_results[team][standing] += 1
        q.put(cumulated_results)

    def cumulate_results(self, q: Queue):
        logger.debug("Cumulating results")
        # give producer some time to start
        time.sleep(3)
        while True:
            if q.empty():
                break
            result = q.get()
            for team, standings in result.items():
                if not self.cumulated_outcomes.get(team):
                    self.cumulated_outcomes[team] = {}
                for standing, amount in standings.items():
                    if not self.cumulated_outcomes[team].get(standing):
                        self.cumulated_outcomes[team][standing] = 0
                    self.cumulated_outcomes[team][standing] += 1

    def create_output(self, process_time: float):
        logger.info("Creating output")
        relative_rows = ""
        absolute_rows = ""
        for team, standings in sorted(
            self.cumulated_outcomes.items(), key=self.sort_result, reverse=True
        ):
            relative_row = ""
            absolute_row = ""
            total = sum(standings.values())
            playoff_probab = 0
            for i in range(1, 11):
                if not standings.get(i):
                    standings[i] = 0
                if i <= self.league.playoff_teams:
                    playoff_probab += standings[i]
                relative_row = f"{relative_row} | {round(standings[i] / total * 100, 2)}"
                absolute_row = f"{absolute_row} | {standings[i]:,}"
            relative_row = (
                f"| {team} {relative_row} | {str(round(playoff_probab / total * 100, 2))} |"
            )
            relative_rows = "".join([relative_rows, relative_row, "\n"])
            absolute_row = f"| {team} {absolute_row} | {total:,} |"
            absolute_rows = "".join([absolute_rows, absolute_row, "\n"])

        with self.template_file.open("r") as template:
            output_template = template.read()

        logger.debug("Formatting output")
        output = output_template.format(
            explanation=self.league.explanation,
            relative_rows=relative_rows,
            absolute_rows=absolute_rows,
            process_time=round(process_time, 0),
        )

        with open(self.league.output_file, "a") as f:
            f.write(output)
        logger.success(f"Output probabilities at '{self.league.output_file.absolute()}'")

    @staticmethod
    def sort_result(item):
        logger.debug("Sorting results")
        for i in range(1, 11):
            if not item[1].get(i):
                item[1][i] = 0

        return [item[1][i] for i in range(1, 11)]
