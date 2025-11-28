"""Generate technical drawing (PDF) from DSL file."""

import sys
from datetime import date
from pathlib import Path
from typing import Optional

import click

from nichiyou_daiku.cli.utils import (
    CliEcho,
    convert_assembly_to_build123d,
    create_assembly_from_model,
    ensure_build123d_available,
    parse_dsl_to_model,
    read_dsl_file,
)


def project_to_2d(part, viewport_origin, viewport_up, page_origin, scale_factor=1.0):
    """Project 3D part to 2D view on page.

    Helper function from build123d tutorial to generate 2D views
    translated on the 2D page.

    Args:
        part: 3D object (Compound)
        viewport_origin: Location of viewport (tuple of 3 floats)
        viewport_up: Direction of viewport Y axis (tuple of 3 floats)
        page_origin: Center of 2D object on page (tuple of 3 floats)
        scale_factor: Part scalar (default: 1.0)

    Returns:
        tuple[ShapeList[Edge], ShapeList[Edge]]: visible & hidden edges
    """
    from build123d import scale as bd_scale, Pos, ShapeList

    scaled_part = part if scale_factor == 1.0 else bd_scale(part, scale_factor)
    visible, hidden = scaled_part.project_to_viewport(
        viewport_origin, viewport_up, look_at=(0, 0, 0)
    )
    visible = [Pos(*page_origin) * e for e in visible]
    hidden = [Pos(*page_origin) * e for e in hidden]

    return ShapeList(visible), ShapeList(hidden)


