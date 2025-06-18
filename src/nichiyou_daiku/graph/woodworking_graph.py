"""Graph-based representation of woodworking assemblies.

This module provides a graph structure for managing lumber pieces and their
connections, enabling complex assembly modeling and analysis.
"""

from dataclasses import dataclass
import networkx as nx

from nichiyou_daiku.core.lumber import LumberPiece, LumberFace, LumberType
from nichiyou_daiku.connectors.general import GeneralJoint


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    joint: GeneralJoint


class WoodworkingGraph:
    """Graph representation of a woodworking assembly.

    This class wraps a NetworkX MultiDiGraph to represent furniture
    assemblies. Nodes represent lumber pieces and edges represent
    joints between them.
    """

    def __init__(self, lumbers: list[LumberPiece], joints: list[Edge]) -> None:
        """Initialize an empty woodworking graph."""
        self._graph = nx.MultiDiGraph()
        for lumber in lumbers:
            self._add_lumber_piece(lumber)
        for edge in joints:
            self._add_joint(edge.src, edge.dst, edge.joint)


    def get_lumber(self, lumber_id: str) -> LumberPiece | None:
        return self._graph.nodes.get(lumber_id)

    def get_joint(self, src_id: str, dst_id: str) -> GeneralJoint | None:
        return self._graph.edges.get((src_id, dst_id, 0), {}).get('data', None)

    def lumbers(self) -> list[tuple[str, LumberPiece]]:
        return [
            (node_id, data['data']) for node_id, data in self._graph.nodes(data=True)
        ]
    
    def joints(self) -> list[tuple[str, str, GeneralJoint]]:
        return [
            (src, dst, data['data']) for src, dst, data in self._graph.edges(data=True)
        ]

    def _add_lumber_piece(self, lumber: LumberPiece) -> None:
        """Add a lumber piece as a node in the graph.

        Args:
            lumber: The lumber piece to add

        Raises:
            ValueError: If lumber ID already exists in graph
        """
        if lumber.id in self._graph:
            raise ValueError(f"Lumber piece '{lumber.id}' already exists in graph")

        self._graph.add_node(lumber.id, data=lumber)

    def _add_joint(
        self,
        src_id: str,
        dst_id: str,
        joint: GeneralJoint,
    ) -> None:
        base_lumber = self.get_lumber(src_id)
        if base_lumber is None:
            raise ValueError(f"Source lumber '{src_id}' not found in graph")

        target_lumber = self.get_lumber(dst_id)
        if target_lumber is None:
            raise ValueError(f"Destination lumber '{dst_id}' not found in graph")

        self._graph.add_edge(src_id, dst_id, data=joint)