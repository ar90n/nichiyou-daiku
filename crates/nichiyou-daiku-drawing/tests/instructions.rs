//! steps.md as the Python version writes it (NAME.steps.md, written by
//! tools/make_goldens.py --cli), from the holes in the Python version's form.

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

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

#[test]
fn steps_md_says_what_the_python_version_says() {
    let mut paths: Vec<PathBuf> = fs::read_dir(CORPUS)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.extension().is_some_and(|e| e == "nd"))
        .collect();
    paths.sort();
    let (mut checked, mut differ) = (0, Vec::new());
    for path in paths {
        let Ok(want) = fs::read_to_string(path.with_extension("steps.md")) else {
            continue;
        };
        let model = nichiyou_daiku_core::dsl::parse(&fs::read_to_string(&path).unwrap()).unwrap();
        let mut assembly = Assembly::of(model).unwrap();
        common::python_holes(&mut assembly);
        let got = steps_markdown(&assembly, &plan_steps(&assembly), "case");
        let want = common::rename_uuids(&want, &mut HashMap::new());
        let got = common::rename_uuids(&got, &mut HashMap::new());
        if want != got {
            differ.push(format!(
                "{}\n--- python\n{want}\n--- rust\n{got}",
                path.display()
            ));
        }
        checked += 1;
    }
    assert!(
        checked >= 600,
        "only {checked} cases have steps.md: run tools/make_goldens.py --cli"
    );
    assert!(
        differ.is_empty(),
        "{} of {checked} differ:\n{}",
        differ.len(),
        differ[..differ.len().min(2)].join("\n")
    );
}
