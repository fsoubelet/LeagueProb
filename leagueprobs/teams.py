from typing import List

from loguru import logger

from leagueprobs.match import Match


class Team:
    """Class to handle a specific team's info."""

    def __init__(self, name: str, matches: List[Match]) -> None:
        self.name = name
        self.matches = matches

    @property
    def wins(self) -> int:
        """Return the current number of wins for this team so far."""
        logger.debug(f"Counting {self.name}'s wins so far")
        return sum(1 for match in self.matches if match.winner == self.name)

    def head_to_head_wins(self, other_teams: List[Team]) -> int:
        """
        Return the number of wins against the teams in other_teams.

        Args:
            other_teams (List[Team]): list of other teams.

        Returns:
            The amount of wins.
        """
        wins: int = 0

        logger.debug(
            f"Gathering {self.name}'s matches against the provided opponents and counting wins"
        )
        for opponent in other_teams:
            matchups: List[Match] = [
                match
                for match in self.matches
                if self.name in match.teams and opponent.name in match.teams
            ]
            for match in matchups:
                if match.winner == self.name:
                    wins += 1
        return wins

    def wins_in_second_half(self) -> int:
        """Return the amount of wins in the second half of a split."""
        wins: int = 0

        logger.debug(f"Gathering {self.name}'s matches for the second half of the split")
        second_half_matches: List[Match] = [
            match
            for match in self.matches
            if match.week > 4 and match.winner  # TODO: remove hardcoded week
        ]

        logger.debug(f"Counting {self.name}'s wins in the second half of the split")
        for match in second_half_matches:
            if match.winner == self.name:
                wins += 1
        return wins
