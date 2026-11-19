import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


BACKGROUND = "#0b132b"
CARD = "#16213e"
CARD_ACCENT = "#1f3a5f"
TEXT = "#f4f7fb"
MUTED = "#a9b8cc"
ACCENT = "#f4b942"
LINE = "#6e86a8"


def load_playoff_field(path: Path) -> list[dict[str, str]]:
    """Load and validate a playoff field CSV ordered by seed."""
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"seed", "rank", "team_name"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Playoff CSV missing columns: {sorted(missing)}")

        teams = []
        for row in reader:
            try:
                seed = int(row["seed"])
                rank = int(row["rank"])
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid seed or rank for {row.get('team_name', 'team')}"
                ) from error

            if seed < 1 or seed > 12:
                raise ValueError(f"Seed must be between 1 and 12: {seed}")

            teams.append({
                "seed": str(seed),
                "rank": str(rank),
                "name": row["team_name"].strip(),
            })

    if len(teams) != 12 or {int(team["seed"]) for team in teams} != set(range(1, 13)):
        raise ValueError("Playoff CSV must contain exactly one team for each seed 1-12")

    return sorted(teams, key=lambda team: int(team["seed"]))


def draw_card(axis, x: float, y: float, team: dict[str, str], width: float = 2.45):
    """Draw a team card centered at (x, y), returning its connection points."""
    height = 0.62
    axis.add_patch(FancyBboxPatch(
        (x - width / 2, y - height / 2),
        width,
        height,
        boxstyle="round,pad=0.03,rounding_size=0.08",
        facecolor=CARD,
        edgecolor=CARD_ACCENT,
        linewidth=1.2,
    ))
    axis.text(
        x - width / 2 + 0.12,
        y + 0.11,
        f"#{team['seed']}  {team['name']}",
        color=TEXT,
        fontsize=8.5,
        fontweight="bold",
        ha="left",
        va="center",
    )
    axis.text(
        x - width / 2 + 0.12,
        y - 0.13,
        f"PageRank rank #{team['rank']}",
        color=MUTED,
        fontsize=6.8,
        ha="left",
        va="center",
    )
    return x - width / 2, x + width / 2


def connect(axis, start_x: float, start_y: float, end_x: float, end_y: float):
    axis.plot(
        [start_x, end_x],
        [start_y, end_y],
        color=LINE,
        linewidth=1.1,
        solid_capstyle="round",
        zorder=0,
    )


