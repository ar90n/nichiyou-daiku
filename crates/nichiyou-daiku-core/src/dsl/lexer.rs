//! Tokens read by context, as Lark's contextual lexer reads them: the parser
//! says which terminals it accepts, and only those are tried.

/// The terminals of the grammar (dsl/grammar.py), with End for the end of input.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Terminal {
    Cname,
    Number,
    EscapedString,
    PieceType,
    CompactFace,
    ScrewType,
    Unknown,
    Steps,
    X,
    LPar,
    RPar,
    LBrace,
    RBrace,
    Colon,
    Comma,
    Equal,
    Plus,
    Minus,
    Star,
    Slash,
    /// `-[`
    OpenConnection,
    /// `]-`
    CloseConnection,
    FromMin,
    FromMax,
    /// `<`
    CompactFromMin,
    /// `>`
    CompactFromMax,
    /// `V`
    CompactVanilla,
    /// `D(`
    DowelStart,
    /// `S(`
    ScrewStart,
    JsonType,
    JsonVanilla,
    JsonDowel,
    JsonRadius,
    JsonDepth,
    JsonScrew,
    JsonDiameter,
    JsonLength,
    End,
}

use Terminal::*;

/// Lark's order for trying terminals: priority, then the unbounded patterns,
/// then the longer literals; the first that matches wins.
const ORDER: [Terminal; 38] = [
    ScrewType,
    Number,
    Cname,
    EscapedString,
    JsonDiameter,
    JsonVanilla,
    JsonLength,
    JsonRadius,
    FromMax,
    FromMin,
    JsonDepth,
    JsonDowel,
    JsonScrew,
    JsonType,
    Steps,
    PieceType,
    OpenConnection,
    CloseConnection,
    DowelStart,
    ScrewStart,
    CompactFace,
    Colon,
    Comma,
    CompactFromMax,
    CompactFromMin,
    CompactVanilla,
    Equal,
    LBrace,
    LPar,
    Minus,
    Plus,
    RBrace,
    RPar,
    Slash,
    Star,
    Unknown,
    X,
    End,
];

const PIECE_TYPES: [&str; 6] = ["1x4", "1x6", "1x8", "2x2", "2x4", "2x6"];

impl Terminal {
    /// The literal text of a terminal written as a string in the grammar.
    pub fn literal(self) -> Option<&'static str> {
        Some(match self {
            Steps => "steps",
            X => "x",
            LPar => "(",
            RPar => ")",
            LBrace => "{",
            RBrace => "}",
            Colon => ":",
            Comma => ",",
            Equal => "=",
            Plus => "+",
            Minus => "-",
            Star => "*",
            Slash => "/",
            Unknown => "?",
            OpenConnection => "-[",
            CloseConnection => "]-",
            FromMin => "FromMin",
            FromMax => "FromMax",
            CompactFromMin => "<",
            CompactFromMax => ">",
            CompactVanilla => "V",
            DowelStart => "D(",
            ScrewStart => "S(",
            JsonType => "\"type\"",
            JsonVanilla => "\"vanilla\"",
            JsonDowel => "\"dowel\"",
            JsonRadius => "\"radius\"",
            JsonDepth => "\"depth\"",
            JsonScrew => "\"screw\"",
            JsonDiameter => "\"diameter\"",
            JsonLength => "\"length\"",
            _ => return None,
        })
    }

    /// How a syntax error names the terminal (parser.py: _describe_terminal).
    pub fn description(self) -> String {
        match self {
            End => "end of input".into(),
            Cname => "identifier".into(),
            Number => "number".into(),
            EscapedString => "string".into(),
            PieceType => format!("piece type ({})", PIECE_TYPES.join(", ")),
            CompactFace => "face letter (T, D, L, R, F, B)".into(),
            ScrewType => "screw type (Slim, Coarse)".into(),
            Unknown => "'?' (unknown)".into(),
            other => crate::pyfmt::repr_str(other.literal().expect("a literal terminal")),
        }
    }

    /// Bytes of `rest` this terminal matches at its start.
    fn matches(self, rest: &str) -> Option<usize> {
        match self {
            Cname => cname(rest),
            Number => number(rest),
            EscapedString => escaped_string(rest),
            PieceType => PIECE_TYPES
                .iter()
                .find(|name| rest.starts_with(**name))
                .map(|name| name.len()),
            CompactFace => rest
                .starts_with(['T', 'D', 'L', 'R', 'F', 'B'])
                .then_some(1),
            ScrewType => ["Slim", "Coarse"].iter().find_map(|name| {
                let after = rest.strip_prefix(name)?;
                (!after.starts_with(is_name_char)).then_some(name.len())
            }),
            End => None,
            other => {
                let literal = other.literal().expect("a literal terminal");
                rest.starts_with(literal).then_some(literal.len())
            }
        }
    }
}

fn is_name_char(ch: char) -> bool {
    ch.is_ascii_alphanumeric() || ch == '_'
}

