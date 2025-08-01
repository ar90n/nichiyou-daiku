"""Integration tests for the DSL module."""

from nichiyou_daiku.core.geometry.offset import FromMax, FromMin
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import PieceType
from nichiyou_daiku.dsl import parse_dsl


class TestCompactNotationIntegration:
    """Integration tests for compact notation DSL."""

    def test_simple_structure_with_compact_notation(self):
        """Test parsing a simple structure using compact notation."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        (beam2:2x4 {"length": 800})
        (beam3:2x4 {"length": 600})
        
        beam1 -[TF<0 BD<0]- beam2
        beam2 -[RB>50 LT<100]- beam3
        """

        model = parse_dsl(dsl)

        assert isinstance(model, Model)
        assert len(model.pieces) == 3
        assert len(model.connections) == 2

        # Check first connection
        conn1 = model.connections[("beam1", "beam2")]
        assert conn1.lhs.contact_face == "top"
        assert conn1.lhs.edge_shared_face == "front"
        assert isinstance(conn1.lhs.offset, FromMin)
        assert conn1.lhs.offset.value == 0.0

        # Check second connection
        conn2 = model.connections[("beam2", "beam3")]
        assert conn2.lhs.contact_face == "right"
        assert conn2.lhs.edge_shared_face == "back"
        assert isinstance(conn2.lhs.offset, FromMax)
        assert conn2.lhs.offset.value == 50.0

    def test_complex_table_with_compact_notation(self):
        """Test a more complex table structure with compact notation."""
        dsl = """
        (top:2x4 {"length": 1200})
        (leg1:2x4 {"length": 700})
        (leg2:2x4 {"length": 700})
        (leg3:2x4 {"length": 700})
        (leg4:2x4 {"length": 700})
        
        top -[DL<50 TF<0]- leg1
        top -[DR>50 TF<0]- leg2
        top -[DL<50 TB>0]- leg3
        top -[DR>50 TB>0]- leg4
        """

        model = parse_dsl(dsl)

        assert len(model.pieces) == 5
        assert len(model.connections) == 4

        # All legs should connect to the bottom of the top
        for (base_id, target_id), conn in model.connections.items():
            assert conn.lhs.contact_face == "down"
            assert conn.rhs.contact_face == "top"

    def test_mixed_notation_in_same_dsl(self):
        """Test using both compact and traditional notation in same DSL."""
        dsl = """
        (p1:2x4 {"length": 500})
        (p2:2x4 {"length": 500})
        (p3:2x4 {"length": 500})
        
        p1 -[TF<0 BD<0]- p2
        p2 -[{"contact_face": "right", "edge_shared_face": "top", "offset": FromMax(100)}
              {"contact_face": "left", "edge_shared_face": "down", "offset": FromMin(50)}]- p3
        """

        model = parse_dsl(dsl)

        assert len(model.pieces) == 3
        assert len(model.connections) == 2

        # First connection uses compact notation
        conn1 = model.connections[("p1", "p2")]
        assert conn1.lhs.contact_face == "top"
        assert conn1.rhs.contact_face == "back"

        # Second connection uses traditional notation
        conn2 = model.connections[("p2", "p3")]
        assert conn2.lhs.contact_face == "right"
        assert conn2.lhs.offset.value == 100.0
        assert conn2.rhs.contact_face == "left"
        assert conn2.rhs.offset.value == 50.0


