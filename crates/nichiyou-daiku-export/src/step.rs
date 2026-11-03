//! STEP (ISO 10303-21, AP214): each piece a part (PRODUCT) named as the
//! design names it, holding one solid in world mm; the design an assembly
//! of them, each in place (OpenCASCADE reads part names, not solid names).

use crate::solid::{Curve, P3, Solid, Surface};

/// A real with the decimal point STEP requires, to a micrometre.
pub fn real(value: f64) -> String {
    if value.abs() < 5e-7 {
        return "0.".into();
    }
    let text = format!("{value:.6}");
    let text = text.trim_end_matches('0');
    text.to_string()
}

/// A string: quotes doubled, everything outside ASCII as \X2\…\X0\.
pub fn string(text: &str) -> String {
    let mut out = String::from("'");
    let mut wide = String::new();
    let flush = |out: &mut String, wide: &mut String| {
        if !wide.is_empty() {
            out.push_str("\\X2\\");
            out.push_str(wide);
            out.push_str("\\X0\\");
            wide.clear();
        }
    };
    for c in text.chars() {
        if c.is_ascii() && !c.is_ascii_control() {
            flush(&mut out, &mut wide);
            match c {
                '\'' => out.push_str("''"),
                '\\' => out.push_str("\\\\"),
                _ => out.push(c),
            }
        } else {
            let mut units = [0u16; 2];
            for unit in c.encode_utf16(&mut units) {
                wide.push_str(&format!("{unit:04X}"));
            }
        }
    }
    flush(&mut out, &mut wide);
    out.push('\'');
    out
}

struct Writer {
    lines: Vec<String>,
}

impl Writer {
    fn add(&mut self, entity: String) -> usize {
        self.lines.push(entity);
        self.lines.len()
    }

    fn point(&mut self, p: P3) -> usize {
        self.add(format!(
            "CARTESIAN_POINT('',({},{},{}))",
            real(p[0]),
            real(p[1]),
            real(p[2])
        ))
    }

    fn direction(&mut self, d: P3) -> usize {
        self.add(format!(
            "DIRECTION('',({},{},{}))",
            real(d[0]),
            real(d[1]),
            real(d[2])
        ))
    }

    fn placement(&mut self, origin: P3, axis: P3, x: P3) -> usize {
        let (o, a, r) = (self.point(origin), self.direction(axis), self.direction(x));
        self.add(format!("AXIS2_PLACEMENT_3D('',#{o},#{a},#{r})"))
    }
}

fn units(w: &mut Writer) -> usize {
    let length = w.add("( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) )".into());
    let angle = w.add("( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )".into());
    let solid = w.add("( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )".into());
    let uncertainty = w.add(format!(
        "UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),#{length},'distance_accuracy_value','confusion accuracy')"
    ));
    w.add(format!(
        "( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{uncertainty})) \
         GLOBAL_UNIT_ASSIGNED_CONTEXT((#{length},#{angle},#{solid})) \
         REPRESENTATION_CONTEXT('Context #1','3D Context with UNIT and UNCERTAINTY') )"
    ))
}

/// A part's definition (PRODUCT … PRODUCT_DEFINITION) with its shape.
fn product(w: &mut Writer, name: &str, application: usize, representation: usize) -> usize {
    let product_context = w.add(format!("PRODUCT_CONTEXT('',#{application},'mechanical')"));
    let product = w.add(format!(
        "PRODUCT({0},{0},'',(#{product_context}))",
        string(name)
    ));
    w.add(format!(
        "PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,(#{product}))"
    ));
    let formation = w.add(format!("PRODUCT_DEFINITION_FORMATION('','',#{product})"));
    let definition_context = w.add(format!(
        "PRODUCT_DEFINITION_CONTEXT('part definition',#{application},'design')"
    ));
    let definition = w.add(format!(
        "PRODUCT_DEFINITION('design','',#{formation},#{definition_context})"
    ));
    let shape = w.add(format!("PRODUCT_DEFINITION_SHAPE('','',#{definition})"));
    w.add(format!(
        "SHAPE_DEFINITION_REPRESENTATION(#{shape},#{representation})"
    ));
    definition
}