fn cname(rest: &str) -> Option<usize> {
    let first = rest.chars().next()?;
    if !(first.is_ascii_alphabetic() || first == '_') {
        return None;
    }
    Some(rest.find(|c: char| !is_name_char(c)).unwrap_or(rest.len()))
}

fn digits(text: &str) -> usize {
    text.find(|c: char| !c.is_ascii_digit())
        .unwrap_or(text.len())
}

/// `[eE][+-]?INT` at the start of `text`.
fn exponent(text: &str) -> Option<usize> {
    let after = text.strip_prefix(['e', 'E'])?;
    let sign = usize::from(after.starts_with(['+', '-']));
    let n = digits(&after[sign..]);
    (n > 0).then_some(1 + sign + n)
}

/// Lark's common.NUMBER, tried as its regex alternation is: INT _EXP, then
/// DECIMAL _EXP?, then INT.
fn number(rest: &str) -> Option<usize> {
    let int = digits(rest);
    if int > 0
        && let Some(e) = exponent(&rest[int..])
    {
        return Some(int + e);
    }
    let decimal = if int > 0 && rest[int..].starts_with('.') {
        Some(int + 1 + digits(&rest[int + 1..]))
    } else if int == 0 && rest.starts_with('.') && digits(&rest[1..]) > 0 {
        Some(1 + digits(&rest[1..]))
    } else {
        None
    };
    if let Some(decimal) = decimal {
        return Some(decimal + exponent(&rest[decimal..]).unwrap_or(0));
    }
    (int > 0).then_some(int)
}

/// `".*?(?<!\\)(\\\\)*?"`: up to the first quote after an even number of
/// backslashes, on one line.
fn escaped_string(rest: &str) -> Option<usize> {
    let body = rest.strip_prefix('"')?;
    let mut backslashes = 0;
    for (i, ch) in body.char_indices() {
        match ch {
            '\n' => return None,
            '"' if backslashes % 2 == 0 => return Some(1 + i + 1),
            '\\' => backslashes += 1,
            _ => backslashes = 0,
        }
    }
    None
}

#[derive(Clone, Debug, PartialEq)]
pub struct Token {
    pub terminal: Terminal,
    pub text: String,
    pub line: usize,
    pub column: usize,
}

#[derive(Clone, Debug, PartialEq)]
pub enum LexError {
    /// No accepted terminal matches, but another one does (Lark's UnexpectedToken)
    Token(Token),
    /// Nothing matches at all (Lark's UnexpectedCharacters)
    Character {
        ch: char,
        line: usize,
        column: usize,
    },
}

pub struct Lexer<'a> {
    source: &'a str,
    position: usize,
    line: usize,
    column: usize,
    last: Option<(usize, usize)>,
}

