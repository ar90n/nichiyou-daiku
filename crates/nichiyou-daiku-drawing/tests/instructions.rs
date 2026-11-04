//! steps.md for every corpus case that assembles, against NAME.steps.md.

use std::path::Path;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::steps::plan_steps;
use nichiyou_daiku_drawing::instructions::{image_name, steps_markdown};

#[path = "../../nichiyou-daiku-core/tests/common/mod.rs"]
mod common;

const CORPUS: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../nichiyou-daiku-core/tests/corpus"
);

#[test]
fn image_names_are_wide_enough_for_every_number() {
    assert_eq!(image_name("part", 3, 9), "part-03.png");
    assert_eq!(image_name("step", 7, 120), "step-007.png");
}

fn steps_md(source: &str) -> Option<String> {
    let model = nichiyou_daiku_core::dsl::parse(source).ok()?;
    let assembly = Assembly::of(model).ok()?;
    Some(steps_markdown(&assembly, &plan_steps(&assembly), "case"))
}

#[test]
fn steps_md_matches_its_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in common::corpus(Path::new(CORPUS)) {
        let got = steps_md(&source);
        checked += usize::from(got.is_some());
        let path = Path::new(CORPUS).join(format!("{name}.steps.md"));
        if let Err(error) = common::check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= 600, "only {checked} cases assemble");
    common::assert_none(&failures, checked);
}
