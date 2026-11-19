import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx


def visualize_graph(
    graph_path: Path,
    output_path: Path,
    label_count: int,
    show: bool,
) -> None:
    """Render a GraphML win graph as a PNG image."""

    graph = nx.read_graphml(graph_path)

    if graph.number_of_nodes() == 0:
        raise ValueError(f"Graph contains no nodes: {graph_path}")

    rankings = nx.pagerank(graph, weight="weight")
    positions = nx.spring_layout(graph, seed=42, weight="weight")
    node_sizes = [
        500 + 5000 * rankings[node]
        for node in graph.nodes
    ]
    edge_widths = [
        0.8 + 0.7 * float(attributes.get("weight", 1))
        for _, _, attributes in graph.edges(data=True)
    ]

    labels = {}
    if label_count > 0:
        ranked_nodes = sorted(
            graph.nodes,
            key=rankings.get,
            reverse=True,
        )[:label_count]
        labels = {
            node: graph.nodes[node].get("name", str(node))
            for node in ranked_nodes
        }

    figure, axis = plt.subplots(figsize=(16, 10))
    nx.draw_networkx_edges(
        graph,
        positions,
        ax=axis,
        width=edge_widths,
        alpha=0.35,
        arrows=True,
        arrowsize=12,
        connectionstyle="arc3,rad=0.04",
    )
    nx.draw_networkx_nodes(
        graph,
        positions,
        ax=axis,
        node_size=node_sizes,
        node_color=list(rankings.values()),
        cmap="viridis",
        alpha=0.9,
        linewidths=0.5,
        edgecolors="white",
    )
    nx.draw_networkx_labels(
        graph,
        positions,
        labels=labels,
        ax=axis,
        font_size=7,
    )

    axis.set_title(
        f"{graph.graph.get('description', 'College football win graph')}\n"
        f"{graph.number_of_nodes()} teams, {graph.number_of_edges()} edges"
    )
    axis.axis("off")
    figure.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=200, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close(figure)

    print(f"Saved visualization: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize a college football GraphML win graph."
    )
    parser.add_argument(
        "graph_file",
        type=Path,
        nargs="?",
        help="Path to a GraphML file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output image path. Defaults to the GraphML filename with .png.",
    )
    parser.add_argument(
        "--labels",
        type=int,
        default=25,
        help="Number of highest-PageRank teams to label; use 0 to hide labels.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open the graph in an interactive window after saving it.",
    )

    args = parser.parse_args()

    if not args.graph_file:
        parser.print_help()
        return

    if not args.graph_file.exists():
        raise FileNotFoundError(f"GraphML file not found: {args.graph_file}")
    if args.labels < 0:
        raise ValueError("--labels must be zero or greater")

    output_path = args.output or args.graph_file.with_suffix(".png")
    visualize_graph(
        args.graph_file,
        output_path,
        args.labels,
        args.show,
    )


if __name__ == "__main__":
    main()
