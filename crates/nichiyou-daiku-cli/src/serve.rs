//! What view serves: the viewer built in, or from a folder, and the one
//! design, read again on every request.

use std::path::{Path, PathBuf};

include!(concat!(env!("OUT_DIR"), "/viewer.rs"));

const TEXT: &str = "text/plain; charset=utf-8";

/// The design view shows: a file read again on each request, or what stdin gave.
pub enum Design {
    File { path: PathBuf, name: String },
    Text { name: String, text: String },
}

impl Design {
    pub fn name(&self) -> &str {
        match self {
            Design::File { name, .. } | Design::Text { name, .. } => name,
        }
    }

    fn read(&self) -> Option<Vec<u8>> {
        match self {
            Design::File { path, .. } => std::fs::read(path).ok(),
            Design::Text { text, .. } => Some(text.clone().into_bytes()),
        }
    }
}

pub struct Reply {
    pub status: u16,
    pub content_type: &'static str,
    pub body: Vec<u8>,
    /// The design changes as it is saved: no cache may keep it
    pub no_store: bool,
}

/// Percent-encodes all but the unreserved characters, so a name goes into a
/// URL's query or path as it is.
pub fn encode(name: &str) -> String {
    name.bytes()
        .map(|b| {
            if b.is_ascii_alphanumeric() || b"-._~".contains(&b) {
                char::from(b).to_string()
            } else {
                format!("%{b:02X}")
            }
        })
        .collect()
}

/// The path with its percent-escapes undone; None for a broken escape or text
/// that is not UTF-8. Browsers leave some characters, such as parentheses,
/// unencoded: comparing decoded paths takes either form.
fn decode(path: &str) -> Option<String> {
    let bytes = path.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' {
            let hex = path.get(i + 1..i + 3)?;
            out.push(u8::from_str_radix(hex, 16).ok()?);
            i += 3;
        } else {
            out.push(bytes[i]);
            i += 1;
        }
    }
    String::from_utf8(out).ok()
}

fn content_type(name: &str) -> &'static str {
    match name.rsplit('.').next() {
        Some("html") => "text/html; charset=utf-8",
        Some("js") => "text/javascript",
        Some("css") => "text/css",
        Some("wasm") => "application/wasm",
        Some("svg") => "image/svg+xml",
        Some("png") => "image/png",
        _ => "application/octet-stream",
    }
}

fn not_found(body: String, no_store: bool) -> Reply {
    Reply {
        status: 404,
        content_type: TEXT,
        body: body.into_bytes(),
        no_store,
    }
}

/// The reply to a request for `url` (its path and query, as the request
/// line has it).
pub fn respond(url: &str, viewer: &[(String, Vec<u8>)], design: &Design) -> Reply {
    let raw = url.split(['?', '#']).next().unwrap_or("/");
    let Some(path) = decode(raw) else {
        return not_found("Not found".into(), false);
    };
    if path.strip_prefix('/') == Some(design.name()) {
        return match design.read() {
            Some(body) => Reply {
                status: 200,
                content_type: TEXT,
                body,
                no_store: true,
            },
            None => not_found(format!("{} is gone: save it again", design.name()), true),
        };
    }
    let wanted = if path == "/" {
        "index.html"
    } else {
        path.trim_start_matches('/')
    };
    match viewer.iter().find(|(name, _)| name == wanted) {
        Some((name, body)) => Reply {
            status: 200,
            content_type: content_type(name),
            body: body.clone(),
            no_store: false,
        },
        None => not_found("Not found".into(), false),
    }
}

fn files(dir: &Path, root: &Path, out: &mut Vec<(String, Vec<u8>)>) -> Result<(), String> {
    let entries =
        std::fs::read_dir(dir).map_err(|e| format!("cannot read {}: {e}", dir.display()))?;
    for entry in entries {
        let path = entry.map_err(|e| e.to_string())?.path();
        if path.is_dir() {
            files(&path, root, out)?;
        } else {
            let name = path
                .strip_prefix(root)
                .expect("a file under the folder")
                .to_string_lossy()
                .replace('\\', "/");
            let body =
                std::fs::read(&path).map_err(|e| format!("cannot read {}: {e}", path.display()))?;
            out.push((name, body));
        }
    }
    Ok(())
}

