"""Tests for build123d export functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from nichiyou_daiku.core.assembly import Assembly, JointPair, Joint
from nichiyou_daiku.core.geometry import Box, Shape3D, Point3D, Vector3D, Orientation3D


class TestAssemblyToBuild123d:
    """Test assembly_to_build123d conversion function."""

    def test_should_handle_import_error_gracefully(self):
        """Should raise ImportError with helpful message when build123d not available."""
        # Create minimal assembly
        assembly = Assembly(boxes={}, joints={}, label="test_assembly")

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

    @patch("nichiyou_daiku.shell.build123d_export.Compound")
    def test_should_convert_empty_assembly(self, mock_compound_class):
        """Should handle empty assembly without errors."""
        # Create empty assembly
        assembly = Assembly(boxes={}, joints={}, label="test_assembly")

        mock_compound_instance = Mock()
        mock_compound_class.return_value = mock_compound_instance

        from nichiyou_daiku.shell.build123d_export import assembly_to_build123d

        result = assembly_to_build123d(assembly)

        assert result == mock_compound_instance
        mock_compound_class.assert_called_once_with(label="test_assembly", children=[])

    @patch("nichiyou_daiku.shell.build123d_export.fillet")
    @patch("nichiyou_daiku.shell.build123d_export.Axis")
    @patch("nichiyou_daiku.shell.build123d_export.Align")
    @patch("nichiyou_daiku.shell.build123d_export.Part")
    @patch("nichiyou_daiku.shell.build123d_export.Box")
    @patch("nichiyou_daiku.shell.build123d_export.Compound")
    def test_should_create_boxes_for_each_piece(
        self,
        mock_compound_class,
        mock_box_class,
        mock_part_class,
        mock_align,
        mock_axis,
        mock_fillet,
    ):
        """Should create build123d Box for each piece in assembly."""
        # Create assembly with two boxes
        box1 = Box(shape=Shape3D(width=100.0, height=50.0, length=200.0))
        box2 = Box(shape=Shape3D(width=80.0, height=40.0, length=150.0))

        assembly = Assembly(
            boxes={"p1": box1, "p2": box2}, joints={}, label="test_assembly"
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
        mock_box_class.side_effect = [mock_box1, mock_box2]
        mock_box1.__add__.return_value = mock_part1
        mock_box2.__add__.return_value = mock_part2
        mock_align.MIN = "MIN"
        mock_axis.X = "X"

        # Mock fillet to return filleted parts without wrapped attribute
        # This will make the implementation use the filleted result directly
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

        mock_fillet.side_effect = mock_fillet_func

        # Part class should return empty part when called with no args
        mock_part_class.return_value = mock_empty_part

        mock_compound_instance = Mock()
        mock_compound_class.return_value = mock_compound_instance

        from nichiyou_daiku.shell.build123d_export import assembly_to_build123d

        result = assembly_to_build123d(assembly)

        # Verify boxes were created with correct dimensions
        assert mock_box_class.call_count == 2
        mock_box_class.assert_any_call(
            length=200.0, width=100.0, height=50.0, align="MIN"
        )
        mock_box_class.assert_any_call(
            length=150.0, width=80.0, height=40.0, align="MIN"
        )

        # Verify fillets were applied
        assert mock_fillet.call_count == 2

        # Verify Compound was created
        mock_compound_class.assert_called_once()
        call_kwargs = mock_compound_class.call_args[1]
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

    @patch("nichiyou_daiku.shell.build123d_export.fillet")
    @patch("nichiyou_daiku.shell.build123d_export.Axis")
    @patch("nichiyou_daiku.shell.build123d_export.Align")
    @patch("nichiyou_daiku.shell.build123d_export.Location")
    @patch("nichiyou_daiku.shell.build123d_export.RigidJoint")
    @patch("nichiyou_daiku.shell.build123d_export.Part")
    @patch("nichiyou_daiku.shell.build123d_export.Box")
    @patch("nichiyou_daiku.shell.build123d_export.Compound")
    def test_should_position_connected_pieces(
        self,
        mock_compound_class,
        mock_box_class,
        mock_part_class,
        mock_rigid_joint_class,
        mock_location_class,
        mock_align,
        mock_axis,
        mock_fillet,
    ):
        """Should position pieces based on connection joint positions using RigidJoints."""
        # Create assembly with connection
        box1 = Box(shape=Shape3D(width=100.0, height=50.0, length=200.0))
        box2 = Box(shape=Shape3D(width=100.0, height=50.0, length=200.0))

        joint1 = Joint(
            position=Point3D(x=50.0, y=25.0, z=100.0),
            orientation=Orientation3D.of(
                direction=Vector3D(x=0.0, y=0.0, z=1.0),
                up=Vector3D(x=0.0, y=1.0, z=0.0),
            ),
        )
        joint2 = Joint(
            position=Point3D(x=0.0, y=0.0, z=0.0),
            orientation=Orientation3D.of(
                direction=Vector3D(x=0.0, y=0.0, z=-1.0),
                up=Vector3D(x=0.0, y=1.0, z=0.0),
            ),
        )

        connection = JointPair(lhs=joint1, rhs=joint2)

        assembly = Assembly(
            boxes={"base": box1, "target": box2},
            joints={("base", "target"): connection},
            label="test_assembly",
        )

        # Create all the parts we'll need
        filleted_parts = []
        created_rigid_joints = []

        # Configure mocks
        mock_align.MIN = "MIN"
        mock_axis.X = "X"

        # Part() should return an empty part mock
        mock_empty_part = Mock()
        mock_part_class.return_value = mock_empty_part

        # Track box creation and configure parts
        created_boxes = []
        created_parts = []

        def create_box(**kwargs):
            box = MagicMock()
            created_boxes.append(box)
            # Configure the box to return a unique part when added to Part()
            part = MagicMock()
            part.label = f"part_{len(created_boxes)}"
            part.joints = {}
            # Configure edges for fillet
            mock_edges = Mock()
            mock_edges.filter_by = Mock(return_value=mock_edges)
            part.edges = Mock(return_value=mock_edges)
            box.__add__.return_value = part
            created_parts.append(part)
            return box

        mock_box_class.side_effect = create_box

        # Track filleted parts
        def track_fillet(obj, radius):
            # Create a new mock object that represents the filleted result
            filleted_part = MagicMock()
            filleted_part.joints = {}
            # Make sure it doesn't have wrapped attribute so it's used directly
            del filleted_part.wrapped
            filleted_parts.append(filleted_part)
            return filleted_part

        mock_fillet.side_effect = track_fillet

        # Create locations
        mock_location_base = Mock()
        mock_location_target = Mock()
        mock_location_class.side_effect = [mock_location_base, mock_location_target]

        # Track rigid joint creation
        def create_rigid_joint(label, to_part, joint_location):
            joint = Mock()
            # Add connect_to method to the joint
            joint.connect_to = Mock()
            created_rigid_joints.append(
                {
                    "label": label,
                    "to_part": to_part,
                    "joint_location": joint_location,
                    "joint": joint,
                }
            )
            # Make sure to_part has a joints dict if it doesn't already
            if not hasattr(to_part, "joints"):
                to_part.joints = {}
            elif not isinstance(to_part.joints, dict):
                to_part.joints = {}
            # Set the joint on the part
            to_part.joints[label] = joint
            return joint

        mock_rigid_joint_class.side_effect = create_rigid_joint

        mock_compound_instance = Mock()
        mock_compound_class.return_value = mock_compound_instance

        from nichiyou_daiku.shell.build123d_export import assembly_to_build123d

        assembly_to_build123d(assembly)

        # Verify RigidJoints were created
        assert len(created_rigid_joints) == 2

        # Verify boxes were created
        assert len(created_boxes) == 2

        # Verify parts were filleted
        assert len(filleted_parts) == 2

        # Check that filleted parts have labels set
        assert filleted_parts[0].label == "base"
        assert filleted_parts[1].label == "target"

        # Check rigid joints details
        base_joint_info = created_rigid_joints[0]
        target_joint_info = created_rigid_joints[1]

        assert base_joint_info["label"] == "to_target"
        assert base_joint_info["joint_location"] == mock_location_base
        assert base_joint_info["to_part"] == filleted_parts[0]  # The base part

        assert target_joint_info["label"] == "to_base"
        assert target_joint_info["joint_location"] == mock_location_target
        assert target_joint_info["to_part"] == filleted_parts[1]  # The target part

        # Verify Location objects were created with correct positions
        assert mock_location_class.call_count == 2

        # Check location calls
        loc_calls = mock_location_class.call_args_list

        # Base location
        assert loc_calls[0][0][0] == (50.0, 25.0, 100.0)
        angles = loc_calls[0][0][1]
        assert len(angles) == 3
        assert all(isinstance(a, (int, float)) for a in angles)

        # Target location
        assert loc_calls[1][0][0] == (0.0, 0.0, 0.0)
        angles = loc_calls[1][0][1]
        assert len(angles) == 3
        assert all(isinstance(a, (int, float)) for a in angles)

        # Verify joints were connected
        # Find which joints were created
        to_target_joint = None
        to_base_joint = None

        for joint_info in created_rigid_joints:
            if joint_info["label"] == "to_target":
                to_target_joint = joint_info["joint"]
            elif joint_info["label"] == "to_base":
                to_base_joint = joint_info["joint"]

        assert to_target_joint is not None
        assert to_base_joint is not None
        assert to_target_joint.connect_to.called
        assert to_target_joint.connect_to.call_args[0][0] == to_base_joint
