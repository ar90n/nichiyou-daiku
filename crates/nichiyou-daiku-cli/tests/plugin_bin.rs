//! The plugin's entry point (bin/nichiyou-daiku) finds the CLI: one on PATH,
//! else this version's from the cache, else downloaded from the release.
#![cfg(unix)]

use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

const ENTRY: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../bin/nichiyou-daiku");
const VERSION: &str = env!("CARGO_PKG_VERSION");

fn executable(path: &Path, script: &str) {
    fs::write(path, script).unwrap();
    fs::set_permissions(path, fs::Permissions::from_mode(0o755)).unwrap();
}

/// Stands in for `curl -fsL -o OUT URL` with a file:// URL, so the tests
/// need no curl (CI's container has none)
const CURL: &str = r#"#!/bin/sh
out=
while [ $# -gt 1 ]; do
  case $1 in
    -o) out=$2; shift 2 ;;
    *) shift ;;
  esac
done
cp "${1#file://}" "$out" 2>/dev/null
"#;

/// A fresh folder: bin/ with a uname saying `system` and `machine` and a
/// curl for file:// URLs, an empty cache, and releases/ to fill.
fn folder(name: &str, system: &str, machine: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("nd-plugin-{}-{name}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    for sub in ["bin", "cache", "releases"] {
        fs::create_dir_all(dir.join(sub)).unwrap();
    }
    executable(
        &dir.join("bin/uname"),
        &format!("#!/bin/sh\ncase $1 in -s) echo {system} ;; -m) echo {machine} ;; esac\n"),
    );
    executable(&dir.join("bin/curl"), CURL);
    dir
}

/// A release of this version for `target` whose CLI prints what it was
/// given, with the right SHA256SUMS line. Returns the archive's name.
fn release(dir: &Path, target: &str) -> String {
    let stage = dir.join("stage");
    fs::create_dir_all(&stage).unwrap();
    executable(
        &stage.join("nichiyou-daiku"),
        "#!/bin/sh\nprintf prebuilt\nfor arg in \"$@\"; do printf ' [%s]' \"$arg\"; done\necho\n",
    );
    let name = format!("nichiyou-daiku-{VERSION}-{target}.tar.gz");
    let at = dir.join(format!("releases/v{VERSION}"));
    fs::create_dir_all(&at).unwrap();
    let packed = Command::new("tar")
        .arg("-czf")
        .arg(at.join(&name))
        .arg("-C")
        .arg(&stage)
        .arg("nichiyou-daiku")
        .status()
        .unwrap();
    assert!(packed.success());
    let sum = Command::new("sh")
        .arg("-c")
        .arg(format!(
            "cd '{}' && (sha256sum {name} || shasum -a 256 {name})",
            at.display()
        ))
        .output()
        .unwrap();
    fs::write(at.join("SHA256SUMS"), sum.stdout).unwrap();
    name
}

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
    fs::write(
        root.join("Cargo.toml"),
        format!("[workspace]\n\n[workspace.package]\nversion = \"{VERSION}\"\n"),
    )
    .unwrap();
    root
}

fn text(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).into_owned()
}

fn cached(dir: &Path) -> PathBuf {
    dir.join(format!("cache/nichiyou-daiku/{VERSION}/nichiyou-daiku"))
}

#[test]
fn a_cli_on_the_path_comes_first() {
    let dir = folder("path", "Linux", "x86_64");
    executable(
        &dir.join("bin/nichiyou-daiku"),
        "#!/bin/sh\necho \"installed $*\"\n",
    );
    let out = run(&dir, &["validate", "t.nd"]);
    assert_eq!(text(&out.stdout), "installed validate t.nd\n");
}

#[test]
fn the_release_is_downloaded_once_then_run_from_the_cache() {
    let dir = folder("download", "Linux", "x86_64");
    release(&dir, "x86_64-unknown-linux-musl");
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
    release(&dir, "aarch64-apple-darwin");
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
    release(&dir, "x86_64-unknown-linux-musl");
    let out = run(&dir, &["validate"]);
    assert_eq!(text(&out.stdout), "prebuilt [validate]\n");
}

#[test]
fn a_wrong_checksum_is_not_cached() {
    let dir = folder("checksum", "Linux", "x86_64");
    let name = release(&dir, "x86_64-unknown-linux-musl");
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
    release(&dir, "x86_64-unknown-linux-musl");
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
    release(&dir, "x86_64-unknown-linux-musl");
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
