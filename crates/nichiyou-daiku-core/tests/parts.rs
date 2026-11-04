//! The part drawings' facts for every corpus case that assembles, against
//! NAME.parts.json.

use std::path::Path;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::parts::{PartTitle, part_facts, part_groups};
use nichiyou_daiku_core::pyfmt::{format_mm, round_mm};
use serde_json::{Value, json};

mod common;
use common::{assert_none, check_golden, corpus, pretty};

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/corpus");

/// The title on one line.
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

fn facts(source: &str) -> Option<Value> {
    let model = nichiyou_daiku_core::dsl::parse(source).ok()?;
    let assembly = Assembly::of(model).ok()?;
    let groups = part_groups(&assembly);
    let parts: Vec<Value> = groups
        .iter()
        .enumerate()
        .filter(|(_, group)| !group.holes.is_empty())
        .map(|(index, _)| {
            let facts = part_facts(&assembly.model, &groups, index);
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
    Some(json!({"parts": parts}))
}

#[test]
fn part_drawings_match_their_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in corpus(Path::new(DIR)) {
        let got = facts(&source).map(|f| pretty(&f));
        checked += usize::from(got.is_some());
        let path = Path::new(DIR).join(format!("{name}.parts.json"));
        if let Err(error) = check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= 600, "only {checked} cases assemble");
    assert_none(&failures, checked);
}
