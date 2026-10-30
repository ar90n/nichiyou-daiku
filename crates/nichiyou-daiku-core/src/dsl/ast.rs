//! The parsed .nd, before evaluation. Every node keeps the position of its
//! first token, as Lark's tree metadata does, for the errors evaluation finds.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Pos {
    pub line: usize,
    pub column: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Op {
    Add,
    Sub,
    Mul,
    Div,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Expr {
    Number(f64, Pos),
    Var(String, Pos),
    /// At the `-`
    Neg(Box<Expr>, Pos),
    /// Operations of one precedence, applied left to right (`a - b - c` is
    /// `(a - b) - c`), kept in a list so that long ones do not nest. At the
    /// start of the first operand, with its bracket if it has one, as Lark
    /// places every operation of the chain.
    Chain(Box<Expr>, Vec<(Op, Expr)>, Pos),
}

impl Expr {
    pub fn pos(&self) -> Pos {
        match self {
            Expr::Number(_, pos) | Expr::Var(_, pos) | Expr::Neg(_, pos) => *pos,
            Expr::Chain(_, _, pos) => *pos,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum Statement {
    Piece(PieceDef),
    Connection(Box<ConnectionDef>),
    Var(VarDef),
    Steps(StepsDef),
}

impl Statement {
    pub fn pos(&self) -> Pos {
        match self {
            Statement::Piece(def) => def.pos,
            Statement::Connection(def) => def.pos,
            Statement::Var(def) => def.pos,
            Statement::Steps(def) => def.pos,
        }
    }
}

/// At the `(`
#[derive(Clone, Debug, PartialEq)]
pub struct PieceDef {
    pub pos: Pos,
    pub id: Option<String>,
    pub kind: String,
    pub length: LengthDef,
}

#[derive(Clone, Debug, PartialEq)]
pub enum LengthDef {
    /// `=expression`, or `=?` (None)
    Compact(Option<Expr>),
    Props(Props),
}

/// `{...}`, at the `{`; entries in the order written
#[derive(Clone, Debug, PartialEq)]
pub struct Props {
    pub pos: Pos,
    pub entries: Vec<Prop>,
}

/// At the key
#[derive(Clone, Debug, PartialEq)]
pub struct Prop {
    pub pos: Pos,
    pub key: String,
    pub value: Value,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Str(String),
    Expr(Expr),
    Offset(OffsetDef),
}

/// At `FromMin`/`FromMax`, or at `<`/`>`
#[derive(Clone, Debug, PartialEq)]
pub struct OffsetDef {
    pub pos: Pos,
    pub from_max: bool,
    pub value: Expr,
}

/// At the base piece's name
#[derive(Clone, Debug, PartialEq)]
pub struct ConnectionDef {
    pub pos: Pos,
    pub base: String,
    pub target: String,
    pub base_anchor: AnchorDef,
    pub target_anchor: AnchorDef,
    pub kind: Option<TypeDef>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum AnchorDef {
    Json(Props),
    /// At the contact face letter; offset None for `?`
    Compact {
        pos: Pos,
        contact: char,
        edge: char,
        offset: Option<OffsetDef>,
        unknown_pos: Option<Pos>,
    },
}

#[derive(Clone, Debug, PartialEq)]
pub enum TypeDef {
    Vanilla,
    /// At the first size (compact) or at `"type"` (JSON)
    Dowel {
        pos: Pos,
        radius: Expr,
        depth: Expr,
    },
    Screw {
        pos: Pos,
        diameter: Expr,
        length: Expr,
    },
    /// At the `:`; sizes as written
    DowelPreset {
        pos: Pos,
        diameter: String,
        length: String,
    },
    /// At the screw type
    ScrewPreset {
        pos: Pos,
        screw_type: String,
        diameter: String,
        length: String,
    },
}

/// At the name
#[derive(Clone, Debug, PartialEq)]
pub struct VarDef {
    pub pos: Pos,
    pub name: String,
    pub value: Expr,
}

/// At `steps`
#[derive(Clone, Debug, PartialEq)]
pub struct StepsDef {
    pub pos: Pos,
    pub steps: Vec<StepDef>,
}

/// At the step's name
#[derive(Clone, Debug, PartialEq)]
pub struct StepDef {
    pub pos: Pos,
    pub name: String,
    pub pieces: Vec<String>,
}
