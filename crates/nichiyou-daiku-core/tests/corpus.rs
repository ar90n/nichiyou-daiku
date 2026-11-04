//! The core's reports for every corpus case against the golden files:
//! NAME.validate.json (what validate --json prints) and, for designs that
//! assemble, NAME.holes.json.

use std::path::Path;

mod common;
use common::{assert_none, check_golden, corpus, pretty};

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/corpus");

#[test]
fn reports_match_their_golden_files() {
    let cases = corpus(Path::new(DIR));
    let mut failures = Vec::new();
    for (name, source) in &cases {
        let validate = pretty(&nichiyou_daiku_core::validate(source));
        let holes = nichiyou_daiku_core::holes(source).map(|h| pretty(&h));
        for (suffix, got) in [("validate.json", Some(validate)), ("holes.json", holes)] {
            let path = Path::new(DIR).join(format!("{name}.{suffix}"));
            if let Err(error) = check_golden(&path, got.as_deref()) {
                failures.push(error);
            }
        }
    }
    assert!(cases.len() >= 700, "only {} corpus cases", cases.len());
    assert_none(&failures, cases.len());
}

#[test]
fn a_golden_file_that_differs_names_its_first_different_line() {
    if common::blessing() {
        return;
    }
    let path = std::env::temp_dir().join(format!("nd-golden-{}.txt", std::process::id()));
    std::fs::write(&path, "a\nb\nc\n").unwrap();
    let error = common::check_golden(&path, Some("a\nB\nc\n")).unwrap_err();
    assert!(
        error.ends_with("differs at line 2:\n  golden: b\n  got:    B"),
        "{error}"
    );
    assert!(common::check_golden(&path, Some("a\nb\nc\n")).is_ok());
    let left = common::check_golden(&path, None).unwrap_err();
    assert!(left.contains("run with ND_BLESS=1 to remove it"), "{left}");
    std::fs::remove_file(&path).unwrap();
    let missing = common::check_golden(&path, Some("x")).unwrap_err();
    assert!(
        missing.contains("is missing; run with ND_BLESS=1"),
        "{missing}"
    );
    assert!(common::check_golden(&path, None).is_ok());
}

#[test]
fn a_report_starts_with_whether_it_is_valid() {
    let report = nichiyou_daiku_core::validate("(a:2x4 =100)");
    let keys: Vec<&str> = report
        .as_object()
        .unwrap()
        .keys()
        .map(String::as_str)
        .collect();
    assert_eq!(
        keys,
        [
            "valid",
            "error",
            "overall_size",
            "size_reference",
            "pieces",
            "connections",
            "steps",
            "problems"
        ]
    );
}

/// Which screws are countersunk: on the head side, and only those without a counterbore.
#[test]
fn screws_without_a_counterbore_and_only_they_are_countersunk_on_the_head_side() {
    use nichiyou_daiku_core::assembly::{Assembly, FastenerKind, countersink_diameter};
    let mut checked = 0;
    for (name, source) in corpus(Path::new(DIR)) {
        let Ok(model) = nichiyou_daiku_core::dsl::parse(&source) else {
            continue;
        };
        let Ok(assembly) = Assembly::of(model) else {
            continue;
        };
        for f in &assembly.fasteners {
            let expected = f.kind == FastenerKind::Screw && f.counterbore.is_none();
            assert_eq!(
                f.countersunk.is_some(),
                expected,
                "{}: {} -> {}",
                name,
                f.base_id,
                f.target_id
            );
            if let Some((at, hole)) = f.countersunk {
                assert_eq!(at.face, f.target_position.face.opposite(), "{}", name);
                assert_eq!(
                    hole.countersink,
                    Some(countersink_diameter(f.diameter)),
                    "{}",
                    name
                );
            }
            checked += 1;
        }
    }
    assert!(checked > 1000, "only {checked} fasteners");
}

const TABLE: &str = "(leg:2x4 =400)
(rail:2x4 =300)
(top:2x4 =300)
(board:1x4 =300)
leg -[FL<300 DF<0]- rail
leg -[TF<0 DF<0 D(:8x30)]- top
top -[FL<0 BL<0 S(Slim:3.3x45)]- board
steps {
  \"Frame\": leg, rail
  \"Top\": top, board
}
";

#[test]
fn a_report_lists_the_connections_and_counts_the_steps() {
    let report = nichiyou_daiku_core::validate(TABLE);
    assert_eq!(report["error"], serde_json::Value::Null);
    assert_eq!(
        report["connections"],
        serde_json::json!([
            {"base": "leg", "target": "rail", "type": "vanilla"},
            {"base": "leg", "target": "top", "type": "dowel"},
            {"base": "top", "target": "board", "type": "screw"},
        ])
    );
    assert_eq!(report["steps"], 2);
    let without = nichiyou_daiku_core::validate(TABLE.split("steps").next().unwrap());
    assert_eq!(without["steps"], 0);
}

#[test]
fn a_report_that_stops_has_no_connections_and_no_steps() {
    let report = nichiyou_daiku_core::validate("(leg:2x4 =)\n");
    assert_eq!(report["error"]["kind"], "syntax");
    assert_eq!(report["connections"], serde_json::json!([]));
    assert_eq!(report["steps"], 0);
}
