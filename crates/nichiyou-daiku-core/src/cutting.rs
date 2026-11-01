//! Cut lists from stock boards (cutting.py): which boards to buy and where to
//! cut each piece, buying the least lumber.

use crate::piece::PieceType;

/// Material each saw cut removes
pub const DEFAULT_KERF_MM: f64 = 3.0;
/// Japanese home centres sell SPF lumber as 6F, 8F, 10F and 12F boards
pub const DEFAULT_LENGTHS: [f64; 4] = [1820.0, 2440.0, 3050.0, 3650.0];
/// Up to this many stock lengths every set of them is tried; above it, all of
/// them together and each alone
const MAX_SEARCHED_LENGTHS: usize = 8;

/// A board to buy and the pieces cut from it, longest first.
#[derive(Clone, Debug, PartialEq)]
pub struct Board {
    pub length: f64,
    pub cuts: Vec<(String, f64)>,
    pub waste: f64,
}

/// The boards for one lumber type.
#[derive(Clone, Debug, PartialEq)]
pub struct LumberPlan {
    /// The store's lengths as given
    pub available: Vec<f64>,
    pub boards: Vec<Board>,
    /// Pieces longer than every board, which cannot be cut from stock
    pub oversize: Vec<(String, f64)>,
}

impl LumberPlan {
    /// Boards to buy per stock length, shortest first.
    pub fn board_counts(&self) -> Vec<(f64, usize)> {
        let mut counts: Vec<(f64, usize)> = Vec::new();
        for board in &self.boards {
            match counts
                .iter_mut()
                .find(|(length, _)| *length == board.length)
            {
                Some((_, n)) => *n += 1,
                None => counts.push((board.length, 1)),
            }
        }
        counts.sort_by(|a, b| a.0.total_cmp(&b.0));
        counts
    }

    pub fn total_waste(&self) -> f64 {
        self.boards.iter().map(|b| b.waste).sum()
    }

    /// Waste as a share of the lumber bought (0 when nothing is bought).
    pub fn waste_percentage(&self) -> f64 {
        let bought: f64 = self.boards.iter().map(|b| b.length).sum();
        if bought > 0.0 {
            self.total_waste() / bought * 100.0
        } else {
            0.0
        }
    }
}

fn longest(lengths: &[f64]) -> f64 {
    lengths.iter().copied().fold(f64::NEG_INFINITY, f64::max)
}

/// Fill boards one at a time, each with the board length that wastes least:
/// first fit decreasing. Every cut removes `kerf`, but a piece ending exactly
/// at the board end needs no final cut. Pieces longer than every board are
/// left out.
fn fill_boards(pieces: &[(String, f64)], lengths: &[f64], kerf: f64) -> Vec<Board> {
    let longest_board = longest(lengths);
    let mut remaining: Vec<&(String, f64)> =
        pieces.iter().filter(|p| p.1 <= longest_board).collect();
    // Stable, as Python's sorted(reverse=True): equal pieces keep their order
    remaining.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    let mut sorted = lengths.to_vec();
    sorted.sort_by(f64::total_cmp);
    let mut boards = Vec::new();
    while !remaining.is_empty() {
        let mut best: Option<(Board, Vec<&(String, f64)>)> = None;
        for &length in &sorted {
            let (mut cuts, mut used, mut left) = (Vec::new(), 0.0, Vec::new());
            for &piece in &remaining {
                let needed = piece.1 + if cuts.is_empty() { 0.0 } else { kerf };
                if used + needed <= length {
                    cuts.push(piece.clone());
                    used += needed;
                } else {
                    left.push(piece);
                }
            }
            if cuts.is_empty() {
                continue;
            }
            // Separating the offcut takes one more cut; never -0.0
            let offcut = length - used - kerf;
            let waste = if offcut > 0.0 { offcut } else { 0.0 };
            if best.as_ref().is_none_or(|(board, _)| waste < board.waste) {
                best = Some((
                    Board {
                        length,
                        cuts,
                        waste,
                    },
                    left,
                ));
            }
        }
        let (board, left) = best.expect("every remaining piece fits the longest board");
        boards.push(board);
        remaining = left;
    }
    boards
}

/// itertools.combinations: every `count` of `items`, in order.
fn combinations(items: &[f64], count: usize) -> Vec<Vec<f64>> {
    let mut out = Vec::new();
    let mut index: Vec<usize> = (0..count).collect();
    loop {
        out.push(index.iter().map(|&i| items[i]).collect());
        let Some(i) = (0..count)
            .rev()
            .find(|&i| index[i] != i + items.len() - count)
        else {
            return out;
        };
        index[i] += 1;
        for j in i + 1..count {
            index[j] = index[j - 1] + 1;
        }
    }
}

/// The sets of stock lengths to try, each shortest first.
fn candidates(lengths: &[f64]) -> Vec<Vec<f64>> {
    if lengths.len() <= MAX_SEARCHED_LENGTHS {
        (1..=lengths.len())
            .flat_map(|count| combinations(lengths, count))
            .collect()
    } else {
        std::iter::once(lengths.to_vec())
            .chain(lengths.iter().map(|&l| vec![l]))
            .collect()
    }
}

