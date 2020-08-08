import json
import re
from pathlib import Path
from typing import List

import bs4
import requests
from loguru import logger

from leagueprobs.match import Match

WEEK_PATTERN = re.compile("\d")


class GamepediaScraper:
    """Class to handle the scraping of data from gamepedia."""

    def __init__(self, gamepedia_url: str, output_file: Path = Path("matches.json")) -> None:
        """Instantiate your scraper.

        Args:
            gamepedia_url (str): string to the webpage of the proper league, year, season on
                                 gamepedia.
            output_file (Path): pathlib.Path object to the file to use to save the matches data.
        """
        self.gamepedia_url = gamepedia_url
        self.output_file = output_file
        self.matches: List[Match] = []

    def tables(self) -> bs4.element.ResultSet:
        """
        Return the tables parsed from the page's HTML content.

        Returns:
            A ResultSet object from BeautifulSoup4.
        """
        logger.info("Querying and parsing tables from Gamepedia")
        return self._get_content_soup().find_all("table", class_="wikitable matchlist")

    def _get_content_soup(self) -> bs4.BeautifulSoup:
        """
        Get the league's full content from the gamepedia page, as a parser BeautifulSoup.

        Returns:
            A BeautifulSoup object of the page's parsed html.
        """
        logger.debug(f"GETing content from '{self.gamepedia_url}'")
        response = requests.get(self.gamepedia_url)
        logger.debug(f"Parsing retrieved HTML content from '{self.gamepedia_url}'")
        return bs4.BeautifulSoup(response.content, "html.parser")

    @staticmethod
    def _construct_match_from_bs4_tag(match_tag: bs4.element.Tag, week: int) -> Match:
        """
        Creates a Match object from one of the match rows in the m
        Args:
            match_tag (bs4.element.Tag): row from the
            week (int): the week for this match.

        Returns:
            A leagueprobs.match.Match object.
        """
        logger.trace("Extracting teams")
        teams_html: bs4.element.ResultSet = match_tag.find_all("span", class_="teamname")
        teams = tuple(team.get_text() for team in teams_html)

        logger.trace(f"Extracting result of {teams[0]} vs {teams[1]}")
        result_html: bs4.element.ResultSet = match_tag.find_all("td", class_="matchlist-score")
        result = tuple(int(result.get_text()) for result in result_html)

        try:
            logger.trace(
                f"Constructing Match {teams[0]} vs {teams[1]} with score {result[0]}-{result[1]}"
            )
        except IndexError:  # This is when match hasn't been played yet and result is None
            logger.trace(f"Constructing Match {teams[0]} vs {teams[1]}, yet to be played")
        return Match(teams, week, result)

    def get_matches(self) -> None:
        """
        Construct the 'matches' attribute with Match objects from the gamepedia page's parsed
        HTML. A Match object is created for each match of the split.
        """
        for wiki_table in self.tables():
            week = int(WEEK_PATTERN.findall(wiki_table.find("th").get_text())[0])
            matches_row: bs4.element.ResultSet = wiki_table.find_all("tr", class_="ml-row")

            for match in matches_row:
                self.matches.append(self._construct_match_from_bs4_tag(match_tag=match, week=week))
        logger.success("The 'matches' attribute has been updates with matches information")

    def save_matches(self) -> None:
        """Dump matches to json file."""
        if not self.matches:
            logger.warning("No matches parsed yet, call the 'get_matches' method to do so")
            return

        matches = [match.__dict__ for match in self.matches]
        try:
            with self.output_file.open("w") as f:
                json.dump(matches, f, indent=4, sort_keys=True)
                logger.success(
                    f"Dumped matches queried from {self.gamepedia_url} to "
                    f"'{self.output_file.absolute()}'"
                )
        except Exception:
            logger.exception(
                f"An error occured when trying to dump matches to '{self.output_file.absolute()}'"
            )

    def scrape_league(self) -> None:
        """Scrape matches and output the data."""
        self.get_matches()
        self.save_matches()
