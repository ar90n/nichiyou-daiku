//! A model: pieces, the connections between them and the assembly steps.

use std::collections::HashMap;

use crate::connection::Connection;
use crate::difflib::close_match;
use crate::piece::Piece;

/// An assembly step: its name and the pieces it adds, in the order they go on.
#[derive(Clone, Debug, PartialEq)]
pub struct Step {
    pub name: String,
    pub pieces: Vec<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Model {
    pub pieces: Vec<Piece>,
    pub connections: Vec<Connection>,
    pub steps: Vec<Step>,
}

impl Model {
    /// Model.of: no duplicate pieces or piece pairs, connections only between
    /// the model's pieces, and steps that cover every piece once.
    pub fn new(
        pieces: Vec<Piece>,
        connections: Vec<Connection>,
        steps: Vec<Step>,
    ) -> Result<Model, String> {
        let mut known: HashMap<&str, &Piece> = HashMap::new();
        for piece in &pieces {
            if known.insert(&piece.id, piece).is_some() {
                return Err(format!("Duplicate piece id: '{}'", piece.id));
            }
        }
        let mut pairs: Vec<(&str, &str)> = Vec::new();
        for connection in &connections {
            for (role, bound) in [("base", &connection.base), ("target", &connection.target)] {
                match known.get(bound.piece.id.as_str()) {
                    None => {
                        return Err(format!(
                            "Connection references unknown {role} piece: '{}'",
                            bound.piece.id
                        ));
                    }
                    Some(piece) if **piece != bound.piece => {
                        return Err(format!(
                            "Connection {role} piece '{}' does not match the model's piece \
                             with the same id",
                            bound.piece.id
                        ));
                    }
                    Some(_) => {}
                }
            }
            let key = (connection.base_id(), connection.target_id());
            if pairs.contains(&key) || pairs.contains(&(key.1, key.0)) {
                return Err(format!(
                    "Duplicate connection between '{}' and '{}': only one connection per \
                     piece pair is supported",
                    key.0, key.1
                ));
            }
            pairs.push(key);
        }
        if !steps.is_empty() {
            check_steps(&pieces, &pairs, &steps)?;
        }
        Ok(Model {
            pieces,
            connections,
            steps,
        })
    }

    pub fn piece(&self, id: &str) -> Option<&Piece> {
        self.pieces.iter().find(|piece| piece.id == id)
    }

    pub fn has_unknowns(&self) -> bool {
        self.pieces.iter().any(|piece| piece.length.is_none())
            || self
                .connections
                .iter()
                .any(|connection| connection.base.anchor.offset.is_none())
    }
}

/// How many separate parts the pairs leave among these pieces, and which.
pub fn connected_parts(pieces: &[&str], pairs: &[(&str, &str)]) -> Vec<Vec<String>> {
    let mut parent: HashMap<&str, &str> = pieces.iter().map(|&p| (p, p)).collect();
    fn root<'a>(parent: &HashMap<&'a str, &'a str>, mut piece: &'a str) -> &'a str {
        while parent[piece] != piece {
            piece = parent[piece];
        }
        piece
    }
    for &(a, b) in pairs {
        if parent.contains_key(a) && parent.contains_key(b) {
            let (ra, rb) = (root(&parent, a), root(&parent, b));
            parent.insert(ra, rb);
        }
    }
    let mut parts: Vec<(String, Vec<String>)> = Vec::new();
    for &piece in pieces {
        let r = root(&parent, piece).to_string();
        match parts.iter_mut().find(|(top, _)| *top == r) {
            Some((_, members)) => members.push(piece.to_string()),
            None => parts.push((r, vec![piece.to_string()])),
        }
    }
    parts.into_iter().map(|(_, members)| members).collect()
}

fn check_steps(pieces: &[Piece], pairs: &[(&str, &str)], steps: &[Step]) -> Result<(), String> {
    let ids: Vec<&str> = pieces.iter().map(|piece| piece.id.as_str()).collect();
    let mut step_of: HashMap<&str, usize> = HashMap::new();
    for (number, step) in steps.iter().enumerate().map(|(i, s)| (i + 1, s)) {
        if step.pieces.is_empty() {
            return Err(format!(
                "Step '{}' adds no pieces; name at least one",
                step.name
            ));
        }
        for piece_id in &step.pieces {
            if !ids.contains(&piece_id.as_str()) {
                let hint = match close_match(piece_id, &ids) {
                    Some(close) => format!("; did you mean '{close}'?"),
                    None => String::new(),
                };
                return Err(format!(
                    "Step '{}' names unknown piece '{piece_id}'{hint}",
                    step.name
                ));
            }
            if let Some(&first) = step_of.get(piece_id.as_str()) {
                let first_name = &steps[first - 1].name;
                let place = if first == number {
                    format!("twice in step '{}'", step.name)
                } else if *first_name == step.name {
                    format!("in steps {first} and {number}, both named '{}'", step.name)
                } else {
                    format!("in steps '{first_name}' and '{}'", step.name)
                };
                return Err(format!("'{piece_id}' is {place}; keep it in one step"));
            }
            step_of.insert(piece_id, number);
        }
    }
    let missing: Vec<&str> = ids
        .iter()
        .copied()
        .filter(|id| !step_of.contains_key(id))
        .collect();
    if !missing.is_empty() {
        let them = if missing.len() == 1 { "it" } else { "them" };
        return Err(format!(
            "steps leaves out {}; add {them} to a step",
            missing.join(", ")
        ));
    }
    let mut placed: Vec<&str> = Vec::new();
    for step in steps {
        placed.extend(step.pieces.iter().map(String::as_str));
        let parts = connected_parts(&placed, pairs)
            .into_iter()
            .filter(|part| part.iter().any(|p| step.pieces.contains(p)))
            .count();
        if parts > 1 {
            return Err(format!(
                "Step '{}' leaves its pieces in {parts} separate parts: split it into steps or \
                 connect the parts",
                step.name
            ));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::piece::{Piece, PieceType};

    fn piece(id: &str) -> Piece {
        Piece::new(id.into(), PieceType::P2x4, Some(100.0)).unwrap()
    }

    #[test]
    fn steps_name_unknown_pieces_with_a_hint() {
        let step = Step {
            name: "A".into(),
            pieces: vec!["lge".into()],
        };
        assert_eq!(
            Model::new(vec![piece("leg")], vec![], vec![step]).unwrap_err(),
            "Step 'A' names unknown piece 'lge'; did you mean 'leg'?"
        );
    }

    #[test]
    fn steps_must_cover_every_piece() {
        let step = Step {
            name: "A".into(),
            pieces: vec!["a".into()],
        };
        assert_eq!(
            Model::new(vec![piece("a"), piece("b")], vec![], vec![step]).unwrap_err(),
            "steps leaves out b; add it to a step"
        );
    }
}
