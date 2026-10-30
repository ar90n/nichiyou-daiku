//! From parsed statements to a model: variables, expressions, presets, and
//! the errors the Python version's transformer gives, where it gives them.

use std::collections::{HashMap, HashSet};

use super::ast::*;
use super::error::{DslError, ErrorKind};
use crate::anchor::{Anchor, BoundAnchor};
use crate::connection::{Connection, ConnectionType};
use crate::geometry::{Face, Offset};
use crate::model::{Model, Step};
use crate::piece::{Piece, PieceType};
use crate::presets::{find_dowel_preset, find_screw_preset};
use crate::pyfmt::repr_str;

const PIECE_PROPERTIES: [&str; 2] = ["length", "note"];
const ANCHOR_PROPERTIES: [&str; 3] = ["contact_face", "edge_shared_face", "offset"];
const FACE_CHOICES: &str = "'top', 'down', 'left', 'right', 'front' or 'back'";

/// A model with where its pieces and connections are written, for errors
/// found once the whole model is known.
pub struct Located {
    pub model: Model,
    pub pieces: HashMap<String, Pos>,
    pub connections: HashMap<(String, String), Pos>,
    /// The first token of the source
    pub start: Pos,
}

fn at(kind: ErrorKind, message: impl Into<String>, pos: Pos) -> DslError {
    DslError::new(kind, message, Some((pos.line, pos.column)))
}

fn semantic(message: impl Into<String>, pos: Pos) -> DslError {
    at(ErrorKind::Semantic, message, pos)
}

fn validation(message: impl Into<String>, pos: Pos) -> DslError {
    at(ErrorKind::Validation, message, pos)
}

/// A property's value once evaluated.
#[derive(Clone, Debug)]
enum PropValue {
    Number(f64),
    Str(String),
    Offset(Offset),
}

impl PropValue {
    /// As Python's `repr` writes the value
    fn repr(&self) -> String {
        match self {
            PropValue::Number(value) => crate::pyfmt::repr_f64(*value),
            PropValue::Str(text) => repr_str(text),
            PropValue::Offset(offset) => offset.repr(),
        }
    }

    /// Python's truthiness, for the transformer's `if not value`
    fn is_truthy(&self) -> bool {
        match self {
            PropValue::Number(value) => *value != 0.0,
            PropValue::Str(text) => !text.is_empty(),
            PropValue::Offset(_) => true,
        }
    }
}

fn face_of_letter(letter: char) -> Face {
    match letter {
        'T' => Face::Top,
        'D' => Face::Down,
        'L' => Face::Left,
        'R' => Face::Right,
        'F' => Face::Front,
        _ => Face::Back,
    }
}

#[derive(Default)]
struct Evaluator {
    variables: HashMap<String, f64>,
    pieces: Vec<Piece>,
    connections: Vec<Connection>,
    piece_positions: HashMap<String, Pos>,
    connection_positions: HashMap<(String, String), Pos>,
    steps: Option<(Vec<Step>, Pos)>,
    anonymous: usize,
}

/// The model of the statements, in source order as Lark's transformer goes:
/// within a statement its parts first, then the statement.
pub fn evaluate(statements: &[Statement]) -> Result<Located, DslError> {
    let start = statements
        .first()
        .map(Statement::pos)
        .unwrap_or(Pos { line: 1, column: 1 });
    let mut evaluator = Evaluator::default();
    for statement in statements {
        match statement {
            Statement::Var(def) => evaluator.var_def(def)?,
            Statement::Piece(def) => evaluator.piece_def(def)?,
            Statement::Connection(def) => evaluator.connection_def(def)?,
            Statement::Steps(def) => evaluator.steps_def(def)?,
        }
    }
    let (steps, steps_pos) = evaluator.steps.take().unwrap_or((Vec::new(), start));
    // Pieces and connections were checked as they were read, so what is left
    // is the steps block
    let model = Model::new(evaluator.pieces, evaluator.connections, steps)
        .map_err(|message| semantic(message, steps_pos))?;
    Ok(Located {
        model,
        pieces: evaluator.piece_positions,
        connections: evaluator.connection_positions,
        start,
    })
}

