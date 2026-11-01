//! The fasteners a design uses, counted by kind and size (resources.py:
//! count_hardware).

use crate::assembly::Assembly;
use crate::connection::ConnectionType;
use crate::presets::ScrewType;
use crate::pyfmt::format_mm;

/// Dowels or screws of one kind and size, and how many the design uses.
#[derive(Clone, Debug, PartialEq)]
pub struct HardwareItem {
    pub name: String,
    pub count: usize,
}

/// Sort order (dowels, then screws by type), diameter, length and name.
type Key = (u8, u8, f64, f64, &'static str);

/// A size at the 0.1mm the list prints, so sizes that print the same count
/// together (Python's round(value, 1)).
pub(crate) fn tenth(value: f64) -> f64 {
    format!("{value:.1}").parse::<f64>().expect("a number") + 0.0
}

/// Count the fasteners laid out: dowels first, then slim, coarse and untyped
/// screws, each by diameter and length. With `connections`, only theirs.
pub fn count_hardware(
    assembly: &Assembly,
    connections: Option<&[(String, String)]>,
) -> Vec<HardwareItem> {
    let mut counts: Vec<(Key, usize)> = Vec::new();
    for fastener in &assembly.fasteners {
        let wanted = |(base, target): &(String, String)| {
            *base == fastener.base_id && *target == fastener.target_id
        };
        if connections.is_some_and(|only| !only.iter().any(wanted)) {
            continue;
        }
        let connection = assembly
            .model
            .connections
            .iter()
            .find(|c| c.base_id() == fastener.base_id && c.target_id() == fastener.target_id)
            .expect("a fastener belongs to a connection");
        let key: Key = match connection.kind {
            ConnectionType::Dowel { radius, depth } => {
                (0, 0, tenth(2.0 * radius), tenth(depth), "Dowel")
            }
            ConnectionType::Screw {
                diameter,
                length,
                screw_type,
            } => {
                let (order, name) = match screw_type {
                    Some(ScrewType::Slim) => (0, "Slim screw"),
                    Some(ScrewType::Coarse) => (1, "Coarse screw"),
                    None => (2, "Screw"),
                };
                (1, order, tenth(diameter), tenth(length), name)
            }
            ConnectionType::Vanilla => continue,
        };
        match counts.iter_mut().find(|(k, _)| *k == key) {
            Some((_, count)) => *count += 1,
            None => counts.push((key, 1)),
        }
    }
    counts.sort_by(|(a, _), (b, _)| {
        (a.0, a.1)
            .cmp(&(b.0, b.1))
            .then(a.2.total_cmp(&b.2))
            .then(a.3.total_cmp(&b.3))
            .then(a.4.cmp(b.4))
    });
    counts
        .into_iter()
        .map(|((_, _, diameter, length, name), count)| HardwareItem {
            name: format!("{name} {}x{}", format_mm(diameter), format_mm(length)),
            count,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dsl::parse;

    const MIXED: &str = "(post:2x4 =600)\n(rail:2x4 =400)\n(rail_low:2x4 =400)\n(cleat:2x4 =400)\n(shelf:2x4 =400)\n\
        post -[FL<300 BT<0 S(Slim:3.3x50)]- rail\npost -[FL<100 BT<0 S(3.5, 50)]- rail_low\n\
        post -[BT<0 FT<0 S(Coarse:3.8x57)]- cleat\npost -[BL<300 DL<0 D(:8x30)]- shelf\n";

    fn listed(items: Vec<HardwareItem>) -> Vec<(String, usize)> {
        items
            .into_iter()
            .map(|item| (item.name, item.count))
            .collect()
    }

    #[test]
    fn dowels_then_slim_coarse_and_untyped_screws() {
        let assembly = Assembly::of(parse(MIXED).unwrap()).unwrap();
        assert_eq!(
            listed(count_hardware(&assembly, None)),
            [
                ("Dowel 8x30", 2),
                ("Slim screw 3.3x50", 2),
                ("Coarse screw 3.8x57", 2),
                ("Screw 3.5x50", 2)
            ]
            .map(|(name, count)| (name.to_string(), count))
        );
    }

    #[test]
    fn only_the_connections_asked_for() {
        let assembly = Assembly::of(parse(MIXED).unwrap()).unwrap();
        let rail = [("post".to_string(), "rail".to_string())];
        assert_eq!(
            listed(count_hardware(&assembly, Some(&rail))),
            [("Slim screw 3.3x50".to_string(), 2)]
        );
        assert_eq!(listed(count_hardware(&assembly, Some(&[]))), []);
    }
}
