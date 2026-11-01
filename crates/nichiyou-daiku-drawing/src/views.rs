//! The views the CLI draws step images from (views.py): the isometric from
//! -x +y +z, and the views along a world axis.

use crate::solid::Projection;

const ORIGIN: [f64; 3] = [0.0, 0.0, 0.0];

/// The step images' isometric: from -x +y +z, z up.
pub fn isometric() -> Projection {
    Projection::new([-1.0, 1.0, 1.0], ORIGIN)
}

/// The view from the `sign` side of world `axis`: z up, or -y up when it
/// looks along z (the front edge at the bottom, as the CLI's top view).
pub fn axis_view(axis: usize, sign: i32) -> Projection {
    let mut direction = [0.0; 3];
    direction[axis] = f64::from(sign);
    let up = if axis == 2 {
        [0.0, -1.0, 0.0]
    } else {
        [0.0, 0.0, 1.0]
    };
    Projection::looking(direction, up, ORIGIN)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn near(a: (f64, f64), b: (f64, f64)) -> bool {
        (a.0 - b.0).abs() < 1e-9 && (a.1 - b.1).abs() < 1e-9
    }

    #[test]
    fn the_front_view_sees_plus_x_on_the_left_and_the_top_view_the_front_below() {
        assert!(near(axis_view(1, 1).project([1.0, 0.0, 0.0]), (-1.0, 0.0)));
        assert!(near(axis_view(1, 1).project([0.0, 0.0, 1.0]), (0.0, 1.0)));
        assert!(near(axis_view(2, 1).project([0.0, 1.0, 0.0]), (0.0, -1.0)));
        assert!(near(axis_view(0, -1).project([0.0, 1.0, 0.0]), (-1.0, 0.0)));
    }

    #[test]
    fn the_isometric_keeps_z_up() {
        let up = isometric().project([0.0, 0.0, 1.0]);
        assert!(up.0.abs() < 1e-9 && up.1 > 0.0);
    }
}