/// The viewer to serve: the folder NICHIYOU_DAIKU_VIEWER names (to try a
/// viewer without building the CLI again), else the one built in.
pub fn viewer(
    folder: Option<&Path>,
    built: &[(&str, &[u8])],
) -> Result<Vec<(String, Vec<u8>)>, String> {
    if let Some(folder) = folder {
        if !folder.join("index.html").is_file() {
            return Err(format!(
                "NICHIYOU_DAIKU_VIEWER names {}, which has no index.html: point it at a built viewer (web/dist)",
                folder.display()
            ));
        }
        let mut found = Vec::new();
        files(folder, folder, &mut found)?;
        return Ok(found);
    }
    if built.is_empty() {
        return Err("This nichiyou-daiku was built without the viewer: build the viewer (make web), then build the CLI again".into());
    }
    Ok(built
        .iter()
        .map(|(name, body)| (name.to_string(), body.to_vec()))
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn folder(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("nd-serve-{}-{name}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn site() -> Vec<(String, Vec<u8>)> {
        vec![
            ("index.html".into(), b"<html>".to_vec()),
            ("assets/a.js".into(), b"js".to_vec()),
            ("assets/a.wasm".into(), b"wasm".to_vec()),
        ]
    }

    fn text(name: &str) -> Design {
        Design::Text {
            name: name.into(),
            text: "(a:2x4 =100)".into(),
        }
    }

    #[test]
    fn a_name_goes_in_a_url_as_it_is() {
        assert_eq!(encode("my table+(1).nd"), "my%20table%2B%281%29.nd");
        assert_eq!(encode("ワゴン.nd"), "%E3%83%AF%E3%82%B4%E3%83%B3.nd");
        assert_eq!(encode("a-b_c.d~e.nd"), "a-b_c.d~e.nd");
    }

    #[test]
    fn browsers_may_leave_some_characters_unencoded() {
        let design = text("my table (1).nd");
        for path in [
            "/my%20table%20%281%29.nd",
            "/my%20table%20(1).nd",
            "/my%20table%20(1).nd?x=1",
        ] {
            let reply = respond(path, &site(), &design);
            assert_eq!(
                (reply.status, reply.body),
                (200, b"(a:2x4 =100)".to_vec()),
                "{path}"
            );
        }
        let japanese = text("ワゴン.nd");
        assert_eq!(
            respond("/%E3%83%AF%E3%82%B4%E3%83%B3.nd", &site(), &japanese).status,
            200
        );
    }

    #[test]
    fn the_design_is_read_again_on_every_request() {
        let dir = folder("design");
        let path = dir.join("t.nd");
        fs::write(&path, "(a:2x4 =100)").unwrap();
        let design = Design::File {
            path: path.clone(),
            name: "t.nd".into(),
        };
        let reply = respond("/t.nd", &[], &design);
        assert_eq!(
            (reply.status, reply.body.as_slice(), reply.no_store),
            (200, &b"(a:2x4 =100)"[..], true)
        );
        assert_eq!(reply.content_type, "text/plain; charset=utf-8");
        fs::write(&path, "(a:2x4 =200)").unwrap();
        assert_eq!(respond("/t.nd", &[], &design).body, b"(a:2x4 =200)");
        fs::remove_file(&path).unwrap();
        let gone = respond("/t.nd", &[], &design);
        assert_eq!(gone.status, 404);
        assert_eq!(
            String::from_utf8(gone.body).unwrap(),
            "t.nd is gone: save it again"
        );
    }

    #[test]
    fn the_viewer_is_served_and_nothing_else() {
        let design = text("t.nd");
        let index = respond("/?src=t.nd&watch", &site(), &design);
        assert_eq!(
            (index.status, index.content_type, index.body.as_slice()),
            (200, "text/html; charset=utf-8", &b"<html>"[..])
        );
        assert_eq!(
            respond("/assets/a.js", &site(), &design).content_type,
            "text/javascript"
        );
        assert_eq!(
            respond("/assets/a.wasm", &site(), &design).content_type,
            "application/wasm"
        );
        for path in [
            "/../Cargo.toml",
            "/assets",
            "/assets/../index.html",
            "/secret.txt",
            "/%ZZ",
        ] {
            assert_eq!(respond(path, &site(), &design).status, 404, "{path}");
        }
    }

    #[test]
    fn a_cli_without_the_viewer_says_how_to_get_it() {
        assert_eq!(
            viewer(None, &[]).unwrap_err(),
            "This nichiyou-daiku was built without the viewer: build the viewer (make web), then build the CLI again"
        );
        let built: &[(&str, &[u8])] = &[("index.html", b"<html>")];
        assert_eq!(
            viewer(None, built).unwrap(),
            vec![("index.html".to_string(), b"<html>".to_vec())]
        );
    }

    #[test]
    fn a_viewer_folder_must_hold_a_built_viewer() {
        let empty = folder("empty");
        let error = viewer(Some(empty.as_path()), &[]).unwrap_err();
        assert!(error.starts_with("NICHIYOU_DAIKU_VIEWER names "), "{error}");
        assert!(
            error.ends_with("which has no index.html: point it at a built viewer (web/dist)"),
            "{error}"
        );
        let built = folder("built");
        fs::create_dir_all(built.join("assets")).unwrap();
        fs::write(built.join("index.html"), "<html>").unwrap();
        fs::write(built.join("assets/x.js"), "js").unwrap();
        let mut names: Vec<String> = viewer(Some(built.as_path()), &[])
            .unwrap()
            .into_iter()
            .map(|(n, _)| n)
            .collect();
        names.sort();
        assert_eq!(names, ["assets/x.js", "index.html"]);
    }
}
