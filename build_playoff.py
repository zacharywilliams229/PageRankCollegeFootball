
import argparse
import csv
from pathlib import Path


POWER_FOUR = {"ACC", "Big Ten", "Big 12", "SEC"}

GROUP_OF_SIX = {
    "American",
    "Conference USA",
    "MAC",
    "Mountain West",
    "Pac-12",
    "Sun Belt",
}


def parse_bool(value):
    return value.strip().lower() in {"true", "1", "yes", "y"}


def load_rankings(path):
    teams = {}

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        required = {"rank", "team_id", "team_name", "pagerank_score"}
        missing = required - set(reader.fieldnames or [])

        if missing:
            raise ValueError(f"Rankings CSV missing columns: {missing}")

        for row in reader:
            team_id = row["team_id"].strip()

            teams[team_id] = {
                "team_id": team_id,
                "name": row["team_name"].strip(),
                "rank": int(row["rank"]),
                "score": float(row["pagerank_score"]),
            }

    return teams


def load_metadata(path):
    metadata = {}

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        required = {
            "team_id",
            "conference",
            "is_fbs",
            "is_conference_champion",
            "is_notre_dame",
        }

        missing = required - set(reader.fieldnames or [])

        if missing:
            raise ValueError(f"Metadata CSV missing columns: {missing}")

        for row in reader:
            team_id = row["team_id"].strip()

            metadata[team_id] = {
                "conference": row["conference"].strip(),
                "is_fbs": parse_bool(row["is_fbs"]),
                "is_champion": parse_bool(
                    row["is_conference_champion"]
                ),
                "is_notre_dame": parse_bool(row["is_notre_dame"]),
            }

    return metadata


def get_projected_conference_winners(eligible):
    """Return up to five winners, with unique conferences."""
    winners = []
    represented_conferences = set()

    # Declared champions retain priority, ordered by team rank.
    champions = [
        team for team in eligible
        if team["is_champion"]
    ]
    champions.sort(key=lambda team: team["rank"])

    for team in champions:
        conference = team["conference"].strip()
        if conference and conference not in represented_conferences:
            winners.append(team)
            represented_conferences.add(conference)

        if len(winners) == 5:
            break

    # When fewer than five champions are known, project the highest-ranked
    # team from each conference that is not already represented.
    conferences = {
        team["conference"].strip()
        for team in eligible
        if team["conference"].strip()
    }

    remaining = [
        conference for conference in conferences
        if conference not in represented_conferences
    ]
    remaining.sort(key=lambda conference: min(
        team["rank"] for team in eligible
        if team["conference"].strip() == conference
    ))

    for conference in remaining:
        conference_teams = [
            team for team in eligible
            if team["conference"].strip() == conference
        ]
        projected = min(conference_teams, key=lambda team: team["rank"])
        if len(winners) == 5:
            break
        winners.append(projected)
        represented_conferences.add(conference)

    return sorted(winners, key=lambda team: team["rank"])


def build_playoff_field(rankings, metadata, playoff_format):
    """
    Select the 12 playoff teams.

    five-champs:
        Five highest-ranked FBS conference winners qualify. If a conference
        has no declared champion, its highest-ranked team is projected.
        Next seven highest-ranked teams fill the remaining spots.

    2026:
        ACC, Big Ten, Big 12, and SEC winners qualify. Missing conference
        champions are projected as each conference's highest-ranked team.
        Highest-ranked Group of Six team qualifies.
        Notre Dame qualifies if ranked in the top 12.
        Remaining spots go to the highest-ranked teams.
    """

    # Only consider FBS teams with metadata.
    eligible = []

    for team_id, team in rankings.items():
        info = metadata.get(team_id)

        if info is None:
            print(f"Warning: Missing metadata for {team['name']}")
            continue

        if not info["is_fbs"]:
            continue

        eligible.append({
            **team,
            **info,
            "automatic_qualifier": False,
        })

    eligible.sort(key=lambda team: team["rank"])

    if playoff_format == "five-champs":
        automatic_qualifiers = get_projected_conference_winners(
            eligible
        )[:5]

    elif playoff_format == "2026":
        automatic_qualifiers = []

        # Four Power Four conference champions.
        for conference in POWER_FOUR:
            champions = [
                team for team in eligible
                if team["conference"] == conference
                and team["is_champion"]
            ]

            if not champions:
                conference_teams = [
                    team for team in eligible
                    if team["conference"] == conference
                ]
                if not conference_teams:
                    raise ValueError(
                        f"No teams found for {conference}."
                    )
                champions = conference_teams

            automatic_qualifiers.append(min(
                champions,
                key=lambda team: team["rank"],
            ))

        # Highest-ranked Group of Six team, champion or not.
        group_of_six = [
            team for team in eligible
            if team["conference"] in GROUP_OF_SIX
        ]

        if not group_of_six:
            raise ValueError("No Group of Six teams found.")

        automatic_qualifiers.append(group_of_six[0])

        # Notre Dame automatically qualifies if in the top 12.
        notre_dame = [
            team for team in eligible
            if team["is_notre_dame"] and team["rank"] <= 12
        ]

        if notre_dame:
            automatic_qualifiers.append(notre_dame[0])

    else:
        raise ValueError(f"Unknown playoff format: {playoff_format}")

    # Mark automatic qualifiers.
    automatic_ids = {
        team["team_id"] for team in automatic_qualifiers
    }

    for team in eligible:
        if team["team_id"] in automatic_ids:
            team["automatic_qualifier"] = True

    # Fill the remaining spots with the highest-ranked teams.
    selected = list(automatic_qualifiers)

    for team in eligible:
        if len(selected) == 12:
            break

        if team["team_id"] not in automatic_ids:
            selected.append(team)

    if len(selected) != 12:
        raise ValueError(
            f"Could only select {len(selected)} playoff teams."
        )

    # Seed according to ranking. Automatic qualifiers outside
    # the top 12 are placed at the bottom of the bracket.
    selected.sort(
        key=lambda team: (
            team["automatic_qualifier"] and team["rank"] > 12,
            team["rank"],
        )
    )

    for seed, team in enumerate(selected, start=1):
        team["seed"] = seed

    return selected