impl Evaluator {
    fn expr(&self, expr: &Expr) -> Result<f64, DslError> {
        Ok(match expr {
            Expr::Number(value, _) => *value,
            Expr::Var(name, pos) => *self.variables.get(name).ok_or_else(|| {
                semantic(
                    format!("Undefined variable '{name}' (define it before it is used)"),
                    *pos,
                )
            })?,
            Expr::Neg(inner, _) => -self.expr(inner)?,
            Expr::Chain(first, rest, pos) => {
                let mut value = self.expr(first)?;
                for (op, operand) in rest {
                    let operand = self.expr(operand)?;
                    value = match op {
                        Op::Add => value + operand,
                        Op::Sub => value - operand,
                        Op::Mul => value * operand,
                        Op::Div if operand == 0.0 => {
                            return Err(validation("Division by zero", *pos));
                        }
                        Op::Div => value / operand,
                    };
                }
                value
            }
        })
    }

    fn var_def(&mut self, def: &VarDef) -> Result<(), DslError> {
        let value = self.expr(&def.value)?;
        if self.variables.contains_key(&def.name) {
            return Err(semantic(
                format!("Variable '{}' is already defined", def.name),
                def.pos,
            ));
        }
        self.variables.insert(def.name.clone(), value);
        Ok(())
    }

    fn offset(&self, def: &OffsetDef) -> Result<Offset, DslError> {
        let value = self.expr(&def.value)?;
        let offset = if def.from_max {
            Offset::from_max(value)
        } else {
            Offset::from_min(value)
        };
        offset.map_err(|error| validation(error.to_string(), def.pos))
    }

    /// The values in order, then the repeated keys (at the first key, as
    /// prop_list), then the keys not allowed (at the `{`).
    fn props(
        &self,
        props: &Props,
        allowed: &[&str],
        kind: &str,
    ) -> Result<HashMap<String, PropValue>, DslError> {
        let mut values = Vec::new();
        for prop in &props.entries {
            let value = match &prop.value {
                Value::Str(text) => PropValue::Str(text.clone()),
                Value::Expr(expr) => PropValue::Number(self.expr(expr)?),
                Value::Offset(def) => PropValue::Offset(self.offset(def)?),
            };
            values.push((prop.key.clone(), value));
        }
        let mut seen = HashSet::new();
        for (key, _) in &values {
            if !seen.insert(key) {
                return Err(validation(
                    format!("Duplicate property '{key}'"),
                    props.entries[0].pos,
                ));
            }
        }
        for (key, _) in &values {
            if !allowed.contains(&key.as_str()) {
                return Err(validation(
                    format!(
                        "Unknown {kind} property '{key}' (allowed: {})",
                        allowed.join(", ")
                    ),
                    props.pos,
                ));
            }
        }
        Ok(values.into_iter().collect())
    }

    fn piece_def(&mut self, def: &PieceDef) -> Result<(), DslError> {
        let length = match &def.length {
            LengthDef::Compact(None) => None,
            LengthDef::Compact(Some(expr)) => Some(self.expr(expr)?),
            LengthDef::Props(props) => {
                let values = self.props(props, &PIECE_PROPERTIES, "piece")?;
                match values.get("length") {
                    None => {
                        return Err(validation("Piece must have a 'length' property", def.pos));
                    }
                    Some(PropValue::Number(length)) => Some(*length),
                    Some(other) => {
                        return Err(validation(
                            format!(
                                "Piece property 'length' must be a number, got {}",
                                other.repr()
                            ),
                            def.pos,
                        ));
                    }
                }
            }
        };
        let id = match &def.id {
            Some(id) => id.clone(),
            None => {
                self.anonymous += 1;
                format!("00000000-0000-4000-8000-{:012x}", self.anonymous)
            }
        };
        let kind = PieceType::parse(&def.kind).expect("the grammar admits only known types");
        let piece =
            Piece::new(id, kind, length).map_err(|error| validation(error.to_string(), def.pos))?;
        if piece.id == "steps" {
            return Err(semantic(
                "'steps' names the steps block and cannot name a piece; rename the piece",
                def.pos,
            ));
        }
        if self.piece_positions.contains_key(&piece.id) {
            return Err(semantic(
                format!("Duplicate piece ID: {}", piece.id),
                def.pos,
            ));
        }
        self.piece_positions.insert(piece.id.clone(), def.pos);
        self.pieces.push(piece);
        Ok(())
    }

