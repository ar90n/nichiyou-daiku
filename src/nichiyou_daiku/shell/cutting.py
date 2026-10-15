"""Plan how to cut lumber pieces from stock boards.

Kept apart from the report so the plan is computed once and can serve any
output, not only the Markdown report.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Tuple

from nichiyou_daiku.core.piece import PieceType

from .resources import PieceResource, ResourceSummary

DEFAULT_KERF_MM = 3.0
"""Material removed by each saw cut."""

# Japanese home centres sell SPF lumber as 6F, 8F, 10F and 12F boards
DEFAULT_STANDARD_LENGTHS: Dict[PieceType, List[float]] = {
    piece_type: [1820.0, 2440.0, 3050.0, 3650.0] for piece_type in PieceType
}

FALLBACK_STANDARD_LENGTHS: List[float] = [2440.0]
"""Stock lengths for a lumber type that ``standard_lengths`` does not list."""


@dataclass
class CutPlan:
    """Plan for cutting pieces from a standard board.

    Attributes:
        board_length: Length of the standard board in mm
        cuts: List of (piece_id, length) tuples to cut from this board
        waste: Remaining unused length in mm
    """

    board_length: float
    cuts: List[Tuple[str, float]]
    waste: float


@dataclass
class LumberPlan:
    """How to cut every piece of one lumber type.

    Attributes:
        available_lengths: Stock board lengths in mm
        boards: One cut plan per board to buy
        oversize: Pieces longer than every stock board; they are not in ``boards``
    """

    available_lengths: List[float]
    boards: List[CutPlan]
    oversize: List[PieceResource]

    @property
    def board_counts(self) -> Dict[float, int]:
        """Number of boards to buy per stock length."""
        counts: Dict[float, int] = {}
        for board in self.boards:
            counts[board.board_length] = counts.get(board.board_length, 0) + 1
        return counts

    @property
    def total_waste(self) -> float:
        return sum(board.waste for board in self.boards)

    @property
    def waste_percentage(self) -> float:
        """Waste as a share of the purchased length (0 when nothing is bought)."""
        purchased = sum(board.board_length for board in self.boards)
        return self.total_waste / purchased * 100 if purchased > 0 else 0.0


def _oversize_pieces(
    pieces: List[PieceResource], available_lengths: List[float]
) -> List[PieceResource]:
    """Pieces longer than every available board (cannot be cut from stock)."""
    longest = max(available_lengths)
    return [p for p in pieces if p.length > longest]


_MAX_SEARCHED_LENGTHS = 8
"""Up to this many stock lengths, every set of them is tried; above it, all of
them together and each alone."""


def _cost(plan: List[CutPlan]) -> tuple[float, int]:
    """What a plan costs: the lumber bought, then the number of boards."""
    return sum(board.board_length for board in plan), len(plan)


def _fill_boards(
    pieces: List[PieceResource],
    available_lengths: List[float],
    kerf: float = DEFAULT_KERF_MM,
) -> List[CutPlan]:
    """Fill boards one at a time, each with the board length that wastes least.

    First fit decreasing over ``available_lengths``. Every cut removes ``kerf``
    mm, except that a piece ending exactly at the board end needs no final
    cut. Pieces longer than every board are left out; see ``_oversize_pieces``.
    """

    oversize = {p.id for p in _oversize_pieces(pieces, available_lengths)}
    # Sort pieces by length (descending) for better optimization
    remaining_pieces = sorted(
        (p for p in pieces if p.id not in oversize),
        key=lambda p: p.length,
        reverse=True,
    )

    # Sort available lengths (ascending) to prefer smaller boards when possible
    sorted_lengths = sorted(available_lengths)

    cut_plans = []
    while remaining_pieces:
        # Find the best board length for remaining pieces
        best_plan = None
        best_remaining = remaining_pieces

        for board_length in sorted_lengths:
            cuts = []
            used_length = 0.0
            temp_remaining = remaining_pieces.copy()

            # Try to fit as many pieces as possible
            for piece in remaining_pieces:
                needed = piece.length + (kerf if cuts else 0.0)
                if used_length + needed <= board_length:
                    cuts.append((piece.id, piece.length))
                    used_length += needed
                    temp_remaining.remove(piece)

            if cuts:  # If we can fit at least one piece
                # Separating the offcut takes one more cut
                waste = max(0.0, board_length - used_length - kerf)
                if best_plan is None or waste < best_plan.waste:
                    best_plan = CutPlan(
                        board_length=board_length, cuts=cuts, waste=waste
                    )
                    best_remaining = temp_remaining

        # Every remaining piece fits the longest board, so a plan always exists
        assert best_plan is not None
        cut_plans.append(best_plan)
        remaining_pieces = best_remaining

    return cut_plans


def _optimize_cuts(
    pieces: List[PieceResource],
    available_lengths: List[float],
    kerf: float = DEFAULT_KERF_MM,
) -> List[CutPlan]:
    """Plan the cuts that buy the least lumber.

    Filling boards greedily (``_fill_boards``) can over-use a short board and
    leave a small piece a whole board of its own, so a board size on offer
    could make the purchase worse. The fill runs with every set of the stock
    lengths whose longest board fits the longest piece, and the plan buying
    the least total length (then the fewest boards) wins. Every cut removes
    ``kerf`` mm; pieces longer than every board are left out.

    Args:
        pieces: List of pieces to cut (all same lumber type)
        available_lengths: Available standard board lengths in mm
        kerf: Material removed by each saw cut in mm

    Returns:
        List of cut plans showing how to cut pieces from standard boards

    Examples:
        >>> from nichiyou_daiku.core.piece import PieceType
        >>> pieces = [
        ...     PieceResource(id="p1", type=PieceType.PT_2x4, length=1000.0,
        ...                  width=89.0, height=38.0, volume=0),
        ...     PieceResource(id="p2", type=PieceType.PT_2x4, length=800.0,
        ...                  width=89.0, height=38.0, volume=0)
        ... ]
        >>> plans = _optimize_cuts(pieces, [2440.0], kerf=3.0)
        >>> len(plans)
        1
        >>> plans[0].board_length
        2440.0
        >>> len(plans[0].cuts)
        2
        >>> plans[0].waste
        634.0
    """
    lengths = sorted(set(available_lengths))
    oversize = {p.id for p in _oversize_pieces(pieces, lengths)}
    longest = max((p.length for p in pieces if p.id not in oversize), default=0.0)
    if len(lengths) <= _MAX_SEARCHED_LENGTHS:
        candidates = [
            list(chosen)
            for count in range(1, len(lengths) + 1)
            for chosen in combinations(lengths, count)
        ]
    else:
        candidates = [lengths, *([length] for length in lengths)]

    best: List[CutPlan] | None = None
    for chosen in candidates:
        if chosen[-1] < longest:
            continue
        plan = _fill_boards(pieces, chosen, kerf)
        if best is None or _cost(plan) < _cost(best):
            best = plan
    return best or []


def plan_cuts(
    summary: ResourceSummary,
    standard_lengths: Mapping[PieceType, Sequence[float]] | None = None,
    kerf: float = DEFAULT_KERF_MM,
) -> Dict[PieceType, LumberPlan]:
    """Plan the cuts for every lumber type in ``summary``, in report order.

    Args:
        summary: Pieces to cut
        standard_lengths: Stock board lengths per lumber type; defaults to
            ``DEFAULT_STANDARD_LENGTHS``. Types it does not list use
            ``FALLBACK_STANDARD_LENGTHS``.
        kerf: Material removed by each saw cut in mm

    Examples:
        >>> piece = PieceResource(id="p1", type=PieceType.PT_2x4, length=1000.0,
        ...                       width=89.0, height=38.0, volume=0)
        >>> summary = ResourceSummary(
        ...     pieces=[piece], total_pieces=1,
        ...     pieces_by_type={PieceType.PT_2x4: 1},
        ...     total_length_by_type={PieceType.PT_2x4: 1000.0},
        ...     total_volume=0,
        ... )
        >>> plan_cuts(summary)[PieceType.PT_2x4].board_counts
        {1820.0: 1}
    """
    if standard_lengths is None:
        standard_lengths = DEFAULT_STANDARD_LENGTHS
    plans: Dict[PieceType, LumberPlan] = {}
    for piece_type in sorted(summary.pieces_by_type, key=lambda t: t.value):
        pieces = [p for p in summary.pieces if p.type == piece_type]
        available = list(standard_lengths.get(piece_type, FALLBACK_STANDARD_LENGTHS))
        plans[piece_type] = LumberPlan(
            available_lengths=available,
            boards=_optimize_cuts(pieces, available, kerf),
            oversize=_oversize_pieces(pieces, available),
        )
    return plans
