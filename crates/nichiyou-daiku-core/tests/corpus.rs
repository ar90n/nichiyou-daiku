//! Compare the Rust core with the Python version's golden files.
//!
//! Every case must match, but for those in known_differences.toml, where the
//! Rust core is better on purpose. `ND_CORPUS_SHOW=<part of a name>` prints
//! how those cases differ.

use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fs;
use std::path::{Path, PathBuf};

use serde_json::Value;

mod common;
use common::normalize;

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/corpus");

/// The descriptions a syntax error lists, as Python prints them.
const DESCRIPTIONS: &[&str] = &[
    "end of input",
    "identifier",
    "number",
    "string",
    "piece type (1x4, 1x6, 1x8, 2x2, 2x4, 2x6)",
    "face letter (T, D, L, R, F, B)",
    "screw type (Slim, Coarse)",
    "'?' (unknown)",
    "':'",
    "','",
    "'>'",
    "'<'",
    "'V'",
    "'D('",
    "'='",
    "'FromMax'",
    "'FromMin'",
    "'{'",
    "'('",
    "'-'",
    "'+'",
    "'}'",
    "')'",
    "'S('",
    "'/'",
    "'*'",
    "'steps'",
    "'x'",
    "'-['",
    "']-'",
    "'\"type\"'",
    "'\"vanilla\"'",
    "'\"dowel\"'",
    "'\"radius\"'",
    "'\"depth\"'",
    "'\"screw\"'",
    "'\"diameter\"'",
    "'\"length\"'",
];
const HINTS: &[&str] = &[
    ". '?' (unknown) works",
    ". 'steps' starts the steps block",
    ". A compact offset",
];

struct Case {
    name: String,
    source: String,
    validate: Value,
    holes: Option<Value>,
}

fn read_json(path: &Path) -> Value {
    serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap()
}

fn cases() -> Vec<Case> {
    let mut paths: Vec<PathBuf> = fs::read_dir(DIR)
        .unwrap()
        .map(|entry| entry.unwrap().path())
        .filter(|path| path.extension().is_some_and(|ext| ext == "nd"))
        .collect();
    paths.sort();
    paths
        .into_iter()
        .map(|path| {
            let name = path.file_stem().unwrap().to_string_lossy().into_owned();
            let holes = Path::new(DIR).join(format!("{name}.holes.json"));
            Case {
                source: fs::read_to_string(&path).unwrap(),
                validate: read_json(&Path::new(DIR).join(format!("{name}.validate.json"))),
                holes: holes.exists().then(|| read_json(&holes)),
                name,
            }
        })
        .collect()
}

fn category(golden: &Value) -> String {
    match golden["error"]["kind"].as_str() {
        Some(kind) => kind.to_string(),
        None if golden["problems"].as_array().is_some_and(|p| !p.is_empty()) => "problems".into(),
        None => "valid".into(),
    }
}

fn compare(path: &str, expected: &Value, actual: &Value) -> Result<(), String> {
    match (expected, actual) {
        (Value::Number(e), Value::Number(a)) => {
            let (e, a) = (e.as_f64().unwrap(), a.as_f64().unwrap());
            if (e - a).abs() <= 1e-6 {
                Ok(())
            } else {
                Err(format!("{path}: expected {e}, got {a}"))
            }
        }
        (Value::Array(e), Value::Array(a)) => {
            if e.len() != a.len() {
                return Err(format!(
                    "{path}: expected {} items, got {}: {actual}",
                    e.len(),
                    a.len()
                ));
            }
            e.iter()
                .zip(a)
                .enumerate()
                .try_for_each(|(i, (e, a))| compare(&format!("{path}[{i}]"), e, a))
        }
        (Value::Object(e), Value::Object(a)) => {
            let (ek, ak): (BTreeSet<_>, BTreeSet<_>) = (e.keys().collect(), a.keys().collect());
            if ek != ak {
                return Err(format!("{path}: keys {ek:?} != {ak:?}"));
            }
            e.iter()
                .try_for_each(|(k, e)| compare(&format!("{path}.{k}"), e, &a[k]))
        }
        (e, a) if e == a => Ok(()),
        (e, a) => Err(format!("{path}: expected {e}, got {a}")),
    }
}

struct SyntaxMessage {
    prefix: String,
    found: String,
    expected: BTreeSet<String>,
    rest: String,
}

fn split_syntax(message: &str) -> SyntaxMessage {
    let (prefix, body) = match message.find(": ") {
        Some(i) if message.starts_with("Syntax error") => (&message[..i + 2], &message[i + 2..]),
        _ => ("", message),
    };
    let mut end = body.len();
    for marker in [". Expected"].iter().chain(HINTS) {
        if let Some(i) = body.find(marker) {
            end = end.min(i);
        }
    }
    let (found, mut rest) = (&body[..end], &body[end..]);
    let mut expected = BTreeSet::new();
    for label in [". Expected one of: ", ". Expected: "] {
        if let Some(mut list) = rest.strip_prefix(label) {
            while let Some(item) = DESCRIPTIONS
                .iter()
                .filter(|d| list.starts_with(**d))
                .max_by_key(|d| d.len())
            {
                expected.insert(item.to_string());
                list = &list[item.len()..];
                match list.strip_prefix(", ") {
                    Some(more) => list = more,
                    None => break,
                }
            }
            rest = list;
            break;
        }
    }
    SyntaxMessage {
        prefix: prefix.into(),
        found: found.into(),
        expected,
        rest: rest.into(),
    }
}

