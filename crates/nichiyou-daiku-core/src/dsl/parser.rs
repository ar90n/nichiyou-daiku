//! A recursive-descent parser for .nd. At each point it knows every terminal
//! that may come next, which the lexer reads by and a syntax error lists.

use super::ast::*;
use super::error::{DslError, ErrorKind};
use super::lexer::{LexError, Lexer, Terminal, Terminal::*, Token};
use crate::pyfmt::repr_str;

const STATEMENT_START: [Terminal; 3] = [LPar, Cname, Steps];
const SUM_START: [Terminal; 4] = [Number, Cname, Minus, LPar];
/// Lark's LALR merges the states after either anchor's compact offset, so
/// its contextual lexer reads the next token by all of their terminals.
const AFTER_COMPACT_OFFSET: [Terminal; 5] = [
    CompactFace,
    CompactVanilla,
    DowelStart,
    ScrewStart,
    CloseConnection,
];
/// Brackets and minus signs inside one another; deeper ones would overflow
/// the stack of the recursive parser and evaluation.
const MAX_NESTING: usize = 100;

fn with(base: &[Terminal], more: &[Terminal]) -> Vec<Terminal> {
    let mut all = base.to_vec();
    for t in more {
        if !all.contains(t) {
            all.push(*t);
        }
    }
    all
}

fn pos(token: &Token) -> Pos {
    Pos {
        line: token.line,
        column: token.column,
    }
}

/// The text of a string token, unescaped as the Python version does.
pub fn unescape(text: &str) -> String {
    let inner = text
        .strip_prefix('"')
        .and_then(|t| t.strip_suffix('"'))
        .unwrap_or(text);
    inner
        .replace("\\\"", "\"")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\\\", "\\")
}

fn is_blank(source: &str) -> bool {
    source
        .lines()
        .map(|line| line.find("//").map_or(line, |i| &line[..i]))
        .all(|line| line.trim().is_empty())
}

/// The statements of an .nd source, or its first syntax error.
pub fn parse_statements(source: &str) -> Result<Vec<Statement>, DslError> {
    if is_blank(source) {
        return Err(DslError::new(
            ErrorKind::Syntax,
            "No pieces defined: the input is empty or contains only comments. Expected at \
             least one piece definition such as (leg:2x4 =720)",
            None,
        ));
    }
    Parser {
        lexer: Lexer::new(source),
        pending: None,
        previous: None,
        before_pending: None,
        nesting: 0,
    }
    .statements()
}

struct Parser<'a> {
    lexer: Lexer<'a>,
    /// A token read ahead that belongs to the caller
    pending: Option<Token>,
    previous: Option<Terminal>,
    before_pending: Option<Terminal>,
    nesting: usize,
}