    fn anchor(&self, def: &AnchorDef) -> Result<Anchor, DslError> {
        match def {
            AnchorDef::Compact {
                pos,
                contact,
                edge,
                offset,
                ..
            } => {
                let offset = offset.as_ref().map(|o| self.offset(o)).transpose()?;
                Anchor::new(face_of_letter(*contact), face_of_letter(*edge), offset)
                    .map_err(|message| validation(message, *pos))
            }
            AnchorDef::Json(props) => {
                let values = self.props(props, &ANCHOR_PROPERTIES, "anchor")?;
                let fail = |message: String| validation(message, props.pos);
                let present = |key: &str| values.get(key).filter(|v| v.is_truthy());
                let contact = present("contact_face")
                    .ok_or_else(|| fail("Anchor must have 'contact_face' property".into()))?;
                let edge = present("edge_shared_face")
                    .ok_or_else(|| fail("Anchor must have 'edge_shared_face' property".into()))?;
                let offset = match present("offset") {
                    None => return Err(fail("Anchor must have 'offset' property".into())),
                    Some(PropValue::Offset(offset)) => *offset,
                    Some(PropValue::Str(_)) => {
                        return Err(fail("Invalid offset type: <class 'str'>".into()));
                    }
                    Some(PropValue::Number(_)) => {
                        return Err(fail("Invalid offset type: <class 'float'>".into()));
                    }
                };
                // pydantic checks the fields in the order Anchor declares them
                let face = |field: &str, value: &PropValue| match value {
                    PropValue::Str(text) => Face::parse(text).ok_or_else(|| {
                        format!(
                            "{field}: Input should be {FACE_CHOICES} (got {})",
                            value.repr()
                        )
                    }),
                    _ => Err(format!(
                        "{field}: Input should be {FACE_CHOICES} (got {})",
                        value.repr()
                    )),
                };
                let edge_face = face("edge_shared_face", edge);
                let contact_face = face("contact_face", contact);
                match (contact_face, edge_face) {
                    (Ok(contact), Ok(edge)) => {
                        Anchor::new(contact, edge, Some(offset)).map_err(fail)
                    }
                    (contact, edge) => {
                        let errors: Vec<String> =
                            [edge.err(), contact.err()].into_iter().flatten().collect();
                        Err(fail(errors.join("; ")))
                    }
                }
            }
        }
    }

    fn connection_type(&self, def: &TypeDef) -> Result<ConnectionType, DslError> {
        match def {
            TypeDef::Vanilla => Ok(ConnectionType::Vanilla),
            TypeDef::Dowel { pos, radius, depth } => {
                let (radius, depth) = (self.expr(radius)?, self.expr(depth)?);
                ConnectionType::dowel(radius, depth).map_err(|message| validation(message, *pos))
            }
            TypeDef::Screw {
                pos,
                diameter,
                length,
            } => {
                let (diameter, length) = (self.expr(diameter)?, self.expr(length)?);
                ConnectionType::screw(diameter, length, None)
                    .map_err(|message| validation(message, *pos))
            }
            TypeDef::DowelPreset {
                pos,
                diameter,
                length,
            } => {
                let size: (f64, f64) = (number(diameter), number(length));
                let (diameter_mm, length_mm) =
                    find_dowel_preset(size.0, size.1).ok_or_else(|| {
                        validation(format!("Unknown dowel preset: {diameter}x{length}"), *pos)
                    })?;
                ConnectionType::dowel(diameter_mm / 2.0, length_mm)
                    .map_err(|message| validation(message, *pos))
            }
            TypeDef::ScrewPreset {
                pos,
                screw_type,
                diameter,
                length,
            } => {
                let (d, l, kind) = find_screw_preset(screw_type, number(diameter), number(length))
                    .ok_or_else(|| {
                        validation(
                            format!("Unknown {screw_type} screw preset: {diameter}x{length}"),
                            *pos,
                        )
                    })?;
                ConnectionType::screw(d, l, Some(kind)).map_err(|message| validation(message, *pos))
            }
        }
    }

