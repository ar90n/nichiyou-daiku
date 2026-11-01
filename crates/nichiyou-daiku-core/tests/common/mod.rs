//! Helpers the corpus tests share.

// Each test crate uses a part of these
#![allow(dead_code)]

use std::collections::{BTreeSet, HashMap};

use serde_json::Value;

// The Python version names anonymous pieces with random UUIDs: both sides
// get anon-1, anon-2, ... in the order the IDs first appear
fn is_uuid_at(bytes: &[u8], at: usize) -> bool {
    const GROUPS: [usize; 5] = [8, 4, 4, 4, 12];
    let mut i = at;
    for (n, len) in GROUPS.iter().enumerate() {
        for _ in 0..*len {
            match bytes.get(i) {
                Some(b) if b.is_ascii_digit() || (b'a'..=b'f').contains(b) => i += 1,
                _ => return false,
            }
        }
        if n < 4 {
            if bytes.get(i) != Some(&b'-') {
                return false;
            }
            i += 1;
        }
    }
    true
}

pub fn rename_uuids(text: &str, names: &mut HashMap<String, String>) -> String {
    let bytes = text.as_bytes();
    let (mut out, mut i) = (String::new(), 0);
    while i < bytes.len() {
        if is_uuid_at(bytes, i) {
            let id = &text[i..i + 36];
            let next = names.len() + 1;
            out.push_str(
                names
                    .entry(id.to_string())
                    .or_insert_with(|| format!("anon-{next}")),
            );
            i += 36;
        } else {
            let ch = text[i..].chars().next().unwrap();
            out.push(ch);
            i += ch.len_utf8();
        }
    }
    out
}

pub fn normalize(value: Value, names: &mut HashMap<String, String>) -> Value {
    match value {
        Value::String(s) => Value::String(rename_uuids(&s, names)),
        Value::Array(items) => {
            Value::Array(items.into_iter().map(|v| normalize(v, names)).collect())
        }
        Value::Object(map) => Value::Object(
            map.into_iter()
                .map(|(k, v)| (rename_uuids(&k, names), normalize(v, names)))
                .collect(),
        ),
        other => other,
    }
}

/// The descriptions a syntax error lists, as Python prints them.
pub const DESCRIPTIONS: &[&str] = &[
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
pub const HINTS: &[&str] = &[
    ". '?' (unknown) works",
    ". 'steps' starts the steps block",
    ". A compact offset",
];

pub struct SyntaxMessage {
    pub prefix: String,
    pub found: String,
    pub expected: BTreeSet<String>,
    pub rest: String,
}

pub fn split_syntax(message: &str) -> SyntaxMessage {
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

/// Whether two syntax error messages agree as the corpus test asks: the same
/// place, token and hints, and every token the Python version expects (the
/// Rust parser may list more).
pub fn same_syntax_message(expected: &str, actual: &str) -> bool {
    let (e, a) = (split_syntax(expected), split_syntax(actual));
    e.prefix == a.prefix
        && e.found == a.found
        && e.rest == a.rest
        && e.expected.is_subset(&a.expected)
}