fn brep(w: &mut Writer, solid: &Solid) -> usize {
    let vertices: Vec<usize> = solid
        .vertices
        .iter()
        .map(|&p| {
            let point = w.point(p);
            w.add(format!("VERTEX_POINT('',#{point})"))
        })
        .collect();
    let edges: Vec<usize> = solid
        .edges
        .iter()
        .map(|edge| {
            let curve = match edge.curve {
                Curve::Line { origin, direction } => {
                    let (o, d) = (w.point(origin), w.direction(direction));
                    let vector = w.add(format!("VECTOR('',#{d},1.)"));
                    w.add(format!("LINE('',#{o},#{vector})"))
                }
                Curve::Circle {
                    centre,
                    axis,
                    x,
                    radius,
                    ..
                } => {
                    let place = w.placement(centre, axis, x);
                    w.add(format!("CIRCLE('',#{place},{})", real(radius)))
                }
            };
            w.add(format!(
                "EDGE_CURVE('',#{},#{},#{curve},.T.)",
                vertices[edge.start], vertices[edge.end]
            ))
        })
        .collect();
    let faces: Vec<usize> = solid
        .faces
        .iter()
        .map(|face| {
            let bounds: Vec<String> = face
                .loops
                .iter()
                .enumerate()
                .map(|(k, uses)| {
                    let oriented: Vec<String> = uses
                        .iter()
                        .map(|&(edge, along)| {
                            let id = w.add(format!(
                                "ORIENTED_EDGE('',*,*,#{},{})",
                                edges[edge],
                                if along { ".T." } else { ".F." }
                            ));
                            format!("#{id}")
                        })
                        .collect();
                    let edge_loop = w.add(format!("EDGE_LOOP('',({}))", oriented.join(",")));
                    let kind = if k == 0 {
                        "FACE_OUTER_BOUND"
                    } else {
                        "FACE_BOUND"
                    };
                    format!("#{}", w.add(format!("{kind}('',#{edge_loop},.T.)")))
                })
                .collect();
            let surface = match face.surface {
                Surface::Plane { origin, normal, x } => {
                    let place = w.placement(origin, normal, x);
                    w.add(format!("PLANE('',#{place})"))
                }
                Surface::Cone {
                    origin,
                    axis,
                    x,
                    radius,
                    slope,
                } if slope.abs() < 1e-12 => {
                    let place = w.placement(origin, axis, x);
                    w.add(format!("CYLINDRICAL_SURFACE('',#{place},{})", real(radius)))
                }
                Surface::Cone {
                    origin,
                    axis,
                    x,
                    radius,
                    slope,
                } => {
                    // STEP's cones widen along their axis: one that narrows turns round
                    let axis = if slope > 0.0 { axis } else { axis.map(|v| -v) };
                    let place = w.placement(origin, axis, x);
                    w.add(format!(
                        "CONICAL_SURFACE('',#{place},{},{})",
                        real(radius),
                        real(slope.abs().atan())
                    ))
                }
            };
            w.add(format!(
                "ADVANCED_FACE('',({}),#{surface},{})",
                bounds.join(","),
                if face.same_sense { ".T." } else { ".F." }
            ))
        })
        .collect();
    let list: Vec<String> = faces.iter().map(|f| format!("#{f}")).collect();
    let shell = w.add(format!("CLOSED_SHELL('',({}))", list.join(",")));
    w.add(format!(
        "MANIFOLD_SOLID_BREP({},#{shell})",
        string(&solid.name)
    ))
}