impl Parser<'_> {
    fn next(&mut self, accept: &[Terminal]) -> Result<Token, DslError> {
        if let Some(token) = self.pending.take() {
            self.previous = Some(token.terminal);
            return Ok(token);
        }
        match self.lexer.next(accept) {
            Ok(token) => {
                self.before_pending = self.previous;
                self.previous = Some(token.terminal);
                Ok(token)
            }
            Err(error) => Err(self.syntax_error(error, accept)),
        }
    }

    fn put_back(&mut self, token: Token) {
        self.previous = self.before_pending;
        self.pending = Some(token);
    }

    /// parser.py: _describe_syntax_error
    fn syntax_error(&self, error: LexError, accept: &[Terminal]) -> DslError {
        let (found, unexpected, operator, line, column) = match error {
            LexError::Character { ch, line, column } => (
                format!("Unexpected character {}", repr_str(&ch.to_string())),
                ch.to_string(),
                false,
                line,
                column,
            ),
            LexError::Token(token) if token.terminal == End => (
                "Unexpected end of input".to_string(),
                String::new(),
                false,
                token.line,
                token.column,
            ),
            LexError::Token(token) => (
                format!("Unexpected token {}", repr_str(&token.text)),
                token.text.clone(),
                matches!(token.text.as_str(), "+" | "-" | "*" | "/"),
                token.line,
                token.column,
            ),
        };
        let mut descriptions: Vec<String> = accept.iter().map(|t| t.description()).collect();
        descriptions.sort();
        descriptions.dedup();
        let mut message = match descriptions.len() {
            0 => found,
            1 => format!("{found}. Expected: {}", descriptions[0]),
            _ => format!("{found}. Expected one of: {}", descriptions.join(", ")),
        };
        if unexpected == "?" && !accept.contains(&Unknown) {
            message.push_str(
                ". '?' (unknown) works in compact notation only, e.g. (x:2x4 =?) or RB? BD?",
            );
        }
        if self.previous == Some(Steps) {
            message.push_str(
                ". 'steps' starts the steps block, so it cannot name a piece or a variable: \
                 rename it, or write a block such as steps { \"Frame\": a, b }",
            );
        }
        if operator && accept.contains(&CompactFace) {
            message.push_str(
                ". A compact offset that is an expression needs parentheses, e.g. FL<(X + 1)",
            );
        }
        DslError::new(ErrorKind::Syntax, message, Some((line, column)))
    }

    fn statements(&mut self) -> Result<Vec<Statement>, DslError> {
        let mut statements = Vec::new();
        let follow = with(&STATEMENT_START, &[End]);
        loop {
            let accept = if statements.is_empty() {
                STATEMENT_START.to_vec()
            } else {
                follow.clone()
            };
            let token = self.next(&accept)?;
            let statement = match token.terminal {
                End => return Ok(statements),
                LPar => Statement::Piece(self.piece_def(&token)?),
                Steps => Statement::Steps(self.steps_def(&token)?),
                _ => {
                    let after = self.next(&[Equal, OpenConnection])?;
                    if after.terminal == Equal {
                        Statement::Var(VarDef {
                            pos: pos(&token),
                            name: token.text.clone(),
                            value: self.sum(&follow)?.0,
                        })
                    } else {
                        Statement::Connection(Box::new(self.connection_def(&token)?))
                    }
                }
            };
            statements.push(statement);
        }
    }

    fn piece_def(&mut self, lpar: &Token) -> Result<PieceDef, DslError> {
        let mut token = self.next(&[Cname, Colon])?;
        let id = if token.terminal == Cname {
            let id = token.text.clone();
            self.next(&[Colon])?;
            Some(id)
        } else {
            None
        };
        token = self.next(&[PieceType])?;
        let kind = token.text.clone();
        let opening = self.next(&[LBrace, Equal])?;
        let length = if opening.terminal == LBrace {
            LengthDef::Props(self.props(&opening)?)
        } else {
            let first = self.next(&with(&SUM_START, &[Unknown]))?;
            if first.terminal == Unknown {
                LengthDef::Compact(None)
            } else {
                self.put_back(first);
                LengthDef::Compact(Some(self.sum(&[RPar])?.0))
            }
        };
        self.next(&[RPar])?;
        Ok(PieceDef {
            pos: pos(lpar),
            id,
            kind,
            length,
        })
    }

    /// `{"key": value, ...}` of a piece
    fn props(&mut self, lbrace: &Token) -> Result<Props, DslError> {
        let mut entries = Vec::new();
        let mut token = self.next(&[EscapedString, RBrace])?;
        while token.terminal == EscapedString {
            self.next(&[Colon])?;
            let first =
                self.next(&[EscapedString, Number, Cname, Minus, LPar, FromMin, FromMax])?;
            let value = match first.terminal {
                EscapedString => Value::Str(unescape(&first.text)),
                FromMin | FromMax => Value::Offset(self.offset_value(&first)?),
                _ => {
                    self.put_back(first);
                    Value::Expr(self.sum(&[Comma, RBrace])?.0)
                }
            };
            entries.push(Prop {
                pos: pos(&token),
                key: unescape(&token.text),
                value,
            });
            if self.next(&[Comma, RBrace])?.terminal == RBrace {
                break;
            }
            token = self.next(&[EscapedString])?;
        }
        Ok(Props {
            pos: pos(lbrace),
            entries,
        })
    }

    /// `{"key": "face" | FromMin(...), ...}` of an anchor
    fn anchor_props(&mut self, lbrace: &Token) -> Result<Props, DslError> {
        let mut entries = Vec::new();
        let mut token = self.next(&[EscapedString, RBrace])?;
        while token.terminal == EscapedString {
            self.next(&[Colon])?;
            let first = self.next(&[EscapedString, FromMin, FromMax])?;
            let value = if first.terminal == EscapedString {
                Value::Str(unescape(&first.text))
            } else {
                Value::Offset(self.offset_value(&first)?)
            };
            entries.push(Prop {
                pos: pos(&token),
                key: unescape(&token.text),
                value,
            });
            if self.next(&[Comma, RBrace])?.terminal == RBrace {
                break;
            }
            token = self.next(&[EscapedString])?;
        }
        Ok(Props {
            pos: pos(lbrace),
            entries,
        })
    }

    /// `FromMin(expression)` or `FromMax(expression)`
    fn offset_value(&mut self, keyword: &Token) -> Result<OffsetDef, DslError> {
        self.next(&[LPar])?;
        let value = self.sum(&[RPar])?.0;
        self.next(&[RPar])?;
        Ok(OffsetDef {
            pos: pos(keyword),
            from_max: keyword.terminal == FromMax,
            value,
        })
    }

    fn connection_def(&mut self, base: &Token) -> Result<ConnectionDef, DslError> {
        let first = self.next(&[LBrace, CompactFace])?;
        let (base_anchor, target_anchor, kind) = if first.terminal == LBrace {
            let base_anchor = AnchorDef::Json(self.anchor_props(&first)?);
            let second = self.next(&[LBrace])?;
            let target_anchor = AnchorDef::Json(self.anchor_props(&second)?);
            let token = self.next(&[LBrace, CloseConnection])?;
            let kind = if token.terminal == LBrace {
                let kind = self.connection_type_props()?;
                self.next(&[CloseConnection])?;
                Some(kind)
            } else {
                None
            };
            (base_anchor, target_anchor, kind)
        } else {
            let base_anchor = self.compact_anchor(&first, &[CompactFace])?;
            let second = self.next(&[CompactFace])?;
            let types = [CompactVanilla, DowelStart, ScrewStart, CloseConnection];
            let target_anchor = self.compact_anchor(&second, &types)?;
            let token = self.next(&types)?;
            let kind = match token.terminal {
                CloseConnection => None,
                CompactVanilla => {
                    self.next(&[CloseConnection])?;
                    Some(TypeDef::Vanilla)
                }
                DowelStart => {
                    let kind = self.dowel_compact()?;
                    self.next(&[CloseConnection])?;
                    Some(kind)
                }
                _ => {
                    let kind = self.screw_compact()?;
                    self.next(&[CloseConnection])?;
                    Some(kind)
                }
            };
            (base_anchor, target_anchor, kind)
        };
        let target = self.next(&[Cname])?;
        Ok(ConnectionDef {
            pos: pos(base),
            base: base.text.clone(),
            target: target.text,
            base_anchor,
            target_anchor,
            kind,
        })
    }

    fn compact_anchor(&mut self, face: &Token, follow: &[Terminal]) -> Result<AnchorDef, DslError> {
        let edge = self.next(&[CompactFace])?;
        let kind = self.next(&[CompactFromMin, CompactFromMax, Unknown])?;
        let (offset, unknown_pos) = if kind.terminal == Unknown {
            (None, Some(pos(&kind)))
        } else {
            let value = self.offset_atom()?;
            (
                Some(OffsetDef {
                    pos: pos(&kind),
                    from_max: kind.terminal == CompactFromMax,
                    value,
                }),
                None,
            )
        };
        let next = self
            .lexer
            .next(&AFTER_COMPACT_OFFSET)
            .map_err(|error| self.syntax_error(error, follow))?;
        if !follow.contains(&next.terminal) {
            return Err(self.syntax_error(LexError::Token(next), follow));
        }
        self.pending = Some(next);
        Ok(AnchorDef::Compact {
            pos: pos(face),
            contact: face.text.chars().next().expect("a face letter"),
            edge: edge.text.chars().next().expect("a face letter"),
            offset,
            unknown_pos,
        })
    }

    /// A number, a variable or a bracketed expression: no operators, so that
    /// the next face letter is not read as part of the offset.
    fn offset_atom(&mut self) -> Result<Expr, DslError> {
        let token = self.next(&[Number, Cname, LPar])?;
        match token.terminal {
            Number => Ok(Expr::Number(number(&token), pos(&token))),
            Cname => Ok(Expr::Var(token.text.clone(), pos(&token))),
            _ => {
                let value = self.sum(&[RPar])?.0;
                self.next(&[RPar])?;
                Ok(value)
            }
        }
    }

    fn dowel_compact(&mut self) -> Result<TypeDef, DslError> {
        let first = self.next(&with(&[Colon], &SUM_START))?;
        let kind = if first.terminal == Colon {
            let diameter = self.next(&[Number])?.text;
            self.next(&[X])?;
            let length = self.next(&[Number])?.text;
            TypeDef::DowelPreset {
                pos: pos(&first),
                diameter,
                length,
            }
        } else {
            self.put_back(first);
            let (radius, start) = self.sum(&[Comma])?;
            self.next(&[Comma])?;
            let depth = self.sum(&[RPar])?.0;
            TypeDef::Dowel {
                pos: start,
                radius,
                depth,
            }
        };
        self.next(&[RPar])?;
        Ok(kind)
    }

    fn screw_compact(&mut self) -> Result<TypeDef, DslError> {
        let first = self.next(&with(&[ScrewType], &SUM_START))?;
        let kind = if first.terminal == ScrewType {
            self.next(&[Colon])?;
            let diameter = self.next(&[Number])?.text;
            self.next(&[X])?;
            let length = self.next(&[Number])?.text;
            TypeDef::ScrewPreset {
                pos: pos(&first),
                screw_type: first.text.clone(),
                diameter,
                length,
            }
        } else {
            self.put_back(first);
            let (diameter, start) = self.sum(&[Comma])?;
            self.next(&[Comma])?;
            let length = self.sum(&[RPar])?.0;
            TypeDef::Screw {
                pos: start,
                diameter,
                length,
            }
        };
        self.next(&[RPar])?;
        Ok(kind)
    }

    /// `{"type": "vanilla" | "dowel", "radius": ..., "depth": ... | "screw", ...}`
    fn connection_type_props(&mut self) -> Result<TypeDef, DslError> {
        let type_key = self.next(&[JsonType])?;
        self.next(&[Colon])?;
        let name = self.next(&[JsonVanilla, JsonDowel, JsonScrew])?;
        let kind = match name.terminal {
            JsonVanilla => TypeDef::Vanilla,
            JsonDowel => {
                let (radius, depth) = self.json_sizes(JsonRadius, JsonDepth)?;
                TypeDef::Dowel {
                    pos: pos(&type_key),
                    radius,
                    depth,
                }
            }
            _ => {
                let (diameter, length) = self.json_sizes(JsonDiameter, JsonLength)?;
                TypeDef::Screw {
                    pos: pos(&type_key),
                    diameter,
                    length,
                }
            }
        };
        self.next(&[RBrace])?;
        Ok(kind)
    }

    fn json_sizes(&mut self, first: Terminal, second: Terminal) -> Result<(Expr, Expr), DslError> {
        self.next(&[Comma])?;
        self.next(&[first])?;
        self.next(&[Colon])?;
        let a = self.sum(&[Comma])?.0;
        self.next(&[Comma])?;
        self.next(&[second])?;
        self.next(&[Colon])?;
        let b = self.sum(&[RBrace])?.0;
        Ok((a, b))
    }

    fn steps_def(&mut self, steps: &Token) -> Result<StepsDef, DslError> {
        self.next(&[LBrace])?;
        let mut defs = Vec::new();
        let mut token = self.next(&[EscapedString])?;
        loop {
            self.next(&[Colon])?;
            let mut pieces = vec![self.next(&[Cname])?.text];
            let after = loop {
                let after = self.next(&[Comma, EscapedString, RBrace])?;
                if after.terminal != Comma {
                    break after;
                }
                pieces.push(self.next(&[Cname])?.text);
            };
            defs.push(StepDef {
                pos: pos(&token),
                name: unescape(&token.text),
                pieces,
            });
            if after.terminal == RBrace {
                break;
            }
            token = after;
        }
        Ok(StepsDef {
            pos: pos(steps),
            steps: defs,
        })
    }

    /// An expression and where it starts (its first bracket, if any).
    fn sum(&mut self, follow: &[Terminal]) -> Result<(Expr, Pos), DslError> {
        let operand_follow = with(follow, &[Plus, Minus]);
        let (first, start) = self.product(&operand_follow)?;
        let mut rest = Vec::new();
        loop {
            let token = self.next(&with(&[Plus, Minus], follow))?;
            let op = match token.terminal {
                Plus => Op::Add,
                Minus => Op::Sub,
                _ => {
                    self.put_back(token);
                    break;
                }
            };
            rest.push((op, self.product(&operand_follow)?.0));
        }
        Ok(chain(first, rest, start))
    }

    fn product(&mut self, follow: &[Terminal]) -> Result<(Expr, Pos), DslError> {
        let (first, start) = self.atom()?;
        let mut rest = Vec::new();
        loop {
            let token = self.next(&with(&[Star, Slash], follow))?;
            let op = match token.terminal {
                Star => Op::Mul,
                Slash => Op::Div,
                _ => {
                    self.put_back(token);
                    break;
                }
            };
            rest.push((op, self.atom()?.0));
        }
        Ok(chain(first, rest, start))
    }

    fn atom(&mut self) -> Result<(Expr, Pos), DslError> {
        let token = self.next(&SUM_START)?;
        let at = pos(&token);
        match token.terminal {
            Number => Ok((Expr::Number(number(&token), at), at)),
            Cname => Ok((Expr::Var(token.text.clone(), at), at)),
            Minus => {
                self.enter(at)?;
                let inner = self.atom()?.0;
                self.nesting -= 1;
                Ok((Expr::Neg(Box::new(inner), at), at))
            }
            _ => {
                self.enter(at)?;
                let inner = self.sum(&[RPar])?.0;
                self.next(&[RPar])?;
                self.nesting -= 1;
                Ok((inner, at))
            }
        }
    }

    fn enter(&mut self, at: Pos) -> Result<(), DslError> {
        self.nesting += 1;
        if self.nesting > MAX_NESTING {
            return Err(DslError::new(
                ErrorKind::Syntax,
                format!(
                    "Expression nested too deeply: more than {MAX_NESTING} brackets or minus signs \
                     inside one another; simplify it"
                ),
                Some((at.line, at.column)),
            ));
        }
        Ok(())
    }
}

