#!/usr/bin/env python3

import argparse
import tempfile
from pathlib import Path

import fetch_season as season_fetch
from build_graph import build_win_graph, save_graph
from build_playoff import (
    build_playoff_field,
    get_first_four_out,
    load_metadata,
    load_rankings,
    save_playoff_field,
)
from create_team_metadata import create_metadata
from rank_teams import rank_combined, save_rankings
from visualize_playoff import draw_playoff_bracket, load_playoff_field


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"


def run_playoff(
    year: int,
    output_path: Path,
    playoff_format: str = "five-champs",
    refresh: bool = False,
) -> None:
    """Build and render a playoff bracket without retaining intermediate files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_dir = DATA_DIR / "api_cache"
    season_fetch.CACHE_DIR = DATA_DIR / "raw_cache"

    with tempfile.TemporaryDirectory(prefix=f"playoff_{year}_") as temp_dir:
        workspace = Path(temp_dir)
        games_csv = workspace / f"{year}_games.csv"
        graph_path = workspace / f"{year}_win_graph.graphml"
        rankings_csv = workspace / f"{year}_rankings.csv"
        metadata_csv = workspace / f"{year}_team_metadata.csv"
        playoff_csv = workspace / "playoff_field.csv"

        games = season_fetch.fetch_season(year, refresh=refresh)
        season_fetch.save_games(year, games, output_dir=workspace)

        graph = build_win_graph(games_csv)
        save_graph(graph, graph_path)

        ranked_graph, rankings = rank_combined(graph_path)
        save_rankings(ranked_graph, rankings, rankings_csv)

        create_metadata(
            year,
            metadata_csv,
            games_path=games_csv,
            cache_dir=cache_dir,
        )

        rankings = load_rankings(rankings_csv)
        metadata = load_metadata(metadata_csv)
        playoff_teams = build_playoff_field(rankings, metadata, playoff_format)
        save_playoff_field(playoff_teams, playoff_csv)
        draw_playoff_bracket(
            load_playoff_field(playoff_csv),
            output_path,
            get_first_four_out(rankings, metadata, playoff_teams),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a college football playoff bracket for any season."
    )
    parser.add_argument("year", type=int, help="Season year, e.g. 2025.")
    parser.add_argument(
        "--format",
        choices=["five-champs", "2026"],
        default="five-champs",
        help="Playoff qualification rules (default: five-champs).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output PNG path (default: data/<year>_playoff_bracket.png).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Redownload cached weekly ESPN responses.",
    )
    args = parser.parse_args()

    output_path = args.output or DATA_DIR / f"{args.year}_playoff_bracket.png"
    run_playoff(args.year, output_path, args.format, args.refresh)


if __name__ == "__main__":
    main()
