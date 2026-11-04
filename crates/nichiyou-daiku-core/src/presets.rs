//! Dowel and screw sizes sold as presets.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ScrewType {
    Slim,
    Coarse,
}

impl ScrewType {
    pub fn as_str(self) -> &'static str {
        match self {
            ScrewType::Slim => "slim",
            ScrewType::Coarse => "coarse",
        }
    }
}

/// Diameter and length in mm.
pub const DOWELS: [(f64, f64); 8] = [
    (6.0, 25.0),
    (6.0, 30.0),
    (8.0, 25.0),
    (8.0, 30.0),
    (8.0, 40.0),
    (10.0, 30.0),
    (10.0, 40.0),
    (12.0, 40.0),
];
pub const SLIM_SCREWS: [(f64, f64); 12] = [
    (3.3, 25.0),
    (3.3, 30.0),
    (3.3, 35.0),
    (3.3, 40.0),
    (3.3, 45.0),
    (3.3, 50.0),
    (3.8, 55.0),
    (3.8, 60.0),
    (3.8, 65.0),
    (3.8, 70.0),
    (3.8, 75.0),
    (4.2, 90.0),
];
pub const COARSE_SCREWS: [(f64, f64); 12] = [
    (3.8, 25.0),
    (3.8, 30.0),
    (3.8, 35.0),
    (3.8, 40.0),
    (3.8, 45.0),
    (3.8, 50.0),
    (3.8, 57.0),
    (4.2, 65.0),
    (4.2, 75.0),
    (4.5, 90.0),
    (4.5, 100.0),
    (5.2, 120.0),
];

pub fn find_dowel_preset(diameter: f64, length: f64) -> Option<(f64, f64)> {
    DOWELS
        .iter()
        .copied()
        .find(|&(d, l)| d == diameter && l == length)
}

/// `type_name` as written in the DSL: Slim or Coarse.
pub fn find_screw_preset(
    type_name: &str,
    diameter: f64,
    length: f64,
) -> Option<(f64, f64, ScrewType)> {
    let (table, kind) = match type_name {
        "Slim" => (&SLIM_SCREWS, ScrewType::Slim),
        "Coarse" => (&COARSE_SCREWS, ScrewType::Coarse),
        _ => return None,
    };
    table
        .iter()
        .copied()
        .find(|&(d, l)| d == diameter && l == length)
        .map(|(d, l)| (d, l, kind))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn presets_are_found_by_size() {
        assert_eq!(find_dowel_preset(8.0, 30.0), Some((8.0, 30.0)));
        assert_eq!(find_dowel_preset(9.0, 99.0), None);
        assert_eq!(
            find_screw_preset("Slim", 3.8, 65.0),
            Some((3.8, 65.0, ScrewType::Slim))
        );
        assert_eq!(
            find_screw_preset("Coarse", 5.2, 120.0),
            Some((5.2, 120.0, ScrewType::Coarse))
        );
        assert_eq!(find_screw_preset("Slim", 3.0, 100.0), None);
    }
}