def draw_playoff_bracket(
    teams: list[dict[str, str]],
    output_path: Path,
    first_four_out: list[dict[str, str]] | None = None,
):
    """Render a 12-team CFP bracket with first-round byes."""
    by_seed = {int(team["seed"]): team for team in teams}
    figure, axis = plt.subplots(figsize=(19, 10), facecolor=BACKGROUND)
    axis.set_facecolor(BACKGROUND)
    axis.axis("off")
    axis.set_xlim(0, 19)
    axis.set_ylim(-0.3, 10.4)

    axis.text(
        0.4,
        10.0,
        "COLLEGE FOOTBALL PLAYOFF",
        color=TEXT,
        fontsize=23,
        fontweight="bold",
        ha="left",
    )
    axis.text(
        0.42,
        9.55,
        "PageRank-powered 12-team field",
        color=ACCENT,
        fontsize=11,
        ha="left",
    )

    columns = {
        "first": 1.65,
        "quarter": 5.25,
        "semi": 9.0,
        "champ": 12.75,
        "winner": 16.45,
    }
    labels = [
        ("FIRST ROUND", columns["first"]),
        ("QUARTERFINALS", columns["quarter"]),
        ("SEMIFINALS", columns["semi"]),
        ("CHAMPIONSHIP", columns["champ"]),
        ("WINNER", columns["winner"]),
    ]
    for label, x in labels:
        axis.text(x, 9.05, label, color=MUTED, fontsize=8, fontweight="bold", ha="center")

    # First-round games, with the top four seeds receiving byes.
    first_round = [(5, 12), (6, 11), (7, 10), (8, 9)]
    first_y = [7.75, 5.75, 3.75, 1.75]
    for (higher, lower), y in zip(first_round, first_y):
        draw_card(axis, columns["first"], y + 0.28, by_seed[higher])
        draw_card(axis, columns["first"], y - 0.28, by_seed[lower])
        axis.plot(
            [columns["first"] + 1.23, columns["first"] + 1.55],
            [y + 0.28, y + 0.28],
            color=LINE,
            linewidth=1.1,
        )
        axis.plot(
            [columns["first"] + 1.23, columns["first"] + 1.55],
            [y - 0.28, y - 0.28],
            color=LINE,
            linewidth=1.1,
        )
        connect(axis, columns["first"] + 1.55, y + 0.28, columns["quarter"] - 1.23, y)

    # Quarterfinals: #4, #1, #3, and #2 get the first-round winners.
    quarter_y = [8.0, 6.0, 3.5, 1.5]
    bye_seeds = [4, 1, 3, 2]
    for seed, y in zip(bye_seeds, quarter_y):
        draw_card(axis, columns["quarter"], y, by_seed[seed])
    for y in quarter_y:
        connect(axis, columns["quarter"] - 1.23, y, columns["quarter"] + 1.23, y)

    # Pair quarterfinals into semifinals, preserving the official bracket order.
    semi_y = [7.0, 2.5]
    for y, top, bottom in zip(semi_y, quarter_y[::2], quarter_y[1::2]):
        connect(axis, columns["quarter"] + 1.23, top, columns["semi"] - 1.23, y)
        connect(axis, columns["quarter"] + 1.23, bottom, columns["semi"] - 1.23, y)
        axis.plot(
            [columns["quarter"] + 1.23, columns["quarter"] + 1.55],
            [top, top],
            color=LINE,
            linewidth=1.1,
        )
        axis.plot(
            [columns["quarter"] + 1.23, columns["quarter"] + 1.55],
            [bottom, bottom],
            color=LINE,
            linewidth=1.1,
        )
    draw_card(axis, columns["semi"], semi_y[0], {"seed": "QF", "rank": "winner", "name": "Semifinal 1"})
    draw_card(axis, columns["semi"], semi_y[1], {"seed": "QF", "rank": "winner", "name": "Semifinal 2"})

    connect(axis, columns["semi"] + 1.23, semi_y[0], columns["champ"] - 1.23, 4.75)
    connect(axis, columns["semi"] + 1.23, semi_y[1], columns["champ"] - 1.23, 4.75)
    draw_card(axis, columns["champ"], 4.75, {"seed": "NC", "rank": "winner", "name": "National Champion"})
    connect(axis, columns["champ"] + 1.23, 4.75, columns["winner"] - 1.23, 4.75)
    draw_card(axis, columns["winner"], 4.75, {"seed": "★", "rank": "—", "name": "Champion"}, width=2.2)

    if first_four_out:
        axis.text(
            15.15,
            9.05,
            "FIRST FOUR OUT",
            color=MUTED,
            fontsize=8,
            fontweight="bold",
            ha="center",
        )
        for index, team in enumerate(first_four_out, start=1):
            axis.text(
                14.45,
                8.6 - (index - 1) * 0.42,
                f"{index}. {team['name']}  (PageRank #{team['rank']})",
                color=TEXT,
                fontsize=7.2,
                ha="left",
                va="center",
            )

    axis.text(
        0.42,
        0.35,
        "Seeds 1–4 receive first-round byes  •  Matchups: 5/12, 6/11, 7/10, 8/9",
        color=MUTED,
        fontsize=8,
        ha="left",
    )
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=220, facecolor=BACKGROUND, bbox_inches="tight")
    plt.close(figure)
    print(f"Saved playoff bracket: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Render a visually appealing 12-team playoff bracket from CSV."
    )
    parser.add_argument(
        "playoff_csv",
        type=Path,
        nargs="?",
        default=Path("data") / "playoff_field.csv",
        help="Path to the playoff field CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data") / "playoff_bracket.png",
        help="Output PNG path.",
    )
    args = parser.parse_args()

    if not args.playoff_csv.exists():
        raise FileNotFoundError(f"Playoff CSV not found: {args.playoff_csv}")

    draw_playoff_bracket(load_playoff_field(args.playoff_csv), args.output)


if __name__ == "__main__":
    main()
