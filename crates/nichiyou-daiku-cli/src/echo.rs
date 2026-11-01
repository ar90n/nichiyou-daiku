//! Where output goes (cli/utils.py: CliEcho): results to stdout, errors and
//! status to stderr, colour only on a terminal (click strips it elsewhere).
//! A closed pipe is not an error worth a panic.

use std::io::{IsTerminal, Write};

#[derive(Clone, Copy)]
pub enum Colour {
    Green,
    Red,
    #[cfg_attr(not(test), expect(dead_code, reason = "the report's warnings use it"))]
    Yellow,
}

pub struct Echo {
    quiet: bool,
    verbose: bool,
}

/// click.style's codes: green successes, bold red failures, yellow warnings.
pub fn styled(message: &str, colour: Colour) -> String {
    match colour {
        Colour::Green => format!("\x1b[32m{message}\x1b[0m"),
        Colour::Red => format!("\x1b[31m\x1b[1m{message}\x1b[0m"),
        Colour::Yellow => format!("\x1b[33m{message}\x1b[0m"),
    }
}

fn line(message: &str, colour: Option<Colour>, to_stderr: bool) {
    let terminal = if to_stderr {
        std::io::stderr().is_terminal()
    } else {
        std::io::stdout().is_terminal()
    };
    let text = match colour {
        Some(colour) if terminal => styled(message, colour),
        _ => message.to_string(),
    };
    let _ = if to_stderr {
        writeln!(std::io::stderr(), "{text}")
    } else {
        writeln!(std::io::stdout(), "{text}")
    };
}

impl Echo {
    pub fn new(quiet: bool, verbose: bool) -> Echo {
        Echo { quiet, verbose }
    }

    /// Command output on stdout, unless --quiet.
    pub fn echo(&self, message: &str, colour: Option<Colour>) {
        if !self.quiet {
            line(message, colour, false);
        }
    }

    /// Errors on stderr, even with --quiet.
    pub fn error(&self, message: &str, colour: Option<Colour>) {
        line(message, colour, true);
    }

    /// Status on stderr, unless --quiet: stdout carries only the output.
    pub fn info(&self, message: &str, colour: Option<Colour>) {
        if !self.quiet {
            line(message, colour, true);
        }
    }

    /// Progress on stderr, with --verbose only.
    pub fn verbose(&self, message: &str) {
        if self.verbose {
            self.info(message, None);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn colours_are_clicks() {
        assert_eq!(styled("ok", Colour::Green), "\x1b[32mok\x1b[0m");
        assert_eq!(styled("no", Colour::Red), "\x1b[31m\x1b[1mno\x1b[0m");
        assert_eq!(styled("hm", Colour::Yellow), "\x1b[33mhm\x1b[0m");
    }
}
