//! Assembly steps: the pieces each step adds, the connections it makes, what
//! kind of step it is and the direction its dimension view looks from
//! (steps.py: plan_steps). A model's steps give the order; without them each
//! step adds one piece.

use crate::assembly::Assembly;
use crate::model::{Model, connected_parts};
use crate::placement::{Bounds, edge_axis};

// Tie-break for the dimension view: from above, then the front, then the side
const AXIS_PREFERENCE: [usize; 3] = [2, 1, 0];
// The step images' isometric looks from -x +y +z. A dimension view from the
// same side of its axis shows the part the same way round, so that side wins
// a tie
const ISOMETRIC_SIDE: [i32; 3] = [-1, 1, 1];

/// What a step does to the parts built so far.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StepKind {
    First,
    /// Adds to one part
    Attach,
    /// Builds a part apart from everything built so far
    SubAssembly,
    /// Brings two or more parts together
    Join,
}

impl StepKind {
    pub fn as_str(self) -> &'static str {
        match self {
            StepKind::First => "first",
            StepKind::Attach => "attach",
            StepKind::SubAssembly => "sub-assembly",
            StepKind::Join => "join",
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct PlannedStep {
    /// 1-based position
    pub number: usize,
    /// The name in the steps block; None without one
    pub name: Option<String>,
    pub pieces: Vec<String>,
    /// The connections it makes, as (base, target)
    pub connections: Vec<(String, String)>,
    pub kind: StepKind,
    /// The pieces of the part it leaves, in model order
    pub shown: Vec<String>,
    /// World axis (0, 1, 2) and side (1, -1) the dimension view looks from
    pub view: (usize, i32),
}

#[derive(Clone, Debug, PartialEq)]
pub struct StepPlan {
    /// Whether the model has a steps block
    pub declared: bool,
    pub steps: Vec<PlannedStep>,
}

/// Without a steps block: start with the first piece and the first piece
/// touching it, then add the first piece (in declaration order) touching
/// what is built; when none does, start a new part the same way.
fn one_piece_steps(model: &Model) -> Vec<Vec<String>> {
    let order: Vec<&str> = model.pieces.iter().map(|p| p.id.as_str()).collect();
    let touching = |a: &str, b: &str| {
        model.connections.iter().any(|c| {
            (c.base_id() == a && c.target_id() == b) || (c.base_id() == b && c.target_id() == a)
        })
    };
    let mut placed: Vec<&str> = Vec::new();
    let mut steps = Vec::new();
    while placed.len() < order.len() {
        let free: Vec<&str> = order
            .iter()
            .copied()
            .filter(|p| !placed.contains(p))
            .collect();
        let next_to_built = free
            .iter()
            .copied()
            .find(|p| placed.iter().any(|q| touching(p, q)));
        let new = match next_to_built {
            Some(piece) => vec![piece],
            None => {
                let start = free[0];
                match free
                    .iter()
                    .copied()
                    .find(|&p| p != start && touching(start, p))
                {
                    Some(partner) => vec![start, partner],
                    None => vec![start],
                }
            }
        };
        placed.extend(&new);
        steps.push(new.into_iter().map(String::from).collect());
    }
    steps
}

type Rect = [f64; 4];

/// The box seen along `axis`: its extent on the two other axes.
fn rect(bounds: &Bounds, axis: usize) -> Rect {
    let (u, v) = match axis {
        0 => (1, 2),
        1 => (0, 2),
        _ => (0, 1),
    };
    [bounds.0[u], bounds.0[v], bounds.1[u], bounds.1[v]]
}

fn overlap(a: &Rect, b: &Rect) -> f64 {
    let width = a[2].min(b[2]) - a[0].max(b[0]);
    let height = a[3].min(b[3]) - a[1].max(b[1]);
    if width > 0.0 && height > 0.0 {
        width * height
    } else {
        0.0
    }
}

fn area(r: &Rect) -> f64 {
    (r[2] - r[0]) * (r[3] - r[1])
}

fn centre(bounds: &Bounds, axis: usize) -> f64 {
    (bounds.0[axis] + bounds.1[axis]) / 2.0
}

/// The axis and side the step's dimension view looks from: across the edges
/// its connections are measured along, where the new pieces hide each other
/// least, from the side where the rest hides them least.
fn view(
    assembly: &Assembly,
    pieces: &[String],
    connections: &[(String, String)],
    shown: &[String],
) -> (usize, i32) {
    let bounds = |id: &str| {
        let shape = assembly
            .model
            .piece(id)
            .expect("a piece of the model")
            .shape();
        assembly.placement.pose(id).bounds(shape)
    };
    let measured: Vec<usize> = connections
        .iter()
        .map(|(base, target)| {
            let connection = assembly
                .model
                .connections
                .iter()
                .find(|c| c.base_id() == base && c.target_id() == target)
                .expect("a connection of the model");
            edge_axis(&assembly.placement.pose(base).rotation, &connection.base)
        })
        .collect();
    let mut axes: Vec<usize> = AXIS_PREFERENCE
        .into_iter()
        .filter(|a| !measured.contains(a))
        .collect();
    if axes.is_empty() {
        axes = AXIS_PREFERENCE.to_vec();
    }
    let crowding = |axis: usize| {
        let rects: Vec<Rect> = pieces.iter().map(|p| rect(&bounds(p), axis)).collect();
        let mut hidden = 0.0;
        for (i, a) in rects.iter().enumerate() {
            for b in &rects[i + 1..] {
                hidden += overlap(a, b);
            }
        }
        (hidden, -rects.iter().map(area).sum::<f64>())
    };
    // Only a strictly better axis replaces one: the preferred wins a tie
    let mut axis = axes[0];
    let mut best = crowding(axis);
    for &candidate in &axes[1..] {
        let crowded = crowding(candidate);
        if crowded < best {
            (axis, best) = (candidate, crowded);
        }
    }
    let others: Vec<&String> = shown.iter().filter(|p| !pieces.contains(p)).collect();
    let hidden = |sign: f64| {
        let mut total = 0.0;
        for p in pieces {
            let own = bounds(p);
            for o in &others {
                let other = bounds(o);
                if sign * centre(&other, axis) > sign * centre(&own, axis) {
                    total += overlap(&rect(&own, axis), &rect(&other, axis));
                }
            }
        }
        total
    };
    // The isometric's side wins a tie
    let side = ISOMETRIC_SIDE[axis];
    if hidden(f64::from(-side)) < hidden(f64::from(side)) {
        (axis, -side)
    } else {
        (axis, side)
    }
}

/// The steps of the model's steps block, or one piece per step without one.
pub fn plan_steps(assembly: &Assembly) -> StepPlan {
    let model = &assembly.model;
    let declared = !model.steps.is_empty();
    let groups: Vec<(Option<String>, Vec<String>)> = if declared {
        model
            .steps
            .iter()
            .map(|s| (Some(s.name.clone()), s.pieces.clone()))
            .collect()
    } else {
        one_piece_steps(model)
            .into_iter()
            .map(|pieces| (None, pieces))
            .collect()
    };
    let step_of = |piece: &str| {
        groups
            .iter()
            .position(|(_, pieces)| pieces.iter().any(|p| p == piece))
            .expect("every piece is in a step")
    };
    let pairs: Vec<(&str, &str)> = model
        .connections
        .iter()
        .map(|c| (c.base_id(), c.target_id()))
        .collect();
    let mut placed: Vec<&str> = Vec::new();
    let mut steps = Vec::new();
    for (i, (name, pieces)) in groups.iter().enumerate() {
        let before = connected_parts(&placed, &pairs);
        placed.extend(pieces.iter().map(String::as_str));
        let part = connected_parts(&placed, &pairs)
            .into_iter()
            .find(|part| part.iter().any(|p| pieces.contains(p)))
            .expect("a step's pieces are in one part");
        let joined = before
            .iter()
            .filter(|old| old.iter().any(|p| part.contains(p)))
            .count();
        let kind = match (i, joined) {
            (0, _) => StepKind::First,
            (_, 0) => StepKind::SubAssembly,
            (_, 1) => StepKind::Attach,
            _ => StepKind::Join,
        };
        let made: Vec<(String, String)> = pairs
            .iter()
            .filter(|(a, b)| step_of(a).max(step_of(b)) == i)
            .map(|(a, b)| (a.to_string(), b.to_string()))
            .collect();
        let shown: Vec<String> = model
            .pieces
            .iter()
            .filter(|p| part.contains(&p.id))
            .map(|p| p.id.clone())
            .collect();
        let view = view(assembly, pieces, &made, &shown);
        steps.push(PlannedStep {
            number: i + 1,
            name: name.clone(),
            pieces: pieces.clone(),
            connections: made,
            kind,
            shown,
            view,
        });
    }
    StepPlan { declared, steps }
}

/// How to group the steps, with the design's own first pieces; None when a
/// steps block is declared or there is one step only.
pub fn grouping_hint(plan: &StepPlan) -> Option<String> {
    if plan.declared || plan.steps.len() < 2 {
        return None;
    }
    Some(format!(
        "No steps block: each step adds one piece. Group pieces with a steps block, e.g. \
         `steps {{ \"Frame\": {}, ... }}`.",
        plan.steps[0].pieces.join(", ")
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dsl::parse;

    const SIX: &str = "(a:2x4 =400)\n(b:2x4 =400)\n(c:2x4 =400)\n(d:2x4 =400)\n(e:2x4 =400)\n(f:2x4 =400)\n\
        a -[TF<0 BD<0]- b\nc -[TF<0 BD<0]- d\nb -[TF<0 BD<0]- e\nd -[TF<0 BD<0]- e\nf -[TF<0 BD<0]- e\n";

    fn plan(source: &str) -> StepPlan {
        plan_steps(&Assembly::of(parse(source).unwrap()).unwrap())
    }

    fn strings(items: &[&str]) -> Vec<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    fn pair(a: &str, b: &str) -> (String, String) {
        (a.to_string(), b.to_string())
    }

    #[test]
    fn a_steps_block_gives_first_sub_assembly_join_and_attach() {
        let source = format!(
            "{SIX}steps {{\n  \"Frame\": a, b\n  \"Other\": c, d\n  \"Join\": e\n  \"Top\": f\n}}\n"
        );
        let plan = plan(&source);
        assert!(plan.declared);
        assert_eq!(grouping_hint(&plan), None);
        let steps = &plan.steps;
        assert_eq!(
            steps
                .iter()
                .map(|s| (s.number, s.name.as_deref(), s.kind))
                .collect::<Vec<_>>(),
            [
                (1, Some("Frame"), StepKind::First),
                (2, Some("Other"), StepKind::SubAssembly),
                (3, Some("Join"), StepKind::Join),
                (4, Some("Top"), StepKind::Attach),
            ]
        );
        assert_eq!(steps[1].shown, strings(&["c", "d"]));
        assert_eq!(steps[2].connections, [pair("b", "e"), pair("d", "e")]);
        assert_eq!(steps[2].shown, strings(&["a", "b", "c", "d", "e"]));
        assert_eq!(steps[3].connections, [pair("f", "e")]);
        assert_eq!(
            steps.iter().map(|s| s.view).collect::<Vec<_>>(),
            [(1, 1), (1, 1), (1, -1), (2, 1)]
        );
    }

    #[test]
    fn without_a_steps_block_each_step_adds_the_first_piece_touching_what_is_built() {
        let plan = plan(SIX);
        assert!(!plan.declared);
        assert_eq!(
            grouping_hint(&plan).as_deref(),
            Some(
                "No steps block: each step adds one piece. Group pieces with a steps block, e.g. `steps { \"Frame\": a, b, ... }`."
            )
        );
        assert_eq!(
            plan.steps
                .iter()
                .map(|s| (s.name.clone(), s.pieces.clone(), s.kind))
                .collect::<Vec<_>>(),
            [
                (None, strings(&["a", "b"]), StepKind::First),
                (None, strings(&["e"]), StepKind::Attach),
                (None, strings(&["d"]), StepKind::Attach),
                (None, strings(&["c"]), StepKind::Attach),
                (None, strings(&["f"]), StepKind::Attach),
            ]
        );
        assert_eq!(
            plan.steps.iter().map(|s| s.view).collect::<Vec<_>>(),
            [(1, 1), (1, -1), (2, 1), (1, 1), (2, 1)]
        );
    }

    #[test]
    fn a_piece_touching_nothing_built_starts_a_sub_assembly() {
        let plan = plan("(a:2x4 =400)\n(b:2x4 =400)\n(c:2x4 =400)\na -[TF<0 BD<0]- b\n");
        assert_eq!(
            plan.steps
                .iter()
                .map(|s| (s.pieces.clone(), s.kind, s.shown.clone()))
                .collect::<Vec<_>>(),
            [
                (strings(&["a", "b"]), StepKind::First, strings(&["a", "b"])),
                (strings(&["c"]), StepKind::SubAssembly, strings(&["c"])),
            ]
        );
    }

    #[test]
    fn one_piece_is_one_step_and_needs_no_hint() {
        let plan = plan("(a:2x4 =400)\n");
        assert_eq!(plan.steps.len(), 1);
        assert_eq!(
            (plan.steps[0].kind, plan.steps[0].view),
            (StepKind::First, (1, 1))
        );
        assert_eq!(grouping_hint(&plan), None);
        assert_eq!(StepKind::SubAssembly.as_str(), "sub-assembly");
    }
}