@click.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output PDF file path (default: <input>.pdf)",
)
@click.option(
    "--title",
    type=str,
    help="Drawing title (default: input filename)",
)
@click.option(
    "--drawing-number",
    type=str,
    default="ND-1",
    help="Drawing number (default: ND-1)",
)
@click.option(
    "--designed-by",
    type=str,
    default="nichiyou-daiku",
    help="Designer name (default: nichiyou-daiku)",
)
@click.option(
    "--fillet-radius",
    type=float,
    default=5.0,
    help="Fillet radius in mm (default: 5.0, use 0 to disable)",
)
@click.option(
    "--page-size",
    type=click.Choice(["A4", "A3", "A2", "A1"], case_sensitive=False),
    default="A3",
    help="Drawing page size (default: A3)",
)
@click.pass_context
def drawing(
    ctx: click.Context,
    input_file: Path,
    output: Optional[Path],
    title: Optional[str],
    drawing_number: str,
    designed_by: str,
    fillet_radius: float,
    page_size: str,
) -> None:
    """Generate technical drawing (PDF) with orthographic views.

    Creates technical drawing with:
    - Top view (plan)
    - Front view (elevation)
    - Side view (right side)
    - Isometric view

    \b
    Examples:
        nichiyou-daiku drawing furniture.nd
        nichiyou-daiku drawing table.nd -o table_drawing.pdf
        nichiyou-daiku drawing chair.nd --title "Chair Design"
        nichiyou-daiku drawing shelf.nd --page-size A2
    """
    echo = CliEcho(ctx)

    # Check build123d availability
    ensure_build123d_available(echo)

    # Import build123d (after availability check)
    try:
        from build123d import TechnicalDrawing, PageSize, ExportSVG, Unit, LineType
        import cairosvg
    except ImportError as e:
        echo.error(
            f"Error importing dependencies: {e}\n"
            "Please install with: uv add nichiyou-daiku[viz]"
        )
        sys.exit(1)

    # Determine output path and title
    output_path = output or input_file.with_suffix(".pdf")
    drawing_title = title or input_file.stem

    # Read and parse DSL
    dsl_content = read_dsl_file(str(input_file))
    model = parse_dsl_to_model(dsl_content, echo)
    assembly = create_assembly_from_model(model, echo)

    # Create 3D model
    compound = convert_assembly_to_build123d(
        assembly, echo, fillet_radius=fillet_radius
    )

    # Create technical drawing border
    try:
        # Map page_size string to PageSize enum
        page_size_map = {
            "A4": PageSize.A4,
            "A3": PageSize.A3,
            "A2": PageSize.A2,
            "A1": PageSize.A1,
        }
        selected_page_size = page_size_map[page_size.upper()]

        border = TechnicalDrawing(
            designed_by=designed_by,
            design_date=date.today(),
            page_size=selected_page_size,
            title=drawing_title,
            sub_title="Units: mm",
            drawing_number=drawing_number,
            sheet_number=1,
            drawing_scale=1,
        )
        border_size = border.bounding_box().size
    except Exception as e:
        echo.error(f"Error creating drawing border: {e}")
        sys.exit(1)

    # Generate projections
    try:
        from build123d import Compound as Build123dCompound

        visible_lines, hidden_lines = [], []

        # Calculate drawing area (considering border and title block)
        # Border: ~20mm, title block: ~40mm height
        drawing_area_width = border_size.X - 40  # Left/right margins
        drawing_area_height = border_size.Y - 80  # Top margin + title block

        # 2x2 grid layout
        margin = 10  # Margin between views
        grid_width = drawing_area_width / 2 - margin
        grid_height = drawing_area_height / 2 - margin

        # Step 1: Project all views at origin to get their bounding boxes
        # This determines the actual size of each view
        top_vis_temp, top_hid_temp = project_to_2d(
            compound, (0, 0, 100), (0, 1, 0), (0, 0), 1.0
        )
        front_vis_temp, front_hid_temp = project_to_2d(
            compound, (0, -100, 0), (0, 0, 1), (0, 0), 1.0
        )
        side_vis_temp, side_hid_temp = project_to_2d(
            compound, (100, 0, 0), (0, 0, 1), (0, 0), 1.0
        )
        iso_vis_temp, iso_hid_temp = project_to_2d(
            compound, (100, 100, 100), (0, 0, 1), (0, 0), 1.0
        )

        # Get bounding boxes
        top_bbox = Build123dCompound(
            children=top_vis_temp + top_hid_temp
        ).bounding_box()
        front_bbox = Build123dCompound(
            children=front_vis_temp + front_hid_temp
        ).bounding_box()
        side_bbox = Build123dCompound(
            children=side_vis_temp + side_hid_temp
        ).bounding_box()
        iso_bbox = Build123dCompound(
            children=iso_vis_temp + iso_hid_temp
        ).bounding_box()

        # Step 2: Calculate unified scale based on largest view
        top_max = max(top_bbox.size.X, top_bbox.size.Y)
        front_max = max(front_bbox.size.X, front_bbox.size.Y)
        side_max = max(side_bbox.size.X, side_bbox.size.Y)
        iso_max = max(iso_bbox.size.X, iso_bbox.size.Y)
        largest_view = max(top_max, front_max, side_max, iso_max)

        # Views should fit in 70% of grid cell (leaving margin)
        max_view_size = min(grid_width, grid_height) * 0.7
        view_scale = max_view_size / largest_view if largest_view > 0 else 1.0

        # Step 3: Re-project with calculated scale to get final bounding boxes
        top_vis_temp, top_hid_temp = project_to_2d(
            compound, (0, 0, 100), (0, 1, 0), (0, 0), view_scale
        )
        front_vis_temp, front_hid_temp = project_to_2d(
            compound, (0, -100, 0), (0, 0, 1), (0, 0), view_scale
        )
        side_vis_temp, side_hid_temp = project_to_2d(
            compound, (100, 0, 0), (0, 0, 1), (0, 0), view_scale
        )
        iso_vis_temp, iso_hid_temp = project_to_2d(
            compound, (100, 100, 100), (0, 0, 1), (0, 0), view_scale
        )

        top_bbox = Build123dCompound(
            children=top_vis_temp + top_hid_temp
        ).bounding_box()
        front_bbox = Build123dCompound(
            children=front_vis_temp + front_hid_temp
        ).bounding_box()
        side_bbox = Build123dCompound(
            children=side_vis_temp + side_hid_temp
        ).bounding_box()
        iso_bbox = Build123dCompound(
            children=iso_vis_temp + iso_hid_temp
        ).bounding_box()

        # Step 4: Calculate grid cell centers
        y_offset = 10  # Offset Y slightly up to account for title block

        left_x_center = -drawing_area_width / 4
        right_x_center = drawing_area_width / 4
        top_y_center = drawing_area_height / 4 + y_offset
        bottom_y_center = -drawing_area_height / 4 + y_offset

        # Step 5: Calculate final positions (bbox center at grid center)
        top_x = left_x_center - top_bbox.center().X
        top_y = top_y_center - top_bbox.center().Y

        front_x = left_x_center - front_bbox.center().X
        front_y = bottom_y_center - front_bbox.center().Y

        iso_x = right_x_center - iso_bbox.center().X
        iso_y = top_y_center - iso_bbox.center().Y

        side_x = right_x_center - side_bbox.center().X
        side_y = bottom_y_center - side_bbox.center().Y

        # Step 6: Final projection at correct positions
        top_vis, top_hid = project_to_2d(
            compound, (0, 0, 100), (0, 1, 0), (top_x, top_y), view_scale
        )
        visible_lines.extend(top_vis)
        hidden_lines.extend(top_hid)

        front_vis, front_hid = project_to_2d(
            compound, (0, -100, 0), (0, 0, 1), (front_x, front_y), view_scale
        )
        visible_lines.extend(front_vis)
        hidden_lines.extend(front_hid)

        iso_vis, iso_hid = project_to_2d(
            compound, (100, 100, 100), (0, 0, 1), (iso_x, iso_y), view_scale
        )
        visible_lines.extend(iso_vis)
        hidden_lines.extend(iso_hid)

        side_vis, side_hid = project_to_2d(
            compound, (100, 0, 0), (0, 0, 1), (side_x, side_y), view_scale
        )
        visible_lines.extend(side_vis)
        hidden_lines.extend(side_hid)

    except Exception as e:
        echo.error(f"Error generating projections: {e}")
        sys.exit(1)

    # Export to SVG
    try:
        exporter = ExportSVG(unit=Unit.MM)
        exporter.add_layer("Visible")
        exporter.add_layer(
            "Hidden", line_color=(99, 99, 99), line_type=LineType.ISO_DOT
        )

        exporter.add_shape(visible_lines, layer="Visible")
        exporter.add_shape(hidden_lines, layer="Hidden")
        exporter.add_shape(border, layer="Visible")

        # Write to temporary SVG
        svg_path = output_path.with_suffix(".svg")
        exporter.write(str(svg_path))

    except Exception as e:
        echo.error(f"Error exporting SVG: {e}")
        sys.exit(1)

    # Convert SVG to PDF
    try:
        cairosvg.svg2pdf(url=str(svg_path), write_to=str(output_path))

        # Clean up temporary SVG
        svg_path.unlink()

        echo.echo(f"Successfully created technical drawing: {output_path}")

    except Exception as e:
        echo.error(f"Error converting to PDF: {e}")
        sys.exit(1)
