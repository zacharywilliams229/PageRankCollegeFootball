
import argparse
import csv
from pathlib import Path

import networkx as nx


def reverse_win_graph(graph: nx.DiGraph) -> nx.DiGraph:
    """Return a copy whose edges point from winners to losers."""
    loss_graph = graph.reverse(copy=True)
    loss_graph.graph["description"] = (
        "College football loss graph. Edges point from winner to loser."
    )
    return loss_graph


def _rank_graph(
    graph: nx.DiGraph,
    alpha: float,
    max_iter: int,
    tolerance: float,
):
    if graph.number_of_nodes() == 0:
        raise ValueError("The graph contains no teams.")

    rankings = nx.pagerank(
        graph,
        alpha=alpha,
        max_iter=max_iter,
        tol=tolerance,
        weight="weight",
    )

    ranked_teams = sorted(
        rankings.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    return graph, ranked_teams


def rank_teams(
    graph_path: Path,
    alpha: float = 0.85,
    max_iter: int = 1000,
    tolerance: float = 1e-8,
):
    # Load the directed win graph.
    graph = nx.read_graphml(graph_path)

    return _rank_graph(
        graph,
        alpha=alpha,
        max_iter=max_iter,
        tolerance=tolerance,
    )


def rank_losses(
    graph_path: Path,
    alpha: float = 0.85,
    max_iter: int = 1000,
    tolerance: float = 1e-8,
):
    """Rank teams using a graph whose edges point from winners to losers."""
    graph = reverse_win_graph(nx.read_graphml(graph_path))

    return _rank_graph(
        graph,
        alpha=alpha,
        max_iter=max_iter,
        tolerance=tolerance,
    )


def rank_combined(
    graph_path: Path,
    alpha: float = 0.85,
    max_iter: int = 1000,
    tolerance: float = 1e-8,
):
    """Rank teams by win PageRank, penalized by loss PageRank."""
    graph = nx.read_graphml(graph_path)
    _, win_rankings = _rank_graph(
        graph,
        alpha=alpha,
        max_iter=max_iter,
        tolerance=tolerance,
    )
    _, loss_rankings = _rank_graph(
        reverse_win_graph(graph),
        alpha=alpha,
        max_iter=max_iter,
        tolerance=tolerance,
    )

    win_scores = dict(win_rankings)
    loss_scores = dict(loss_rankings)
    combined_rankings = sorted(
        (
            (team_id, win_scores[team_id] - loss_scores[team_id])
            for team_id in graph.nodes
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    return graph, combined_rankings


def save_rankings(graph, ranked_teams, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["rank", "team_id", "team_name", "pagerank_score"])

        for rank, (team_id, score) in enumerate(ranked_teams, start=1):
            team_name = graph.nodes[team_id].get("name", team_id)

            writer.writerow([
                rank,
                team_id,
                team_name,
                score,
            ])

    print(f"\nSaved rankings to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Rank college football teams using PageRank."
    )

    parser.add_argument(
        "graph_file",
        type=Path,
        help="Path to the GraphML win graph.",
    )

    parser.add_argument(
        "--alpha",
        type=float,
        default=0.85,
        help="PageRank damping factor (default: 0.85).",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path.",
    )

    ranking_group = parser.add_mutually_exclusive_group()
    ranking_group.add_argument(
        "--losses",
        action="store_true",
        help="Rank teams using edges from winners to losers.",
    )
    ranking_group.add_argument(
        "--combined",
        action="store_true",
        help="Rank teams by win PageRank minus loss PageRank.",
    )

    args = parser.parse_args()

    if not args.graph_file.exists():
        raise FileNotFoundError(f"Graph not found: {args.graph_file}")

    if not 0 < args.alpha < 1:
        raise ValueError("Alpha must be between 0 and 1.")

    if args.combined:
        rank_function = rank_combined
    elif args.losses:
        rank_function = rank_losses
    else:
        rank_function = rank_teams
    graph, ranked_teams = rank_function(args.graph_file, alpha=args.alpha)

    print(f"\nTeams ranked: {len(ranked_teams)}")
    print(f"PageRank damping factor: {args.alpha}")
    ranking_type = (
        "Combined"
        if args.combined
        else "Loss"
        if args.losses
        else "Win"
    )
    print(f"\nTop 25 Teams by {ranking_type} PageRank")
    print("-" * 50)

    for rank, (team_id, score) in enumerate(ranked_teams[:25], start=1):
        team_name = graph.nodes[team_id].get("name", team_id)
        print(f"{rank:>3}. {team_name:<35} {score:.8f}")

    output_suffix = (
        "_combined_rankings.csv"
        if args.combined
        else "_loss_rankings.csv"
        if args.losses
        else "_rankings.csv"
    )
    output_path = args.output or args.graph_file.with_name(
        args.graph_file.stem.replace("_win_graph", "") + output_suffix
    )

    save_rankings(graph, ranked_teams, output_path)


if __name__ == "__main__":
    main()
