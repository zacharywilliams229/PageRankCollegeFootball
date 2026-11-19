
import argparse
import csv
from pathlib import Path

import requests


BASE_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/football/college-football"
)

TEAMS_URL = f"{BASE_URL}/teams"
GROUPS_URL = f"{BASE_URL}/groups"

FBS_GROUP_ID = "80"
NOTRE_DAME_ID = "87"


def fetch_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    response.raise_for_status()
    return response.json()


def load_conferences():
    data = fetch_json(GROUPS_URL)
    conferences = {}

    def process(groups):
        for group in groups:
            group_id = str(group.get("id", ""))
            name = group.get("name", "")

            if group_id and name:
                conferences[group_id] = name

            process(group.get("children", []))

    process(data.get("groups", []))
    return conferences


def find_team_records(data):
    """
    Recursively find ESPN team objects in the response.

    Handles both:
        {"team": {...}}
    and direct team objects.
    """

    found = {}

    def walk(obj):
        if isinstance(obj, dict):

            # ESPN frequently wraps team records in a "team" key.
            if isinstance(obj.get("team"), dict):
                team = obj["team"]

                if team.get("id") and team.get("displayName"):
                    found[str(team["id"])] = team

            # Also support direct team records.
            if obj.get("id") and obj.get("displayName"):
                if any(key in obj for key in (
                    "abbreviation",
                    "groups",
                    "logos",
                    "location",
                )):
                    found[str(obj["id"])] = obj

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return list(found.values())


def get_conference(team, conferences):
    groups = team.get("groups", {})

    if isinstance(groups, dict):
        group_id = str(groups.get("id", ""))

        if group_id in conferences:
            return conferences[group_id]

        # Some responses contain a nested parent group.
        parent = groups.get("parent", {})
        parent_id = str(parent.get("id", ""))

        if parent_id in conferences:
            return conferences[parent_id]

        if groups.get("name"):
            return groups["name"]

    elif isinstance(groups, list):
        for group in groups:
            group_id = str(group.get("id", ""))

            if group_id in conferences:
                return conferences[group_id]

    return ""


def load_conference_champion_ids(games_path, season):
    if not games_path.exists():
        raise RuntimeError(
            f"Games CSV not found: {games_path}. "
            f"Run fetch_season.py {season} first."
        )

    champion_ids = set()

    with games_path.open("r", newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            if str(row.get("season", "")).strip() != str(season):
                continue

            is_championship = row.get(
                "is_championship_game", ""
            ).strip().lower() == "true"

            if is_championship:
                winner_id = row.get("winner_id", "").strip()
                if winner_id:
                    champion_ids.add(winner_id)

    if not champion_ids:
        raise RuntimeError(
            f"No conference champions found in {games_path}. "
            "The games CSV must contain is_championship_game=True rows."
        )

    return champion_ids


def create_metadata(season, output_path):
    print("Fetching conference information...")
    conferences = load_conferences()

    print("Fetching FBS teams from ESPN...")

    data = fetch_json(
        TEAMS_URL,
        params={
            "limit": 1000,
            "groups": FBS_GROUP_ID,
        },
    )

    teams = find_team_records(data)

    if not teams:
        print("\nCould not locate team records.")
        print("Response keys:", list(data.keys()))
        print("Response preview:", str(data)[:2000])

        raise RuntimeError(
            "ESPN returned no recognizable team records."
        )

    games_path = Path("data") / f"{season}_games.csv"
    conference_champion_ids = load_conference_champion_ids(
        games_path,
        season,
    )

    metadata = []

    for team in teams:
        team_id = str(team["id"])
        team_name = team.get("displayName", "")

        metadata.append({
            "team_id": team_id,
            "team_name": team_name,
            "conference": get_conference(team, conferences),
            "is_fbs": "true",
            "is_conference_champion": str(
                team_id in conference_champion_ids
            ).lower(),
            "is_notre_dame": str(
                team_id == NOTRE_DAME_ID
            ).lower(),
        })

    # Remove duplicate teams and sort alphabetically.
    unique = {
        team["team_id"]: team
        for team in metadata
    }

    metadata = sorted(
        unique.values(),
        key=lambda team: team["team_name"],
    )

    if len(metadata) < 100:
        raise RuntimeError(
            f"Only found {len(metadata)} teams. "
            "Expected approximately 130 FBS teams. "
            "Refusing to create an incomplete metadata file."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "team_id",
        "team_name",
        "conference",
        "is_fbs",
        "is_conference_champion",
        "is_notre_dame",
    ]

    with output_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(metadata)

    print("\nMetadata generation complete")
    print("-----------------------------")
    print(f"Season:      {season}")
    print(f"Teams:       {len(metadata)}")
    print(f"Conferences: {len(set(t['conference'] for t in metadata))}")
    print(f"Output:      {output_path}")

    print("\nTeams with missing conference information:")

    missing = [
        team["team_name"]
        for team in metadata
        if not team["conference"]
    ]

    if missing:
        for name in missing:
            print(f"  - {name}")
    else:
        print("  None")

    champions = sum(
        team["is_conference_champion"].lower() == "true"
        for team in metadata
    )

    print(f"\nConference champions marked: {champions}")
    print(f"Source: {games_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate FBS team metadata from ESPN."
    )

    parser.add_argument(
        "season",
        type=int,
        help="Season year, e.g. 2025.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path. Defaults to data/<season>_team_metadata.csv.",
    )

    args = parser.parse_args()
    output_path = args.output or Path(
        f"data/{args.season}_team_metadata.csv"
    )

    create_metadata(args.season, output_path)


if __name__ == "__main__":
    main()
