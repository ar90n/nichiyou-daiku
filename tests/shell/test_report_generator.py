"""Tests for report generation module."""

from unittest.mock import patch

from nichiyou_daiku.core.piece import PieceType
from nichiyou_daiku.core.resources import ResourceSummary, PieceResource, AnchorInfo
from nichiyou_daiku.shell.report_generator import (
    CutPlan,
    _get_default_standard_lengths,
    _optimize_cuts,
    _generate_overview_section,
    _generate_bill_of_materials,
    _generate_shopping_list,
    _generate_purchase_recommendations,
    _generate_cut_list,
    _generate_anchor_details,
    generate_markdown_report,
)


class TestCutPlan:
    """Test CutPlan dataclass."""

    def test_should_create_cut_plan(self):
        """Should create a CutPlan with all attributes."""
        plan = CutPlan(
            board_length=2440.0,
            cuts=[("piece1", 1000.0), ("piece2", 800.0)],
            waste=640.0,
        )

        assert plan.board_length == 2440.0
        assert len(plan.cuts) == 2
        assert plan.cuts[0] == ("piece1", 1000.0)
        assert plan.waste == 640.0


class TestGetDefaultStandardLengths:
    """Test default standard lengths function."""

    def test_should_return_standard_lengths(self):
        """Should return dict with standard lengths for each piece type."""
        lengths = _get_default_standard_lengths()

        assert isinstance(lengths, dict)
        assert PieceType.PT_2x4 in lengths
        assert PieceType.PT_1x4 in lengths

        # Check that 2x4 has reasonable lengths
        assert len(lengths[PieceType.PT_2x4]) >= 3
        assert all(length > 2000 for length in lengths[PieceType.PT_2x4])

        # Check that 1x4 has different lengths
        assert len(lengths[PieceType.PT_1x4]) >= 3
        assert lengths[PieceType.PT_2x4] != lengths[PieceType.PT_1x4]


class TestOptimizeCuts:
    """Test cut optimization function."""

    def test_should_optimize_simple_cuts(self):
        """Should optimize cuts for simple case."""
        pieces = [
            PieceResource(
                id="p1",
                type=PieceType.PT_2x4,
                length=1000.0,
                width=89.0,
                height=38.0,
                volume=0,
            ),
            PieceResource(
                id="p2",
                type=PieceType.PT_2x4,
                length=800.0,
                width=89.0,
                height=38.0,
                volume=0,
            ),
        ]

        plans = _optimize_cuts(pieces, [2440.0])

        assert len(plans) == 1
        assert plans[0].board_length == 2440.0
        assert len(plans[0].cuts) == 2
        assert plans[0].waste == 640.0

        # Check cuts include both pieces
        cut_ids = [cut[0] for cut in plans[0].cuts]
        assert "p1" in cut_ids
        assert "p2" in cut_ids

    def test_should_use_multiple_boards_when_needed(self):
        """Should use multiple boards when pieces don't fit on one."""
        pieces = [
            PieceResource(
                id="p1",
                type=PieceType.PT_2x4,
                length=2000.0,
                width=89.0,
                height=38.0,
                volume=0,
            ),
            PieceResource(
                id="p2",
                type=PieceType.PT_2x4,
                length=2000.0,
                width=89.0,
                height=38.0,
                volume=0,
            ),
        ]

        plans = _optimize_cuts(pieces, [2440.0])

        assert len(plans) == 2
        assert all(plan.board_length == 2440.0 for plan in plans)
        assert all(len(plan.cuts) == 1 for plan in plans)

    def test_should_choose_optimal_board_length(self):
        """Should choose the most efficient board length."""
        pieces = [
            PieceResource(
                id="p1",
                type=PieceType.PT_2x4,
                length=1500.0,
                width=89.0,
                height=38.0,
                volume=0,
            )
        ]

        # Should prefer the 1830mm board over 2440mm to minimize waste
        plans = _optimize_cuts(pieces, [1830.0, 2440.0])

        assert len(plans) == 1
        assert plans[0].board_length == 1830.0
        assert plans[0].waste == 330.0

    def test_should_handle_empty_pieces_list(self):
        """Should handle empty pieces list gracefully."""
        plans = _optimize_cuts([], [2440.0])
        assert plans == []


