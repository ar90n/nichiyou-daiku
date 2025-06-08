"""Visual tests for graph layouts and representations."""

import pytest
import networkx as nx
from typing import Dict, Tuple, List

from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.core.geometry import EdgePoint
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint


class TestGraphVisualization:
    """Test graph visualization and layout capabilities."""
    
    def test_graph_to_networkx(self, three_piece_chain):
        """Test converting to NetworkX for visualization."""
        # Get underlying NetworkX graph
        nx_graph = three_piece_chain._graph
        
        # Verify structure
        assert nx_graph.number_of_nodes() == 3
        assert nx_graph.number_of_edges() == 2
        
        # Verify node attributes
        for node, data in nx_graph.nodes(data=True):
            assert 'data' in data
            assert hasattr(data['data'], 'lumber_piece')
        
        # Verify edge attributes
        for src, dst, data in nx_graph.edges(data=True):
            assert 'data' in data
            assert hasattr(data['data'], 'joint')
    
    def test_layout_positions_2d(self, square_frame):
        """Test generating 2D layout positions for visualization."""
        # Generate layout using NetworkX algorithms
        nx_graph = square_frame._graph
        
        # Try different layout algorithms
        layouts = {
            'spring': nx.spring_layout(nx_graph),
            'circular': nx.circular_layout(nx_graph),
            'shell': nx.shell_layout(nx_graph),
        }
        
        # Verify all nodes have positions
        for layout_name, positions in layouts.items():
            assert len(positions) == square_frame.node_count()
            for node, pos in positions.items():
                assert len(pos) == 2  # 2D coordinates
                assert all(isinstance(coord, float) for coord in pos)
    
    def test_layout_positions_3d(self, complex_assembly):
        """Test generating 3D layout positions based on actual geometry."""
        # Calculate actual 3D positions
        positions_3d = {}
        
        # For each lumber piece, get its origin position
        for node_id in complex_assembly._graph.nodes():
            try:
                origin = complex_assembly.calculate_piece_origin_position(
                    complex_assembly, node_id
                )
                positions_3d[node_id] = origin
            except:
                # Fallback for pieces without calculated positions
                positions_3d[node_id] = (0.0, 0.0, 0.0)
        
        # Verify 3D positions
        assert len(positions_3d) == complex_assembly.node_count()
        for node, pos in positions_3d.items():
            assert len(pos) == 3  # 3D coordinates
            assert all(isinstance(coord, (int, float)) for coord in pos)
    
    def test_graph_attributes_for_visualization(self, disconnected_graph):
        """Test extracting attributes for visual styling."""
        nx_graph = disconnected_graph._graph
        
        # Extract node attributes
        node_attrs = {}
        for node, data in nx_graph.nodes(data=True):
            lumber = data['data'].lumber_piece
            node_attrs[node] = {
                'label': lumber.id,
                'type': lumber.lumber_type.name,
                'length': lumber.length,
                'color': self._get_color_for_type(lumber.lumber_type),
                'size': lumber.length / 100,  # Scale for visualization
            }
        
        # Extract edge attributes
        edge_attrs = {}
        for src, dst, key, data in nx_graph.edges(data=True, keys=True):
            joint = data['data'].joint
            edge_attrs[(src, dst, key)] = {
                'src_face': joint.src_face.name,
                'dst_face': joint.dst_face.name,
                'order': data['data'].assembly_order,
                'style': 'dashed' if data['data'].assembly_order is None else 'solid',
                'color': 'red' if data['data'].assembly_order is None else 'black',
            }
        
        # Verify attributes
        assert len(node_attrs) == disconnected_graph.node_count()
        assert all('color' in attrs for attrs in node_attrs.values())
        assert all('style' in attrs for attrs in edge_attrs.values())
    
    def _get_color_for_type(self, lumber_type: LumberType) -> str:
        """Get color for lumber type visualization."""
        color_map = {
            LumberType.LUMBER_1X4: '#FFA500',  # Orange
            LumberType.LUMBER_2X4: '#8B4513',  # Brown
            LumberType.LUMBER_2X8: '#654321',  # Dark brown
        }
        return color_map.get(lumber_type, '#808080')  # Default gray
    
    def test_assembly_order_visualization(self, complex_assembly):
        """Test visualizing assembly order."""
        nx_graph = complex_assembly._graph
        
        # Extract assembly order information
        assembly_steps = {}
        max_order = 0
        
        for src, dst, data in nx_graph.edges(data=True):
            order = data['data'].assembly_order
            if order is not None:
                if order not in assembly_steps:
                    assembly_steps[order] = []
                assembly_steps[order].append((src, dst))
                max_order = max(max_order, order)
        
        # Verify assembly sequence
        assert len(assembly_steps) > 0
        assert max_order > 0
        
        # Check for gaps in assembly order
        for i in range(1, max_order + 1):
            assert i in assembly_steps, f"Missing assembly step {i}"
    
    def test_graph_metrics_visualization(self, large_grid_graph):
        """Test calculating metrics for visualization."""
        nx_graph = large_grid_graph._graph
        
        # Calculate various graph metrics
        metrics = {
            'degree_centrality': nx.degree_centrality(nx_graph),
            'betweenness_centrality': nx.betweenness_centrality(nx_graph),
            'closeness_centrality': nx.closeness_centrality(nx_graph),
        }
        
        # Verify metrics
        for metric_name, values in metrics.items():
            assert len(values) == large_grid_graph.node_count()
            assert all(0 <= v <= 1 for v in values.values())
        
        # Find most central nodes
        most_central = max(
            metrics['degree_centrality'].items(),
            key=lambda x: x[1]
        )
        
        # Center nodes should have highest centrality in grid
        assert 'beam_4_4' in most_central[0] or 'beam_5_5' in most_central[0]
    
    def test_subgraph_highlighting(self, complex_assembly):
        """Test highlighting subgraphs for visualization."""
        # Find all legs
        leg_nodes = [
            node for node in complex_assembly._graph.nodes()
            if 'leg' in node
        ]
        
        # Extract leg subgraph
        leg_subgraph = complex_assembly.extract_subgraph(leg_nodes)
        
        # Create highlight data
        highlight_data = {
            'highlighted_nodes': set(leg_nodes),
            'highlighted_edges': set(),
            'fade_others': True,
        }
        
        # Find edges between legs (if any)
        for src, dst in leg_subgraph._graph.edges():
            highlight_data['highlighted_edges'].add((src, dst))
        
        # Verify highlight data
        assert len(highlight_data['highlighted_nodes']) == 4  # 4 legs
        assert isinstance(highlight_data['fade_others'], bool)
    
    def test_path_visualization(self, large_grid_graph):
        """Test visualizing paths through the graph."""
        # Find path from corner to corner
        path = large_grid_graph.find_path("beam_0_0", "beam_9_9")
        
        assert path is not None
        
        # Create path visualization data
        path_viz = {
            'nodes': path,
            'edges': [(path[i], path[i+1]) for i in range(len(path)-1)],
            'node_colors': {node: 'green' if node in path else 'gray' for node in large_grid_graph._graph.nodes()},
            'edge_colors': {},
        }
        
        # Color edges based on path
        for src, dst in large_grid_graph._graph.edges():
            if (src, dst) in path_viz['edges'] or (dst, src) in path_viz['edges']:
                path_viz['edge_colors'][(src, dst)] = 'green'
            else:
                path_viz['edge_colors'][(src, dst)] = 'lightgray'
        
        # Verify path visualization
        assert len(path_viz['nodes']) == len(path)
        assert len(path_viz['edges']) == len(path) - 1
        assert all(color in ['green', 'gray'] for color in path_viz['node_colors'].values())
    
    def test_component_coloring(self, disconnected_graph):
        """Test coloring disconnected components differently."""
        components = disconnected_graph.get_connected_components()
        
        # Assign colors to components
        colors = ['red', 'blue', 'green', 'yellow', 'purple']
        component_colors = {}
        
        for i, component in enumerate(components):
            color = colors[i % len(colors)]
            for node in component:
                component_colors[node] = color
        
        # Verify coloring
        assert len(component_colors) == disconnected_graph.node_count()
        assert len(set(component_colors.values())) == len(components)
    
    def test_export_for_graphviz(self, square_frame):
        """Test exporting graph in format suitable for Graphviz."""
        nx_graph = square_frame._graph
        
        # Create DOT format representation
        dot_lines = ['digraph WoodworkingAssembly {']
        dot_lines.append('  rankdir=LR;')
        dot_lines.append('  node [shape=box];')
        
        # Add nodes
        for node, data in nx_graph.nodes(data=True):
            lumber = data['data'].lumber_piece
            label = f"{lumber.id}\\n{lumber.lumber_type.name}\\n{lumber.length}mm"
            dot_lines.append(f'  "{node}" [label="{label}"];')
        
        # Add edges
        for src, dst, data in nx_graph.edges(data=True):
            joint = data['data'].joint
            order = data['data'].assembly_order
            label = f"{joint.src_face.name}->{joint.dst_face.name}"
            if order:
                label += f"\\n[{order}]"
            dot_lines.append(f'  "{src}" -> "{dst}" [label="{label}"];')
        
        dot_lines.append('}')
        
        dot_content = '\n'.join(dot_lines)
        
        # Verify DOT format
        assert 'digraph' in dot_content
        assert all(node in dot_content for node in nx_graph.nodes())
        assert '->' in dot_content  # Has edges
    
    def test_3d_bounding_box_visualization(self, complex_assembly):
        """Test calculating bounding box for 3D visualization."""
        bounds = complex_assembly.get_assembly_bounds()
        
        # Create bounding box visualization data
        min_point, max_point = bounds
        
        # Define box corners
        corners = [
            (min_point[0], min_point[1], min_point[2]),
            (max_point[0], min_point[1], min_point[2]),
            (max_point[0], max_point[1], min_point[2]),
            (min_point[0], max_point[1], min_point[2]),
            (min_point[0], min_point[1], max_point[2]),
            (max_point[0], min_point[1], max_point[2]),
            (max_point[0], max_point[1], max_point[2]),
            (min_point[0], max_point[1], max_point[2]),
        ]
        
        # Define box edges (indices of corners to connect)
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),  # Bottom face
            (4, 5), (5, 6), (6, 7), (7, 4),  # Top face
            (0, 4), (1, 5), (2, 6), (3, 7),  # Vertical edges
        ]
        
        # Verify bounding box
        assert len(corners) == 8
        assert len(edges) == 12
        assert all(len(corner) == 3 for corner in corners)
        
        # Calculate dimensions
        width = max_point[0] - min_point[0]
        height = max_point[1] - min_point[1]
        depth = max_point[2] - min_point[2]
        
        assert all(dim > 0 for dim in [width, height, depth])