    fn connection_def(&mut self, def: &ConnectionDef) -> Result<(), DslError> {
        let base_anchor = self.anchor(&def.base_anchor)?;
        let target_anchor = self.anchor(&def.target_anchor)?;
        let kind = match &def.kind {
            None => ConnectionType::Vanilla,
            Some(kind) => self.connection_type(kind)?,
        };
        let find = |id: &str| {
            self.pieces
                .iter()
                .find(|piece| piece.id == id)
                .cloned()
                .ok_or_else(|| semantic(format!("Unknown piece reference: {id}"), def.pos))
        };
        let (base, target) = (find(&def.base)?, find(&def.target)?);
        let key = (def.base.clone(), def.target.clone());
        let reversed = (def.target.clone(), def.base.clone());
        if self.connection_positions.contains_key(&key)
            || self.connection_positions.contains_key(&reversed)
        {
            return Err(semantic(
                format!(
                    "Duplicate connection between '{}' and '{}': only one connection per \
                     piece pair is supported",
                    def.base, def.target
                ),
                def.pos,
            ));
        }
        let fail = |message: String| validation(message, def.pos);
        let base = BoundAnchor::new(base, base_anchor).map_err(fail)?;
        let target = BoundAnchor::new(target, target_anchor).map_err(fail)?;
        let connection = Connection::new(base, target, kind).map_err(fail)?;
        self.connection_positions.insert(key, def.pos);
        self.connections.push(connection);
        Ok(())
    }

    fn steps_def(&mut self, def: &StepsDef) -> Result<(), DslError> {
        if self.steps.is_some() {
            return Err(semantic(
                "Only one steps block is allowed; merge them into one",
                def.pos,
            ));
        }
        let steps = def
            .steps
            .iter()
            .map(|step| Step {
                name: step.name.clone(),
                pieces: step.pieces.clone(),
            })
            .collect();
        self.steps = Some((steps, def.pos));
        Ok(())
    }
}

fn number(text: &str) -> f64 {
    text.parse()
        .expect("the lexer reads only numbers as NUMBER")
}

#[cfg(test)]
mod tests {
    use crate::dsl::parse;

    fn error(source: &str) -> String {
        parse(source).expect_err("an error").to_string()
    }

    #[test]
    fn values_are_checked_where_they_are_written() {
        assert_eq!(
            error("(a:2x4 =0)"),
            "line 1, column 1: length: Input should be greater than 0 (got 0.0)"
        );
        assert_eq!(
            error("(a:2x4 =1e308*10)"),
            "line 1, column 1: length: Input should be a finite number (got inf)"
        );
        assert_eq!(
            error("(a:2x4 =100)\n(b:2x4 =100)\na -[FL<(0-5) BL<0]- b"),
            "line 3, column 7: value: Input should be greater than or equal to 0 (got -5.0)"
        );
        assert_eq!(
            error("(a:2x4 =100)\n(b:2x4 =100)\na -[FL<0 BL<0 D(0-1, 10)]- b"),
            "line 3, column 17: radius: Input should be greater than or equal to 0 (got -1.0)"
        );
        assert_eq!(
            error("(a:2x4 {\"length\": FromMin(5)})"),
            "line 1, column 1: Piece property 'length' must be a number, got FromMin(value=5.0)"
        );
        assert_eq!(
            error("(a:2x4 {\"length\": \"abc\"})"),
            "line 1, column 1: Piece property 'length' must be a number, got 'abc'"
        );
        assert_eq!(
            error("(a:2x4 {\"length\": 5, \"colour\": \"red\"})"),
            "line 1, column 8: Unknown piece property 'colour' (allowed: length, note)"
        );
    }

