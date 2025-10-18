"""Generate technical drawing (PDF) from DSL file."""

import sys
from datetime import date
from pathlib import Path
from typing import Optional

import click

from nichiyou_daiku.cli.utils import read_dsl_file, CliEcho
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d, HAS_BUILD123D


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
@click.pass_context
def drawing(
    ctx: click.Context,
    input_file: Path,
    output: Optional[Path],
    title: Optional[str],
    drawing_number: str,
    designed_by: str,
    fillet_radius: float,
) -> None:
    """Generate technical drawing (PDF) with orthographic views.

    Creates A4 technical drawing with:
    - Top view (plan)
    - Front view (elevation)
    - Side view (right side)
    - Isometric view

    \b
    Examples:
        nichiyou-daiku drawing furniture.nd
        nichiyou-daiku drawing table.nd -o table_drawing.pdf
        nichiyou-daiku drawing chair.nd --title "Chair Design"
    """
    echo = CliEcho(ctx)

    # Check build123d availability
    if not HAS_BUILD123D:
        echo.error(
            "Error: build123d is required for technical drawing.\n"
            "Please install it with: uv add nichiyou-daiku[viz]"
        )
        sys.exit(1)

    # Import build123d (after availability check)
    try:
        from build123d import TechnicalDrawing, PageSize, ExportSVG, Unit, LineType
        import cairosvg
    except ImportError as e:
        echo.error(f"Error importing dependencies: {e}\n"
                   "Please install with: uv add nichiyou-daiku[viz]")
        sys.exit(1)

    # Determine output path and title
    output_path = output or input_file.with_suffix(".pdf")
    drawing_title = title or input_file.stem

    # Read and parse DSL
    try:
        dsl_content = read_dsl_file(str(input_file))
        model = parse_dsl(dsl_content)
    except Exception as e:
        echo.error(f"Error parsing DSL file: {e}")
        sys.exit(1)

    # Create assembly and 3D model
    try:
        assembly = Assembly.of(model)
        compound = assembly_to_build123d(assembly, fillet_radius=fillet_radius)
    except Exception as e:
        echo.error(f"Error creating 3D model: {e}")
        sys.exit(1)

    # Create technical drawing border
    try:
        border = TechnicalDrawing(
            designed_by=designed_by,
            design_date=date.today(),
            page_size=PageSize.A4,
            title=drawing_title,
            sub_title="Units: mm",
            drawing_number=drawing_number,
            sheet_number=1,
            drawing_scale=1,
        )
        page_size = border.bounding_box().size
    except Exception as e:
        echo.error(f"Error creating drawing border: {e}")
        sys.exit(1)

    # Generate projections
    try:
        visible_lines, hidden_lines = [], []

        # Calculate unified scale based on model bounding box
        bbox = compound.bounding_box()
        max_dim = max(bbox.size)
        # Target size: 60% of A4 short edge (210mm)
        target_size = 210 * 0.6  # 126mm
        view_scale = target_size / max_dim if max_dim > 0 else 1.0

        # Isometric view (right-top)
        iso_v, iso_h = project_to_2d(
            compound,
            (100, 100, 100),
            (0, 0, 1),
            (page_size.X * 0.25, page_size.Y * 0.2),
            view_scale,
        )
        visible_lines.extend(iso_v)
        hidden_lines.extend(iso_h)

        # Top view (plan, left-top)
        vis, hid = project_to_2d(
            compound,
            (0, 0, 100),
            (0, 1, 0),
            (page_size.X * -0.25, page_size.Y * 0.2),
            view_scale,
        )
        visible_lines.extend(vis)
        hidden_lines.extend(hid)

        # Front view (left-bottom)
        vis, hid = project_to_2d(
            compound,
            (0, -100, 0),
            (0, 0, 1),
            (page_size.X * -0.25, page_size.Y * -0.2),
            view_scale,
        )
        visible_lines.extend(vis)
        hidden_lines.extend(hid)

        # Side view (right-bottom)
        vis, hid = project_to_2d(
            compound,
            (100, 0, 0),
            (0, 0, 1),
            (page_size.X * 0.25, page_size.Y * -0.2),
            view_scale,
        )
        visible_lines.extend(vis)
        hidden_lines.extend(hid)

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
