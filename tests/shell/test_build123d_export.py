"""Tests for build123d export functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from nichiyou_daiku.core.assembly import Assembly, JointPair, Joint as NichiyouJoint
from nichiyou_daiku.core.geometry import Box, Shape3D, Point3D, Vector3D, Orientation3D


class TestAssemblyToBuild123d:
    """Test assembly_to_build123d conversion function."""

    def test_should_handle_import_error_gracefully(self):
        """Should raise ImportError with helpful message when build123d not available."""
        from nichiyou_daiku.core.model import Model

        # Create minimal model and assembly
        model = Model.of(pieces=[], connections=[])
        assembly = Assembly(
            model=model, boxes={}, joints={}, joint_pairs=[], label="test_assembly"
        )

        # Temporarily set the flag to simulate build123d not being available
        import nichiyou_daiku.shell.build123d_export as export_module

        original_available = export_module.HAS_BUILD123D

        try:
            export_module.HAS_BUILD123D = False

            from nichiyou_daiku.shell.build123d_export import assembly_to_build123d

            with pytest.raises(ImportError) as exc_info:
                assembly_to_build123d(assembly)

            assert "build123d is required" in str(exc_info.value)
            assert "pip install nichiyou-daiku[viz]" in str(exc_info.value)
        finally:
            # Restore original value
            export_module.HAS_BUILD123D = original_available

    def test_should_convert_empty_assembly(self):
        """Should handle empty assembly without errors."""
        # Patch the entire module to inject mocks
        with patch.dict("sys.modules", {"build123d": MagicMock()}):
            # Now we can safely import and patch
            import nichiyou_daiku.shell.build123d_export as export_module

            # Temporarily set build123d as available
            original_available = export_module.HAS_BUILD123D
            export_module.HAS_BUILD123D = True

            try:
                # Reload to pick up mocked build123d
                import importlib

                importlib.reload(export_module)

                from nichiyou_daiku.core.model import Model

                # Create empty model and assembly
                model = Model.of(pieces=[], connections=[])
                assembly = Assembly(
                    model=model,
                    boxes={},
                    joints={},
                    joint_pairs=[],
                    label="test_assembly",
                )

                # Mock the Compound class
                mock_compound_instance = Mock()
                export_module.Compound = Mock(return_value=mock_compound_instance)

                result = export_module.assembly_to_build123d(assembly)

                assert result == mock_compound_instance
                export_module.Compound.assert_called_once_with(
                    label="test_assembly", children=[]
                )

            finally:
                export_module.HAS_BUILD123D = original_available
                importlib.reload(export_module)

    def test_should_create_boxes_for_each_piece(self):
        """Should create build123d Box for each piece in assembly."""
        # Patch the entire module to inject mocks
        with patch.dict("sys.modules", {"build123d": MagicMock()}):
            import nichiyou_daiku.shell.build123d_export as export_module

            # Temporarily set build123d as available
            original_available = export_module.HAS_BUILD123D
            export_module.HAS_BUILD123D = True

            try:
                # Reload to pick up mocked build123d
                import importlib

                importlib.reload(export_module)

                from nichiyou_daiku.core.model import Model

                # Create assembly with two boxes
                box1 = Box(shape=Shape3D(width=100.0, height=50.0, length=200.0))
                box2 = Box(shape=Shape3D(width=80.0, height=40.0, length=150.0))

                model = Model.of(pieces=[], connections=[])
                assembly = Assembly(
                    model=model,
                    boxes={"p1": box1, "p2": box2},
                    joints={},
                    joint_pairs=[],
                    label="test_assembly",
                )

                # Setup mocks
                mock_box1 = MagicMock()
                mock_box2 = MagicMock()
                mock_part1 = Mock()
                mock_part1.label = "p1"
                mock_part2 = Mock()
                mock_part2.label = "p2"

                # Part() should return an empty part mock when called with no args
                mock_empty_part = Mock()

                # Configure edges mock for fillet
                mock_edges1 = Mock()
                mock_edges1.filter_by = Mock(return_value=mock_edges1)
                mock_part1.edges = Mock(return_value=mock_edges1)

                mock_edges2 = Mock()
                mock_edges2.filter_by = Mock(return_value=mock_edges2)
                mock_part2.edges = Mock(return_value=mock_edges2)

                # Configure mocks
                export_module.Box = Mock(side_effect=[mock_box1, mock_box2])
                mock_box1.__add__.return_value = mock_part1
                mock_box2.__add__.return_value = mock_part2
                export_module.Align = Mock()
                export_module.Align.MIN = "MIN"
                export_module.Axis = Mock()
                export_module.Axis.X = "X"

                # Mock fillet to return filleted parts
                filleted_parts = []
                mock_filleted_part1 = Mock()
                mock_filleted_part2 = Mock()
                # Make sure they don't have wrapped attribute
                del mock_filleted_part1.wrapped
                del mock_filleted_part2.wrapped

                def mock_fillet_func(obj, radius):
                    # Return different filleted parts based on the input
                    if obj == mock_edges1:
                        filleted_parts.append(mock_filleted_part1)
                        return mock_filleted_part1
                    elif obj == mock_edges2:
                        filleted_parts.append(mock_filleted_part2)
                        return mock_filleted_part2
                    else:
                        raise ValueError(f"Unexpected obj: {obj}")

                export_module.fillet = Mock(side_effect=mock_fillet_func)

                # Part class should return empty part when called with no args
                export_module.Part = Mock(return_value=mock_empty_part)

                mock_compound_instance = Mock()
                export_module.Compound = Mock(return_value=mock_compound_instance)

                result = export_module.assembly_to_build123d(assembly)

                # Verify Box was created with correct dimensions
                assert export_module.Box.call_count == 2
                export_module.Box.assert_any_call(
                    length=200.0, width=100.0, height=50.0, align="MIN"
                )
                export_module.Box.assert_any_call(
                    length=150.0, width=80.0, height=40.0, align="MIN"
                )

                # Verify fillets were applied
                assert export_module.fillet.call_count == 2

                # Verify Compound was created
                export_module.Compound.assert_called_once()
                call_kwargs = export_module.Compound.call_args[1]
                assert call_kwargs["label"] == "test_assembly"
                assert len(call_kwargs["children"]) == 2
                # Check that parts were created
                assert len(filleted_parts) == 2
                children = call_kwargs["children"]
                assert len(children) == 2
                # The filleted parts should be in the compound's children
                assert mock_filleted_part1 in children
                assert mock_filleted_part2 in children
                # Check that labels were set on the filleted parts
                assert mock_filleted_part1.label == "p1"
                assert mock_filleted_part2.label == "p2"
                assert result == mock_compound_instance

            finally:
                export_module.HAS_BUILD123D = original_available
                importlib.reload(export_module)

    def test_should_position_connected_pieces(self):
        """Should position pieces based on connection joint positions using RigidJoints."""
        # Patch the entire module to inject mocks
        with patch.dict("sys.modules", {"build123d": MagicMock()}):
            import nichiyou_daiku.shell.build123d_export as export_module

            # Temporarily set build123d as available
            original_available = export_module.HAS_BUILD123D
            export_module.HAS_BUILD123D = True

            try:
                # Reload to pick up mocked build123d
                import importlib

                importlib.reload(export_module)

                from nichiyou_daiku.core.model import Model

                # Create assembly with connection
                box1 = Box(shape=Shape3D(width=100.0, height=50.0, length=200.0))
                box2 = Box(shape=Shape3D(width=100.0, height=50.0, length=200.0))

                joint1 = NichiyouJoint(
                    id="joint1",
                    position=Point3D(x=50.0, y=25.0, z=100.0),
                    orientation=Orientation3D.of(
                        direction=Vector3D(x=0.0, y=0.0, z=1.0),
                        up=Vector3D(x=1.0, y=0.0, z=0.0),
                    ),
                )
                joint2 = NichiyouJoint(
                    id="joint2",
                    position=Point3D(x=-50.0, y=-25.0, z=-100.0),
                    orientation=Orientation3D.of(
                        direction=Vector3D(x=0.0, y=0.0, z=-1.0),
                        up=Vector3D(x=-1.0, y=0.0, z=0.0),
                    ),
                )

                # Mock model with connections for joint_pair_to_pieces mapping
                from nichiyou_daiku.core.piece import Piece, PieceType
                from nichiyou_daiku.core.connection import Connection, Anchor
                from nichiyou_daiku.core.geometry import FromMin
                from nichiyou_daiku.core.model import PiecePair

                p1 = Piece.of(PieceType.PT_2x4, 200.0, "p1")
                p2 = Piece.of(PieceType.PT_2x4, 200.0, "p2")
                conn = Connection(
                    lhs=Anchor(contact_face="front", edge_shared_face="top", offset=FromMin(value=0)),
                    rhs=Anchor(contact_face="down", edge_shared_face="front", offset=FromMin(value=0)),
                )
                model = Model.of(pieces=[p1, p2], connections=[(PiecePair(base=p1, target=p2), conn)])

                assembly = Assembly(
                    model=model,
                    boxes={"p1": box1, "p2": box2},
                    joints={"joint1": joint1, "joint2": joint2},
                    joint_pairs=[("joint1", "joint2")],
                    label="test_assembly",
                )

                # Setup mocks
                mock_box1 = MagicMock()
                mock_box2 = MagicMock()
                mock_part1 = Mock()
                mock_part1.label = "p1"
                mock_part2 = Mock()
                mock_part2.label = "p2"
                mock_empty_part = Mock()

                # Configure edges mock for fillet
                mock_edges1 = Mock()
                mock_edges1.filter_by = Mock(return_value=mock_edges1)
                mock_part1.edges = Mock(return_value=mock_edges1)

                mock_edges2 = Mock()
                mock_edges2.filter_by = Mock(return_value=mock_edges2)
                mock_part2.edges = Mock(return_value=mock_edges2)

                # Setup basic mocks
                export_module.Box = Mock(side_effect=[mock_box1, mock_box2])
                mock_box1.__add__.return_value = mock_part1
                mock_box2.__add__.return_value = mock_part2
                export_module.Part = Mock(return_value=mock_empty_part)
                export_module.Align = Mock()
                export_module.Align.MIN = "MIN"
                export_module.Axis = Mock()
                export_module.Axis.X = "X"

                # Mock fillet to return filleted parts
                mock_filleted_part1 = Mock()
                mock_filleted_part2 = Mock()
                del mock_filleted_part1.wrapped
                del mock_filleted_part2.wrapped

                # Set up joints dictionaries for the filleted parts
                mock_joint_p1_to_joint2 = Mock()
                mock_joint_p2_to_joint1 = Mock()
                mock_joint_p1_to_joint2.connect_to = Mock()
                mock_filleted_part1.joints = {"to_joint2": mock_joint_p1_to_joint2}
                mock_filleted_part2.joints = {"to_joint1": mock_joint_p2_to_joint1}

                def mock_fillet_func(obj, radius):
                    if obj == mock_edges1:
                        return mock_filleted_part1
                    elif obj == mock_edges2:
                        return mock_filleted_part2

                export_module.fillet = Mock(side_effect=mock_fillet_func)

                # Mock Location and RigidJoint
                mock_location1 = Mock()
                mock_location2 = Mock()
                export_module.Location = Mock(
                    side_effect=[mock_location1, mock_location2]
                )

                # Mock RigidJoint to return the joints we set up
                def mock_rigid_joint_func(label, to_part, joint_location):
                    if label == "to_joint2" and to_part == mock_filleted_part1:
                        return mock_joint_p1_to_joint2
                    elif label == "to_joint1" and to_part == mock_filleted_part2:
                        return mock_joint_p2_to_joint1
                    else:
                        return Mock()

                export_module.RigidJoint = Mock(side_effect=mock_rigid_joint_func)

                mock_compound_instance = Mock()
                export_module.Compound = Mock(return_value=mock_compound_instance)

                result = export_module.assembly_to_build123d(assembly)

                # Verify RigidJoint was created properly for both joints
                assert export_module.RigidJoint.call_count == 2
                # Joints are now labeled by joint IDs, not piece IDs
                export_module.RigidJoint.assert_any_call(
                    label="to_joint2",
                    to_part=mock_filleted_part1,
                    joint_location=mock_location1,
                )
                export_module.RigidJoint.assert_any_call(
                    label="to_joint1",
                    to_part=mock_filleted_part2,
                    joint_location=mock_location2,
                )

                # Verify connect_to was called
                mock_joint_p1_to_joint2.connect_to.assert_called_once_with(
                    mock_joint_p2_to_joint1
                )

                # Verify result
                assert result == mock_compound_instance

            finally:
                export_module.HAS_BUILD123D = original_available
                importlib.reload(export_module)
