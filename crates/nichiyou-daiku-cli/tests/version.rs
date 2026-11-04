//! The CLI names itself and its version, which tells it from the Python
//! version (that has no --version).

use std::process::Command;

#[test]
fn version_names_the_cli_and_its_version() {
    let out = Command::new(env!("CARGO_BIN_EXE_nichiyou-daiku"))
        .arg("--version")
        .output()
        .unwrap();
    assert!(out.status.success());
    assert_eq!(
        String::from_utf8(out.stdout).unwrap(),
        format!("nichiyou-daiku {}\n", env!("CARGO_PKG_VERSION"))
    );
}
