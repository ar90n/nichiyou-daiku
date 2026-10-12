"""Tests for unknown lengths and sliding (unknown-offset) connections."""

from pathlib import Path

import pytest

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.placement import solve_placement
from nichiyou_daiku.core.resolve import ResolutionError, resolve_model
from nichiyou_daiku.dsl import DSLValidationError, parse_dsl

TABLE = (
    Path(__file__).parents[2] / "examples" / "nd_files" / "simple_table_compact.nd"
).read_text()


def _line_of(source: str, text: str) -> int:
    return next(i for i, line in enumerate(source.splitlines(), 1) if text in line)


class TestUnknownLength:
    def test_apron_length_is_solved_from_the_legs(self):
        source = TABLE.replace("(apron_front:2x4 =622)", "(apron_front:2x4 =?)")
        assert parse_dsl(source).pieces["apron_front"].length == 622.0

    def test_solved_model_matches_the_written_one(self):
        source = TABLE.replace("(apron_front:2x4 =622)", "(apron_front:2x4 =?)")
        solved = solve_placement(parse_dsl(source))
        written = solve_placement(parse_dsl(TABLE))
        assert solved == written

    def test_length_not_fixed_by_the_connections_is_an_error(self):
        source = TABLE.replace("(apron_front:2x4 =622)", "(apron_front:2x4 =?)")
        source = source.replace("(apron_back:2x4 =622)", "(apron_back:2x4 =?)")
        with pytest.raises(DSLValidationError, match="'apron_front'") as exc:
            parse_dsl(source)
        assert "not fixed" in str(exc.value)
        assert exc.value.line == _line_of(source, "(apron_front:2x4 =?)")

    def test_unconnected_piece_of_unknown_length_is_an_error(self):
        with pytest.raises(DSLValidationError, match="'b'"):
            parse_dsl("(a:2x4 =500)\n(b:2x4 =?)")


# q lies on a's front face from z=0; s lies on it from z=S and carries r on
# its own front face, level with q's front face
STACK = (
    "(a:2x4 =1000)\n(q:2x4 =300)\n(s:2x4 =300)\n(r:2x4 =300)\n"
    "a -[FL<0 BL<0]- q\na -[FL<{S} BL<0]- s\ns -[FL<0 BL<0]- r\n"
)
# u runs on a's front face from the top end of q to the down end of s
BETWEEN = (
    "(a:2x4 =1000)\n(q:2x4 =300)\n(s:2x4 =300)\n(u:2x4 =?)\n"
    "a -[FL<0 BL<0]- q\na -[FL<{S} BL<0]- s\n"
    "q -[TL<0 DL<0]- u\nu -[TL<0 DL<0]- s\n"
)


class TestUnknownLengthBetweenPieces:
    def test_length_spans_the_gap(self):
        assert parse_dsl(BETWEEN.format(S=500)).pieces["u"].length == 200.0

    def test_negative_length_is_an_error(self):
        with pytest.raises(DSLValidationError, match="-100mm") as exc:
            parse_dsl(BETWEEN.format(S=200))
        assert exc.value.line == 4


class TestSlidingConnection:
    def test_sliding_pieces_meet_where_their_edges_start_to_overlap(self):
        model = parse_dsl(STACK.format(S=200) + "q -[FL? BL?]- r\n")
        connection = model.connections[("q", "r")]
        assert connection.base.anchor.offset == FromMin(value=200.0)
        assert connection.target.anchor.offset == FromMin(value=0.0)
        assert solve_placement(model).conflicts == ()

    def test_sliding_pieces_whose_edges_do_not_meet_is_an_error(self):
        with pytest.raises(DSLValidationError, match="do not meet") as exc:
            parse_dsl(STACK.format(S=500) + "q -[FL? BL?]- r\n")
        assert exc.value.line == 8

    def test_top_boards_can_also_be_doweled_to_the_back_apron(self):
        extra = "".join(
            f"\napron_back -[RB? BD? D(:8x30)]- table_top_{k}" for k in range(2, 8)
        )
        model = parse_dsl(TABLE + extra)
        assembly = Assembly.of(model)
        written = Assembly.of(parse_dsl(TABLE))
        assert assembly.placement == written.placement
        assert assembly.fastener_issues == ()
        assert sum(f.base_id == "apron_back" for f in assembly.fasteners) == 12
        # The solved offsets match the ones written for the front apron
        for k in range(2, 8):
            front = model.connections[("apron_front", f"table_top_{k}")]
            back = model.connections[("apron_back", f"table_top_{k}")]
            assert back.base.anchor.offset == front.base.anchor.offset

    def test_piece_held_only_by_a_sliding_connection_is_an_error(self):
        source = "(a:2x4 =500)\n(b:2x4 =300)\na -[FL? DF?]- b"
        with pytest.raises(DSLValidationError, match="'b'") as exc:
            parse_dsl(source)
        assert "slide" in str(exc.value)
        assert exc.value.line == 2

    def test_unknown_offset_must_be_on_both_anchors(self):
        with pytest.raises(DSLValidationError, match="both anchors"):
            parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL? DF<0]- b")