impl<'a> Lexer<'a> {
    pub fn new(source: &'a str) -> Lexer<'a> {
        Lexer {
            source,
            position: 0,
            line: 1,
            column: 1,
            last: None,
        }
    }

    fn advance(&mut self, bytes: usize) {
        for ch in self.source[self.position..self.position + bytes].chars() {
            if ch == '\n' {
                self.line += 1;
                self.column = 1;
            } else {
                self.column += 1;
            }
        }
        self.position += bytes;
    }

    fn skip_ignored(&mut self) {
        loop {
            let rest = &self.source[self.position..];
            let space = rest
                .find(|c: char| !matches!(c, ' ' | '\t' | '\x0c' | '\r' | '\n'))
                .unwrap_or(rest.len());
            if space > 0 {
                self.advance(space);
            } else if rest.starts_with("//") {
                self.advance(rest.find('\n').unwrap_or(rest.len()));
            } else {
                return;
            }
        }
    }

    /// The first terminal of `accept` (in Lark's order) that matches here,
    /// with Lark's "unless": a name or a string that spells an accepted
    /// keyword is that keyword.
    fn match_here(&self, accept: &[Terminal]) -> Option<(Terminal, usize)> {
        let rest = &self.source[self.position..];
        let (terminal, length) = ORDER
            .iter()
            .filter(|t| accept.contains(t))
            .find_map(|&t| t.matches(rest).map(|n| (t, n)))?;
        let keywords: &[Terminal] = match terminal {
            Cname => &[Steps, X, FromMin, FromMax, CompactVanilla],
            EscapedString => &[
                JsonType,
                JsonVanilla,
                JsonDowel,
                JsonRadius,
                JsonDepth,
                JsonScrew,
                JsonDiameter,
                JsonLength,
            ],
            _ => &[],
        };
        let text = &rest[..length];
        let keyword = keywords
            .iter()
            .find(|k| accept.contains(k) && k.literal() == Some(text));
        Some((keyword.copied().unwrap_or(terminal), length))
    }

    fn token(&mut self, terminal: Terminal, length: usize) -> Token {
        let token = Token {
            terminal,
            text: self.source[self.position..self.position + length].to_string(),
            line: self.line,
            column: self.column,
        };
        self.advance(length);
        self.last = Some((token.line, token.column));
        token
    }

    /// The next token among `accept`, skipping whitespace and comments. At the
    /// end of the input it gives End when End is accepted, at the place of
    /// the last token (as Lark does).
    pub fn next(&mut self, accept: &[Terminal]) -> Result<Token, LexError> {
        self.skip_ignored();
        if self.position == self.source.len() {
            let (line, column) = self.last.unwrap_or((self.line, self.column));
            let end = Token {
                terminal: End,
                text: String::new(),
                line,
                column,
            };
            return if accept.contains(&End) {
                Ok(end)
            } else {
                Err(LexError::Token(end))
            };
        }
        if let Some((terminal, length)) = self.match_here(accept) {
            return Ok(self.token(terminal, length));
        }
        let (line, column) = (self.line, self.column);
        match self.match_here(&ORDER) {
            Some((terminal, length)) => Err(LexError::Token(Token {
                terminal,
                text: self.source[self.position..self.position + length].to_string(),
                line,
                column,
            })),
            None => Err(LexError::Character {
                ch: self.source[self.position..]
                    .chars()
                    .next()
                    .expect("not at the end"),
                line,
                column,
            }),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn read(source: &str, accepts: &[&[Terminal]]) -> Vec<(Terminal, String)> {
        let mut lexer = Lexer::new(source);
        accepts
            .iter()
            .map(|accept| {
                let t = lexer.next(accept).unwrap();
                (t.terminal, t.text)
            })
            .collect()
    }

    #[test]
    fn face_letters_are_letters_only_where_faces_are_expected() {
        let got = read(
            "TF<0",
            &[
                &[LBrace, CompactFace],
                &[CompactFace],
                &[CompactFromMin, CompactFromMax, Unknown],
                &[Number, Cname, LPar],
            ],
        );
        assert_eq!(
            got,
            [
                (CompactFace, "T".to_string()),
                (CompactFace, "F".to_string()),
                (CompactFromMin, "<".to_string()),
                (Number, "0".to_string())
            ]
        );
        assert_eq!(read("TF", &[&[Cname, LPar]]), [(Cname, "TF".to_string())]);
    }

    #[test]
    fn keywords_win_over_names_only_where_both_are_accepted() {
        assert_eq!(
            read("steps", &[&[LPar, Cname, Steps]]),
            [(Steps, "steps".to_string())]
        );
        assert_eq!(read("steps", &[&[Cname]]), [(Cname, "steps".to_string())]);
        assert_eq!(
            read("stepsX", &[&[LPar, Cname, Steps]]),
            [(Cname, "stepsX".to_string())]
        );
    }

    #[test]
    fn screw_types_need_a_word_boundary() {
        let sum = [ScrewType, Number, Cname, Minus, LPar];
        assert_eq!(read("Slim:", &[&sum]), [(ScrewType, "Slim".to_string())]);
        assert_eq!(read("SlimD", &[&sum]), [(Cname, "SlimD".to_string())]);
    }

    #[test]
    fn numbers_read_like_lark() {
        for text in ["1e3", "1E-2", ".5", "5.", "3.3", "12"] {
            assert_eq!(
                read(text, &[&[Number]]),
                [(Number, text.to_string())],
                "{text}"
            );
        }
        assert_eq!(
            read("8x30", &[&[Number], &[X], &[Number]]),
            [
                (Number, "8".to_string()),
                (X, "x".to_string()),
                (Number, "30".to_string())
            ]
        );
    }

    #[test]
    fn positions_count_characters_and_skip_comments() {
        let mut lexer = Lexer::new("// 日本語のコメント\r\n(名前 :2x4");
        let t = lexer.next(&[LPar, Cname, Steps]).unwrap();
        assert_eq!((t.line, t.column), (2, 1));
        match lexer.next(&[Cname, Colon]) {
            Err(LexError::Character { ch, line, column }) => {
                assert_eq!((ch, line, column), ('名', 2, 2))
            }
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn a_token_that_is_not_accepted_is_reported_as_a_token() {
        let mut lexer = Lexer::new("4x4");
        match lexer.next(&[PieceType]) {
            Err(LexError::Token(t)) => {
                assert_eq!((t.terminal, t.text.as_str(), t.column), (Number, "4", 1))
            }
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn the_end_is_placed_at_the_last_token() {
        let mut lexer = Lexer::new("(a:2x4 =100");
        for accept in [
            &[LPar][..],
            &[Cname, Colon],
            &[Colon],
            &[PieceType],
            &[LBrace, Equal],
            &[Number, Cname, Minus, LPar, Unknown],
        ] {
            lexer.next(accept).unwrap();
        }
        let end = lexer.next(&[RPar, Plus, Minus, Star, Slash, End]).unwrap();
        assert_eq!((end.terminal, end.line, end.column), (End, 1, 9));
    }
}
