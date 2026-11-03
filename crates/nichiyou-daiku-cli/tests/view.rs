//! view serves the viewer and the design on this machine.

use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

/// A fresh folder with a stand-in viewer in it.
fn folder(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("nd-view-{}-{name}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(dir.join("viewer/assets")).unwrap();
    fs::write(dir.join("viewer/index.html"), "VIEWER PAGE").unwrap();
    fs::write(dir.join("viewer/assets/app.js"), "APP").unwrap();
    dir
}

fn command(dir: &Path, args: &[&str]) -> Command {
    let mut command = Command::new(env!("CARGO_BIN_EXE_nichiyou-daiku"));
    command
        .args(args)
        .current_dir(dir)
        .env("NICHIYOU_DAIKU_VIEWER", dir.join("viewer"))
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::piped());
    command
}

/// A running view, stopped when dropped.
struct Running(Child);

impl Drop for Running {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

/// The URL in view's first line.
fn url_in(line: &str) -> String {
    line.split(" at ")
        .nth(1)
        .and_then(|rest| rest.split(" (Ctrl-C").next())
        .unwrap_or_else(|| panic!("no URL in {line:?}"))
        .to_string()
}

/// Starts view and returns it with the URL it printed.
fn start(dir: &Path, args: &[&str]) -> (Running, String) {
    let mut child = command(dir, args).spawn().unwrap();
    let mut lines = BufReader::new(child.stderr.take().unwrap()).lines();
    let line = lines.next().expect("a line about where it serves").unwrap();
    (Running(child), url_in(&line))
}

/// The status and body of a GET for `path` on the server `url` names.
fn get(url: &str, path: &str) -> (u16, String) {
    let address = url.trim_start_matches("http://").split('/').next().unwrap();
    let mut stream = TcpStream::connect(address).unwrap();
    write!(
        stream,
        "GET {path} HTTP/1.1\r\nHost: {address}\r\nConnection: close\r\n\r\n"
    )
    .unwrap();
    let mut reply = String::new();
    stream.read_to_string(&mut reply).unwrap();
    let status = reply.split(' ').nth(1).unwrap().parse().unwrap();
    let body = reply
        .split_once("\r\n\r\n")
        .map_or("", |(_, b)| b)
        .to_string();
    (status, body)
}

#[test]
fn view_serves_the_viewer_and_the_design_as_saved() {
    let dir = folder("serves");
    fs::write(dir.join("my table (1).nd"), "(a:2x4 =400)\n").unwrap();
    let (_running, url) = start(
        &dir,
        &["view", "my table (1).nd", "--no-open", "--port", "0"],
    );
    assert!(url.starts_with("http://127.0.0.1:"), "{url}");
    assert!(
        // src holds the file's URL, itself escaped as a query value
        url.ends_with("/?src=my%2520table%2520%25281%2529.nd&watch"),
        "{url}"
    );
    assert_eq!(get(&url, "/"), (200, "VIEWER PAGE".into()));
    assert_eq!(get(&url, "/assets/app.js"), (200, "APP".into()));
    assert_eq!(
        get(&url, "/my%20table%20(1).nd"),
        (200, "(a:2x4 =400)\n".into())
    );
    fs::write(dir.join("my table (1).nd"), "(a:2x4 =500)\n").unwrap();
    assert_eq!(
        get(&url, "/my%20table%20%281%29.nd"),
        (200, "(a:2x4 =500)\n".into())
    );
    assert_eq!(get(&url, "/secret.txt").0, 404);
}

#[test]
fn view_stops_before_serving_a_file_that_is_not_there() {
    let dir = folder("missing");
    let out = command(&dir, &["view", "nope.nd", "--no-open"])
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(1));
    assert_eq!(
        String::from_utf8(out.stderr).unwrap(),
        "Error: File not found: nope.nd\n"
    );
}

#[test]
fn a_port_in_use_is_named() {
    let dir = folder("port");
    fs::write(dir.join("t.nd"), "(a:2x4 =400)\n").unwrap();
    let (_running, url) = start(&dir, &["view", "t.nd", "--no-open"]);
    let port = url
        .trim_start_matches("http://127.0.0.1:")
        .split('/')
        .next()
        .unwrap()
        .to_string();
    let out = command(&dir, &["view", "t.nd", "--no-open", "--port", &port])
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(1));
    let err = String::from_utf8(out.stderr).unwrap();
    assert!(
        err.starts_with(&format!("Error: Cannot serve on 127.0.0.1:{port}: ")),
        "{err}"
    );
    assert!(
        err.ends_with(". Choose another --port or --host\n"),
        "{err}"
    );
}

#[test]
fn a_viewer_folder_without_a_viewer_is_named() {
    let dir = folder("no-viewer");
    fs::write(dir.join("t.nd"), "(a:2x4 =400)\n").unwrap();
    fs::remove_file(dir.join("viewer/index.html")).unwrap();
    let out = command(&dir, &["view", "t.nd", "--no-open"])
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(1));
    let err = String::from_utf8(out.stderr).unwrap();
    assert!(
        err.starts_with("Error: NICHIYOU_DAIKU_VIEWER names "),
        "{err}"
    );
}

#[test]
fn a_design_from_stdin_is_served_without_following() {
    let dir = folder("stdin");
    let mut child = command(&dir, &["view", "-", "--no-open"])
        .stdin(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(b"(a:2x4 =400)\n")
        .unwrap();
    let mut lines = BufReader::new(child.stderr.take().unwrap()).lines();
    let line = lines.next().unwrap().unwrap();
    let _running = Running(child);
    assert!(
        line.starts_with("Viewing stdin.nd at http://127.0.0.1:"),
        "{line}"
    );
    assert!(line.ends_with("/?src=stdin.nd (Ctrl-C to stop)"), "{line}");
    assert_eq!(
        get(&url_in(&line), "/stdin.nd"),
        (200, "(a:2x4 =400)\n".into())
    );
}

#[test]
fn a_name_with_url_characters_is_served() {
    // The viewer fetches src's value as a URL: '#', '?' and '%' must reach
    // the server escaped
    let dir = folder("characters");
    fs::write(dir.join("a#1 100%.nd"), "(a:2x4 =400)\n").unwrap();
    let (_running, url) = start(&dir, &["view", "a#1 100%.nd", "--no-open"]);
    assert!(
        url.ends_with("/?src=a%25231%2520100%2525.nd&watch"),
        "{url}"
    );
    assert_eq!(
        get(&url, "/a%231%20100%25.nd"),
        (200, "(a:2x4 =400)\n".into())
    );
}