fn compare_report(expected: &Value, actual: &Value) -> Result<(), String> {
    if expected["error"]["kind"] != "syntax" {
        return compare("validate", expected, actual);
    }
    let (mut e, mut a) = (expected.clone(), actual.clone());
    let (em, am) = (e["error"]["message"].take(), a["error"]["message"].take());
    compare("validate", &e, &a)?;
    let (Some(em), Some(am)) = (em.as_str(), am.as_str()) else {
        return Err(format!("syntax message: expected {em}, got {am}"));
    };
    let (e, a) = (split_syntax(em), split_syntax(am));
    if e.prefix != a.prefix
        || e.found != a.found
        || e.rest != a.rest
        || !e.expected.is_subset(&a.expected)
    {
        return Err(format!("syntax message:\n  expected {em}\n  got      {am}"));
    }
    Ok(())
}

fn check(case: &Case) -> Result<(), String> {
    let expected = normalize(case.validate.clone(), &mut HashMap::new());
    let actual = normalize(
        nichiyou_daiku_core::validate(&case.source),
        &mut HashMap::new(),
    );
    compare_report(&expected, &actual)?;
    match (&case.holes, nichiyou_daiku_core::holes(&case.source)) {
        (None, None) => Ok(()),
        (Some(e), Some(a)) => {
            let e = normalize(e.clone(), &mut HashMap::new());
            let a = normalize(a, &mut HashMap::new());
            compare("holes", &e, &a)
        }
        (e, a) => Err(format!(
            "holes: expected {}, got {}",
            e.is_some(),
            a.is_some()
        )),
    }
}

fn known_differences() -> BTreeSet<String> {
    let text = fs::read_to_string(Path::new(DIR).join("known_differences.toml")).unwrap();
    let table: toml::Table = text.parse().unwrap();
    table
        .get("difference")
        .and_then(|d| d.as_array())
        .map(|items| {
            items
                .iter()
                .map(|item| item["case"].as_str().unwrap().to_string())
                .collect()
        })
        .unwrap_or_default()
}

#[test]
fn corpus_matches_the_python_version() {
    let known = known_differences();
    let show = std::env::var("ND_CORPUS_SHOW").ok();
    let mut counts: BTreeMap<String, (usize, usize)> = BTreeMap::new();
    let mut failures = Vec::new();
    let cases = cases();
    for case in &cases {
        let result = check(case);
        let entry = counts.entry(category(&case.validate)).or_default();
        entry.1 += 1;
        if result.is_ok() {
            entry.0 += 1;
        }
        if let (Some(part), Err(error)) = (&show, &result)
            && case.name.contains(part.as_str())
        {
            println!("--- {}\n{}\n{error}", case.name, case.source);
        }
        match (known.contains(&case.name), result) {
            (false, Err(error)) => failures.push(format!("{}: {error}", case.name)),
            (true, Ok(())) => failures.push(format!(
                "{} matches now; remove it from known_differences.toml",
                case.name
            )),
            _ => {}
        }
    }
    for name in &known {
        assert!(
            cases.iter().any(|case| &case.name == name),
            "known_differences.toml names {name}, which is not a case"
        );
    }
    for (kind, (ok, all)) in &counts {
        println!("{kind:12} {ok}/{all}");
    }
    assert!(
        failures.is_empty(),
        "{} cases differ from the Python version:\n{}",
        failures.len(),
        failures.join("\n")
    );
}

#[test]
fn a_fuller_expected_list_is_fine_but_a_shorter_one_is_not() {
    let python =
        "Syntax error at line 1, column 9: Unexpected end of input. Expected one of: ')', '+', '-'";
    let fuller = "Syntax error at line 1, column 9: Unexpected end of input. Expected one of: ')', '*', '+', '-', '/'";
    let shorter = "Syntax error at line 1, column 9: Unexpected end of input. Expected: ')'";
    let report = |m: &str| {
        serde_json::json!({"valid": false, "error": {"kind": "syntax", "message": m, "line": 1, "column": 9},
            "overall_size": null, "size_reference": null, "pieces": [], "problems": []})
    };
    assert!(compare_report(&report(python), &report(fuller)).is_ok());
    assert!(compare_report(&report(python), &report(shorter)).is_err());
}

#[test]
fn hints_and_found_tokens_must_match_exactly() {
    let m = split_syntax(
        "Syntax error at line 1, column 5: Unexpected token '?'. Expected one of: '(', '-', identifier, number. '?' (unknown) works in compact notation only, e.g. (x:2x4 =?) or RB? BD?",
    );
    assert_eq!(m.found, "Unexpected token '?'");
    assert_eq!(m.expected.len(), 4);
    assert!(m.rest.starts_with(". '?' (unknown) works"));
    let piece = split_syntax(
        "Syntax error at line 1, column 4: Unexpected token '4'. Expected: piece type (1x4, 1x6, 1x8, 2x2, 2x4, 2x6)",
    );
    assert_eq!(piece.expected.len(), 1);
    assert_eq!(piece.prefix, "Syntax error at line 1, column 4: ");
}

#[test]
fn ids_without_names_are_compared_by_order() {
    let mut names = HashMap::new();
    let v = normalize(
        serde_json::json!([
            "2b0e4a47-8f2e-4c0a-9a8e-1f2d3c4b5a69 x",
            "2b0e4a47-8f2e-4c0a-9a8e-1f2d3c4b5a69"
        ]),
        &mut names,
    );
    assert_eq!(v, serde_json::json!(["anon-1 x", "anon-1"]));
}