    #[test]
    fn json_anchors_are_checked_as_pydantic_does() {
        let source = |anchor: &str| {
            format!(
                "(a:2x4 =100)\n(b:2x4 =100)\na -[{anchor} {{\"contact_face\":\"back\",\"edge_shared_face\":\"left\",\"offset\":FromMin(0)}}]- b"
            )
        };
        assert_eq!(
            error(&source(
                "{\"contact_face\":\"upper\",\"edge_shared_face\":\"lower\",\"offset\":FromMin(0)}"
            )),
            "line 3, column 5: edge_shared_face: Input should be 'top', 'down', 'left', 'right', 'front' or 'back' (got 'lower'); contact_face: Input should be 'top', 'down', 'left', 'right', 'front' or 'back' (got 'upper')"
        );
        assert_eq!(
            error(&source(
                "{\"contact_face\":\"front\",\"edge_shared_face\":\"left\",\"offset\":\"abc\"}"
            )),
            "line 3, column 5: Invalid offset type: <class 'str'>"
        );
        assert_eq!(
            error(&source(
                "{\"contact_face\":\"front\",\"contact_face\":\"left\"}"
            )),
            "line 3, column 6: Duplicate property 'contact_face'"
        );
    }

    #[test]
    fn variables_and_division() {
        assert_eq!(
            error("(a:2x4 =W)"),
            "line 1, column 9: Undefined variable 'W' (define it before it is used)"
        );
        assert_eq!(
            error("W = 5\n(a:2x4 =W/0)"),
            "line 2, column 9: Division by zero"
        );
        assert_eq!(
            error("W = 1\nW = 2\n(a:2x4 =W)"),
            "line 2, column 1: Variable 'W' is already defined"
        );
        let model = parse("W = 10 * (2 + 1)\n(a:2x4 =W - 5)").unwrap();
        assert_eq!(model.pieces[0].length, Some(25.0));
    }

    #[test]
    fn steps_errors_point_at_the_block() {
        assert_eq!(
            error("(leg:2x4 =100)\nsteps { \"A\": lge }"),
            "line 2, column 1: Step 'A' names unknown piece 'lge'; did you mean 'leg'?"
        );
    }

    #[test]
    fn pieces_without_names_get_ids_shaped_like_uuids() {
        let model = parse("(:2x4 =100)\n(:2x4 =200)").unwrap();
        assert_eq!(model.pieces[0].id, "00000000-0000-4000-8000-000000000001");
        assert_eq!(model.pieces[1].id, "00000000-0000-4000-8000-000000000002");
    }

    #[test]
    fn an_operation_is_placed_at_its_first_operand_with_its_brackets() {
        assert_eq!(error("W = (1+1) / 0"), "line 1, column 5: Division by zero");
        assert_eq!(error("W = ((1+1))/0"), "line 1, column 5: Division by zero");
        assert_eq!(error("W = (1/0)"), "line 1, column 6: Division by zero");
        assert_eq!(error("W = -(1+1)/0"), "line 1, column 5: Division by zero");
        let p = "(a:2x4 =100)\n(b:2x4 =100)\n";
        assert_eq!(
            error(&format!("{p}a -[FL<0 BL<0 D((0-1), 10)]- b")),
            "line 3, column 17: radius: Input should be greater than or equal to 0 (got -1.0)"
        );
        assert_eq!(
            error(&format!("{p}a -[FL<0 BL<0 S((0-1),10)]- b")),
            "line 3, column 17: diameter: Input should be greater than or equal to 0 (got -1.0)"
        );
    }

    #[test]
    fn a_long_sum_evaluates_without_deep_recursion() {
        let model = parse(&format!("W = 1{}\n(a:2x4 =W)", "+1".repeat(100_000))).unwrap();
        assert_eq!(model.pieces[0].length, Some(100_001.0));
    }
}
