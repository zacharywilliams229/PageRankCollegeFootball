
import argparse
import csv
from pathlib import Path

import networkx as nx


def build_win_graph(csv_path: Path) -> nx.DiGraph:
    """
    Build a directed graph from regular-season college football games.

    Edge direction:
        Loser -> Winner

    Only season_type == 2 is included.
    Repeated wins between the same teams increase the edge weight.
    """

    graph = nx.DiGraph()
    graph.graph["description"] = (
        "College football win graph. Edges point from loser to winner."
    )
    graph.graph["season_type"] = 2

    total_rows = 0
    included_games = 0
    excluded_games = 0
    invalid_games = 0

    with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        required_columns = {
            "season_type",
            "winner_id",
            "winner",
            "loser_id",
            "loser",
        }

        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"CSV is missing required columns: {sorted(missing)}"
            )

        for row in reader:
            total_rows += 1

            # Exclude playoffs, bowls, and other postseason games.
            if row["season_type"].strip() != "2":
                excluded_games += 1
                continue

            winner_id = row["winner_id"].strip()
            winner_name = row["winner"].strip()
            loser_id = row["loser_id"].strip()
            loser_name = row["loser"].strip()

            # Ignore ties or incomplete game records.
            if not all([winner_id, winner_name, loser_id, loser_name]):
                invalid_games += 1
                continue

            if winner_id == loser_id:
                invalid_games += 1
                continue

            # Add/update team nodes.
            graph.add_node(winner_id, name=winner_name)
            graph.add_node(loser_id, name=loser_name)

            # Add an edge from loser to winner.
            if graph.has_edge(loser_id, winner_id):
                graph[loser_id][winner_id]["weight"] += 1
            else:
                graph.add_edge(
                    loser_id,
                    winner_id,
                    weight=1
                )

            included_games += 1

    print("\nGraph construction complete")
    print("---------------------------")
    print(f"CSV rows:          {total_rows}")
    print(f"Included games:    {included_games}")
    print(f"Excluded games:    {excluded_games} (not season_type 2)")
    print(f"Invalid games:     {invalid_games}")
    print(f"Teams:             {graph.number_of_nodes()}")
    print(f"Unique edges:      {graph.number_of_edges()}")

    return graph


def save_graph(graph: nx.DiGraph, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save the complete graph in GraphML format.
    nx.write_graphml(graph, output_path)

    # Also export nodes and edges as CSV files for inspection.
    nodes_path = output_path.with_name(
        output_path.stem + "_nodes.csv"
    )
    edges_path = output_path.with_name(
        output_path.stem + "_edges.csv"
    )

    with nodes_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["team_id", "team_name"])

        for team_id, attributes in graph.nodes(data=True):
            writer.writerow([team_id, attributes["name"]])

    with edges_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["loser_id", "loser_name",
                         "winner_id", "winner_name", "weight"])

        for loser, winner, attributes in graph.edges(data=True):
            writer.writerow([
                loser,
                graph.nodes[loser]["name"],
                winner,
                graph.nodes[winner]["name"],
                attributes["weight"],
            ])

    print(f"\nSaved graph: {output_path}")
    print(f"Saved nodes: {nodes_path}")
    print(f"Saved edges: {edges_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Build a college football regular-season win graph."
    )

    parser.add_argument(
        "csv_file",
        type=Path,
        help="Path to the season CSV file."
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output GraphML path."
    )

    args = parser.parse_args()

    if not args.csv_file.exists():
        raise FileNotFoundError(f"CSV not found: {args.csv_file}")

    output_path = args.output or args.csv_file.with_name(
        args.csv_file.stem + "_win_graph.graphml"
    )

    graph = build_win_graph(args.csv_file)
    save_graph(graph, output_path)


if __name__ == "__main__":
    main()
