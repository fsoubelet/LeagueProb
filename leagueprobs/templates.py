EXPLANATION_TEMPLATE = """
# All {league_name} Playoff scenarios

With accounting for the following tiebreaker rules:
1) by tied standings the team with the favored head-to-head record gets the higher standing,
2) If that doesnt resolve the tie, the team with more wins in the 2nd half of the split gets the 
higher placing.

If after 2) ties remain, tiebreaker game(s) will be played but are not represented here, 
which can leads to an uneven distribution of the places.
"""


OUTPUT_TEMPLATE = """
{explanation}

## Relative:
| Team | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Playoff % |
| ---  | --- | --- | --- | --- | ---  | --- | --- | --- | --- | --- | --- |
{relative_rows}

## Absolute:
| Team | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Total |
| ---  | --- | --- | --- | --- | ---  | --- | --- | --- | --- | --- | --- |
{absolute_rows}

Process Time: {process_time}s
"""
