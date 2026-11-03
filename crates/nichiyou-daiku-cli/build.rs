//! Builds the viewer (web/dist) into the CLI for `view` when it has been
//! built; without it the table is empty and `view` says how to get it.

use std::fmt::Write as _;
use std::path::{Path, PathBuf};

fn files(dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    let mut paths: Vec<PathBuf> = entries.filter_map(Result::ok).map(|e| e.path()).collect();
    paths.sort();
    for path in paths {
        if path.is_dir() {
            files(&path, out);
        } else {
            out.push(path);
        }
    }
}

fn main() {
    let manifest = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").expect("cargo sets it"));
    let dist = manifest.join("../../web/dist");
    // A missing folder makes cargo run this again on every build, which
    // costs little and picks the viewer up once it is built
    println!("cargo::rerun-if-changed={}", dist.display());
    let mut found = Vec::new();
    if dist.join("index.html").is_file() {
        files(&dist, &mut found);
    }
    let mut table = String::from("pub static VIEWER: &[(&str, &[u8])] = &[\n");
    for path in &found {
        let name = path
            .strip_prefix(&dist)
            .expect("a file under dist")
            .to_string_lossy()
            .replace('\\', "/");
        let full = path.canonicalize().expect("a file found");
        writeln!(
            table,
            "    ({name:?}, include_bytes!({:?})),",
            full.display().to_string()
        )
        .expect("a string takes writes");
    }
    table.push_str("];\n");
    let out = PathBuf::from(std::env::var("OUT_DIR").expect("cargo sets it"));
    std::fs::write(out.join("viewer.rs"), table).expect("OUT_DIR takes the table");
}