class TestGenerateOverviewSection:
    """Test overview section generation."""

    def test_should_generate_overview(self):
        """Should generate project overview section."""
        summary = ResourceSummary(
            pieces=[],
            total_pieces=5,
            pieces_by_type={PieceType.PT_2x4: 3, PieceType.PT_1x4: 2},
            total_length_by_type={PieceType.PT_2x4: 3000.0, PieceType.PT_1x4: 1200.0},
            total_volume=12_000_000.0,
        )

        with patch("nichiyou_daiku.shell.report_generator.datetime") as mock_datetime:
            mock_now = mock_datetime.now.return_value
            mock_now.strftime.return_value = "2023-12-25 10:30"

            overview = _generate_overview_section(summary, "Test Project")

        assert "# Test Project Report" in overview
        assert "Total Pieces**: 5" in overview
        assert "Lumber Types**: 2 (1x4, 2x4)" in overview
        assert "Total Volume**: 12,000,000 mm³" in overview
        assert "~6.0 kg" in overview  # Weight estimation
        assert "2023-12-25 10:30" in overview


class TestGenerateBillOfMaterials:
    """Test bill of materials generation."""

    def test_should_generate_bom_table(self):
        """Should generate markdown table for bill of materials."""
        pieces = [
            PieceResource(
                id="leg1",
                type=PieceType.PT_2x4,
                length=750.0,
                width=89.0,
                height=38.0,
                volume=2_536_500.0,
            ),
            PieceResource(
                id="top1",
                type=PieceType.PT_1x4,
                length=1200.0,
                width=89.0,
                height=19.0,
                volume=2_029_200.0,
            ),
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=2,
            pieces_by_type={PieceType.PT_2x4: 1, PieceType.PT_1x4: 1},
            total_length_by_type={PieceType.PT_2x4: 750.0, PieceType.PT_1x4: 1200.0},
            total_volume=4_565_700.0,
        )

        bom = _generate_bill_of_materials(summary)

        assert "## Bill of Materials" in bom
        assert "| ID | Type | Length (mm)" in bom
        assert "| leg1 | 2x4 | 750 |" in bom
        assert "| top1 | 1x4 | 1200 |" in bom
        assert "2,536,500" in bom  # Volume with commas


class TestGenerateShoppingList:
    """Test shopping list generation."""

    def test_should_generate_shopping_list(self):
        """Should generate aggregated shopping list."""
        summary = ResourceSummary(
            pieces=[],
            total_pieces=7,
            pieces_by_type={PieceType.PT_2x4: 4, PieceType.PT_1x4: 3},
            total_length_by_type={PieceType.PT_2x4: 4800.0, PieceType.PT_1x4: 3600.0},
            total_volume=20_000_000.0,
        )

        shopping_list = _generate_shopping_list(summary)

        assert "## Shopping List" in shopping_list
        assert "**1x4**: 3 pieces, total 3.6 meters" in shopping_list
        assert "**2x4**: 4 pieces, total 4.8 meters" in shopping_list


class TestGeneratePurchaseRecommendations:
    """Test purchase recommendations generation."""

    def test_should_generate_purchase_recommendations(self):
        """Should generate purchase recommendations with optimization."""
        pieces = [
            PieceResource(
                id="p1",
                type=PieceType.PT_2x4,
                length=1000.0,
                width=89.0,
                height=38.0,
                volume=0,
            ),
            PieceResource(
                id="p2",
                type=PieceType.PT_2x4,
                length=800.0,
                width=89.0,
                height=38.0,
                volume=0,
            ),
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=2,
            pieces_by_type={PieceType.PT_2x4: 2},
            total_length_by_type={PieceType.PT_2x4: 1800.0},
            total_volume=6_087_600.0,
        )

        standard_lengths = {PieceType.PT_2x4: [2440.0, 3050.0]}

        recommendations = _generate_purchase_recommendations(summary, standard_lengths)

        assert "## Purchase Recommendations" in recommendations
        assert "2x4 Lumber (Available: 2440mm, 3050mm)" in recommendations
        assert "1 × 2440mm boards" in recommendations
        assert "640mm" in recommendations  # Waste calculation


class TestGenerateCutList:
    """Test cut list generation."""

    def test_should_generate_cut_list(self):
        """Should generate optimized cut list."""
        pieces = [
            PieceResource(
                id="leg1",
                type=PieceType.PT_2x4,
                length=750.0,
                width=89.0,
                height=38.0,
                volume=0,
            ),
            PieceResource(
                id="leg2",
                type=PieceType.PT_2x4,
                length=750.0,
                width=89.0,
                height=38.0,
                volume=0,
            ),
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=2,
            pieces_by_type={PieceType.PT_2x4: 2},
            total_length_by_type={PieceType.PT_2x4: 1500.0},
            total_volume=5_073_000.0,
        )

        standard_lengths = {PieceType.PT_2x4: [2440.0]}

        cut_list = _generate_cut_list(summary, standard_lengths)

        assert "## Optimized Cut List" in cut_list
        assert "2x4 Boards" in cut_list
        assert "Board 1" in cut_list
        assert "Cut 750mm → leg1" in cut_list
        assert "Cut 750mm → leg2" in cut_list
        assert "Waste: 940mm" in cut_list


