//! render and steps write their images where the Python version wrote them.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use resvg::tiny_skia::Pixmap;

const TABLE: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../examples/nd_files/simple_table_compact.nd"
);

/// A fresh folder with the table in it, as t.nd.
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
    assert_eq!(
        run(&["render", "-", "-o", "out/check.png"], &table, &dir).0,
        1
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
