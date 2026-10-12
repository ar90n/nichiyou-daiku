"""Tests for planning cuts from stock boards."""

import pytest

from nichiyou_daiku.core.piece import PieceType
from nichiyou_daiku.shell.cutting import (
    DEFAULT_STANDARD_LENGTHS,
    CutPlan,
    _optimize_cuts,
    plan_cuts,
)
from nichiyou_daiku.shell.resources import PieceResource, ResourceSummary


def _piece(
    id_: str, length: float, piece_type: PieceType = PieceType.PT_2x4
) -> PieceResource:
    return PieceResource(
        id=id_, type=piece_type, length=length, width=89.0, height=38.0, volume=0
    )


def _summary(*pieces: PieceResource) -> ResourceSummary:
    by_type: dict[PieceType, int] = {}
    lengths: dict[PieceType, float] = {}
    for piece in pieces:
        by_type[piece.type] = by_type.get(piece.type, 0) + 1
        lengths[piece.type] = lengths.get(piece.type, 0.0) + piece.length
    return ResourceSummary(
        pieces=list(pieces),
        total_pieces=len(pieces),
        pieces_by_type=by_type,
        total_length_by_type=lengths,
        total_volume=0.0,
    )


class TestCutPlan:
    def test_should_create_cut_plan(self):
        plan = CutPlan(
            board_length=2440.0,
            cuts=[("piece1", 1000.0), ("piece2", 800.0)],
            waste=640.0,
        )

        assert plan.board_length == 2440.0
        assert len(plan.cuts) == 2
        assert plan.cuts[0] == ("piece1", 1000.0)
        assert plan.waste == 640.0


class TestDefaultStandardLengths:
    def test_every_lumber_type_has_common_stock_lengths(self):
        one_by = [1830.0, 2440.0, 3050.0]  # 6, 8 and 10ft
        two_by = [2440.0, 3050.0, 3660.0]  # 8, 10 and 12ft
        expected = {
            "1x4": one_by,
            "1x6": one_by,
            "1x8": one_by,
            "2x2": two_by,
            "2x4": two_by,
            "2x6": two_by,
        }
        assert {t.value: v for t, v in DEFAULT_STANDARD_LENGTHS.items()} == expected


class TestOptimizeCuts:
    def test_should_optimize_simple_cuts(self):
        plans = _optimize_cuts(
            [_piece("p1", 1000.0), _piece("p2", 800.0)], [2440.0], kerf=0.0
        )

        assert len(plans) == 1
        assert plans[0].board_length == 2440.0
        assert [cut[0] for cut in plans[0].cuts] == ["p1", "p2"]
        assert plans[0].waste == 640.0

    def test_should_use_multiple_boards_when_needed(self):
        plans = _optimize_cuts(
            [_piece("p1", 2000.0), _piece("p2", 2000.0)], [2440.0], kerf=0.0
        )

        assert len(plans) == 2
        assert all(plan.board_length == 2440.0 for plan in plans)
        assert all(len(plan.cuts) == 1 for plan in plans)

    def test_should_choose_optimal_board_length(self):
        # The 1830mm board wastes less than the 2440mm one
        plans = _optimize_cuts([_piece("p1", 1500.0)], [1830.0, 2440.0], kerf=0.0)

        assert len(plans) == 1
        assert plans[0].board_length == 1830.0
        assert plans[0].waste == 330.0

    def test_should_handle_empty_pieces_list(self):
        assert _optimize_cuts([], [2440.0]) == []


class TestCutPlanKerf:
    def test_saw_kerf_is_allowed_between_cuts(self):
        # 3 x 813 = 2439mm fits 2440 only if the saw removes nothing
        pieces = [_piece("a", 813.0), _piece("b", 813.0), _piece("c", 813.0)]
        assert len(_optimize_cuts(pieces, [2440.0], kerf=3.0)) == 2

    def test_offcut_excludes_kerf(self):
        plans = _optimize_cuts(
            [_piece("a", 1000.0), _piece("b", 800.0)], [2440.0], kerf=3.0
        )
        assert plans[0].waste == 634.0

    def test_exact_fit_needs_no_final_cut(self):
        plans = _optimize_cuts(
            [_piece("a", 1218.5), _piece("b", 1218.5)], [2440.0], kerf=3.0
        )
        assert len(plans) == 1
        assert plans[0].waste == 0.0

    def test_piece_longer_than_every_board_is_not_planned(self):
        pieces = [_piece("long", 4000.0), _piece("short", 500.0)]
        plans = _optimize_cuts(pieces, [2440.0, 3050.0, 3660.0], kerf=0.0)
        assert [piece_id for plan in plans for piece_id, _ in plan.cuts] == ["short"]
        assert all(plan.waste >= 0 for plan in plans)


class TestPlanCuts:
    def test_uses_the_default_stock_lengths(self):
        plan = plan_cuts(_summary(_piece("a", 1000.0)))[PieceType.PT_2x4]
        assert plan.available_lengths == [2440.0, 3050.0, 3660.0]
        assert plan.board_counts == {2440.0: 1}

    def test_type_missing_from_standard_lengths_uses_2440mm(self):
        summary = _summary(_piece("a", 1000.0, PieceType.PT_1x4))
        plans = plan_cuts(summary, {PieceType.PT_2x4: [3050.0]})
        assert plans[PieceType.PT_1x4].available_lengths == [2440.0]

    def test_oversize_pieces_are_listed_instead_of_planned(self):
        summary = _summary(_piece("long", 4000.0), _piece("short", 500.0))
        plan = plan_cuts(summary, {PieceType.PT_2x4: [2440.0]})[PieceType.PT_2x4]
        assert [piece.id for piece in plan.oversize] == ["long"]
        assert [cut[0] for board in plan.boards for cut in board.cuts] == ["short"]

    def test_all_pieces_oversize_means_no_boards_and_no_waste(self):
        summary = _summary(_piece("long", 4000.0))
        plan = plan_cuts(summary, {PieceType.PT_2x4: [2440.0]})[PieceType.PT_2x4]
        assert plan.boards == []
        assert plan.board_counts == {}
        assert plan.total_waste == 0
        assert plan.waste_percentage == 0.0

    def test_totals_add_up_over_the_boards(self):
        summary = _summary(_piece("a", 2000.0), _piece("b", 2000.0), _piece("c", 300.0))
        plan = plan_cuts(summary, {PieceType.PT_2x4: [2440.0]})[PieceType.PT_2x4]
        assert plan.board_counts == {2440.0: 2}
        assert plan.total_waste == sum(board.waste for board in plan.boards)
        assert plan.waste_percentage == pytest.approx(plan.total_waste / 4880.0 * 100)

    def test_lumber_types_come_in_report_order(self):
        summary = _summary(_piece("a", 500.0), _piece("b", 500.0, PieceType.PT_1x4))
        assert list(plan_cuts(summary)) == [PieceType.PT_1x4, PieceType.PT_2x4]

    def test_no_pieces_means_no_plans(self):
        assert plan_cuts(_summary()) == {}
