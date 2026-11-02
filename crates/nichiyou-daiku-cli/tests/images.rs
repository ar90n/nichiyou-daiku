//! render and steps write their images where the Python version wrote them.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use resvg::tiny_skia::Pixmap;

const TABLE: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../examples/nd_files/simple_table_unknowns.nd"
);

/// A fresh folder with the table (screwed, so it has part drawings) in it,
/// as t.nd.
fn folder(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("nd-images-{}-{name}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).unwrap();
    fs::copy(TABLE, dir.join("t.nd")).unwrap();
    dir
}

/// The exit code and stderr of the CLI run in `dir`.
fn run(args: &[&str], stdin: &str, dir: &Path) -> (i32, String) {
    let mut child = Command::new(env!("CARGO_BIN_EXE_nichiyou-daiku"))
        .args(args)
        .current_dir(dir)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let _ = child.stdin.take().unwrap().write_all(stdin.as_bytes());
    let out = child.wait_with_output().unwrap();
    (
        out.status.code().unwrap(),
        String::from_utf8(out.stderr).unwrap(),
    )
}

fn size_of(path: &Path) -> (u32, u32) {
    let image = Pixmap::decode_png(&fs::read(path).unwrap()).unwrap();
    (image.width(), image.height())
}

#[test]
fn render_writes_a_square_png_beside_the_design() {
    let dir = folder("render");
    assert_eq!(
        run(&["render", "t.nd", "--size", "600"], "", &dir),
        (0, "Successfully rendered: t.png\n".into())
    );
    assert_eq!(size_of(&dir.join("t.png")), (600, 600));
}

#[test]
fn render_from_stdin_needs_an_output() {
    let dir = folder("render-stdin");
    let table = fs::read_to_string(TABLE).unwrap();
    assert_eq!(
        run(&["render", "-"], &table, &dir),
        (
            1,
            "Error: An output file (-o) is required when reading from stdin ('-').\n".into()
        )
    );
    // Which file could not be written, so the user knows what to fix
    let (code, err) = run(&["render", "-", "-o", "out/check.png"], &table, &dir);
    assert_eq!(code, 1);
    assert!(
        err.starts_with("Error rendering the image: cannot write out/check.png: "),
        "{err}"
    );
    fs::create_dir_all(dir.join("out")).unwrap();
    assert_eq!(
        run(&["render", "-", "-o", "out/check.png"], &table, &dir),
        (0, "Successfully rendered: out/check.png\n".into())
    );
}

#[test]
fn render_does_not_write_over_its_input() {
    let dir = folder("render-overwrite");
    assert_eq!(
        run(&["render", "t.nd", "-o", "t.nd"], "", &dir),
        (
            1,
            "Error: Refusing to overwrite the input file: t.nd. Choose a different output path with -o.\n"
                .into()
        )
    );
}

fn listed(dir: &Path) -> Vec<String> {
    let mut names: Vec<String> = fs::read_dir(dir)
        .unwrap()
        .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
        .collect();
    names.sort();
    names
}

#[test]
fn steps_writes_the_page_and_its_images() {
    let dir = folder("steps");
    let (code, err) = run(&["steps", "t.nd", "--size", "500"], "", &dir);
    assert_eq!(code, 0, "{err}");
    let out = dir.join("t-steps");
    let names = listed(&out);
    let parts = names.iter().filter(|n| n.starts_with("part-")).count();
    let steps = names.iter().filter(|n| n.starts_with("step-")).count();
    assert!(parts > 0 && steps > 0 && names.contains(&"steps.md".to_string()));
    assert!(
        err.ends_with(&format!(
            "Successfully wrote steps.md, {parts} part drawings and {steps} step images to t-steps\n"
        )),
        "{err}"
    );
    assert_eq!(size_of(&out.join("step-01.png")).0, 500);
    assert!(
        fs::read_to_string(out.join("steps.md"))
            .unwrap()
            .starts_with("# t: assembly steps\n")
    );
}

#[test]
fn old_images_go_and_other_files_stay() {
    let dir = folder("steps-old");
    let out = dir.join("t-steps");
    fs::create_dir_all(&out).unwrap();
    for name in ["step-99.png", "part-77.png", "notes.txt"] {
        fs::write(out.join(name), "old").unwrap();
    }
    assert_eq!(run(&["steps", "t.nd", "--size", "400"], "", &dir).0, 0);
    let names = listed(&out);
    assert!(!names.contains(&"step-99.png".to_string()));
    assert!(!names.contains(&"part-77.png".to_string()));
    assert!(names.contains(&"notes.txt".to_string()));
}

#[test]
fn steps_wants_a_folder() {
    let dir = folder("steps-file");
    fs::write(dir.join("taken"), "").unwrap();
    assert_eq!(
        run(&["steps", "t.nd", "-o", "taken"], "", &dir),
        (
            1,
            "taken is a file; give -o a directory for the steps\n".into()
        )
    );
    let table = fs::read_to_string(TABLE).unwrap();
    assert_eq!(
        run(&["steps", "-"], &table, &dir),
        (
            1,
            "Error: An output file (-o) is required when reading from stdin ('-').\n".into()
        )
    );
    assert_eq!(
        run(
            &["steps", "-", "-o", "piped", "--size", "400"],
            &table,
            &dir
        )
        .0,
        0
    );
    assert!(
        fs::read_to_string(dir.join("piped/steps.md"))
            .unwrap()
            .starts_with("# piped: assembly steps\n")
    );
}

#[test]
fn a_design_without_holes_has_no_part_drawings() {
    let dir = folder("steps-plain");
    fs::write(
        dir.join("plain.nd"),
        "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n",
    )
    .unwrap();
    let (code, err) = run(&["steps", "plain.nd", "--size", "400"], "", &dir);
    assert_eq!(code, 0, "{err}");
    assert!(
        err.ends_with("Successfully wrote steps.md and 1 step image to plain-steps\n"),
        "{err}"
    );
}

#[test]
fn steps_says_which_folder_it_could_not_make() {
    let dir = folder("steps-unwritable");
    let (code, err) = run(&["steps", "t.nd", "-o", "t.nd/steps"], "", &dir);
    assert_eq!(code, 1);
    assert!(
        err.starts_with("Error writing the steps: cannot create t.nd/steps: "),
        "{err}"
    );
}

/// The first page's MediaBox in pt.
fn media_box(pdf: &[u8]) -> Vec<f64> {
    let text = String::from_utf8_lossy(pdf);
    let start = text.find("/MediaBox [").expect("a page size") + "/MediaBox [".len();
    let end = start + text[start..].find(']').expect("a closed MediaBox");
    text[start..end]
        .split_whitespace()
        .map(|n| n.parse().unwrap())
        .collect()
}

#[test]
fn drawing_writes_an_a3_pdf_beside_the_design() {
    let dir = folder("drawing");
    let (code, err) = run(&["drawing", "t.nd"], "", &dir);
    assert_eq!(code, 0, "{err}");
    assert!(
        err.ends_with("Successfully created technical drawing: t.pdf\n"),
        "{err}"
    );
    let pdf = fs::read(dir.join("t.pdf")).unwrap();
    assert!(pdf.starts_with(b"%PDF-"));
    let size = media_box(&pdf);
    assert!(
        (size[2] - 1190.55).abs() < 0.05 && (size[3] - 841.89).abs() < 0.05,
        "{size:?}"
    );
}

#[test]
fn drawing_writes_svg_for_an_svg_name_on_the_page_asked() {
    let dir = folder("drawing-svg");
    let (code, err) = run(
        &["drawing", "t.nd", "-o", "t.SVG", "--page-size", "a4"],
        "",
        &dir,
    );
    assert_eq!(code, 0, "{err}");
    let svg = fs::read_to_string(dir.join("t.SVG")).unwrap();
    assert!(
        svg.starts_with(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"297mm\" height=\"210mm\""
        )
    );
    assert!(svg.contains(">t</text>"), "the title is the design's name");
}

#[test]
fn drawing_from_stdin_is_titled_by_its_output() {
    let dir = folder("drawing-stdin");
    let table = fs::read_to_string(TABLE).unwrap();
    assert_eq!(
        run(&["drawing", "-"], &table, &dir),
        (
            1,
            "Error: An output file (-o) is required when reading from stdin ('-').\n".into()
        )
    );
    assert_eq!(run(&["drawing", "-", "-o", "piped.svg"], &table, &dir).0, 0);
    assert!(
        fs::read_to_string(dir.join("piped.svg"))
            .unwrap()
            .contains(">piped</text>")
    );
}

#[test]
fn drawing_says_why_unconnected_pieces_have_no_dimensions() {
    let dir = folder("drawing-apart");
    fs::write(dir.join("apart.nd"), "(a:2x4 =400)\n(b:2x4 =400)\n").unwrap();
    let (code, err) = run(&["drawing", "apart.nd", "-o", "apart.svg"], "", &dir);
    assert_eq!(code, 0, "{err}");
    assert!(
        err.contains(
            "Warning: the drawing has no dimensions: the pieces are in 2 separate parts. Connect them to dimension it\n"
        ),
        "{err}"
    );
    // Leaving the dimensions out says nothing about them
    let (_, quiet) = run(
        &["drawing", "apart.nd", "-o", "apart.svg", "--no-dimensions"],
        "",
        &dir,
    );
    assert!(!quiet.contains("has no dimensions"), "{quiet}");
}

#[test]
fn drawing_says_which_file_it_could_not_write() {
    let dir = folder("drawing-unwritable");
    let (code, err) = run(&["drawing", "t.nd", "-o", "missing/d.pdf"], "", &dir);
    assert_eq!(code, 1);
    assert!(
        err.starts_with("Error converting to PDF: cannot write missing/d.pdf: "),
        "{err}"
    );
    let (code, err) = run(&["drawing", "t.nd", "-o", "missing/d.svg"], "", &dir);
    assert_eq!(code, 1);
    assert!(
        err.starts_with("Error exporting SVG: cannot write missing/d.svg: "),
        "{err}"
    );
}

#[test]
fn drawing_does_not_write_over_its_input() {
    let dir = folder("drawing-overwrite");
    assert_eq!(
        run(&["drawing", "t.nd", "-o", "t.nd"], "", &dir),
        (
            1,
            "Error: Refusing to overwrite the input file: t.nd. Choose a different output path with -o.\n"
                .into()
        )
    );
}