class TestCompactPieceIntegration:
    """Integration tests for compact piece notation."""

    def test_full_project_with_compact_pieces(self):
        """Test a complete project using compact piece notation."""
        dsl = """
        (leg1:2x4 =720)
        (leg2:2x4 =720)
        (leg3:2x4 =720)
        (leg4:2x4 =720)
        
        (apron_front:2x4 =600)
        (apron_back:2x4 =600)
        
        leg1 -[LB>0 DB>0]- apron_front
        leg2 -[RF>0 TF>0]- apron_front
        leg3 -[LB>0 DB>0]- apron_back
        leg4 -[RF>0 TF>0]- apron_back
        """

        model = parse_dsl(dsl)

        assert len(model.pieces) == 6
        assert len(model.connections) == 4

        # Check all pieces have correct lengths
        for i in range(1, 5):
            assert model.pieces[f"leg{i}"].length == 720.0
        assert model.pieces["apron_front"].length == 600.0
        assert model.pieces["apron_back"].length == 600.0

    def test_mixed_notation_pieces_and_connections(self):
        """Test mixing compact and traditional notation for both pieces and connections."""
        dsl = """
        (p1:2x4 =1000)
        (p2:2x4 {"length": 1200})
        (p3:1x4 =800)
        (p4:1x4 {"length": 600})
        
        p1 -[TF<0 BD<0]- p2
        p3 -[{"contact_face": "right", "edge_shared_face": "top", "offset": FromMax(100)}
              {"contact_face": "left", "edge_shared_face": "down", "offset": FromMin(50)}]- p4
        """

        model = parse_dsl(dsl)

        assert len(model.pieces) == 4
        assert len(model.connections) == 2

        # Check pieces
        assert model.pieces["p1"].length == 1000.0
        assert model.pieces["p2"].length == 1200.0
        assert model.pieces["p3"].length == 800.0
        assert model.pieces["p4"].length == 600.0

        # Check both connection types work
        assert ("p1", "p2") in model.connections
        assert ("p3", "p4") in model.connections

    def test_compact_pieces_with_decimal_lengths(self):
        """Test compact notation with decimal lengths."""
        dsl = """
        (beam1:2x4 =1000.5)
        (beam2:2x4 =999.75)
        (beam3:2x4 =1001.25)
        
        beam1 -[TF<10.5 BD>20.25]- beam2
        beam2 -[RB<30.333 LT>40.667]- beam3
        """

        model = parse_dsl(dsl)

        assert model.pieces["beam1"].length == 1000.5
        assert model.pieces["beam2"].length == 999.75
        assert model.pieces["beam3"].length == 1001.25

        # Check connections preserve decimal offsets
        conn1 = model.connections[("beam1", "beam2")]
        assert conn1.lhs.offset.value == 10.5
        assert conn1.rhs.offset.value == 20.25


