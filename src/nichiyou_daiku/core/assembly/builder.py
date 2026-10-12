"""Assembly builder for creating 3D assemblies from models.

This module contains the Assembly class that turns a Model into placed
pieces with their fasteners and pilot holes.
"""

from pydantic import BaseModel

from ..geometry import Box, SurfacePoint
from ..model import Model
from ..piece import get_shape
from ..placement import Placement, solve_placement
from ..resolve import resolve_model
from .fasteners import find_hole_collisions, layout_fasteners
from .models import Fastener, Hole, LayoutIssue


class Assembly(BaseModel, frozen=True):
    """Complete 3D assembly: placed pieces, fasteners and pilot holes.

    Attributes:
        model: The source model with piece and connection definitions
        boxes: Dictionary mapping piece IDs to their 3D boxes
        fasteners: Dowels and screws laid out in each connection's contact area
            (none for connections that contradict the placement)
        fastener_issues: Connections whose fasteners could not be laid out, or
            whose holes run into another connection's holes inside a piece
        pilot_holes: Dictionary mapping piece IDs to lists of (SurfacePoint, Hole)
            tuples; the SurfacePoint names the face the hole is drilled into
        placement: World placement of every piece, solved from the connections
        label: Optional label for the assembly

    Examples:
        >>> from nichiyou_daiku.dsl import parse_dsl
        >>> assembly = Assembly.of(
        ...     parse_dsl("(a:2x4 =500)\\n(b:2x4 =300)\\na -[FL<100 DF<0 D(4, 30)]- b\\n")
        ... )
        >>> len(assembly.fasteners)
        2
        >>> [hole.diameter for _, hole in assembly.pilot_holes["a"]]
        [8.0, 8.0]
    """

    model: Model
    boxes: dict[str, Box]
    fasteners: tuple[Fastener, ...]
    fastener_issues: tuple[LayoutIssue, ...]
    pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]]
    placement: Placement
    label: str | None

    @classmethod
    def of(cls, model: Model) -> "Assembly":
        """Create an Assembly from a Model.

        Args:
            model: Model containing pieces and connections; unknown lengths
                and offsets are resolved first (see ``resolve_model``)

        Returns:
            Assembly with placement, fasteners and pilot holes
        """
        model = resolve_model(model)
        boxes = {
            piece.id: Box(shape=get_shape(piece)) for piece in model.pieces.values()
        }

        placement = solve_placement(model)
        # A connection that contradicts the placement does not hold in the
        # assembled piece, so drilling for it would make holes that never meet.
        rejected = {(c.base_id, c.target_id) for c in placement.conflicts}

        fasteners: list[Fastener] = []
        issues: list[LayoutIssue] = []
        for (base_id, target_id), connection in model.connections.items():
            if (base_id, target_id) in rejected:
                continue
            laid_out, issue = layout_fasteners(connection)
            fasteners.extend(laid_out)
            if issue is not None:
                issues.append(issue)
        issues += find_hole_collisions(fasteners, model.pieces)

        pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]] = {}
        for fastener in fasteners:
            pilot_holes.setdefault(fastener.base_id, []).append(
                (fastener.base_position, fastener.base_hole)
            )
            pilot_holes.setdefault(fastener.target_id, []).append(
                (fastener.target_position, fastener.target_hole)
            )

        return cls(
            model=model,
            label=model.label,
            boxes=boxes,
            fasteners=tuple(fasteners),
            fastener_issues=tuple(issues),
            pilot_holes=pilot_holes,
            placement=placement,
        )
