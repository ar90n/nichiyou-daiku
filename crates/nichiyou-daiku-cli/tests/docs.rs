//! The docs stay true to the code: their .nd examples are sound, their
//! tables are the code's, the links and the paths they name exist, and the
//! CLI reference covers every command.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

use nichiyou_daiku_core::piece::PieceType;
use nichiyou_daiku_core::presets::{COARSE_SCREWS, DOWELS, SLIM_SCREWS};
use nichiyou_daiku_core::pyfmt::format_mm;
use regex::Regex;
use serde_json::Value;

fn root() -> PathBuf {
    Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../.."))
        .canonicalize()
        .unwrap()
}

fn walk(dir: &Path) -> Vec<PathBuf> {
    let mut files = Vec::new();
    for entry in fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            files.extend(walk(&path));
        } else {
            files.push(path);
        }
    }
    files
}

fn with_extension(files: Vec<PathBuf>, ext: &str) -> Vec<PathBuf> {
    files
        .into_iter()
        .filter(|p| p.extension().is_some_and(|e| e == ext))
        .collect()
}

/// The Markdown the tests read: docs/ (not its subfolders), the README and the skills.
fn markdown() -> Vec<PathBuf> {
    let root = root();
    let mut files = with_extension(
        fs::read_dir(root.join("docs"))
            .unwrap()
            .map(|e| e.unwrap().path())
            .collect(),
        "md",
    );
    files.push(root.join("README.md"));
    files.extend(with_extension(walk(&root.join("skills")), "md"));
    files.sort();
    files
}

fn spec() -> String {
    fs::read_to_string(root().join("docs/dsl-specification.md")).unwrap()
}

/// (line, language, body) of each fenced block, indented or not.
fn fences(text: &str) -> Vec<(usize, String, String)> {
    let opening = Regex::new(r"^(\s*)(`{3,}|~{3,})\s*([\w-]*)").unwrap();
    let lines: Vec<&str> = text.split_inclusive('\n').collect();
    let mut blocks = Vec::new();
    let mut i = 0;
    while i < lines.len() {
        let Some(open) = opening.captures(lines[i]) else {
            i += 1;
            continue;
        };
        let indent = open[1].to_string();
        let fence = &open[2];
        let closing = Regex::new(&format!(
            r"^\s*{}{{{},}}\s*$",
            regex::escape(&fence[..1]),
            fence.len()
        ))
        .unwrap();
        let mut body = String::new();
        let mut j = i + 1;
        while j < lines.len() && !closing.is_match(lines[j]) {
            body.push_str(lines[j].strip_prefix(indent.as_str()).unwrap_or(lines[j]));
            j += 1;
        }
        blocks.push((i + 1, open[3].to_string(), body));
        i = j + 1;
    }
    blocks
}

fn nd_blocks() -> Vec<(String, String)> {
    let root = root();
    let mut blocks = Vec::new();
    for path in markdown() {
        let rel = path.strip_prefix(&root).unwrap().display().to_string();
        for (line, language, body) in fences(&fs::read_to_string(&path).unwrap()) {
            if language == "nd" {
                blocks.push((format!("{rel}:{line}"), body));
            }
        }
    }
    blocks
}

/// What makes an example unsound: an error, or contradicting connections,
/// overlaps and fasteners that do not fit (an example may leave pieces
/// unconnected).
fn problems(source: &str) -> Vec<String> {
    let report = nichiyou_daiku_core::validate(source);
    if !report["error"].is_null() {
        return vec![report["error"]["message"].to_string()];
    }
    report["problems"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|p| {
            matches!(
                p["kind"].as_str(),
                Some("conflict" | "overlap" | "fastener")
            )
        })
        .map(|p| p["message"].to_string())
        .collect()
}

fn cli(args: &[&str], dir: &Path) -> Output {
    Command::new(env!("CARGO_BIN_EXE_nichiyou-daiku"))
        .args(args)
        .current_dir(dir)
        .output()
        .unwrap()
}

#[test]
fn every_nd_fence_is_collected() {
    // A parser slip would silently drop examples from the test below
    let opening = Regex::new(r"(?m)^\s*(`{3,}|~{3,})\s*nd\b").unwrap();
    let written: usize = markdown()
        .iter()
        .map(|p| opening.find_iter(&fs::read_to_string(p).unwrap()).count())
        .sum();
    let collected = nd_blocks().len();
    assert!(
        written > 0 && collected == written,
        "{collected} of {written}"
    );
}

