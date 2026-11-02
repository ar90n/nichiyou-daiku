//! The part drawings' facts match the Python version's (NAME.parts.json,
//! written by tools/make_goldens.py).

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::parts::{PartTitle, part_facts, part_groups};
use nichiyou_daiku_core::pyfmt::{format_mm, round_mm};
use serde_json::{Value, json};

mod common;
use common::normalize;

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/corpus");

/// The title as the Python version wrote it on one line.
fn one_line(title: &PartTitle) -> String {
    let count = title.pieces.len();
    let names = title.pieces.join(", ");
    let mut fields = vec![
        if count > 1 {
            format!("{names} ×{count}")
        } else {
            names
        },
        title.lumber.to_string(),
        format_mm(title.length),
    ];
    for kind in &title.holes {
        let deep = kind
            .depth
            .map_or(String::new(), |d| format!(" ↧{}", format_mm(d)));
        fields.push(format!(
            "φ{}{deep} ×{}",
            format_mm(kind.diameter),
            kind.count
        ));
    }
    fields.join("   ")
}

fn facts(source: &str) -> Value {
    let model = nichiyou_daiku_core::dsl::parse(source).expect("a source that assembles");
    let mut assembly = Assembly::of(model).expect("a source that assembles");
    common::python_holes(&mut assembly);
    let parts: Vec<Value> = part_groups(&assembly)
        .iter()
        .enumerate()
        .filter(|(_, group)| !group.holes.is_empty())
        .map(|(index, group)| {
            let facts = part_facts(&assembly.model, group);
            let letters: serde_json::Map<String, Value> = facts
                .letters
                .iter()
                .map(|(f, l)| (f.as_str().to_string(), json!(l.to_string())))
                .collect();
            let faces: Vec<Value> = facts
                .faces
                .iter()
                .map(|f| {
                    json!({
                        "face": f.face.as_str(),
                        "right": f.right.iter().map(|&s| round_mm(s)).collect::<Vec<_>>(),
                        "up": f.up.iter().map(|&s| round_mm(s)).collect::<Vec<_>>(),
                    })
                })
                .collect();
            json!({"index": index, "title": one_line(&facts.title), "letters": letters, "faces": faces})
        })
        .collect();
    json!({"parts": parts})
}

#[test]
fn part_drawings_say_what_the_python_version_says() {
    let mut paths: Vec<PathBuf> = fs::read_dir(DIR)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.extension().is_some_and(|e| e == "nd"))
        .collect();
    paths.sort();
    let (mut checked, mut differ) = (0, Vec::new());
    for path in paths {
        let Ok(text) = fs::read_to_string(path.with_extension("parts.json")) else {
            continue;
        };
        let expected = normalize(serde_json::from_str(&text).unwrap(), &mut HashMap::new());
        let actual = normalize(
            facts(&fs::read_to_string(&path).unwrap()),
            &mut HashMap::new(),
        );
        if actual != expected {
            differ.push(format!(
                "{}\n  rust:   {actual}\n  python: {expected}",
                path.display()
            ));
        }
        checked += 1;
    }
    assert!(
        checked >= 600,
        "only {checked} cases have parts goldens: run tools/make_goldens.py --steps-only"
    );
    assert!(
        differ.is_empty(),
        "{} of {checked} cases differ:\n{}",
        differ.len(),
        differ
            .iter()
            .take(3)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    );
}
