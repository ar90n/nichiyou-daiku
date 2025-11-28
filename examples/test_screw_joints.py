"""Test screw joint implementation with various face combinations."""

from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.connection import BoundAnchor, Connection, DowelConnection
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.assembly import Assembly


def test_face_combination(
    lhs_face: str,
    lhs_edge: str,
    rhs_face: str,
    rhs_edge: str,
    description: str,
):
    """Test a specific face combination for screw joints."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"  LHS: contact={lhs_face}, edge={lhs_edge}")
    print(f"  RHS: contact={rhs_face}, edge={rhs_edge}")
    print(f"{'='*60}")

    # Create pieces
    p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
    p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")

    # Create screw connection
    conn = Connection(
        base=BoundAnchor(
            piece=p1,
            anchor=Anchor(
                contact_face=lhs_face,
                edge_shared_face=lhs_edge,
                offset=FromMax(value=100),
            ),
        ),
        target=BoundAnchor(
            piece=p2,
            anchor=Anchor(
                contact_face=rhs_face,
                edge_shared_face=rhs_edge,
                offset=FromMin(value=50),
            ),
        ),
        type=DowelConnection(radius=4.0, depth=20.0),
    )

    # Create model and assembly
    try:
        model = Model.of(
            pieces=[p1, p2],
            connections=[conn],
            label=f"test_{lhs_face}_{rhs_face}",
        )

        assembly = Assembly.of(model)

        # Verify joints were created
        print(f"✅ SUCCESS")
        print(f"   Created {len(assembly.joints)} joints:")
        for joint_id, joint in assembly.joints.items():
            print(
                f"     {joint_id}: face={joint.position.face}, "
                f"u={joint.position.position.u:.1f}, v={joint.position.position.v:.1f}"
            )
        print(f"   Joint pairs: {len(assembly.joint_conns)}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def main():
    """Test various face combinations."""
    print("\n" + "=" * 60)
    print("SCREW JOINT FACE COMBINATION TESTS")
    print("=" * 60)

    results = []

    # Group A: top/down <-> left/right
    results.append(
        test_face_combination(
            "top", "front", "left", "top", "Group A: top <-> left"
        )
    )
    results.append(
        test_face_combination(
            "down", "back", "right", "down", "Group A: down <-> right"
        )
    )

    # Group B: top/down <-> front/back
    results.append(
        test_face_combination(
            "top", "left", "front", "top", "Group B: top <-> front"
        )
    )
    results.append(
        test_face_combination(
            "down", "right", "back", "down", "Group B: down <-> back"
        )
    )

    # Group C: left/right <-> front/back
    results.append(
        test_face_combination(
            "left", "front", "front", "left", "Group C: left <-> front"
        )
    )
    results.append(
        test_face_combination(
            "right", "back", "back", "right", "Group C: right <-> back"
        )
    )

    # Existing: top/down <-> top/down (should work)
    results.append(
        test_face_combination(
            "top", "front", "down", "front", "Existing: top <-> down"
        )
    )

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All face combinations working correctly!")
        return 0
    else:
        print(f"❌ {total - passed} face combination(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
