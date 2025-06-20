"""Tests for build123d export functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from nichiyou_daiku.core.assembly import Assembly, Connection, Joint
from nichiyou_daiku.core.geometry import Box, Shape3D, Point3D, Vector3D
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d


class TestAssemblyToBuild123d:
    """Test assembly_to_build123d conversion function."""
    
    def test_should_handle_import_error_gracefully(self):
        """Should raise ImportError with helpful message when build123d not available."""
        # Create minimal assembly
        assembly = Assembly(boxes={}, connections={})
        
        # Mock the import to fail
        with patch.dict('sys.modules', {'build123d': None}):
            with pytest.raises(ImportError) as exc_info:
                assembly_to_build123d(assembly)
            
            assert "build123d is required" in str(exc_info.value)
            assert "pip install build123d" in str(exc_info.value)
    
    def test_should_convert_empty_assembly(self):
        """Should handle empty assembly without errors."""
        # Create empty assembly
        assembly = Assembly(boxes={}, connections={})
        
        mock_compound_instance = Mock()
        mock_compound_class = Mock(return_value=mock_compound_instance)
        
        mock_b3d = MagicMock()
        mock_b3d.Box = Mock()
        mock_b3d.Compound = mock_compound_class
        mock_b3d.Part = Mock()
        mock_b3d.Location = Mock()
        mock_b3d.Vector = Mock()
        mock_b3d.RigidJoint = Mock()
        mock_b3d.Align = MagicMock()
        mock_b3d.Align.MIN = Mock()
        
        with patch.dict('sys.modules', {'build123d': mock_b3d}):
            result = assembly_to_build123d(assembly)
        
        assert result == mock_compound_instance
        mock_compound_class.assert_called_once_with([])
    
    def test_should_create_boxes_for_each_piece(self):
        """Should create build123d Box for each piece in assembly."""
        # Create assembly with two boxes
        box1 = Box(shape=Shape3D(width=100.0, height=50.0, length=200.0))
        box2 = Box(shape=Shape3D(width=80.0, height=40.0, length=150.0))
        
        assembly = Assembly(
            boxes={"p1": box1, "p2": box2},
            connections={}
        )
        
        # Create mocks for build123d objects
        mock_box1 = Mock(wrapped=Mock())
        mock_box2 = Mock(wrapped=Mock())
        mock_part1 = Mock()
        mock_part2 = Mock()
        
        # Create mock build123d module
        mock_b3d = MagicMock()
        
        # Configure Box class to return our mock instances
        mock_b3d.Box.side_effect = [mock_box1, mock_box2]
        
        # Configure Part class
        mock_b3d.Part.side_effect = [mock_part1, mock_part2]
        
        # Configure Compound class
        mock_compound = Mock()
        mock_b3d.Compound.return_value = mock_compound
        
        mock_b3d.Location = Mock()
        mock_b3d.Vector = Mock()
        mock_b3d.RigidJoint = Mock()
        mock_b3d.Align = MagicMock()
        mock_b3d.Align.MIN = Mock()
        
        with patch.dict('sys.modules', {'build123d': mock_b3d}):
            result = assembly_to_build123d(assembly)
        
        # Verify boxes were created with correct dimensions
        assert mock_b3d.Box.call_count == 2
        
        # Check box dimensions
        box_calls = mock_b3d.Box.call_args_list
        dimensions_called = [
            (call[1]['length'], call[1]['width'], call[1]['height'])
            for call in box_calls
        ]
        
        # Verify both sets of dimensions are present
        assert (200.0, 100.0, 50.0) in dimensions_called
        assert (150.0, 80.0, 40.0) in dimensions_called
        
        # Verify Parts were created
        assert mock_b3d.Part.call_count == 2
        mock_b3d.Part.assert_any_call(mock_box1.wrapped)
        mock_b3d.Part.assert_any_call(mock_box2.wrapped)
        
        # Verify Compound was created with all parts
        mock_b3d.Compound.assert_called_once()
        parts_arg = mock_b3d.Compound.call_args[0][0]
        assert len(parts_arg) == 2
        assert mock_part1 in parts_arg
        assert mock_part2 in parts_arg
    
    def test_should_position_connected_pieces(self):
        """Should position pieces based on connection joint positions using RigidJoints."""
        # Create assembly with connection
        box1 = Box(shape=Shape3D(width=100.0, height=50.0, length=200.0))
        box2 = Box(shape=Shape3D(width=100.0, height=50.0, length=200.0))
        
        joint1 = Joint(
            position=Point3D(x=50.0, y=25.0, z=100.0),
            direction=Vector3D(x=0.0, y=0.0, z=1.0)
        )
        joint2 = Joint(
            position=Point3D(x=0.0, y=0.0, z=0.0),
            direction=Vector3D(x=0.0, y=0.0, z=-1.0)
        )
        
        connection = Connection(joint1=joint1, joint2=joint2)
        
        assembly = Assembly(
            boxes={"base": box1, "target": box2},
            connections={("base", "target"): connection}
        )
        
        # Create mocks
        mock_box = Mock(wrapped=Mock())
        mock_part_base = Mock()
        mock_part_target = Mock()
        mock_location_base = Mock()
        mock_location_target = Mock()
        mock_rigid_joint_base = Mock()
        mock_rigid_joint_target = Mock()
        
        # Create mock build123d module
        mock_b3d = MagicMock()
        mock_b3d.Box.return_value = mock_box
        mock_b3d.Part.side_effect = [mock_part_base, mock_part_target]
        mock_b3d.Location.side_effect = [mock_location_base, mock_location_target]
        mock_b3d.RigidJoint.side_effect = [mock_rigid_joint_base, mock_rigid_joint_target]
        mock_b3d.Compound = Mock()
        mock_b3d.Vector = Mock()
        mock_b3d.Align = MagicMock()
        mock_b3d.Align.MIN = Mock()
        
        with patch.dict('sys.modules', {'build123d': mock_b3d}):
            assembly_to_build123d(assembly)
        
        # Verify RigidJoints were created
        assert mock_b3d.RigidJoint.call_count == 2
        
        # Check base rigid joint
        base_call = mock_b3d.RigidJoint.call_args_list[0]
        assert base_call[1]['label'] == "base_to_target"
        assert base_call[1]['to_part'] == mock_part_base
        
        # Check target rigid joint  
        target_call = mock_b3d.RigidJoint.call_args_list[1]
        assert target_call[1]['label'] == "target_to_base"
        assert target_call[1]['to_part'] == mock_part_target
        
        # Verify Location objects were created with correct positions
        assert mock_b3d.Location.call_count == 2
        
        # Base location should have position and Euler angles
        base_loc_call = mock_b3d.Location.call_args_list[0]
        assert base_loc_call[0][0] == (50.0, 25.0, 100.0)  # position
        # Direction (0,0,1) converts to (0,0,0) Euler angles
        assert base_loc_call[0][1] == (0.0, 0.0, 0.0)      # Euler angles
        
        # Target location should have negated direction as Euler angles
        target_loc_call = mock_b3d.Location.call_args_list[1]
        assert target_loc_call[0][0] == (0.0, 0.0, 0.0)    # position
        # Direction (0,0,-1) negated becomes (0,0,1) which converts to (0,0,0) Euler angles
        assert target_loc_call[0][1] == (0.0, 0.0, 0.0)    # Euler angles
        
        # Verify joints were connected
        mock_rigid_joint_base.connect_to.assert_called_once_with(mock_rigid_joint_target)