class TestGenerateMarkdownReport:
    """Test complete markdown report generation."""

    def test_should_generate_complete_report(self):
        """Should generate complete markdown report with all sections."""
        pieces = [
            PieceResource(
                id="test",
                type=PieceType.PT_2x4,
                length=1000.0,
                width=89.0,
                height=38.0,
                volume=3_382_000.0,
            )
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=1,
            pieces_by_type={PieceType.PT_2x4: 1},
            total_length_by_type={PieceType.PT_2x4: 1000.0},
            total_volume=3_382_000.0,
        )

        report = generate_markdown_report(summary, "Test Project")

        # Check all major sections are present
        assert "# Test Project Report" in report
        assert "## Project Overview" in report
        assert "## Bill of Materials" in report
        assert "## Shopping List" in report
        assert "## Purchase Recommendations" in report
        assert "## Optimized Cut List" in report
        assert "*Report generated by nichiyou-daiku*" in report

        # Ensure no internal enum names leak through
        assert "PT_2x4" not in report
        assert "2x4" in report

    def test_should_use_custom_standard_lengths(self):
        """Should use custom standard lengths when provided."""
        pieces = [
            PieceResource(
                id="test",
                type=PieceType.PT_2x4,
                length=1000.0,
                width=89.0,
                height=38.0,
                volume=0,
            )
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=1,
            pieces_by_type={PieceType.PT_2x4: 1},
            total_length_by_type={PieceType.PT_2x4: 1000.0},
            total_volume=3_382_000.0,
        )

        custom_lengths = {PieceType.PT_2x4: [1200.0, 1500.0]}

        report = generate_markdown_report(
            summary, "Custom Project", standard_lengths=custom_lengths
        )

        assert "Available: 1200mm, 1500mm" in report
        assert "1 × 1200mm boards" in report

    def test_should_exclude_cut_diagram_when_requested(self):
        """Should exclude cut diagram section when include_cut_diagram=False."""
        pieces = [
            PieceResource(
                id="test",
                type=PieceType.PT_2x4,
                length=1000.0,
                width=89.0,
                height=38.0,
                volume=0,
            )
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=1,
            pieces_by_type={PieceType.PT_2x4: 1},
            total_length_by_type={PieceType.PT_2x4: 1000.0},
            total_volume=3_382_000.0,
        )

        report = generate_markdown_report(
            summary, "No Cuts Project", include_cut_diagram=False
        )

        assert "## Optimized Cut List" not in report
        assert "## Purchase Recommendations" in report  # Other sections still present

    def test_should_handle_empty_summary(self):
        """Should handle empty resource summary gracefully."""
        summary = ResourceSummary(
            pieces=[],
            total_pieces=0,
            pieces_by_type={},
            total_length_by_type={},
            total_volume=0.0,
        )

        report = generate_markdown_report(summary, "Empty Project")

        assert "# Empty Project Report" in report
        assert "Total Pieces**: 0" in report
        assert "Lumber Types**: 0" in report


