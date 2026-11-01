//! Writes a real design's part drawings for a person to look at:
//! `ND_DESIGN=path/to/design.nd cargo test -p nichiyou-daiku-drawing -- --ignored`
//! writes /tmp/part-N.svg for each drilled part.

use std::fs;

#[test]
#[ignore]
fn writes_part_drawings_to_look_at() {
    let path = std::env::var("ND_DESIGN").expect("ND_DESIGN names the .nd to draw");
    let source = fs::read_to_string(&path).expect("a readable .nd");
    for part in 0.. {
        match nichiyou_daiku_drawing::part_drawing(&source, part) {
            Ok(drawing) => fs::write(format!("/tmp/part-{part}.svg"), drawing.svg).unwrap(),
            Err(error) if error.starts_with("There is no part") => break,
            Err(_) => continue,
        }
    }
}
