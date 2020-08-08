import json
from pathlib import Path
from typing import List, Tuple, Union

from loguru import logger


class Match:
    """Class to handle a specific match between two teams."""

    def __init__(self, teams: Tuple[str, str], week: int, result: Tuple[int, int]) -> None:
        self.teams = teams
        self.week = week
        self.result = result

    def __str__(self):
        return f"Match(W{self.week} {self.teams[0]}-{self.teams[1]})"

    def __repr__(self):
        if self.result:
            return (
                f"Match[Week {self.week}: {self.teams[0]} ({self.result[0]} - "
                f"{self.result[1]}) {self.teams[1]}]"
            )
        else:
            return f"Match[Week {self.week}: {self.teams[0]} ? - ? {self.teams[1]}]"

    @property
    def winner(self) -> Union[str, None]:
        """
        Return the winner of this specific match, based on the result provided at instantiation.

        Returns:
            The name of the winning team, if there is a winning team (bo2 formats are weird).
        """
        if not self.result:
            logger.debug(
                f"Week {self.week}: '{self.teams[0]} vs {self.teams[1]}' either hasn't played or "
                f"is a draw, indicating no winner yet"
            )
            return None
        elif self.result[0] > self.result[1]:
            return self.teams[0]
        else:
            return self.teams[1]

    @property
    def loser(self) -> Union[str, None]:
        """
        Return the loser of this specific match, based on the result provided at instantiation.

        Returns:
            The name of the losing team, if there is a losing team (bo2 formats are weird).
        """
        if not self.result:
            logger.debug(
                f"Week {self.week}: '{self.teams[0]} vs {self.teams[1]}' either hasn't played or "
                f"is a draw, indicating no loser yet"
            )
            return None
        elif self.result[0] > self.result[1]:
            return self.teams[1]
        else:
            return self.teams[0]


def get_matches_from_json(json_file: Path) -> List[Match]:
    """
    Return matches classes from a json file of results.

    Args:
        json_file (pathlib.Path): Path to the json file with results.

    Returns:
        List of Matches instantiated from the json contents.
    """
    with json_file.open("r") as f:
        matches: List[Match] = [
            Match(match["teams"], match["week"], match["result"]) for match in json.load(f)
        ]
    return matches
