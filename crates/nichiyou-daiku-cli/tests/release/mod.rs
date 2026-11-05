//! A fake GitHub release and a system for the entry point's and
//! install.sh's tests: curl for file:// URLs and uname saying what we ask.

#![allow(dead_code)]

use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::Command;

pub fn executable(path: &Path, script: &str) {
    fs::write(path, script).unwrap();
    fs::set_permissions(path, fs::Permissions::from_mode(0o755)).unwrap();
}

/// Stands in for `curl -fsL -o OUT URL` with a file:// URL, so the tests
/// need no curl (CI's container has none)
pub const CURL: &str = r#"#!/bin/sh
out=
effective=
while [ $# -gt 1 ]; do
  case $1 in
    -o) out=$2; shift 2 ;;
    -w) effective=1; shift 2 ;;
    *) shift ;;
  esac
done
if [ -n "$effective" ]; then
  # Stands in for -w '%{url_effective}': the file holds where the URL leads
  cat "${1#file://}" 2>/dev/null
else
  cp "${1#file://}" "$out" 2>/dev/null
fi
"#;

/// A fresh folder: bin/ with a uname saying `system` and `machine` and a
/// curl for file:// URLs, an empty cache, and releases/ to fill.
pub fn folder(name: &str, system: &str, machine: &str) -> PathBuf {
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

/// A release of `version` for `target` whose CLI prints what it was
/// given, each argument in brackets, with the right SHA256SUMS line.
/// Returns the archive's name.
pub fn release(dir: &Path, version: &str, target: &str) -> String {
    let stage = dir.join("stage");
    fs::create_dir_all(&stage).unwrap();
    executable(
        &stage.join("nichiyou-daiku"),
        "#!/bin/sh\nprintf prebuilt\nfor arg in \"$@\"; do printf ' [%s]' \"$arg\"; done\necho\n",
    );
    let name = format!("nichiyou-daiku-{version}-{target}.tar.gz");
    let at = dir.join(format!("releases/v{version}"));
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

pub fn text(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).into_owned()
}
