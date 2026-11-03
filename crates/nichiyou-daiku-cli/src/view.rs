//! `view`: the design in the browser viewer, served from this machine; the
//! page follows the file as it is saved.

use std::path::PathBuf;
use std::process::{Command, Stdio};

use crate::echo::Echo;
use crate::input::read_source;
use crate::serve::{Design, VIEWER, encode, respond, viewer};

#[derive(clap::Args)]
pub struct Args {
    /// Path to .nd file or '-' for stdin
    file: String,
    /// Address to serve on; 0.0.0.0 or this machine's address lets another machine's browser in
    #[arg(long, default_value = "127.0.0.1")]
    host: String,
    /// Port to serve on (default: a free one)
    #[arg(long, default_value_t = 0)]
    port: u16,
    /// Print the address without opening a browser
    #[arg(long)]
    no_open: bool,
}

/// Addresses only this machine's browser reaches: the ones view opens
const LOOPBACK: [&str; 3] = ["127.0.0.1", "localhost", "::1"];
/// Addresses that listen on every interface: not one a browser can open
const EVERY: [&str; 2] = ["0.0.0.0", "::"];

/// An IPv6 address goes in a URL or a socket address in brackets.
fn bracketed(host: &str) -> String {
    if host.contains(':') {
        format!("[{host}]")
    } else {
        host.to_string()
    }
}

/// Asks the desktop to open `url`; false when there is nothing to ask.
fn open_browser(url: &str) -> bool {
    let mut command = if cfg!(target_os = "macos") {
        let mut c = Command::new("open");
        c.arg(url);
        c
    } else if cfg!(windows) {
        let mut c = Command::new("cmd");
        // start's first quoted argument is the window title
        c.args(["/C", "start", "", url]);
        c
    } else {
        let mut c = Command::new("xdg-open");
        c.arg(url);
        c
    };
    command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .is_ok()
}

pub fn run(args: &Args, echo: &Echo) -> u8 {
    // Read now, so a mistake is told here rather than in the browser
    let text = match read_source(&args.file) {
        Ok(text) => text,
        Err(message) => {
            echo.error(&format!("Error: {message}"), None);
            return 1;
        }
    };
    let design = if args.file == "-" {
        Design::Text {
            name: "stdin.nd".into(),
            text,
        }
    } else {
        let path = PathBuf::from(&args.file);
        let name = path
            .file_name()
            .map_or("design.nd".into(), |n| n.to_string_lossy().into_owned());
        Design::File { path, name }
    };
    let folder = std::env::var_os("NICHIYOU_DAIKU_VIEWER").map(PathBuf::from);
    let site = match viewer(folder.as_deref(), VIEWER) {
        Ok(site) => site,
        Err(message) => {
            echo.error(&format!("Error: {message}"), None);
            return 1;
        }
    };
    let address = format!("{}:{}", bracketed(&args.host), args.port);
    let server = match tiny_http::Server::http(&address) {
        Ok(server) => server,
        Err(e) => {
            echo.error(
                &format!("Error: Cannot serve on {address}: {e}. Choose another --port or --host"),
                None,
            );
            return 1;
        }
    };
    let port = server.server_addr().to_ip().map_or(args.port, |a| a.port());
    let watch = if matches!(design, Design::File { .. }) {
        "&watch"
    } else {
        ""
    };
    // src holds the design's URL, a query value escaped once more: the
    // viewer fetches the value as it is, so '#', '?' and '%' stay escaped
    let url = format!(
        "http://{}:{port}/?src={}{watch}",
        bracketed(&args.host),
        encode(&encode(design.name()))
    );
    let mut line = format!("Viewing {} at {url} (Ctrl-C to stop)", design.name());
    if EVERY.contains(&args.host.as_str()) {
        line.push_str(&format!(
            "; from another machine, open it with this machine's address in place of {}",
            args.host
        ));
    }
    echo.info(&line, None);
    if !args.no_open && LOOPBACK.contains(&args.host.as_str()) && !open_browser(&url) {
        echo.info(&format!("Open {url} in a browser"), None);
    }
    for request in server.incoming_requests() {
        let reply = respond(request.url(), &site, &design);
        let mut response =
            tiny_http::Response::from_data(reply.body).with_status_code(reply.status);
        response.add_header(
            tiny_http::Header::from_bytes("Content-Type", reply.content_type)
                .expect("an ASCII header"),
        );
        if reply.no_store {
            response.add_header(
                tiny_http::Header::from_bytes("Cache-Control", "no-store")
                    .expect("an ASCII header"),
            );
        }
        // A browser that went away is no reason to stop
        let _ = request.respond(response);
    }
    0
}