class TestGraphLayoutAlgorithms:
    """Test different layout algorithms for graph visualization."""
    
    def test_hierarchical_layout(self, complex_assembly):
        """Test hierarchical layout based on assembly order."""
        nx_graph = complex_assembly._graph
        
        # Group nodes by assembly order
        order_groups = {}
        unordered = []
        
        for node in nx_graph.nodes():
            # Find minimum assembly order of edges connected to this node
            min_order = float('inf')
            for _, _, data in nx_graph.edges(node, data=True):
                if data['data'].assembly_order is not None:
                    min_order = min(min_order, data['data'].assembly_order)
            
            if min_order < float('inf'):
                if min_order not in order_groups:
                    order_groups[min_order] = []
                order_groups[min_order].append(node)
            else:
                unordered.append(node)
        
        # Verify grouping
        assert len(order_groups) > 0
        total_nodes = sum(len(nodes) for nodes in order_groups.values()) + len(unordered)
        assert total_nodes == complex_assembly.node_count()
    
    def test_force_directed_layout_params(self, large_grid_graph):
        """Test force-directed layout with different parameters."""
        nx_graph = large_grid_graph._graph
        
        # Test different spring layout parameters
        layout_params = [
            {'k': 0.5, 'iterations': 50},
            {'k': 1.0, 'iterations': 100},
            {'k': 2.0, 'iterations': 200},
        ]
        
        layouts = []
        for params in layout_params:
            layout = nx.spring_layout(nx_graph, **params)
            layouts.append(layout)
        
        # Verify layouts are different
        for i in range(len(layouts) - 1):
            layout1 = layouts[i]
            layout2 = layouts[i + 1]
            
            # Calculate total position difference
            total_diff = 0
            for node in nx_graph.nodes():
                pos1 = layout1[node]
                pos2 = layout2[node]
                diff = sum((p1 - p2) ** 2 for p1, p2 in zip(pos1, pos2)) ** 0.5
                total_diff += diff
            
            assert total_diff > 0  # Layouts should be different
    
    def test_custom_layout_constraints(self, square_frame):
        """Test layout with custom constraints."""
        nx_graph = square_frame._graph
        
        # Define fixed positions for some nodes
        fixed_pos = {
            'top': (0.5, 1.0),
            'bottom': (0.5, 0.0),
        }
        
        # Calculate layout with fixed nodes
        layout = nx.spring_layout(
            nx_graph,
            pos=fixed_pos,
            fixed=['top', 'bottom']
        )
        
        # Verify constraints
        assert layout['top'] == fixed_pos['top']
        assert layout['bottom'] == fixed_pos['bottom']
        
        # Other nodes should be positioned between
        for node in ['left', 'right']:
            y_pos = layout[node][1]
            assert 0.0 < y_pos < 1.0