//! Writes a design's STEP and STL to check with tools/check_step.py:
//! `ND_DESIGN=path/to/design.nd cargo test -p nichiyou-daiku-export --test look -- --ignored`

#[test]
#[ignore]
fn writes_the_3d_to_check() {
    let path = std::env::var("ND_DESIGN").expect("ND_DESIGN names the .nd");
    let source = std::fs::read_to_string(&path).unwrap();
    let assembly = nichiyou_daiku_core::assembly::Assembly::of(
        nichiyou_daiku_core::dsl::parse(&source).unwrap(),
    )
    .unwrap();
    let made = nichiyou_daiku_export::model(&assembly);
    std::fs::write(
        "/tmp/export.step",
        nichiyou_daiku_export::step::step(&made.solids, "look.nd", "2026-11-03T00:00:00", "0.2.0"),
    )
    .unwrap();
    let meshes: Vec<_> = made
        .solids
        .iter()
        .map(nichiyou_daiku_export::mesh::mesh)
        .collect();
    std::fs::write("/tmp/export.stl", nichiyou_daiku_export::stl::stl(&meshes)).unwrap();
}
