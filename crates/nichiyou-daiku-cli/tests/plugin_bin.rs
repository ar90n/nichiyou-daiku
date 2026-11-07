//! The plugin's entry point (bin/nichiyou-daiku) runs the plugin's own
//! version of the CLI: from the cache, else downloaded from the release;
//! never one on PATH. NICHIYOU_DAIKU_BIN names one to run instead.
#![cfg(unix)]

use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

mod release;
use release::*;

const ENTRY: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../bin/nichiyou-daiku");
const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Runs `script` (the entry point or a copy or link of it) with only
/// `dir/bin` and the system's tools on PATH.
fn run_script(dir: &Path, script: &Path, args: &[&str]) -> Output {
    Command::new("sh")
        .arg(script)
        .args(args)
        .env_clear()
        .env(
            "PATH",
            format!("{}:/usr/bin:/bin", dir.join("bin").display()),
        )
        .env("HOME", dir)
        .env("XDG_CACHE_HOME", dir.join("cache"))
        .env(
            "NICHIYOU_DAIKU_RELEASES",
            format!("file://{}", dir.join("releases").display()),
        )
        .output()
        .unwrap()
}

fn run(dir: &Path, args: &[&str]) -> Output {
    run_script(dir, Path::new(ENTRY), args)
}

/// A copy of the entry point in a plugin root at `dir/name`, with the
/// version it reads.
fn plugin(dir: &Path, name: &str) -> PathBuf {
    let root = dir.join(name);
    fs::create_dir_all(root.join("bin")).unwrap();
    fs::copy(ENTRY, root.join("bin/nichiyou-daiku")).unwrap();
    fs::copy(
        concat!(env!("CARGO_MANIFEST_DIR"), "/../../install.sh"),
        root.join("install.sh"),
    )
    .unwrap();
    fs::write(
        root.join("Cargo.toml"),
        format!("[workspace]\n\n[workspace.package]\nversion = \"{VERSION}\"\n"),
    )
    .unwrap();
    root
}

fn cached(dir: &Path) -> PathBuf {
    dir.join(format!("cache/nichiyou-daiku/{VERSION}/nichiyou-daiku"))
}

#[test]
fn a_cli_on_the_path_is_not_used() {
    // Such as the Python version installed with uv: the plugin runs its own
    let dir = folder("path", "Linux", "x86_64");
    executable(
        &dir.join("bin/nichiyou-daiku"),
        "#!/bin/sh\necho installed\n",
    );
    release(&dir, VERSION, "x86_64-unknown-linux-musl");
    let out = run(&dir, &["validate", "t.nd"]);
    assert_eq!(
        text(&out.stdout),
        "prebuilt [validate] [t.nd]\n",
        "{}",
        text(&out.stderr)
    );
}

#[test]
fn nichiyou_daiku_bin_runs_instead() {
    let dir = folder("bin", "Linux", "x86_64");
    executable(&dir.join("dev"), "#!/bin/sh\necho \"dev $*\"\n");
    let out = Command::new("sh")
        .arg(ENTRY)
        .arg("validate")
        .env_clear()
        .env("PATH", "/usr/bin:/bin")
        .env("NICHIYOU_DAIKU_BIN", dir.join("dev"))
        .output()
        .unwrap();
    assert_eq!(text(&out.stdout), "dev validate\n");
}

#[test]
fn the_release_is_downloaded_once_then_run_from_the_cache() {
    let dir = folder("download", "Linux", "x86_64");
    release(&dir, VERSION, "x86_64-unknown-linux-musl");
    let out = run(&dir, &["validate", "t.nd"]);
    assert_eq!(
        text(&out.stdout),
        "prebuilt [validate] [t.nd]\n",
        "{}",
        text(&out.stderr)
    );
    assert_eq!(
        text(&out.stderr),
        format!("nichiyou-daiku: downloaded v{VERSION} for x86_64-unknown-linux-musl\n")
    );
    assert!(cached(&dir).is_file());
    fs::remove_dir_all(dir.join("releases")).unwrap();
    let again = run(&dir, &["report", "t.nd"]);
    assert_eq!(text(&again.stdout), "prebuilt [report] [t.nd]\n");
    assert_eq!(text(&again.stderr), "");
}

#[test]
fn a_mac_on_arm_gets_the_arm_build() {
    let dir = folder("mac", "Darwin", "arm64");
    release(&dir, VERSION, "aarch64-apple-darwin");
    let out = run(&dir, &["--help"]);
    assert_eq!(
        text(&out.stdout),
        "prebuilt [--help]\n",
        "{}",
        text(&out.stderr)
    );
}