class TestDSLIntegration:
    """Integration tests for complete DSL workflows."""

    def test_simple_table_structure(self):
        """Test parsing a simple table structure."""
        dsl = """
        (top:2x4 {"length": 1200})
        (leg1:2x4 {"length": 700})
        (leg2:2x4 {"length": 700})
        (leg3:2x4 {"length": 700})
        (leg4:2x4 {"length": 700})
        
        top -[{"contact_face": "down", "edge_shared_face": "left", "offset": FromMin(50)}
              {"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}]- leg1
              
        top -[{"contact_face": "down", "edge_shared_face": "right", "offset": FromMax(50)}
              {"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}]- leg2
              
        top -[{"contact_face": "down", "edge_shared_face": "left", "offset": FromMin(50)}
              {"contact_face": "top", "edge_shared_face": "back", "offset": FromMax(0)}]- leg3
              
        top -[{"contact_face": "down", "edge_shared_face": "right", "offset": FromMax(50)}
              {"contact_face": "top", "edge_shared_face": "back", "offset": FromMax(0)}]- leg4
        """

        model = parse_dsl(dsl)

        # Check pieces
        assert len(model.pieces) == 5
        # model.pieces is already a dict

        assert model.pieces["top"].length == 1200.0
        assert all(model.pieces[f"leg{i}"].length == 700.0 for i in range(1, 5))

        # Check connections
        assert len(model.connections) == 4

        # Verify all connections are from top to legs
        for (base_id, target_id), connection in model.connections.items():
            assert base_id == "top"
            assert target_id.startswith("leg")

    def test_mixed_piece_types(self):
        """Test parsing with mixed piece types."""
        dsl = """
        (frame1:2x4 {"length": 1000})
        (frame2:2x4 {"length": 1000})
        (panel1:1x4 {"length": 500})
        (panel2:1x4 {"length": 500})
        
        frame1 -[{"contact_face": "right", "edge_shared_face": "top", "offset": FromMin(100)}
                {"contact_face": "left", "edge_shared_face": "top", "offset": FromMin(100)}]- frame2
                
        frame1 -[{"contact_face": "front", "edge_shared_face": "down", "offset": FromMin(50)}
                {"contact_face": "back", "edge_shared_face": "left", "offset": FromMin(0)}]- panel1
        """

        model = parse_dsl(dsl)

        # Check pieces
        assert len(model.pieces) == 4

        assert model.pieces["frame1"].type == PieceType.PT_2x4
        assert model.pieces["frame2"].type == PieceType.PT_2x4
        assert model.pieces["panel1"].type == PieceType.PT_1x4
        assert model.pieces["panel2"].type == PieceType.PT_1x4

        # Check connections
        assert len(model.connections) == 2

    def test_complex_offset_patterns(self):
        """Test various offset patterns."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        (beam2:2x4 {"length": 1000})
        (beam3:2x4 {"length": 1000})
        
        beam1 -[{"contact_face": "front", "edge_shared_face": "top", "offset": FromMin(0)}
                {"contact_face": "back", "edge_shared_face": "down", "offset": FromMax(0)}]- beam2
                
        beam2 -[{"contact_face": "right", "edge_shared_face": "front", "offset": FromMin(100)}
                {"contact_face": "left", "edge_shared_face": "back", "offset": FromMax(100)}]- beam3
        """

        model = parse_dsl(dsl)

        # Check connections and offsets
        assert len(model.connections) == 2

        for (base_id, target_id), connection in model.connections.items():
            # Check that offsets are properly parsed
            assert isinstance(connection.lhs.offset, (FromMin, FromMax))
            assert isinstance(connection.rhs.offset, (FromMin, FromMax))
            assert connection.lhs.offset.value >= 0
            assert connection.rhs.offset.value >= 0

    def test_model_api_compatibility(self):
        """Test that DSL-generated models are compatible with the Model API."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        (beam2:2x4 {"length": 2000})
        beam1 -[{"contact_face": "front", "edge_shared_face": "top", "offset": FromMax(100)}
                {"contact_face": "down", "edge_shared_face": "front", "offset": FromMin(50)}]- beam2
        """

        # Parse DSL
        dsl_model = parse_dsl(dsl)

        # Create equivalent model using API
        from nichiyou_daiku.core.piece import Piece

        beam1 = Piece.of(PieceType.PT_2x4, 1000.0, "beam1")
        beam2 = Piece.of(PieceType.PT_2x4, 2000.0, "beam2")

        from nichiyou_daiku.core.connection import Anchor, Connection
        from nichiyou_daiku.core.model import PiecePair

        connection = Connection(
            lhs=Anchor(
                contact_face="front", edge_shared_face="top", offset=FromMax(value=100)
            ),
            rhs=Anchor(
                contact_face="down",
                edge_shared_face="front",
                offset=FromMin(value=50),
            ),
        )

        api_model = Model.of(
            pieces=[beam1, beam2],
            connections=[(PiecePair(base=beam1, target=beam2), connection)],
        )

        # Compare models
        assert len(dsl_model.pieces) == len(api_model.pieces)
        assert len(dsl_model.connections) == len(api_model.connections)

        # Check piece properties match
        # Both models have pieces as dicts
        for piece_id in ["beam1", "beam2"]:
            assert dsl_model.pieces[piece_id].type == api_model.pieces[piece_id].type
            assert (
                dsl_model.pieces[piece_id].length == api_model.pieces[piece_id].length
            )

    def test_whitespace_flexibility(self):
        """Test that DSL is flexible with whitespace."""
        # Compact version
        dsl_compact = '(a:2x4{"length":1000})(b:2x4{"length":1000})a-[{"contact_face":"front","edge_shared_face":"top","offset":FromMax(100)}{"contact_face":"down","edge_shared_face":"front","offset":FromMin(50)}]-b'

        # Spaced version
        dsl_spaced = """
        ( a : 2x4 { "length" : 1000 } )
        ( b : 2x4 { "length" : 1000 } )
        a -[ { "contact_face" : "front" , "edge_shared_face" : "top" , "offset" : FromMax( 100 ) }
             { "contact_face" : "down" , "edge_shared_face" : "front" , "offset" : FromMin( 50 ) } ]- b
        """

        model_compact = parse_dsl(dsl_compact)
        model_spaced = parse_dsl(dsl_spaced)

        assert len(model_compact.pieces) == len(model_spaced.pieces)
        assert len(model_compact.connections) == len(model_spaced.connections)
