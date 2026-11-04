//! install.sh puts the newest release's CLI, or the version asked, in a
//! folder, checked against SHA256SUMS, and says what keeps it from running.
#![cfg(unix)]

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};

mod release;
use release::*;

const INSTALL: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../install.sh");

/// Runs install.sh with `args`, PATH being dir/bin, `extra` and the system's tools.
fn install(dir: &Path, extra: &[PathBuf], args: &[&str]) -> Output {
    let mut path = vec![dir.join("bin")];
    path.extend(extra.iter().cloned());
    let path: Vec<String> = path.iter().map(|p| p.display().to_string()).collect();
    Command::new("sh")
        .arg(INSTALL)
        .args(args)
        .env_clear()
        .env("PATH", format!("{}:/usr/bin:/bin", path.join(":")))
        .env("HOME", dir)
        .env(
            "NICHIYOU_DAIKU_RELEASES",
            format!("file://{}", dir.join("releases").display()),
        )
        .env(
            "NICHIYOU_DAIKU_LATEST",
            format!("file://{}", dir.join("latest.json").display()),
        )
        .output()
        .unwrap()
}

fn newest(dir: &Path, version: &str) {
    fs::write(
        dir.join("latest.json"),
        format!("{{\n  \"url\": \"x\",\n  \"tag_name\": \"v{version}\",\n  \"name\": \"v{version}\"\n}}\n"),
    )
    .unwrap();
}

fn runs(binary: &Path) -> String {
    text(
        &Command::new(binary)
            .arg("validate")
            .output()
            .unwrap()
            .stdout,
    )
}

#[test]
fn installs_the_newest_release() {
    let dir = folder("newest", "Linux", "x86_64");
    newest(&dir, "9.9.9");
    release(&dir, "9.9.9", "x86_64-unknown-linux-musl");
    let to = dir.join("tools");
    let out = install(
        &dir,
        std::slice::from_ref(&to),
        &["--to", to.to_str().unwrap()],
    );
    let err = text(&out.stderr);
    assert!(out.status.success(), "{err}");
    assert_eq!(
        err,
        format!(
            "nichiyou-daiku: installed v9.9.9 for x86_64-unknown-linux-musl in {}\n",
            to.display()
        )
    );
    assert_eq!(runs(&to.join("nichiyou-daiku")), "prebuilt [validate]\n");
}

#[test]
fn installs_the_version_asked() {
    let dir = folder("asked", "Darwin", "arm64");
    release(&dir, "1.2.3", "aarch64-apple-darwin");
    let to = dir.join("tools");
    for asked in ["1.2.3", "v1.2.3"] {
        let out = install(
            &dir,
            std::slice::from_ref(&to),
            &["--version", asked, "--to", to.to_str().unwrap()],
        );
        assert!(out.status.success(), "{}", text(&out.stderr));
    }
    assert_eq!(runs(&to.join("nichiyou-daiku")), "prebuilt [validate]\n");
}

#[test]
fn a_wrong_checksum_installs_nothing() {
    let dir = folder("checksum", "Linux", "x86_64");
    let name = release(&dir, "1.2.3", "x86_64-unknown-linux-musl");
    fs::write(
        dir.join("releases/v1.2.3/SHA256SUMS"),
        format!("{}  {name}\n", "0".repeat(64)),
    )
    .unwrap();
    let to = dir.join("tools");
    let out = install(
        &dir,
        std::slice::from_ref(&to),
        &["--version", "1.2.3", "--to", to.to_str().unwrap()],
    );
    assert_eq!(out.status.code(), Some(1));
    let err = text(&out.stderr);
    assert!(
        err.contains("could not install v1.2.3 (its checksum does not match SHA256SUMS)"),
        "{err}"
    );
    assert!(
        err.contains("https://github.com/ar90n/nichiyou-daiku/releases"),
        "{err}"
    );
    assert!(!to.join("nichiyou-daiku").exists());
}

#[test]
fn an_unknown_system_is_named() {
    let dir = folder("unknown", "Plan9", "pdp11");
    let out = install(&dir, &[], &["--version", "1.2.3"]);
    assert_eq!(out.status.code(), Some(1));
    let err = text(&out.stderr);
    assert!(
        err.contains("no prebuilt nichiyou-daiku for Plan9 pdp11"),
        "{err}"
    );
    assert!(err.contains("build it from source"), "{err}");
}

#[test]
fn a_folder_off_the_path_is_named() {
    let dir = folder("off", "Linux", "x86_64");
    release(&dir, "1.2.3", "x86_64-unknown-linux-musl");
    let to = dir.join("tools");
    let out = install(
        &dir,
        &[],
        &["--version", "1.2.3", "--to", to.to_str().unwrap()],
    );
    let err = text(&out.stderr);
    assert!(
        err.contains(&format!("{} is not on PATH; add it", to.display())),
        "{err}"
    );
    // By default it goes to ~/.local/bin
    let out = install(&dir, &[], &["--version", "1.2.3"]);
    assert!(out.status.success(), "{}", text(&out.stderr));
    assert!(dir.join(".local/bin/nichiyou-daiku").is_file());
}

#[test]
fn an_older_python_cli_on_the_path_is_named() {
    let dir = folder("python", "Linux", "x86_64");
    release(&dir, "1.2.3", "x86_64-unknown-linux-musl");
    let old = dir.join("old");
    fs::create_dir_all(&old).unwrap();
    // click answers an unknown option with exit 2
    executable(
        &old.join("nichiyou-daiku"),
        "#!/bin/sh\necho 'Error: No such option: --version' >&2\nexit 2\n",
    );
    let to = dir.join("tools");
    let out = install(
        &dir,
        &[old.clone(), to.clone()],
        &["--version", "1.2.3", "--to", to.to_str().unwrap()],
    );
    let err = text(&out.stderr);
    assert!(out.status.success(), "{err}");
    assert!(
        err.contains(&format!(
            "{} is an older nichiyou-daiku (the Python version); remove it with: uv tool uninstall nichiyou-daiku",
            old.join("nichiyou-daiku").display()
        )),
        "{err}"
    );
}

#[test]
fn piped_into_sh_it_installs() {
    // As in curl -fsSL …/install.sh | sh -s -- --to DIR
    let dir = folder("piped", "Linux", "x86_64");
    release(&dir, "1.2.3", "x86_64-unknown-linux-musl");
    let to = dir.join("tools");
    let mut child = Command::new("sh")
        .args([
            "-s",
            "--",
            "--version",
            "1.2.3",
            "--to",
            to.to_str().unwrap(),
        ])
        .env_clear()
        .env(
            "PATH",
            format!(
                "{}:{}:/usr/bin:/bin",
                dir.join("bin").display(),
                to.display()
            ),
        )
        .env("HOME", &dir)
        .env(
            "NICHIYOU_DAIKU_RELEASES",
            format!("file://{}", dir.join("releases").display()),
        )
        .stdin(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(&fs::read(INSTALL).unwrap())
        .unwrap();
    let out = child.wait_with_output().unwrap();
    assert!(out.status.success(), "{}", text(&out.stderr));
    assert_eq!(runs(&to.join("nichiyou-daiku")), "prebuilt [validate]\n");
}