#[test]
fn an_older_version_in_the_cache_is_not_used() {
    let dir = folder("older", "Linux", "x86_64");
    let old = dir.join("cache/nichiyou-daiku/0.0.1");
    fs::create_dir_all(&old).unwrap();
    executable(&old.join("nichiyou-daiku"), "#!/bin/sh\necho old\n");
    release(&dir, VERSION, "x86_64-unknown-linux-musl");
    let out = run(&dir, &["validate"]);
    assert_eq!(text(&out.stdout), "prebuilt [validate]\n");
}

#[test]
fn a_wrong_checksum_is_not_cached() {
    let dir = folder("checksum", "Linux", "x86_64");
    let name = release(&dir, VERSION, "x86_64-unknown-linux-musl");
    let wrong = format!("{}  {name}\n", "0".repeat(64));
    fs::write(dir.join(format!("releases/v{VERSION}/SHA256SUMS")), wrong).unwrap();
    let out = run(&dir, &["validate"]);
    assert_eq!(out.status.code(), Some(127));
    let err = text(&out.stderr);
    assert!(
        err.contains("(its checksum does not match SHA256SUMS)"),
        "{err}"
    );
    assert!(err.contains("cargo is not installed to build it"), "{err}");
    assert!(!cached(&dir).exists());
}

#[test]
fn a_missing_release_says_what_to_do() {
    let dir = folder("missing", "Linux", "x86_64");
    let out = run(&dir, &["validate"]);
    assert_eq!(out.status.code(), Some(127));
    let err = text(&out.stderr);
    assert!(
        err.starts_with(&format!(
            "nichiyou-daiku: could not download v{VERSION} for x86_64-unknown-linux-musl ("
        )),
        "{err}"
    );
    assert!(
        err.contains("https://github.com/ar90n/nichiyou-daiku/releases"),
        "{err}"
    );
    assert!(err.contains("https://rustup.rs"), "{err}");
    assert!(
        err.contains(&format!("and put it at {}", cached(&dir).display())),
        "{err}"
    );
}

#[test]
fn an_unknown_machine_is_named() {
    let dir = folder("unknown", "Plan9", "pdp11");
    let out = run(&dir, &["validate"]);
    assert_eq!(out.status.code(), Some(127));
    let err = text(&out.stderr);
    assert!(
        err.contains("no prebuilt nichiyou-daiku for Plan9 pdp11"),
        "{err}"
    );
}

#[test]
fn the_entry_point_is_a_posix_shell_script() {
    assert!(
        fs::read_to_string(ENTRY)
            .unwrap()
            .starts_with("#!/bin/sh\n")
    );
}

#[test]
fn a_plugin_path_with_spaces_stays_whole() {
    let dir = folder("spaces", "Linux", "x86_64");
    release(&dir, VERSION, "x86_64-unknown-linux-musl");
    let root = plugin(&dir, "my plugin");
    let out = run_script(
        &dir,
        &root.join("bin/nichiyou-daiku"),
        &["validate", "my table.nd"],
    );
    assert_eq!(
        text(&out.stdout),
        "prebuilt [validate] [my table.nd]\n",
        "{}",
        text(&out.stderr)
    );
}

#[test]
fn a_link_to_the_entry_point_finds_its_plugin() {
    let dir = folder("link", "Linux", "x86_64");
    release(&dir, VERSION, "x86_64-unknown-linux-musl");
    let root = plugin(&dir, "plugin");
    std::os::unix::fs::symlink(root.join("bin/nichiyou-daiku"), dir.join("nd")).unwrap();
    let out = run_script(&dir, &dir.join("nd"), &["validate"]);
    assert_eq!(
        text(&out.stdout),
        "prebuilt [validate]\n",
        "{}",
        text(&out.stderr)
    );
}

#[test]
fn a_nichiyou_daiku_bin_that_is_not_there_is_named() {
    let out = Command::new("sh")
        .arg(ENTRY)
        .arg("validate")
        .env_clear()
        .env("PATH", "/usr/bin:/bin")
        .env("NICHIYOU_DAIKU_BIN", "/nowhere/nichiyou-daiku")
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(127));
    let err = text(&out.stderr);
    assert!(
        err.contains(
            "NICHIYOU_DAIKU_BIN names /nowhere/nichiyou-daiku, which is not an executable file"
        ),
        "{err}"
    );
}

#[test]
fn a_failed_build_says_what_to_do() {
    let dir = folder("build", "Linux", "x86_64");
    executable(
        &dir.join("bin/cargo"),
        "#!/bin/sh\necho 'error: no network' >&2\nexit 101\n",
    );
    let out = run(&dir, &["validate"]);
    assert_eq!(out.status.code(), Some(127));
    let err = text(&out.stderr);
    assert!(
        err.contains("could not build it from source either"),
        "{err}"
    );
    assert!(
        err.contains("Download the CLI for your system from"),
        "{err}"
    );
}