#[test]
fn nd_examples_in_the_docs_are_sound() {
    let unsound: Vec<String> = nd_blocks()
        .into_iter()
        .filter_map(|(at, source)| {
            let found = problems(&source);
            (!found.is_empty()).then(|| format!("{at}: {found:?}"))
        })
        .collect();
    assert!(unsound.is_empty(), "{unsound:#?}");
}

#[test]
fn example_files_are_sound() {
    let root = root();
    let mut files = with_extension(
        fs::read_dir(root.join("examples/nd_files"))
            .unwrap()
            .map(|e| e.unwrap().path())
            .collect(),
        "nd",
    );
    files.extend(with_extension(walk(&root.join("skills")), "nd"));
    assert!(files.len() >= 6);
    for file in files {
        let found = problems(&fs::read_to_string(&file).unwrap());
        assert!(found.is_empty(), "{}: {found:?}", file.display());
    }
}

/// The text from `heading` up to the next heading of any level below it.
fn section<'a>(text: &'a str, heading: &str) -> &'a str {
    let start = text.find(heading).unwrap_or_else(|| panic!("no {heading}")) + heading.len();
    let rest = &text[start..];
    &rest[..rest.find("\n#").unwrap_or(rest.len())]
}

#[test]
fn the_lumber_table_is_the_code_s() {
    let row = Regex::new(r"(?m)^\| `(\d+x\d+)` \| (\d+) \| (\d+) \|").unwrap();
    let spec = spec();
    let documented: BTreeMap<String, (f64, f64)> = row
        .captures_iter(section(&spec, "### Lumber Types"))
        .map(|c| {
            (
                c[1].to_string(),
                (c[2].parse().unwrap(), c[3].parse().unwrap()),
            )
        })
        .collect();
    let code: BTreeMap<String, (f64, f64)> = PieceType::ALL
        .iter()
        .map(|t| (t.as_str().to_string(), t.cross_section()))
        .collect();
    assert_eq!(documented, code);
}

#[test]
fn the_preset_tables_are_the_code_s() {
    let spec = spec();
    let preset = |(d, l): &(f64, f64)| format!("{}x{}", format_mm(*d), format_mm(*l));
    // Lumber rows look like dowel rows: read only the dowel section
    let dowel_row = Regex::new(r"(?m)^\| `(\d+x\d+)` \| [\d.]+ \| [\d.]+ \|").unwrap();
    let documented: BTreeSet<String> = dowel_row
        .captures_iter(
            &spec[spec.find("### Dowel Connection").unwrap()..spec.find("### Screw").unwrap()],
        )
        .map(|c| c[1].to_string())
        .collect();
    assert_eq!(documented, DOWELS.iter().map(preset).collect());
    let screw_row = Regex::new(r"(?m)^\| `((?:Slim|Coarse):[\d.]+x[\d.]+)` \|").unwrap();
    let documented: BTreeSet<String> = screw_row
        .captures_iter(&spec)
        .map(|c| c[1].to_string())
        .collect();
    let code: BTreeSet<String> = SLIM_SCREWS
        .iter()
        .map(|p| format!("Slim:{}", preset(p)))
        .chain(
            COARSE_SCREWS
                .iter()
                .map(|p| format!("Coarse:{}", preset(p))),
        )
        .collect();
    assert_eq!(documented, code);
}