def get_first_four_out(rankings, metadata, playoff_teams):
    """Return the four highest-ranked eligible teams left outside the field."""
    selected_ids = {team["team_id"] for team in playoff_teams}
    eligible = [
        {
            **team,
            **metadata[team_id],
        }
        for team_id, team in rankings.items()
        if team_id in metadata
        and metadata[team_id]["is_fbs"]
        and team_id not in selected_ids
    ]
    return sorted(eligible, key=lambda team: team["rank"])[:4]


def print_bracket(teams):
    by_seed = {team["seed"]: team for team in teams}

    def describe(seed):
        team = by_seed[seed]
        return (
            f"#{seed} {team['name']} "
            f"(rank #{team['rank']})"
        )

    print("\nCOLLEGE FOOTBALL PLAYOFF")
    print("=" * 65)

    print("\nFIRST-ROUND BYES")
    for seed in range(1, 5):
        print(f"  {describe(seed)}")

    print("\nFIRST ROUND")
    matchups = [
        (5, 12),
        (6, 11),
        (7, 10),
        (8, 9),
    ]

    for higher, lower in matchups:
        print(f"  {describe(higher)} vs. {describe(lower)}")

    print("\nQUARTERFINALS")
    print("  #4 vs. Winner of #5 / #12")
    print("  #1 vs. Winner of #8 / #9")
    print("  #3 vs. Winner of #6 / #11")
    print("  #2 vs. Winner of #7 / #10")

    print("\nSEMIFINALS")
    print("  Winner of Quarterfinal 1 vs. Winner of Quarterfinal 2")
    print("  Winner of Quarterfinal 3 vs. Winner of Quarterfinal 4")

    print("\nNATIONAL CHAMPIONSHIP")
    print("  Semifinal winners")


def save_playoff_field(teams, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow([
            "seed",
            "rank",
            "team_id",
            "team_name",
            "conference",
            "automatic_qualifier",
            "pagerank_score",
        ])

        for team in teams:
            writer.writerow([
                team["seed"],
                team["rank"],
                team["team_id"],
                team["name"],
                team["conference"],
                team["automatic_qualifier"],
                team["score"],
            ])

    print(f"\nSaved playoff field to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a 12-team college football playoff bracket."
    )

    parser.add_argument(
        "rankings_csv",
        type=Path,
        help="PageRank rankings CSV.",
    )

    parser.add_argument(
        "metadata_csv",
        type=Path,
        help="Team conference and championship metadata CSV.",
    )

    parser.add_argument(
        "--format",
        choices=["five-champs", "2026"],
        default="five-champs",
        help="Playoff qualification rules (default: five-champs).",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data") / "playoff_field.csv",
        help="Output CSV file.",
    )

    args = parser.parse_args()

    rankings = load_rankings(args.rankings_csv)
    metadata = load_metadata(args.metadata_csv)

    playoff_teams = build_playoff_field(
        rankings,
        metadata,
        args.format,
    )

    print_bracket(playoff_teams)
    save_playoff_field(playoff_teams, args.output)


if __name__ == "__main__":
    main()