/// The plan buying the least total length, then the fewest boards: filling
/// greedily can over-use a short board and leave a small piece a whole board
/// of its own, so the fill runs with every set of the stock lengths whose
/// longest board fits the longest piece.
fn optimize_cuts(pieces: &[(String, f64)], available: &[f64], kerf: f64) -> Vec<Board> {
    let mut lengths = available.to_vec();
    lengths.sort_by(f64::total_cmp);
    lengths.dedup();
    let board = longest(&lengths);
    let needed = pieces
        .iter()
        .map(|p| p.1)
        .filter(|&l| l <= board)
        .fold(0.0, f64::max);
    let cost = |plan: &[Board]| (plan.iter().map(|b| b.length).sum::<f64>(), plan.len());
    let mut best: Option<Vec<Board>> = None;
    for chosen in candidates(&lengths) {
        if *chosen.last().expect("a length") < needed {
            continue;
        }
        let plan = fill_boards(pieces, &chosen, kerf);
        if best
            .as_ref()
            .is_none_or(|b| cost(&plan).partial_cmp(&cost(b)) == Some(std::cmp::Ordering::Less))
        {
            best = Some(plan);
        }
    }
    best.unwrap_or_default()
}

/// The cuts for every lumber type the pieces use, in report order.
pub fn plan_cuts(
    pieces: &[(String, PieceType, f64)],
    lengths: &[(PieceType, Vec<f64>)],
    kerf: f64,
) -> Vec<(PieceType, LumberPlan)> {
    let mut kinds: Vec<PieceType> = Vec::new();
    for (_, kind, _) in pieces {
        if !kinds.contains(kind) {
            kinds.push(*kind);
        }
    }
    kinds.sort_by_key(|kind| kind.as_str());
    kinds
        .into_iter()
        .map(|kind| {
            let of_kind: Vec<(String, f64)> = pieces
                .iter()
                .filter(|(_, k, _)| *k == kind)
                .map(|(id, _, length)| (id.clone(), *length))
                .collect();
            let available = lengths
                .iter()
                .find(|(k, _)| *k == kind)
                .map_or(DEFAULT_LENGTHS.to_vec(), |(_, l)| l.clone());
            let board = longest(&available);
            let plan = LumberPlan {
                boards: optimize_cuts(&of_kind, &available, kerf),
                oversize: of_kind.iter().filter(|p| p.1 > board).cloned().collect(),
                available,
            };
            (kind, plan)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pieces(list: &[(&str, f64)]) -> Vec<(String, f64)> {
        list.iter()
            .map(|(id, length)| (id.to_string(), *length))
            .collect()
    }

    fn typed(list: &[(&str, PieceType, f64)]) -> Vec<(String, PieceType, f64)> {
        list.iter()
            .map(|(id, kind, length)| (id.to_string(), *kind, *length))
            .collect()
    }

    fn ids(boards: &[Board]) -> Vec<&str> {
        boards
            .iter()
            .flat_map(|b| b.cuts.iter().map(|(id, _)| id.as_str()))
            .collect()
    }

    #[test]
    fn two_pieces_share_a_board() {
        let boards = optimize_cuts(&pieces(&[("p1", 1000.0), ("p2", 800.0)]), &[2440.0], 0.0);
        assert_eq!(boards.len(), 1);
        assert_eq!(boards[0].length, 2440.0);
        assert_eq!(ids(&boards), ["p1", "p2"]);
        assert_eq!(boards[0].waste, 640.0);
    }

    #[test]
    fn pieces_too_long_together_take_a_board_each() {
        let boards = optimize_cuts(&pieces(&[("p1", 2000.0), ("p2", 2000.0)]), &[2440.0], 0.0);
        assert_eq!(boards.len(), 2);
        assert!(
            boards
                .iter()
                .all(|b| b.length == 2440.0 && b.cuts.len() == 1)
        );
    }

    #[test]
    fn the_board_that_wastes_least_is_chosen() {
        let boards = optimize_cuts(&pieces(&[("p1", 1500.0)]), &[1830.0, 2440.0], 0.0);
        assert_eq!((boards[0].length, boards[0].waste), (1830.0, 330.0));
    }

    #[test]
    fn no_pieces_need_no_boards() {
        assert!(optimize_cuts(&[], &[2440.0], DEFAULT_KERF_MM).is_empty());
    }

    #[test]
    fn the_saw_takes_its_kerf_between_cuts() {
        // 3 x 813 = 2439mm fits 2440 only if the saw removes nothing
        let three = pieces(&[("a", 813.0), ("b", 813.0), ("c", 813.0)]);
        assert_eq!(optimize_cuts(&three, &[2440.0], 3.0).len(), 2);
        let boards = optimize_cuts(&pieces(&[("a", 1000.0), ("b", 800.0)]), &[2440.0], 3.0);
        assert_eq!(boards[0].waste, 634.0);
    }

    #[test]
    fn an_exact_fit_needs_no_final_cut() {
        let boards = optimize_cuts(&pieces(&[("a", 1218.5), ("b", 1218.5)]), &[2440.0], 3.0);
        assert_eq!((boards.len(), boards[0].waste), (1, 0.0));
    }

    #[test]
    fn a_piece_longer_than_every_board_is_not_planned() {
        let boards = optimize_cuts(
            &pieces(&[("long", 4000.0), ("short", 500.0)]),
            &[2440.0, 3050.0, 3660.0],
            0.0,
        );
        assert_eq!(ids(&boards), ["short"]);
    }

    #[test]
    fn the_default_lengths_are_the_home_centres() {
        let plans = plan_cuts(
            &typed(&[("a", PieceType::P2x4, 1000.0)]),
            &[],
            DEFAULT_KERF_MM,
        );
        assert_eq!(plans[0].1.available, DEFAULT_LENGTHS);
        assert_eq!(plans[0].1.board_counts(), [(1820.0, 1)]);
    }

    #[test]
    fn a_type_the_store_leaves_out_keeps_the_defaults() {
        let plans = plan_cuts(
            &typed(&[("a", PieceType::P1x4, 1000.0)]),
            &[(PieceType::P2x4, vec![3050.0])],
            DEFAULT_KERF_MM,
        );
        assert_eq!(plans[0].1.available, DEFAULT_LENGTHS);
    }

    #[test]
    fn oversize_pieces_are_listed_not_planned() {
        let only = [(PieceType::P2x4, vec![2440.0])];
        let plans = plan_cuts(
            &typed(&[
                ("long", PieceType::P2x4, 4000.0),
                ("short", PieceType::P2x4, 500.0),
            ]),
            &only,
            DEFAULT_KERF_MM,
        );
        assert_eq!(plans[0].1.oversize, [("long".to_string(), 4000.0)]);
        assert_eq!(ids(&plans[0].1.boards), ["short"]);
        let all = plan_cuts(
            &typed(&[("long", PieceType::P2x4, 4000.0)]),
            &only,
            DEFAULT_KERF_MM,
        );
        assert!(all[0].1.boards.is_empty() && all[0].1.board_counts().is_empty());
        assert_eq!(
            (all[0].1.total_waste(), all[0].1.waste_percentage()),
            (0.0, 0.0)
        );
    }

    #[test]
    fn totals_add_up_over_the_boards() {
        let only = [(PieceType::P2x4, vec![2440.0])];
        let list = typed(&[
            ("a", PieceType::P2x4, 2000.0),
            ("b", PieceType::P2x4, 2000.0),
            ("c", PieceType::P2x4, 300.0),
        ]);
        let plan = &plan_cuts(&list, &only, DEFAULT_KERF_MM)[0].1;
        assert_eq!(plan.board_counts(), [(2440.0, 2)]);
        assert_eq!(
            plan.total_waste(),
            plan.boards.iter().map(|b| b.waste).sum::<f64>()
        );
        assert!((plan.waste_percentage() - plan.total_waste() / 4880.0 * 100.0).abs() < 1e-9);
    }

    #[test]
    fn lumber_types_come_in_report_order() {
        let list = typed(&[("a", PieceType::P2x4, 500.0), ("b", PieceType::P1x4, 500.0)]);
        let kinds: Vec<PieceType> = plan_cuts(&list, &[], DEFAULT_KERF_MM)
            .into_iter()
            .map(|(k, _)| k)
            .collect();
        assert_eq!(kinds, [PieceType::P1x4, PieceType::P2x4]);
        assert!(plan_cuts(&[], &[], DEFAULT_KERF_MM).is_empty());
    }

    #[test]
    fn a_shorter_board_on_offer_never_makes_the_purchase_longer() {
        // Filling each board greedily over-used 1820mm boards and left a
        // 524mm piece a whole board of its own (the example table)
        let list = pieces(&[("a", 1200.0), ("b", 1200.0), ("c", 1200.0), ("d", 524.0)]);
        let bought = |lengths: &[f64]| {
            optimize_cuts(&list, lengths, 3.0)
                .iter()
                .map(|b| b.length)
                .sum::<f64>()
        };
        let every = bought(&DEFAULT_LENGTHS);
        assert!(every <= bought(&[2440.0, 3050.0, 3650.0]));
        assert!(every <= bought(&[1820.0, 3650.0]));
        assert!(every <= bought(&[3650.0]));
    }

    #[test]
    fn combinations_come_in_itertools_order() {
        assert_eq!(
            combinations(&[1.0, 2.0, 3.0], 2),
            [vec![1.0, 2.0], vec![1.0, 3.0], vec![2.0, 3.0]]
        );
    }

    #[test]
    fn nine_or_more_lengths_try_all_together_and_each_alone() {
        let lengths: Vec<f64> = (1..=9).map(|i| 1000.0 + 100.0 * f64::from(i)).collect();
        assert_eq!(candidates(&lengths).len(), 10);
        assert_eq!(candidates(&lengths[..8]).len(), 255);
    }
}
