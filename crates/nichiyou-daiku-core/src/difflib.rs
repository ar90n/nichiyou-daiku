//! Python's difflib.get_close_matches, for "did you mean" hints.

use std::collections::HashMap;

const CUTOFF: f64 = 0.6;

/// `difflib.get_close_matches(word, possibilities, n=1)`: the best match
/// scoring at least 0.6, the larger string on a tie.
pub fn close_match(word: &str, possibilities: &[&str]) -> Option<String> {
    let b: Vec<char> = word.chars().collect();
    let b2j = index(&b);
    let mut best: Option<(f64, &str)> = None;
    for &x in possibilities {
        let a: Vec<char> = x.chars().collect();
        if real_quick_ratio(&a, &b) < CUTOFF || quick_ratio(&a, &b) < CUTOFF {
            continue;
        }
        let score = ratio(&a, &b, &b2j);
        if score < CUTOFF {
            continue;
        }
        let better = match best {
            None => true,
            Some((top, name)) => score > top || (score == top && x > name),
        };
        if better {
            best = Some((score, x));
        }
    }
    best.map(|(_, x)| x.to_string())
}

fn calculate_ratio(matches: usize, length: usize) -> f64 {
    if length == 0 {
        1.0
    } else {
        2.0 * matches as f64 / length as f64
    }
}

fn real_quick_ratio(a: &[char], b: &[char]) -> f64 {
    calculate_ratio(a.len().min(b.len()), a.len() + b.len())
}

fn quick_ratio(a: &[char], b: &[char]) -> f64 {
    let mut counts: HashMap<char, isize> = HashMap::new();
    for &c in b {
        *counts.entry(c).or_default() += 1;
    }
    let mut matches = 0;
    for c in a {
        let left = counts.entry(*c).or_default();
        if *left > 0 {
            matches += 1;
        }
        *left -= 1;
    }
    calculate_ratio(matches, a.len() + b.len())
}

/// Where each element of b is, without b's "popular" elements, which
/// SequenceMatcher leaves out for sequences of 200 or more.
fn index(b: &[char]) -> HashMap<char, Vec<usize>> {
    let mut b2j: HashMap<char, Vec<usize>> = HashMap::new();
    for (j, &c) in b.iter().enumerate() {
        b2j.entry(c).or_default().push(j);
    }
    if b.len() >= 200 {
        let limit = b.len() / 100 + 1;
        b2j.retain(|_, places| places.len() <= limit);
    }
    b2j
}

fn ratio(a: &[char], b: &[char], b2j: &HashMap<char, Vec<usize>>) -> f64 {
    let mut matches = 0;
    let mut queue = vec![(0, a.len(), 0, b.len())];
    while let Some((alo, ahi, blo, bhi)) = queue.pop() {
        let (i, j, k) = longest_match(a, b, b2j, alo, ahi, blo, bhi);
        if k > 0 {
            matches += k;
            if alo < i && blo < j {
                queue.push((alo, i, blo, j));
            }
            if i + k < ahi && j + k < bhi {
                queue.push((i + k, ahi, j + k, bhi));
            }
        }
    }
    calculate_ratio(matches, a.len() + b.len())
}

/// SequenceMatcher.find_longest_match without junk.
fn longest_match(
    a: &[char],
    b: &[char],
    b2j: &HashMap<char, Vec<usize>>,
    alo: usize,
    ahi: usize,
    blo: usize,
    bhi: usize,
) -> (usize, usize, usize) {
    let (mut besti, mut bestj, mut bestsize) = (alo, blo, 0);
    let mut j2len: HashMap<usize, usize> = HashMap::new();
    for (i, item) in a.iter().enumerate().take(ahi).skip(alo) {
        let mut next: HashMap<usize, usize> = HashMap::new();
        for &j in b2j.get(item).map(Vec::as_slice).unwrap_or(&[]) {
            if j < blo {
                continue;
            }
            if j >= bhi {
                break;
            }
            let k = j
                .checked_sub(1)
                .and_then(|p| j2len.get(&p))
                .copied()
                .unwrap_or(0)
                + 1;
            next.insert(j, k);
            if k > bestsize {
                (besti, bestj, bestsize) = (i + 1 - k, j + 1 - k, k);
            }
        }
        j2len = next;
    }
    while besti > alo && bestj > blo && a[besti - 1] == b[bestj - 1] {
        (besti, bestj, bestsize) = (besti - 1, bestj - 1, bestsize + 1);
    }
    while besti + bestsize < ahi
        && bestj + bestsize < bhi
        && a[besti + bestsize] == b[bestj + bestsize]
    {
        bestsize += 1;
    }
    (besti, bestj, bestsize)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_difflib() {
        // Python: difflib.get_close_matches(word, possibilities, n=1)
        assert_eq!(close_match("lge", &["leg", "apron"]), Some("leg".into()));
        assert_eq!(
            close_match("appel", &["ape", "apple", "peach", "puppy"]),
            Some("apple".into())
        );
        assert_eq!(
            close_match("wheel", &["while", "shell", "awhile"]),
            Some("while".into())
        );
        assert_eq!(close_match("xyz", &["leg", "apron"]), None);
    }
}
