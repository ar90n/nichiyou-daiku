"""Problems and piece positions as data, for validate --json."""

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import DSLSyntaxError, parse_dsl
from nichiyou_daiku.shell.diagnostics import (
    ValidationFailure,
    ValidationReport,
    collect_problems,
    describe_assembly_issues,
    failure_report,
    validation_report,
)
from nichiyou_daiku.shell.resources import extract_resources

CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
OVERLAP = (
    "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
    "a -[FL<100 DF<0]- b\na -[FL<100 DF<0]- c\n"
)
COLLISION = (
    "(post:2x4 =600)\n(front:2x4 =300)\n(other:2x4 =300)\n"
    "post -[FL<300 DF<0 D(4, 40)]- front\n"
    "post -[BL<300 DB<0 D(4, 40)]- other\n"
)


def _report(source: str) -> ValidationReport:
    return validation_report(Assembly.of(parse_dsl(source)))


def _flip(direction: str) -> str:
    return ("-" if direction[0] == "+" else "+") + direction[1]


class TestPositions:
    def test_the_overall_box_starts_at_the_origin(self):
        report = _report(CORNER)
        assert report.overall_size is not None
        lows = [min(p.min[axis] for p in report.pieces) for axis in range(3)]
        highs = [max(p.max[axis] for p in report.pieces) for axis in range(3)]
        assert lows == [0, 0, 0]
        assert highs == list(report.overall_size)

    def test_overall_size_matches_the_report(self):
        assembly = Assembly.of(parse_dsl(CORNER))
        assert (
            validation_report(assembly).overall_size
            == extract_resources(assembly).overall_size
        )

    def test_each_box_is_the_piece_turned_into_place(self):
        report = _report(CORNER)
        assert [(p.id, p.type, p.length, p.group) for p in report.pieces] == [
            ("a", "2x4", 400, 0),
            ("b", "2x4", 400, 0),
        ]
        for piece in report.pieces:
            extent = sorted(hi - lo for lo, hi in zip(piece.min, piece.max))
            assert extent == [38, 89, 400]

    def test_faces_follow_the_placement_rules(self):
        # a -[TF<0 BD<0]- b: b's back lies on a's top (contact faces face each
        # other) and b's down end is flush with a's front (same direction)
        a, b = _report(CORNER).pieces
        assert a.faces.model_dump() == {"top": "+z", "right": "+x", "front": "+y"}
        assert b.faces.front == a.faces.top
        assert _flip(b.faces.top) == a.faces.front

    def test_the_first_declared_piece_sets_the_axes(self):
        # Declared first, b is the unturned one although a is the base
        report = _report("(b:2x4 =400)\n(a:2x4 =400)\na -[TF<0 BD<0]- b\n")
        assert report.size_reference == "b"
        assert report.pieces[0].faces.model_dump() == {
            "top": "+z",
            "right": "+x",
            "front": "+y",
        }

    def test_unconnected_groups_have_no_overall_size(self):
        report = _report(
            "(a:2x4 =500)\n(b:2x4 =300)\n(floating:2x4 =300)\na -[FL<100 DF<0]- b\n"
        )
        assert (report.overall_size, report.size_reference) == (None, None)
        assert {p.id: p.group for p in report.pieces} == {
            "a": 0,
            "b": 0,
            "floating": 1,
        }
        [problem] = report.problems
        assert problem.kind == "unconnected"
        assert problem.groups == (("a", "b"), ("floating",))


class TestProblems:
    def test_a_conflict_names_the_connection_constraint_and_mismatch(self):
        report = _report(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
            "a -[FL<100 DF<0]- b\na -[FL>100 DF<0]- c\nb -[RF<0 LF<0]- c\n"
        )
        [conflict] = [p for p in report.problems if p.kind == "conflict"]
        assert conflict.connection == ("b", "c")
        assert (conflict.constraint, conflict.axis) == ("contact", "z")
        assert conflict.mismatch_mm is not None and abs(conflict.mismatch_mm) == 389
        assert conflict.loop == ("b", "a", "c")
        assert conflict.message == (
            "Connection b -> c: contact (z) is off by 389mm (loop: b -> a -> c)"
        )

    def test_an_orientation_conflict_has_no_axis_or_mismatch(self):
        report = _report(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
            "a -[RF<0 LF<0]- b\na -[FL<100 DF<0]- c\nb -[RF<0 LF<0]- c\n"
        )
        [conflict] = [p for p in report.problems if p.kind == "conflict"]
        assert (conflict.constraint, conflict.axis, conflict.mismatch_mm) == (
            "rotation",
            None,
            None,
        )

    def test_a_fastener_without_room(self):
        report = _report("(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(5, 30)]- b\n")
        [problem] = report.problems
        assert (problem.kind, problem.connection, problem.fastener) == (
            "fastener",
            ("a", "b"),
            "dowel",
        )
        assert problem.message == (
            "Connection a -> b: contact area 19.0 x 89.0mm is too narrow "
            "for a 10.0mm dowel (needs 20.0mm)"
        )

    def test_a_hole_collision_says_where_both_holes_are(self):
        report = _report(COLLISION)
        [problem] = report.problems
        assert problem.kind == "hole_collision"
        assert (
            problem.connection,
            problem.other_connection,
            problem.piece,
            problem.fastener,
        ) == (("post", "other"), ("post", "front"), "post", "dowel")
        post = next(p for p in report.pieces if p.id == "post")
        for hole in problem.holes:
            assert (hole.depth, hole.diameter) == (20, 8)
            axis = "xyz".index(hole.direction[1])
            inward = 1 if hole.direction[0] == "+" else -1
            # Enters on the post's surface and runs into it
            surface = post.min if inward > 0 else post.max
            assert hole.entry[axis] == surface[axis]
            assert post.min[axis] <= hole.entry[axis] + inward * 20 <= post.max[axis]
        # From the back and the front, towards each other
        assert problem.holes[0].direction == _flip(problem.holes[1].direction)

    def test_overlaps_carry_the_pieces_and_volume(self):
        [problem] = _report(OVERLAP).problems
        assert (problem.kind, problem.pieces, problem.volume_mm3) == (
            "overlap",
            ("b", "c"),
            1014600,
        )
        assert problem.message == "Pieces 'b' and 'c' overlap (1014600mm³)"

    def test_the_warnings_leave_out_overlaps(self):
        assembly = Assembly.of(parse_dsl(OVERLAP))
        assert [p.kind for p in collect_problems(assembly)] == ["overlap"]
        assert describe_assembly_issues(assembly) == []

    def test_a_sound_model_is_valid(self):
        report = _report(CORNER)
        assert report.valid is True
        assert (report.error, report.problems) == (None, ())


def test_a_failure_keeps_the_error_and_its_position():
    error = DSLSyntaxError("Unexpected token", line=3, column=5)
    report = failure_report("syntax", error)
    assert report == ValidationReport(
        valid=False,
        error=ValidationFailure(kind="syntax", message=str(error), line=3, column=5),
    )
    assert (report.overall_size, report.pieces, report.problems) == (None, (), ())