class TestPythonApi:
    def _model(self) -> Model:
        """The simple table, built with the Python API, front apron unknown."""
        written = parse_dsl(TABLE)
        pieces = {
            piece_id: Piece.of(piece.type, None, piece_id)
            if piece_id == "apron_front"
            else piece
            for piece_id, piece in written.pieces.items()
        }
        connections = [
            Connection(
                base=BoundAnchor(piece=pieces[c.base.piece.id], anchor=c.base.anchor),
                target=BoundAnchor(
                    piece=pieces[c.target.piece.id], anchor=c.target.anchor
                ),
                type=c.type,
            )
            for c in written.connections.values()
        ]
        return Model.of(pieces=list(pieces.values()), connections=connections)

    def test_get_shape_needs_a_known_length(self):
        with pytest.raises(ValueError, match="resolve"):
            get_shape(Piece.of(PieceType.PT_2x4, None, "b"))

    def test_solve_placement_rejects_unknowns(self):
        with pytest.raises(ValueError, match="resolve"):
            solve_placement(self._model())

    def test_assembly_resolves_unknowns(self):
        assembly = Assembly.of(self._model())
        assert assembly.model.pieces["apron_front"].length == 622.0
        assert assembly.model == resolve_model(self._model())

    def test_resolve_model_leaves_a_known_model_alone(self):
        model = parse_dsl(TABLE)
        assert resolve_model(model) is model

    def test_offset_of_an_unknown_length_edge_is_not_checked_yet(self):
        piece = Piece.of(PieceType.PT_2x4, None, "b")
        bound = BoundAnchor(
            piece=piece, anchor=Anchor.of("front", "left", FromMax(value=5000))
        )
        assert bound.anchor.offset == FromMax(value=5000)

    def test_offset_across_a_known_side_is_still_checked(self):
        piece = Piece.of(PieceType.PT_2x4, None, "b")
        with pytest.raises(ValueError, match="exceeds"):
            BoundAnchor(piece=piece, anchor=Anchor.of("top", "left", FromMin(value=50)))

    def test_resolution_error_names_the_piece(self):
        a = Piece.of(PieceType.PT_2x4, 500.0, "a")
        b = Piece.of(PieceType.PT_2x4, None, "b")
        with pytest.raises(ResolutionError) as exc:
            resolve_model(Model.of(pieces=[a, b], connections=[]))
        assert exc.value.piece_id == "b"


def test_unknowns_example_is_valid():
    path = (
        Path(__file__).parents[2] / "examples" / "nd_files" / "simple_table_unknowns.nd"
    )
    model = parse_dsl(path.read_text())
    assembly = Assembly.of(model)
    assert model.pieces["apron_front"].length == 622.0
    assert assembly.placement.conflicts == ()
    assert assembly.fastener_issues == ()
    assert sum(f.base_id == "apron_back" for f in assembly.fasteners) == 12


WRITTEN = parse_dsl(TABLE)
WRITTEN_PLACEMENT = solve_placement(WRITTEN)
UNKNOWNS_EXAMPLE = (
    Path(__file__).parents[2] / "examples" / "nd_files" / "simple_table_unknowns.nd"
).read_text()


def _blank_length(piece_id: str) -> Model:
    pieces = {
        pid: Piece.of(p.type, None, pid) if pid == piece_id else p
        for pid, p in WRITTEN.pieces.items()
    }
    return _rebuild(pieces, {})


def _make_sliding(key: tuple[str, str]) -> Model:
    return _rebuild(dict(WRITTEN.pieces), {key})


