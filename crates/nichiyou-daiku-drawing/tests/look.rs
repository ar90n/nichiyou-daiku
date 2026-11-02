//! Writes a real design's drawings for a person to look at:
//! `ND_DESIGN=path/to/design.nd cargo test -p nichiyou-daiku-drawing -- --ignored`
//! writes /tmp/part-N.svg for each drilled part and /tmp/step-N.svg for each
//! step, and /tmp/render.svg, the check image.

use std::fs;

fn source() -> String {
    let path = std::env::var("ND_DESIGN").expect("ND_DESIGN names the .nd to draw");
    fs::read_to_string(&path).expect("a readable .nd")
}

#[test]
#[ignore]
fn writes_part_drawings_to_look_at() {
    let source = source();
    for part in 0.. {
        match nichiyou_daiku_drawing::part_drawing(&source, part) {
            Ok(drawing) => fs::write(format!("/tmp/part-{part}.svg"), drawing.svg).unwrap(),
            Err(error) if error.starts_with("There is no part") => break,
            Err(_) => continue,
        }
    }
}

#[test]
#[ignore]
fn writes_step_drawings_to_look_at() {
    let source = source();
    for step in 1.. {
        match nichiyou_daiku_drawing::step_drawing(&source, step) {
            Ok(drawing) => fs::write(format!("/tmp/step-{step}.svg"), drawing.svg).unwrap(),
            Err(error) if error.starts_with("There is no step") => break,
            Err(error) => panic!("{error}"),
        }
    }
}

#[test]
#[ignore]
fn writes_the_check_image_to_look_at() {
    let source = source();
    let model = nichiyou_daiku_core::dsl::parse(&source).unwrap();
    let assembly = nichiyou_daiku_core::assembly::Assembly::of(model).unwrap();
    let sheet = nichiyou_daiku_drawing::render::render_sheet(&assembly, "look.nd", 1400);
    fs::write("/tmp/render.svg", sheet.svg).unwrap();
}
