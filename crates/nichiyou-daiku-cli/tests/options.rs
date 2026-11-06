//! The CLI takes no option that does nothing: those kept for the Python
//! version's callers went with it.

use std::process::Command;

fn help(args: &[&str]) -> String {
    let out = Command::new(env!("CARGO_BIN_EXE_nichiyou-daiku"))
        .args(args)
        .arg("--help")
        .output()
        .unwrap();
    String::from_utf8(out.stdout).unwrap()
}

#[test]
fn no_option_is_kept_only_for_the_python_version() {
    assert!(!help(&[]).contains("--debug"), "{}", help(&[]));
    for command in ["render", "steps", "drawing", "export"] {
        let text = help(&[command]);
        assert!(!text.contains("--fillet-radius"), "{command}: {text}");
    }
}
