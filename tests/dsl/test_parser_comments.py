"""Tests for DSL parser comment support."""

import pytest

from nichiyou_daiku.dsl import parse_dsl


class TestCommentSupport:
    """Test single-line comment support in DSL."""

    def test_parse_single_line_comment(self):
        """Test parsing a single-line comment."""
        dsl = """
        // This is a comment
        (beam1:2x4 {"length": 1000})
        """
        model = parse_dsl(dsl)
        assert len(model.pieces) == 1
        assert "beam1" in model.pieces

    def test_parse_comment_at_end_of_line(self):
        """Test parsing comment at the end of a line."""
        dsl = """
        (beam1:2x4 {"length": 1000})  // This is a beam
        (beam2:2x4 =800)  // Using compact notation
        """
        model = parse_dsl(dsl)
        assert len(model.pieces) == 2
        assert model.pieces["beam1"].length == 1000.0
        assert model.pieces["beam2"].length == 800.0

    def test_parse_multiple_comments(self):
        """Test parsing multiple comment lines."""
        dsl = """
        // Project: Simple Table
        // Author: Test
        // Date: 2024-01-01
        
        (leg1:2x4 =720)
        (leg2:2x4 =720)
        
        // Define connection
        leg1 -[TF<0 BD<0]- leg2
        """
        model = parse_dsl(dsl)
        assert len(model.pieces) == 2
        assert len(model.connections) == 1

    def test_parse_comment_only_lines(self):
        """Test parsing file with only comments should fail."""
        dsl = """
        // Just comments
        // No actual DSL content
        """
        from nichiyou_daiku.dsl.exceptions import DSLSyntaxError
        with pytest.raises(DSLSyntaxError) as exc_info:
            parse_dsl(dsl)
        # The grammar expects at least one statement, so this will fail with a syntax error
        assert "Unexpected token" in str(exc_info.value) or "Expected" in str(exc_info.value)

    def test_parse_comment_with_special_characters(self):
        """Test parsing comments with special characters."""
        dsl = """
        // Comment with special chars: !@#$%^&*()_+-=[]{}|;':",./<>?
        (beam1:2x4 =1000)  // Price: $50, Size: 2"x4"
        """
        model = parse_dsl(dsl)
        assert len(model.pieces) == 1
        assert model.pieces["beam1"].length == 1000.0

    def test_parse_empty_comment(self):
        """Test parsing empty comment lines."""
        dsl = """
        //
        (beam1:2x4 =1000)
        //
        """
        model = parse_dsl(dsl)
        assert len(model.pieces) == 1

    def test_parse_comment_with_dsl_syntax(self):
        """Test that DSL syntax in comments is ignored."""
        dsl = """
        // (ignored:2x4 =500) - this should be ignored
        (real:2x4 =1000)
        // beam1 -[TF<0 BD<0]- beam2  // This connection is commented out
        """
        model = parse_dsl(dsl)
        assert len(model.pieces) == 1
        assert "real" in model.pieces
        assert "ignored" not in model.pieces
        assert len(model.connections) == 0

    def test_parse_mixed_content_with_comments(self):
        """Test parsing a complete DSL file with comments."""
        dsl = """
        // Table design with 4 legs and 2 aprons
        
        // Define legs
        (leg1:2x4 =720)  // Front left
        (leg2:2x4 =720)  // Front right
        (leg3:2x4 =720)  // Back left
        (leg4:2x4 =720)  // Back right
        
        // Define aprons
        (apron_front:2x4 =600)
        (apron_back:2x4 =600)
        
        // Connect legs to aprons
        leg1 -[LB>0 DB>0]- apron_front  // Left side
        leg2 -[RF>0 TF>0]- apron_front  // Right side
        
        // Back connections
        leg3 -[LB>0 DB>0]- apron_back
        leg4 -[RF>0 TF>0]- apron_back
        """
        model = parse_dsl(dsl)
        
        # Check pieces
        assert len(model.pieces) == 6
        assert all(f"leg{i}" in model.pieces for i in range(1, 5))
        assert "apron_front" in model.pieces
        assert "apron_back" in model.pieces
        
        # Check connections
        assert len(model.connections) == 4

    def test_parse_comment_not_affecting_string_literals(self):
        """Test that // inside string literals is not treated as comment."""
        dsl = """
        (beam1:2x4 {"length": 1000, "note": "Size: 2x4 // standard"})
        """
        model = parse_dsl(dsl)
        assert len(model.pieces) == 1
        # Note: Current implementation only uses length, but parsing should not fail