class TestGenerateAnchorDetails:
    """Test anchor details generation."""

    def test_should_generate_anchor_details(self):
        """Should generate anchor details table for pieces with anchors."""
        anchors = [
            AnchorInfo(
                contact_face="front",
                edge_shared_face="top",
                offset_type="FromMax",
                offset_value=100.0,
            ),
            AnchorInfo(
                contact_face="back",
                edge_shared_face="left",
                offset_type="FromMin",
                offset_value=50.0,
            ),
        ]

        pieces = [
            PieceResource(
                id="leg1",
                type=PieceType.PT_2x4,
                length=750.0,
                width=89.0,
                height=38.0,
                volume=0,
                anchors=anchors,
            ),
            PieceResource(
                id="top1",
                type=PieceType.PT_1x4,
                length=1200.0,
                width=89.0,
                height=19.0,
                volume=0,
                anchors=[],  # No anchors
            ),
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=2,
            pieces_by_type={PieceType.PT_2x4: 1, PieceType.PT_1x4: 1},
            total_length_by_type={PieceType.PT_2x4: 750.0, PieceType.PT_1x4: 1200.0},
            total_volume=0,
        )

        anchor_details = _generate_anchor_details(summary)

        assert "## Anchor Details" in anchor_details
        assert "### leg1 (2x4, 750mm)" in anchor_details
        assert "| Contact Face | Edge Face | Offset |" in anchor_details
        assert "| front | top | FromMax 100.0mm |" in anchor_details
        assert "| back | left | FromMin 50.0mm |" in anchor_details
        # top1 should not appear (no anchors)
        assert "### top1" not in anchor_details

    def test_should_handle_no_anchors(self):
        """Should handle pieces with no anchors gracefully."""
        pieces = [
            PieceResource(
                id="leg1",
                type=PieceType.PT_2x4,
                length=750.0,
                width=89.0,
                height=38.0,
                volume=0,
                anchors=[],
            )
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=1,
            pieces_by_type={PieceType.PT_2x4: 1},
            total_length_by_type={PieceType.PT_2x4: 750.0},
            total_volume=0,
        )

        anchor_details = _generate_anchor_details(summary)

        assert "## Anchor Details" in anchor_details
        assert "*No anchor points in this project.*" in anchor_details

    def test_should_sort_pieces_by_id(self):
        """Should sort pieces by ID in anchor details."""
        pieces = [
            PieceResource(
                id="z_piece",
                type=PieceType.PT_2x4,
                length=750.0,
                width=89.0,
                height=38.0,
                volume=0,
                anchors=[
                    AnchorInfo(
                        contact_face="front",
                        edge_shared_face="top",
                        offset_type="FromMax",
                        offset_value=100.0,
                    )
                ],
            ),
            PieceResource(
                id="a_piece",
                type=PieceType.PT_2x4,
                length=800.0,
                width=89.0,
                height=38.0,
                volume=0,
                anchors=[
                    AnchorInfo(
                        contact_face="down",
                        edge_shared_face="back",
                        offset_type="FromMin",
                        offset_value=50.0,
                    )
                ],
            ),
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=2,
            pieces_by_type={PieceType.PT_2x4: 2},
            total_length_by_type={PieceType.PT_2x4: 1550.0},
            total_volume=0,
        )

        anchor_details = _generate_anchor_details(summary)

        # Check that a_piece appears before z_piece
        a_pos = anchor_details.find("### a_piece")
        z_pos = anchor_details.find("### z_piece")
        assert a_pos > 0
        assert z_pos > 0
        assert a_pos < z_pos


class TestGenerateMarkdownReportWithAnchors:
    """Test markdown report generation with anchor details."""

    def test_should_include_anchor_details_by_default(self):
        """Should include anchor details section by default."""
        pieces = [
            PieceResource(
                id="test",
                type=PieceType.PT_2x4,
                length=1000.0,
                width=89.0,
                height=38.0,
                volume=0,
                anchors=[
                    AnchorInfo(
                        contact_face="front",
                        edge_shared_face="top",
                        offset_type="FromMax",
                        offset_value=100.0,
                    )
                ],
            )
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=1,
            pieces_by_type={PieceType.PT_2x4: 1},
            total_length_by_type={PieceType.PT_2x4: 1000.0},
            total_volume=0,
        )

        report = generate_markdown_report(summary, "Test Project")

        assert "## Anchor Details" in report
        assert "### test (2x4, 1000mm)" in report
        assert "| front | top | FromMax 100.0mm |" in report

    def test_should_exclude_anchor_details_when_requested(self):
        """Should exclude anchor details when include_anchor_details=False."""
        pieces = [
            PieceResource(
                id="test",
                type=PieceType.PT_2x4,
                length=1000.0,
                width=89.0,
                height=38.0,
                volume=0,
                anchors=[
                    AnchorInfo(
                        contact_face="front",
                        edge_shared_face="top",
                        offset_type="FromMax",
                        offset_value=100.0,
                    )
                ],
            )
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=1,
            pieces_by_type={PieceType.PT_2x4: 1},
            total_length_by_type={PieceType.PT_2x4: 1000.0},
            total_volume=0,
        )

        report = generate_markdown_report(
            summary, "Test Project", include_anchor_details=False
        )

        assert "## Anchor Details" not in report
        assert "## Bill of Materials" in report  # Other sections still present

    def test_should_place_anchor_details_after_bom(self):
        """Should place anchor details section after BOM and before shopping list."""
        pieces = [
            PieceResource(
                id="test",
                type=PieceType.PT_2x4,
                length=1000.0,
                width=89.0,
                height=38.0,
                volume=0,
                anchors=[
                    AnchorInfo(
                        contact_face="front",
                        edge_shared_face="top",
                        offset_type="FromMax",
                        offset_value=100.0,
                    )
                ],
            )
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=1,
            pieces_by_type={PieceType.PT_2x4: 1},
            total_length_by_type={PieceType.PT_2x4: 1000.0},
            total_volume=0,
        )

        report = generate_markdown_report(summary, "Test Project")

        # Check order of sections
        bom_pos = report.find("## Bill of Materials")
        anchor_pos = report.find("## Anchor Details")
        shopping_pos = report.find("## Shopping List")

        assert bom_pos > 0
        assert anchor_pos > 0
        assert shopping_pos > 0
        assert bom_pos < anchor_pos < shopping_pos
