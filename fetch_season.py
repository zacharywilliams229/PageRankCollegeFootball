
#!/usr/bin/env python3

import argparse
import csv
import json
import re
import time
from pathlib import Path

import requests

BASE_URLS = [
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
    "https://site.web.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
]

OUTPUT_DIR = Path("data")
CACHE_DIR = OUTPUT_DIR / "raw_cache"

MAX_WEEKS = 25
REQUEST_DELAY = 1.0

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; CollegeFootballResearch/1.0)"
})


def fetch_week(year, season_type, week, refresh=False):
    """Fetch one week's scoreboard, using the local cache when possible."""

    cache_file = CACHE_DIR / f"{year}_type{season_type}_week{week}.json"

    if cache_file.exists() and not refresh:
        print(f"  Using cache: Type {season_type}, Week {week}")
        with cache_file.open() as f:
            return json.load(f)

    params = {
        "dates": str(year),
        "seasontype": season_type,
        "week": week,
        "groups": 80,       # FBS
        "limit": 1000,
    }

    last_error = None

    for base_url in BASE_URLS:
        for attempt in range(4):
            try:
                response = session.get(
                    base_url,
                    params=params,
                    timeout=30
                )

                if response.status_code == 403:
                    last_error = "403 Forbidden"
                    break

                if response.status_code == 429:
                    wait = 15 * (attempt + 1)
                    print(f"  Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()

                cache_file.parent.mkdir(parents=True, exist_ok=True)

                with cache_file.open("w") as f:
                    json.dump(data, f, indent=2)

                time.sleep(REQUEST_DELAY)
                return data

            except (requests.RequestException, ValueError) as error:
                last_error = str(error)

                if attempt < 3:
                    wait = 2 ** attempt
                    print(f"  Request failed: {error}")
                    print(f"  Retrying in {wait}s...")
                    time.sleep(wait)

        print(f"  Trying next ESPN endpoint...")

    raise RuntimeError(
        f"Could not fetch {year}, type {season_type}, "
        f"week {week}: {last_error}"
    )


def extract_game(event, year, season_type, week):
    """Convert an ESPN event into a normalized game record."""

    competitions = event.get("competitions", [])

    if not competitions:
        return None

    competition = competitions[0]

    status = competition.get("status", {}).get("type", {})

    # Ignore games that have not been completed.
    if not status.get("completed", False):
        return None

    competitors = competition.get("competitors", [])

    if len(competitors) != 2:
        return None

    teams = []

    for competitor in competitors:
        team = competitor.get("team", {})

        teams.append({
            "id": team.get("id"),
            "name": team.get("displayName"),
            "abbreviation": team.get("abbreviation"),
            "score": competitor.get("score"),
            "home_away": competitor.get("homeAway"),
            "winner": competitor.get("winner", False),
        })

    # ESPN normally supplies the winner boolean.
    winners = [t for t in teams if t["winner"] is True]

    if len(winners) == 1:
        winner = winners[0]
        loser = next(t for t in teams if t is not winner)
        result = "win"

    else:
        # Fall back to comparing scores.
        try:
            score_a = int(teams[0]["score"])
            score_b = int(teams[1]["score"])

            if score_a == score_b:
                winner = None
                loser = None
                result = "tie"
            else:
                winner = teams[0] if score_a > score_b else teams[1]
                loser = teams[1] if winner is teams[0] else teams[0]
                result = "win"

        except (TypeError, ValueError):
            return None

    notes = competition.get("notes", [])

    note_text = " ".join(
        str(note.get("headline", ""))
        for note in notes
    )

    event_name = event.get("name", "")

    championship_text = f"{event_name} {note_text}".lower()

    is_championship = (
        "championship" in championship_text
        and "national championship" not in championship_text
        and "playoff semifinal" not in championship_text
    )

    return {
        "event_id": event.get("id"),
        "season": year,
        "season_type": season_type,
        "week": week,
        "date": event.get("date"),
        "event_name": event_name,
        "result": result,
        "is_championship_game": is_championship,
        "winner": {
            "id": winner["id"],
            "name": winner["name"],
            "abbreviation": winner["abbreviation"],
            "score": winner["score"],
        } if winner else None,
        "loser": {
            "id": loser["id"],
            "name": loser["name"],
            "abbreviation": loser["abbreviation"],
            "score": loser["score"],
        } if loser else None,
        "teams": teams,
    }


def fetch_season(year, refresh=False):
    """Fetch all available regular and postseason FBS games."""

    games = {}
    season_types = [2, 3]

    for season_type in season_types:
        print(f"\nFetching season type {season_type}...")

        consecutive_empty_weeks = 0
        found_games = False

        for week in range(1, MAX_WEEKS + 1):
            print(f"Week {week}...")

            data = fetch_week(
                year,
                season_type,
                week,
                refresh
            )

            events = data.get("events", [])
            week_games = []

            for event in events:
                game = extract_game(
                    event,
                    year,
                    season_type,
                    week
                )

                if game:
                    week_games.append(game)

            print(f"  Completed games found: {len(week_games)}")

            if week_games:
                found_games = True
                consecutive_empty_weeks = 0

                for game in week_games:
                    games[game["event_id"]] = game
            else:
                consecutive_empty_weeks += 1

            # Stop after two consecutive empty weeks, but don't
            # stop before finding the first games in a season type.
            if found_games and consecutive_empty_weeks >= 2:
                print("  No more games expected. Moving on.")
                break

    return list(games.values())


def save_games(year, games, output_dir=None):
    """Save normalized JSON and convenient CSV output."""

    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    games.sort(key=lambda g: (g["date"] or "", g["event_id"]))

    json_file = output_dir / f"{year}_games.json"

    with json_file.open("w") as f:
        json.dump(games, f, indent=2)

    csv_file = output_dir / f"{year}_games.csv"

    columns = [
        "event_id",
        "season",
        "season_type",
        "week",
        "date",
        "event_name",
        "result",
        "is_championship_game",
        "winner_id",
        "winner",
        "winner_abbreviation",
        "winner_score",
        "loser_id",
        "loser",
        "loser_abbreviation",
        "loser_score",
    ]

    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for game in games:
            winner = game["winner"] or {}
            loser = game["loser"] or {}

            writer.writerow({
                "event_id": game["event_id"],
                "season": game["season"],
                "season_type": game["season_type"],
                "week": game["week"],
                "date": game["date"],
                "event_name": game["event_name"],
                "result": game["result"],
                "is_championship_game": game["is_championship_game"],
                "winner_id": winner.get("id"),
                "winner": winner.get("name"),
                "winner_abbreviation": winner.get("abbreviation"),
                "winner_score": winner.get("score"),
                "loser_id": loser.get("id"),
                "loser": loser.get("name"),
                "loser_abbreviation": loser.get("abbreviation"),
                "loser_score": loser.get("score"),
            })

    print("\nSaved:")
    print(f"  {json_file}")
    print(f"  {csv_file}")
    print(f"  Total completed games: {len(games)}")

    print(f"  Wins: {sum(g['result'] == 'win' for g in games)}")
    print(f"  Ties: {sum(g['result'] == 'tie' for g in games)}")


def main():
    parser = argparse.ArgumentParser(
        description="Download ESPN college football game results."
    )

    parser.add_argument(
        "year",
        type=int,
        help="Season year, e.g. 2025"
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Redownload cached weekly responses."
    )

    args = parser.parse_args()

    games = fetch_season(args.year, args.refresh)
    save_games(args.year, games)


if __name__ == "__main__":
    main()
