//! Helpers the corpus tests share.

use std::collections::HashMap;

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

fn rename_uuids(text: &str, names: &mut HashMap<String, String>) -> String {
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
