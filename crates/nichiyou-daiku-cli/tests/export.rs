//! export writes STL and STEP where and as the Python version did.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

const TABLE: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../examples/nd_files/simple_table_unknowns.nd"
);
const CORPUS: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../nichiyou-daiku-core/tests/corpus"
);

fn folder(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("nd-export-{}-{name}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).unwrap();
    fs::copy(TABLE, dir.join("t.nd")).unwrap();
    dir
}

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

#[test]
fn export_writes_binary_stl_named_by_the_format() {
    let dir = folder("stl");
    let (code, err) = run(&["export", "t.nd", "-f", "stl"], "", &dir);
    assert_eq!(code, 0, "{err}");
    assert!(err.ends_with("Successfully exported to: t.stl\n"), "{err}");
    let bytes = fs::read(dir.join("t.stl")).unwrap();
    let count = u32::from_le_bytes(bytes[80..84].try_into().unwrap()) as usize;
    assert!(count > 0 && bytes.len() == 84 + 50 * count);
}

#[test]
fn export_writes_step_for_a_step_name() {
    let dir = folder("step");
    let (code, err) = run(&["export", "t.nd", "-o", "t.STEP"], "", &dir);
    assert_eq!(code, 0, "{err}");
    let text = fs::read_to_string(dir.join("t.STEP")).unwrap();
    assert!(text.starts_with("ISO-10303-21;"));
    assert!(text.contains("PRODUCT('leg_1','leg_1','',"));
    assert_eq!(run(&["export", "t.nd", "-f", "stp"], "", &dir).0, 0);
    assert!(
        fs::read_to_string(dir.join("t.stp"))
            .unwrap()
            .starts_with("ISO-10303-21;")
    );
}

#[test]
fn export_needs_a_format_it_can_tell() {
    let dir = folder("format");
    assert_eq!(
        run(&["export", "t.nd"], "", &dir),
        (
            1,
            "Error: Either output file (-o) or format (-f) must be specified.\n".into()
        )
    );
    assert_eq!(
        run(&["export", "t.nd", "-o", "t.obj"], "", &dir),
        (1, "Error: Cannot detect format from extension '.obj'. Please specify format with -f option.\n".into())
    );
    assert_eq!(
        run(&["export", "t.nd", "-o", "t.stl", "-f", "step"], "", &dir),
        (
            1,
            "Error: Output extension '.stl' does not match format 'step'.\n".into()
        )
    );
}

#[test]
fn export_from_stdin_needs_an_output_and_never_writes_over_its_input() {
    let dir = folder("stdin");
    let table = fs::read_to_string(TABLE).unwrap();
    assert_eq!(
        run(&["export", "-", "-f", "stl"], &table, &dir),
        (
            1,
            "Error: An output file (-o) is required when reading from stdin ('-').\n".into()
        )
    );
    assert_eq!(run(&["export", "-", "-o", "piped.stl"], &table, &dir).0, 0);
    assert!(dir.join("piped.stl").is_file());
    assert_eq!(
        run(&["export", "t.nd", "-o", "t.nd", "-f", "step"], "", &dir).0,
        1
    );
}

#[test]
fn export_says_which_file_it_could_not_write() {
    let dir = folder("unwritable");
    let (code, err) = run(&["export", "t.nd", "-o", "missing/t.stl"], "", &dir);
    assert_eq!(code, 1);
    assert!(
        err.starts_with("Error exporting file: cannot write missing/t.stl: "),
        "{err}"
    );
}

#[test]
fn export_says_which_hole_it_left_out() {
    // Designs validate reports a hole collision in. It judges by the screw,
    // wider than its hole, so the first whose holes really cross
    let mut cases: Vec<PathBuf> = fs::read_dir(CORPUS)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.to_string_lossy().ends_with(".validate.json"))
        .filter(|p| {
            fs::read_to_string(p)
                .unwrap()
                .contains("\"hole_collision\"")
        })
        .collect();
    cases.sort();
    let dir = folder("collision");
    let warned = cases.iter().find_map(|case| {
        fs::copy(
            case.to_string_lossy().replace(".validate.json", ".nd"),
            dir.join("c.nd"),
        )
        .unwrap();
        let (code, err) = run(&["export", "c.nd", "-f", "step"], "", &dir);
        assert_eq!(code, 0, "{err}");
        err.contains("runs into another hole").then_some(err)
    });
    let err = warned.expect("a collision in the corpus leaves a hole out");
    assert!(
        err.lines().any(|line| line.starts_with("Warning: ")
            && line.contains(": the φ")
            && line.ends_with(
                "runs into another hole; it is left out of the 3D. Fix the collision validate reports"
            )),
        "{err}"
    );
}
