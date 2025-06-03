"""
Graph data structures for workflow orchestration.

Custom graph implementation to avoid LangChain dependency issues.
"""

from typing import Dict, List, Optional


class Node:
    """Represents a node in the workflow graph."""
    
    def __init__(self, id: str, label: str, type: str):
        self.id = id
        self.label = label
        self.type = type


class Edge:
    """Represents an edge/connection between nodes in the workflow graph."""
    
    def __init__(self, source: str, target: str, label: str):
        self.source = source
        self.target = target
        self.label = label


class Graph:
    """A graph data structure for representing workflow relationships."""
    
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
    
    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node
    
    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)
    
    def add_graph_documents(self, documents: List['GraphDocument']) -> None:
        """Add multiple graph documents to this graph."""
        for doc in documents:
            for node in doc.nodes:
                self.add_node(node)
            for edge in doc.edges:
                self.add_edge(edge)
    
    def get_node_ids(self) -> List[str]:
        """Get all node IDs in the graph."""
        return list(self.nodes.keys())
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by its ID."""
        return self.nodes.get(node_id)
    
    def get_edge_ids(self) -> List[int]:
        """Get all edge indices."""
        return [i for i in range(len(self.edges))]
    
    def get_edge(self, edge_id: int) -> Optional[Edge]:
        """Get an edge by its index."""
        if edge_id < len(self.edges):
            return self.edges[edge_id]
        return None


class GraphDocument:
    """A document containing graph nodes and edges."""
    
    def __init__(self, nodes: Optional[List[Node]] = None, edges: Optional[List[Edge]] = None):
        self.nodes = nodes or []
        self.edges = edges or []