#[test]
fn the_stock_file_example_reads_as_described() {
    let spec = spec();
    let tomls: Vec<String> = fences(&spec)
        .into_iter()
        .filter(|(_, language, _)| language == "toml")
        .map(|(_, _, body)| body)
        .collect();
    assert_eq!(tomls.len(), 1);
    let dir = std::env::temp_dir().join(format!("nd-docs-stock-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    fs::write(dir.join("stock.toml"), &tomls[0]).unwrap();
    fs::write(dir.join("d.nd"), "(a:1x4 =500)\n(b:2x6 =500)\n").unwrap();
    let out = cli(&["report", "d.nd", "--stock", "stock.toml"], &dir);
    let report = String::from_utf8(out.stdout).unwrap();
    assert!(report.contains("Saw kerf: 2mm per cut"), "{report}");
    assert!(
        report.contains("### 1x4 Lumber (Available: 910mm, 1820mm)"),
        "{report}"
    );
    // Lumber types left out keep the defaults
    assert!(
        report.contains("### 2x6 Lumber (Available: 1820mm, 2440mm, 3050mm, 3650mm)"),
        "{report}"
    );
    fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn relative_links_point_at_existing_files() {
    let link = Regex::new(r#"\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)"#).unwrap();
    let reference = Regex::new(r#"(?m)^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+"[^"]*")?\s*$"#).unwrap();
    let mut missing = Vec::new();
    for path in markdown() {
        let text = fs::read_to_string(&path).unwrap();
        for target in link
            .captures_iter(&text)
            .chain(reference.captures_iter(&text))
            .map(|c| c[1].to_string())
        {
            if ["http:", "https:", "mailto:", "#"]
                .iter()
                .any(|p| target.starts_with(p))
            {
                continue;
            }
            let file = target.split('#').next().unwrap();
            if !path.parent().unwrap().join(file).exists() {
                missing.push(format!("{}: {target}", path.display()));
            }
        }
    }
    assert!(missing.is_empty(), "{missing:#?}");
}

/// Repository paths a text names in code spans or prose, e.g.
/// `skills/design/SKILL.md`, that exist neither from the root nor from
/// `dir`. prompts/, src/ and tests/ stay listed so that naming what was
/// removed fails.
fn missing_mentions(text: &str, dir: &Path) -> Vec<String> {
    let path = Regex::new(
        r"(?:^|[^\w/.-])((?:docs|prompts|examples|skills|bin|src|tests|crates)/[\w./-]*[\w/])",
    )
    .unwrap();
    let plugin = Regex::new(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]*[\w/])").unwrap();
    let root = root();
    let named = path
        .captures_iter(text)
        .map(|c| c[1].to_string())
        .filter(|m| !root.join(m).exists() && !dir.join(m).exists());
    let plugin_named = plugin
        .captures_iter(text)
        .map(|c| c[1].to_string())
        .filter(|m| !root.join(m).exists());
    named.chain(plugin_named).collect()
}

#[test]
fn missing_mentions_are_found() {
    let text = "Read `${CLAUDE_PLUGIN_ROOT}/docs/nope.md` and `prompts/system.md`.";
    assert_eq!(
        missing_mentions(text, &root()),
        ["prompts/system.md", "docs/nope.md"]
    );
}

#[test]
fn mentioned_repo_paths_exist() {
    let mut missing = Vec::new();
    for path in markdown() {
        for mention in missing_mentions(&fs::read_to_string(&path).unwrap(), path.parent().unwrap())
        {
            missing.push(format!("{}: {mention}", path.display()));
        }
    }
    assert!(missing.is_empty(), "{missing:#?}");
}

#[test]
fn the_validate_json_example_is_what_the_cli_prints() {
    let file = "examples/nd_files/corner_angle_compact.nd";
    let blocks = fences(&spec());
    let at = blocks
        .iter()
        .position(|(_, _, body)| body.contains(&format!("validate --json {file}")))
        .expect("the example's command");
    let (_, language, documented) = &blocks[at + 1];
    assert_eq!(language, "json");
    let documented: Value = serde_json::from_str(documented).unwrap();
    let printed: Value =
        serde_json::from_slice(&cli(&["validate", "--json", file], &root()).stdout).unwrap();
    assert_eq!(documented, printed);
}

#[test]
fn every_command_is_in_the_cli_reference() {
    // The DSL specification is the CLI's reference
    let help = String::from_utf8(cli(&["--help"], &root()).stdout).unwrap();
    let commands: Vec<String> = help
        .split("Commands:\n")
        .nth(1)
        .unwrap()
        .lines()
        .take_while(|line| !line.trim().is_empty())
        .filter_map(|line| line.split_whitespace().next())
        .filter(|command| *command != "help")
        .map(str::to_string)
        .collect();
    let spec = spec();
    let missing: Vec<&String> = commands
        .iter()
        .filter(|c| !spec.contains(&format!("nichiyou-daiku {c}")))
        .collect();
    assert!(
        commands.len() >= 7 && missing.is_empty(),
        "{commands:?}: {missing:?}"
    );
}