def _rebuild(pieces, sliding) -> Model:
    def anchor(old: Anchor, slide: bool) -> Anchor:
        if not slide:
            return old
        return Anchor.of(old.contact_face, old.edge_shared_face, None)

    connections = [
        Connection(
            base=BoundAnchor(
                piece=pieces[c.base.piece.id],
                anchor=anchor(c.base.anchor, key in sliding),
            ),
            target=BoundAnchor(
                piece=pieces[c.target.piece.id],
                anchor=anchor(c.target.anchor, key in sliding),
            ),
            type=c.type,
        )
        for key, c in WRITTEN.connections.items()
    ]
    return Model.of(pieces=list(pieces.values()), connections=connections)


class TestEveryUnknownInALoopModel:
    """Leave one value of the written table unknown at a time: it either
    resolves back to exactly the written table or is reported as open."""

    @pytest.mark.parametrize("piece_id", list(WRITTEN.pieces))
    def test_unknown_length(self, piece_id):
        try:
            resolved = resolve_model(_blank_length(piece_id))
        except ResolutionError as error:
            assert error.piece_id is not None
            return
        assert resolved.pieces[piece_id].length == WRITTEN.pieces[piece_id].length
        assert solve_placement(resolved) == WRITTEN_PLACEMENT

    @pytest.mark.parametrize("key", list(WRITTEN.connections))
    def test_sliding_connection(self, key):
        try:
            resolved = resolve_model(_make_sliding(key))
        except ResolutionError:
            return
        assert solve_placement(resolved) == WRITTEN_PLACEMENT

    @pytest.mark.parametrize(
        "piece_id",
        ["leg_1", "leg_2", "leg_3", "leg_4"]
        + ["apron_front", "apron_back", "apron_left", "apron_right"],
    )
    def test_legs_and_aprons_are_fixed_by_the_rest(self, piece_id):
        resolved = resolve_model(_blank_length(piece_id))
        assert resolved.pieces[piece_id].length == WRITTEN.pieces[piece_id].length


class TestReviewFollowUps:
    def test_conflicting_sliding_connection_reports_only_the_real_conflict(self):
        # Lower the back apron by 1mm: the boards no longer rest on it
        source = UNKNOWNS_EXAMPLE.replace(
            "leg_3 -[LB>0 DB>0]- apron_back", "leg_3 -[LB>1 DB>0]- apron_back"
        ).replace("leg_4 -[RF>0 TF>0]- apron_back", "leg_4 -[RF>1 TF>0]- apron_back")
        conflicts = Assembly.of(parse_dsl(source)).placement.conflicts
        assert len(conflicts) == 6
        assert {c.kind for c in conflicts} == {"contact"}
        assert {c.mismatch_mm for c in conflicts} == {-1.0}

    def test_check_failing_on_the_solved_length_points_at_the_connection(self):
        # u resolves to 200mm, too short for an anchor 250mm from its top
        source = BETWEEN.format(S=500) + "(x:2x4 =100)\nu -[FR>250 BR<0]- x\n"
        with pytest.raises(DSLValidationError, match="exceeds") as exc:
            parse_dsl(source)
        assert exc.value.line == 10

    def test_check_failing_on_the_solved_model_is_a_resolution_error(self):
        source = BETWEEN.format(S=500) + "(x:2x4 =100)\nu -[FR>250 BR<0]- x\n"
        model = parse_dsl(source.replace("(u:2x4 =?)", "(u:2x4 =1000)"))
        pieces = {
            pid: Piece.of(p.type, None, pid) if pid == "u" else p
            for pid, p in model.pieces.items()
        }
        unresolved = Model.of(
            pieces=list(pieces.values()),
            connections=[
                Connection(
                    base=BoundAnchor(
                        piece=pieces[c.base.piece.id], anchor=c.base.anchor
                    ),
                    target=BoundAnchor(
                        piece=pieces[c.target.piece.id], anchor=c.target.anchor
                    ),
                    type=c.type,
                )
                for c in model.connections.values()
            ],
        )
        with pytest.raises(ResolutionError, match="exceeds") as exc:
            resolve_model(unresolved)
        assert exc.value.connection == ("u", "x")

    def test_each_group_is_resolved_on_its_own(self):
        model = parse_dsl(BETWEEN.format(S=500) + "(lonely:2x4 =100)\n")
        assert model.pieces["u"].length == 200.0
        assert len(solve_placement(model).groups) == 2

    def test_sliding_error_names_the_connections(self):
        with pytest.raises(DSLValidationError, match="a -> b"):
            parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL? DF?]- b")

    def test_unknown_in_json_notation_gets_a_hint(self):
        with pytest.raises(Exception, match="compact notation"):
            parse_dsl('(a:2x4 {"length": ?})')
