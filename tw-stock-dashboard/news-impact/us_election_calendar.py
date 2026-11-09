"""Legally scheduled U.S. federal general-election voting dates.

The result is a *voting-day calendar*, not the date/time results were known,
the actual winning party, an electoral surprise, or a tradable signal.
House: https://uscode.house.gov/us/usc/t2/s7/
President: https://uscode.house.gov/us/usc/t3/s21/
"""
from datetime import date, datetime, timedelta, timezone

START_YEAR = 1940
CATEGORY = "美國選舉"
PRESIDENT_LAW = "https://uscode.house.gov/us/usc/t3/s21/"
CONGRESS_LAW = "https://uscode.house.gov/us/usc/t2/s7/"


def election_day(year):
    """Tuesday after first Monday in November (November 2 through 8)."""
    if year % 2:
        raise ValueError("U.S. scheduled federal general elections have even election years")
    first = date(year, 11, 1)
    first_monday = first + timedelta(days=(0 - first.weekday()) % 7)
    return first_monday + timedelta(days=1)


def election_events(now=None, start_year=START_YEAR):
    now = now or datetime.now(timezone.utc)
    if not isinstance(start_year, int) or start_year < 1872:
        raise ValueError("invalid first election year")
    start_year += start_year % 2
    rows = []
    for year in range(start_year, now.year + 1, 2):
        voting = election_day(year)
        # Do not add a future calendar date to a database of already-occurring
        # historical event observations.
        if voting > now.date():
            continue
        presidential = year % 4 == 0
        subtype = "總統選舉" if presidential else "期中選舉"
        rows.append({
            "id": f"us-election-{voting.isoformat()}",
            "category": CATEGORY, "subtype": subtype, "date": voting.isoformat(),
            "timezone": "America/New_York", "localTime": None,
            "timeAccuracy": "statutory_voting_day_only",
            "title": f"{year} 美國{'總統與國會' if presidential else '國會期中'}大選投票日",
            "source": "U.S. Code (Office of the Law Revision Counsel)",
            "sourceUrl": PRESIDENT_LAW if presidential else CONGRESS_LAW,
            "evidence": "Voting date follows the statutory first-Tuesday-after-first-Monday rule; exact result timing, winning party and election surprise are unverified.",
            "directionKnown": False,
            "eventCalendarKind": "federal_general_election_voting_day",
            "resultTimeKnown": False,
            "winnerKnown": False,
            "marketSurpriseKnown": False,
        })
    return rows
