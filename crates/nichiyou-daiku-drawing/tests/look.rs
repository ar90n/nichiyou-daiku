//! Writes a real design's drawings for a person to look at:
//! `ND_DESIGN=path/to/design.nd cargo test -p nichiyou-daiku-drawing -- --ignored`
//! writes /tmp/part-N.svg for each drilled part and /tmp/step-N.svg for each
//! step.

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