fn chain(first: Expr, rest: Vec<(Op, Expr)>, start: Pos) -> (Expr, Pos) {
    if rest.is_empty() {
        (first, start)
    } else {
        (Expr::Chain(Box::new(first), rest, start), start)
    }
}

fn number(token: &Token) -> f64 {
    token
        .text
        .parse()
        .expect("the lexer reads only numbers as NUMBER")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn error(source: &str) -> String {
        parse_statements(source)
            .expect_err("a syntax error")
            .to_string()
    }

    #[test]
    fn the_parser_reads_every_kind_of_statement() {
        let source = "W = 10 * (2 + 1)\n(leg:2x4 =W)\n(top:1x4 {\"length\": 300})\n\
            leg -[TF<0 BD<0 S(Slim:3.3x45)]- top\nsteps { \"A\": leg, top }\n";
        assert_eq!(parse_statements(source).unwrap().len(), 5);
    }

    #[test]
    fn errors_point_where_python_does() {
        assert_eq!(
            error("(a:2x4 =100"),
            "Syntax error at line 1, column 9: Unexpected end of input. Expected one of: ')', '*', '+', '-', '/'"
        );
        assert_eq!(
            error("(a:2x4 =100 $"),
            "Syntax error at line 1, column 13: Unexpected character '$'. Expected one of: ')', '*', '+', '-', '/'"
        );
        assert_eq!(
            error("(a:4x4 =100)"),
            "Syntax error at line 1, column 4: Unexpected token '4'. Expected: piece type (1x4, 1x6, 1x8, 2x2, 2x4, 2x6)"
        );
        assert_eq!(
            error("// nothing"),
            "Syntax error: No pieces defined: the input is empty or contains only comments. Expected at least one piece definition such as (leg:2x4 =720)"
        );
    }

    #[test]
    fn hints_follow_the_list() {
        assert_eq!(
            error("W = ?"),
            "Syntax error at line 1, column 5: Unexpected token '?'. Expected one of: '(', '-', identifier, number. '?' (unknown) works in compact notation only, e.g. (x:2x4 =?) or RB? BD?"
        );
        assert_eq!(
            error("steps = 5"),
            "Syntax error at line 1, column 7: Unexpected token '='. Expected: '{'. 'steps' starts the steps block, so it cannot name a piece or a variable: rename it, or write a block such as steps { \"Frame\": a, b }"
        );
        assert_eq!(
            error("(a:2x4 =100)\n(b:2x4 =100)\na -[FL<W + 1 BL<0]- b"),
            "Syntax error at line 3, column 10: Unexpected token '+'. Expected: face letter (T, D, L, R, F, B). A compact offset that is an expression needs parentheses, e.g. FL<(X + 1)"
        );
    }

    #[test]
    fn after_a_compact_offset_tokens_are_read_as_lark_reads_them() {
        let p = "(a:2x4 =100)\n(b:2x4 =100)\n";
        assert_eq!(
            error(&format!("{p}a -[TF<0 D(:8x30)]- b")),
            "Syntax error at line 3, column 10: Unexpected token 'D('. Expected: face letter (T, D, L, R, F, B)"
        );
        assert_eq!(
            error(&format!("{p}a -[TF<0 S(Slim:3.3x45)]- b")),
            "Syntax error at line 3, column 10: Unexpected token 'S('. Expected: face letter (T, D, L, R, F, B)"
        );
        assert_eq!(
            error(&format!("{p}a -[BD<0 TF<0 TF<0]- b")),
            "Syntax error at line 3, column 15: Unexpected token 'T'. Expected one of: 'D(', 'S(', 'V', ']-'"
        );
        assert_eq!(
            error(&format!("{p}a -[TF<5V00 BD<0]- b")),
            "Syntax error at line 3, column 9: Unexpected token 'V'. Expected: face letter (T, D, L, R, F, B)"
        );
        assert_eq!(
            error(&format!("{p}a -[TF? D(:8x30)]- b")),
            "Syntax error at line 3, column 9: Unexpected token 'D('. Expected: face letter (T, D, L, R, F, B)"
        );
    }

    #[test]
    fn invisible_characters_are_named_as_python_names_them() {
        assert_eq!(
            error("(a:2x4\u{3000}=100)"),
            "Syntax error at line 1, column 7: Unexpected character '\\u3000'. Expected one of: '=', '{'"
        );
        assert_eq!(
            error("\u{feff}(a:2x4 =100)"),
            "Syntax error at line 1, column 1: Unexpected character '\\ufeff'. Expected one of: '(', 'steps', identifier"
        );
    }

    #[test]
    fn deep_nesting_is_an_error_not_a_crash() {
        let brackets = format!("W = {}1{}", "(".repeat(10_000), ")".repeat(10_000));
        assert!(
            error(&brackets).contains("nested too deeply"),
            "{}",
            error(&brackets)
        );
        let signs = format!("W = {}1", "-".repeat(100_000));
        assert!(error(&signs).contains("nested too deeply"));
        // A long sum is not nested: it parses
        let terms = format!("W = 1{}\n(a:2x4 =W)", "+1".repeat(100_000));
        assert!(parse_statements(&terms).is_ok());
    }
}