pub fn step(solids: &[Solid], title: &str, timestamp: &str, version: &str) -> String {
    let mut w = Writer { lines: Vec::new() };
    let application =
        w.add("APPLICATION_CONTEXT('core data for automotive mechanical design processes')".into());
    w.add(format!(
        "APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#{application})"
    ));
    let context = units(&mut w);
    let origin = w.placement([0.0; 3], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]);
    // Every part in place: one placement in the assembly for each
    let places: Vec<usize> = solids
        .iter()
        .map(|_| w.placement([0.0; 3], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]))
        .collect();
    let items: Vec<String> = std::iter::once(origin)
        .chain(places.iter().copied())
        .map(|i| format!("#{i}"))
        .collect();
    let assembly_shape = w.add(format!(
        "SHAPE_REPRESENTATION('',({}),#{context})",
        items.join(",")
    ));
    let assembly = product(&mut w, title, application, assembly_shape);
    for (k, solid) in solids.iter().enumerate() {
        let body = brep(&mut w, solid);
        let shape = w.add(format!(
            "ADVANCED_BREP_SHAPE_REPRESENTATION('',(#{origin},#{body}),#{context})"
        ));
        let part = product(&mut w, &solid.name, application, shape);
        let usage = w.add(format!(
            "NEXT_ASSEMBLY_USAGE_OCCURRENCE('{}',{},'',#{assembly},#{part},$)",
            k + 1,
            string(&solid.name)
        ));
        let placement = w.add(format!(
            "PRODUCT_DEFINITION_SHAPE('Placement','Placement of an item',#{usage})"
        ));
        let transformation = w.add(format!(
            "ITEM_DEFINED_TRANSFORMATION('','',#{origin},#{})",
            places[k]
        ));
        let relationship = w.add(format!(
            "( REPRESENTATION_RELATIONSHIP('','',#{shape},#{assembly_shape}) \
             REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#{transformation}) \
             SHAPE_REPRESENTATION_RELATIONSHIP() )"
        ));
        w.add(format!(
            "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION(#{relationship},#{placement})"
        ));
    }
    let mut out = String::from("ISO-10303-21;\nHEADER;\n");
    out.push_str("FILE_DESCRIPTION(('nichiyou-daiku model'),'2;1');\n");
    let system = string(&format!("nichiyou-daiku {version}"));
    out.push_str(&format!(
        "FILE_NAME({},{},(''),(''),{system},{system},'');\n",
        string(title),
        string(timestamp)
    ));
    out.push_str("FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\nENDSEC;\nDATA;\n");
    for (k, line) in w.lines.iter().enumerate() {
        out.push_str(&format!("#{} = {line};\n", k + 1));
    }
    out.push_str("ENDSEC;\nEND-ISO-10303-21;\n");
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bore::{Bore, Span};
    use crate::solid::piece_solid;
    use nichiyou_daiku_core::placement::Pose;

    fn still() -> Pose {
        Pose {
            rotation: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            translation: [0.0; 3],
        }
    }

    fn two() -> Vec<crate::solid::Solid> {
        let hole = Bore {
            axis: 1,
            at: [44.5, 100.0],
            cavities: vec![vec![Span {
                t0: 0.0,
                t1: 15.0,
                r0: 4.0,
                r1: 4.0,
            }]],
        };
        vec![
            piece_solid("leg_fl", [89.0, 38.0, 400.0], &[hole], &still()),
            piece_solid("rail", [89.0, 38.0, 300.0], &[], &still()),
        ]
    }

    #[test]
    fn a_step_file_has_its_parts_named() {
        let text = step(&two(), "wagon.nd", "2026-11-03T12:00:00", "0.2.0");
        assert!(text.starts_with("ISO-10303-21;\nHEADER;\n"));
        assert!(text.contains("FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));"));
        assert!(text.contains("PRODUCT('leg_fl','leg_fl','',"));
        assert!(text.contains("PRODUCT('rail','rail','',"));
        assert_eq!(text.matches("MANIFOLD_SOLID_BREP(").count(), 2);
        assert_eq!(text.matches("NEXT_ASSEMBLY_USAGE_OCCURRENCE(").count(), 2);
        assert!(text.contains("CYLINDRICAL_SURFACE("));
        assert!(text.trim_end().ends_with("END-ISO-10303-21;"));
    }

    #[test]
    fn every_reference_is_to_an_entity() {
        let text = step(&two(), "wagon.nd", "2026-11-03T12:00:00", "0.2.0");
        let defined: std::collections::HashSet<&str> = text
            .lines()
            .filter_map(|l| l.split_once(" = ").map(|(id, _)| id))
            .collect();
        for line in text.lines().filter(|l| l.contains(" = ")) {
            let body = line.split_once(" = ").unwrap().1;
            for part in body.split(['(', ')', ',']) {
                let part = part.trim();
                if part.starts_with('#') {
                    assert!(defined.contains(part), "{part} in {line}");
                }
            }
        }
    }

    #[test]
    fn reals_always_carry_a_point() {
        assert_eq!(real(0.0), "0.");
        assert_eq!(real(3.0), "3.");
        assert_eq!(real(-12.5), "-12.5");
        assert_eq!(real(1e-7), "0.");
        assert_eq!(real(0.123456789), "0.123457");
    }

    #[test]
    fn strings_are_escaped_as_the_standard_says() {
        assert_eq!(string("it's"), "'it''s'");
        // Outside ASCII: \X2\ and four hex digits per UTF-16 unit
        assert_eq!(string("ワゴン.nd"), "'\\X2\\30EF30B430F3\\X0\\.nd'");
    }
}
