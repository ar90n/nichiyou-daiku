//! The Claude Code plugin's manifests and its design skill.

use std::fs;
use std::path::{Path, PathBuf};

use regex::Regex;
use serde_json::Value;

fn root() -> PathBuf {
    Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../.."))
        .canonicalize()
        .unwrap()
}

fn manifest(name: &str) -> Value {
    serde_json::from_str(&fs::read_to_string(root().join(".claude-plugin").join(name)).unwrap())
        .unwrap()
}

fn skill() -> String {
    fs::read_to_string(root().join("skills/design/SKILL.md")).unwrap()
}

#[test]
fn the_manifest_names_the_plugin_without_pinning_a_version() {
    let plugin = manifest("plugin.json");
    assert_eq!(plugin["name"], "nichiyou-daiku");
    assert!(
        plugin["description"]
            .as_str()
            .is_some_and(|d| !d.is_empty())
    );
    // A version pins users to it; without one they follow the commits
    assert!(plugin.get("version").is_none());
}

#[test]
fn the_marketplace_offers_the_repository_as_the_plugin() {
    let market = manifest("marketplace.json");
    assert_eq!(market["name"], "nichiyou-daiku");
    assert!(
        market["owner"]["name"]
            .as_str()
            .is_some_and(|n| !n.is_empty())
    );
    let plugins = market["plugins"].as_array().unwrap();
    assert_eq!(plugins.len(), 1);
    assert_eq!(plugins[0]["name"], manifest("plugin.json")["name"]);
    assert_eq!(plugins[0]["source"], "./");
}

#[test]
fn every_skill_names_and_describes_itself() {
    let header = Regex::new(r"(?s)\A---\n(.*?)\n---\n").unwrap();
    let field = Regex::new(r"(?m)^(\w+): (.+)$").unwrap();
    let skills: Vec<PathBuf> = fs::read_dir(root().join("skills"))
        .unwrap()
        .map(|e| e.unwrap().path().join("SKILL.md"))
        .filter(|p| p.is_file())
        .collect();
    assert!(skills.iter().any(|p| p.ends_with("design/SKILL.md")));
    for path in skills {
        let text = fs::read_to_string(&path).unwrap();
        let front = header.captures(&text).expect("a frontmatter")[1].to_string();
        let fields: Vec<(String, String)> = field
            .captures_iter(&front)
            .map(|c| (c[1].to_string(), c[2].to_string()))
            .collect();
        let get = |key: &str| {
            fields
                .iter()
                .find(|(k, _)| k == key)
                .map(|(_, v)| v.clone())
                .unwrap()
        };
        let folder = path
            .parent()
            .unwrap()
            .file_name()
            .unwrap()
            .to_string_lossy()
            .into_owned();
        assert_eq!(get("name"), folder);
        assert!((1..=1024).contains(&get("description").len()));
    }
}

#[test]
fn the_skill_reads_the_specification_up_to_its_complete_examples() {
    // The examples, CLI, grammar and error sections after that line are not
    // needed to design, and every line read stays in the agent's context
    let found = Regex::new(r"its first (\d+) lines")
        .unwrap()
        .captures(&skill())
        .expect("SKILL.md names how many lines of the specification to read")[1]
        .parse::<usize>()
        .unwrap();
    let spec = fs::read_to_string(root().join("docs/dsl-specification.md")).unwrap();
    assert!(
        spec.lines()
            .nth(found)
            .unwrap()
            .starts_with("## Complete Examples")
    );
}

#[test]
fn the_skill_does_not_rely_on_claude_code_s_plugin_root() {
    // Only Claude Code substitutes it: opencode and other tools read the
    // same skill, so files are linked relative to the skill instead
    let mut stack = vec![root().join("skills")];
    let mut literal = Vec::new();
    while let Some(dir) = stack.pop() {
        for entry in fs::read_dir(dir).unwrap() {
            let path = entry.unwrap().path();
            if path.is_dir() {
                stack.push(path);
            } else if fs::read_to_string(&path).is_ok_and(|t| t.contains("${CLAUDE_PLUGIN_ROOT}")) {
                literal.push(path.display().to_string());
            }
        }
    }
    assert!(literal.is_empty(), "{literal:?}");
}

#[test]
fn the_skill_says_what_to_do_when_the_cli_cannot_be_downloaded() {
    // The entry point downloads the plugin's own CLI; when it cannot, the
    // user downloads it by hand where the message says or installs Rust
    let skill = skill();
    assert!(skill.contains("could not download"), "{skill}");
    assert!(skill.contains("https://rustup.rs"), "{skill}");
    assert!(!skill.contains("cairo"), "{skill}");
}
