# R6 Python を消して Rust 版を届ける Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 製品の Python のコードを消し、Rust 版の出力を正解にして、インストールのスクリプトとプラグインの入口で Rust 版を利用者に届け、main を第 2 世代にする。

**Architecture:** 正解ファイルは Rust の出力で書き直して完全一致で比べ、`ND_BLESS=1` で書き直す。ドキュメントとプラグインのテストは Rust（`crates/nichiyou-daiku-cli/tests/`）に移す。評価（Python）は CLI の `validate --json` で設計を確かめる。`install.sh` が Releases から落とす処理を持ち、プラグインの入口はそれを読み込んで自分の版だけを使う。最後にタグ・リリース・main の早送りで届ける。

**Tech Stack:** Rust（cargo、clap、serde_json、regex は dev のみ）、POSIX sh、Python 3.13（評価と CI の道具、uv）、Dagger、GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-11-04-r6-python-removal-and-delivery-design.md`

## Global Constraints

- コメントは最小限・英語・Why。エラーメッセージは「何が悪く、どう直すか」を書く。
- CLI の実行ファイルの依存を増やさない（`regex` はテストだけ、`[dev-dependencies]`）。
- `bin/nichiyou-daiku` と `install.sh` は POSIX sh（bash の機能を使わない）。テストは `sh` で動かす。
- リリースの置き方は R4c のまま: `releases/download/v<版>/nichiyou-daiku-<版>-<target>.<tar.gz|zip>` と `SHA256SUMS`。版は `Cargo.toml` の `[workspace.package] version`（`0.2.0`）。
- 正解ファイルの比べ方は完全一致（report の日付だけ置き換え）。`ND_BLESS=1 cargo test` で書き直す。
- 評価の設計の確かめは `nichiyou-daiku validate --json` の出力だけで行う。CLI は `NICHIYOU_DAIKU_BIN`、無ければプラグインの入口。
- opencode は `opencode-go/…` だけ（最終レビューの deepseek は `opencode-go/deepseek-v4.1-flash`）。
- コミットは計画のコミットの手順で。タグ・リリース・push は Task 9 で、その都度ユーザーに頼んでから。
- コミット前に `make check`、`next` に入れる前に `make ci-local`。

## Review Focus

1. `install.sh` を `curl … | sh` や `sh -s -- --to DIR` でパイプから動かしたとき、オプションを読んで入れる。入口が読み込んだときは関数を定めるだけで何もしない（Task 5 の `piped_into_sh_it_installs` と入口のテスト）。
2. 古い Python 版が PATH にある人がプラグインを更新しても、プラグインは自分の版を動かす（Task 5 の `a_cli_on_the_path_is_not_used`）。
3. 正解ファイルを 2 回書き直しても同じバイトになる（並びや浮動小数の揺れが無い。Task 1 の Step 7）。
4. cargo の無い機械で評価を始めると、何も使う前に止まり、Rust を入れるよう言う（Task 4 の `test_an_evaluation_without_cargo_stops_before_spending`）。
5. 読めない設計の `validate --json` は `connections` が空、`steps` が 0（Task 3 の `a_report_that_stops_has_no_connections_and_no_steps`）。

## 仕様からの細かい違い（計画の判断）

- 評価の仕組みのテスト（`tests/evals/`、約 1,600 行）は消さずに `evals/tests/` に移し、`make check` と CI で動かす。仕様の「`tests/` を消す」は Python 版の本体のテストのこと。評価を Python で残す以上、そのテストも残す。
- `install.sh` のテストは `plugin.rs` ではなく `install.rs` に置く（入口のテスト `plugin_bin.rs` と偽のリリースの道具を共有する）。
- Task 2 で `Makefile` の Python のカバレッジの閾値（90%）を外す。docs のテストを Rust に移すと、消える前の Python 本体のカバレッジが下がりうるため。本体は Task 6 で消える。
- 入口が CLI を落とせないときの案内は「PATH に置く」から「キャッシュの場所に置く」に変える。入口が PATH を見なくなったため（決定 3 の帰結）。

---

### Task 1: 正解ファイルを Rust の出力にする

**Files:**
- Modify: `crates/nichiyou-daiku-core/tests/common/mod.rs`（全体を書き換え）
- Modify: `crates/nichiyou-daiku-core/tests/corpus.rs`・`steps.rs`・`parts.rs`・`chains.rs`
- Modify: `crates/nichiyou-daiku-cli/tests/golden.rs`
- Modify: `crates/nichiyou-daiku-drawing/tests/render.rs`・`instructions.rs`
- Modify: `crates/nichiyou-daiku-export/tests/solids.rs`
- Delete: `crates/nichiyou-daiku-core/tests/corpus/known_differences.toml`、`tools/make_goldens.py`、`tools/capture_dsl.py`
- Rewrite（生成）: `crates/nichiyou-daiku-core/tests/corpus/*.{validate,holes,steps,parts,chains,render,solids}.json`・`*.steps.md`・`*.cli-*.txt`、`crates/nichiyou-daiku-cli/tests/cli/*.txt`

**Interfaces:**
- Produces（`common/mod.rs`、各テストクレートが `#[path]` で読む）:
  - `pub fn blessing() -> bool`
  - `pub fn pretty(value: &serde_json::Value) -> String`（`to_string_pretty` ＋改行）
  - `pub fn check_golden(path: &Path, got: Option<&str>) -> Result<(), String>`
  - `pub fn corpus(dir: &Path) -> Vec<(String, String)>`（名前と .nd の中身、名前順）
  - `pub fn shown(name: &str) -> bool`（`example-`・`doc-` の例）
  - `pub fn assert_none(failures: &[String], checked: usize)`
- 正解ファイルの決まり（どの例に作るか）:
  - `validate.json`・`cli-validate.txt`・`cli-report.txt`: すべての例
  - `holes.json`・`steps.json`・`parts.json`・`chains.json`・`steps.md`: 組み立てられる例（`nichiyou_daiku_core::holes(source)` が `Some`）
  - `render.json`・`solids.json`: `shown(name)` の例
  - `cli-validate-json.txt`: `example-` の例

- [ ] **Step 1: 落ちるテストを書く**

`crates/nichiyou-daiku-core/tests/corpus.rs` の `use` の後に足す:
```rust
#[test]
fn a_golden_file_that_differs_names_its_first_different_line() {
    if common::blessing() {
        return;
    }
    let path = std::env::temp_dir().join(format!("nd-golden-{}.txt", std::process::id()));
    std::fs::write(&path, "a\nb\nc\n").unwrap();
    let error = common::check_golden(&path, Some("a\nB\nc\n")).unwrap_err();
    assert!(
        error.ends_with("differs at line 2:\n  golden: b\n  got:    B"),
        "{error}"
    );
    assert!(common::check_golden(&path, Some("a\nb\nc\n")).is_ok());
    let left = common::check_golden(&path, None).unwrap_err();
    assert!(left.contains("run with ND_BLESS=1 to remove it"), "{left}");
    std::fs::remove_file(&path).unwrap();
    let missing = common::check_golden(&path, Some("x")).unwrap_err();
    assert!(missing.contains("is missing; run with ND_BLESS=1"), "{missing}");
    assert!(common::check_golden(&path, None).is_ok());
}
```

- [ ] **Step 2: 落ちるのを確かめる**

Run: `cargo test -p nichiyou-daiku-core --test corpus 2>&1 | grep -E "^error" | sort | uniq -c`
Expected: `cannot find function \`check_golden\`` などのコンパイルエラー

- [ ] **Step 3: 共通の道具を書き換える**

`crates/nichiyou-daiku-core/tests/common/mod.rs` を全部これにする:
```rust
//! Helpers the golden-file tests share. The golden files hold the Rust
//! version's own output: `ND_BLESS=1 cargo test` writes what the tests get
//! over them, to review in the diff before committing.

// Each test crate uses a part of these
#![allow(dead_code)]

use std::fs;
use std::path::{Path, PathBuf};

use serde_json::Value;

pub fn blessing() -> bool {
    std::env::var_os("ND_BLESS").is_some()
}

/// JSON as the golden files keep it: indented, with a final newline.
pub fn pretty(value: &Value) -> String {
    serde_json::to_string_pretty(value).unwrap() + "\n"
}

/// Compares what a test got with the golden file at `path`, None meaning
/// the case has no such file; when blessing, writes or removes it instead.
pub fn check_golden(path: &Path, got: Option<&str>) -> Result<(), String> {
    if blessing() {
        match got {
            Some(text) => fs::write(path, text).unwrap(),
            None if path.exists() => fs::remove_file(path).unwrap(),
            None => {}
        }
        return Ok(());
    }
    let name = path.display();
    match (fs::read_to_string(path).ok(), got) {
        (None, None) => Ok(()),
        (Some(_), None) => Err(format!(
            "{name} belongs to no output any more; run with ND_BLESS=1 to remove it"
        )),
        (None, Some(_)) => Err(format!(
            "{name} is missing; run with ND_BLESS=1 to write it"
        )),
        (Some(want), Some(got)) if want == got => Ok(()),
        (Some(want), Some(got)) => {
            let same = want
                .lines()
                .zip(got.lines())
                .take_while(|(w, g)| w == g)
                .count();
            Err(format!(
                "{name} differs at line {}:\n  golden: {}\n  got:    {}",
                same + 1,
                want.lines().nth(same).unwrap_or("<end>"),
                got.lines().nth(same).unwrap_or("<end>")
            ))
        }
    }
}

/// The corpus's designs (`NAME.nd` in `dir`): their names and sources, by name.
pub fn corpus(dir: &Path) -> Vec<(String, String)> {
    let mut paths: Vec<PathBuf> = fs::read_dir(dir)
        .unwrap()
        .map(|entry| entry.unwrap().path())
        .filter(|path| path.extension().is_some_and(|ext| ext == "nd"))
        .collect();
    paths.sort();
    paths
        .into_iter()
        .map(|path| {
            (
                path.file_stem().unwrap().to_string_lossy().into_owned(),
                fs::read_to_string(&path).unwrap(),
            )
        })
        .collect()
}

/// The examples' and the docs' designs, which also get images and solids.
pub fn shown(name: &str) -> bool {
    name.starts_with("example-") || name.starts_with("doc-")
}

/// Fails listing the first differences, if any, of `checked` comparisons.
pub fn assert_none(failures: &[String], checked: usize) {
    assert!(
        failures.is_empty(),
        "{} of {checked} differ (ND_BLESS=1 cargo test rewrites the golden files; review the diff):\n{}",
        failures.len(),
        failures[..failures.len().min(5)].join("\n")
    );
}
```

Run: `cargo test -p nichiyou-daiku-core --test corpus a_golden_file 2>&1 | grep "test result"`
Expected: コンパイルエラー（`corpus.rs` がまだ `normalize`・`split_syntax` を使う）。Step 4 で直す。

- [ ] **Step 4: core のテストを書き換える**

`corpus.rs` の Step 1 のテスト以外を、これに置き換える（`a_report_starts_with_whether_it_is_valid` と皿取りの不変条件のテストは残し、`cases()` を `corpus()` にする）:
```rust
//! The core's reports for every corpus case against the golden files:
//! NAME.validate.json (what validate --json prints) and, for designs that
//! assemble, NAME.holes.json.

use std::path::Path;

mod common;
use common::{assert_none, check_golden, corpus, pretty};

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/corpus");

#[test]
fn reports_match_their_golden_files() {
    let cases = corpus(Path::new(DIR));
    let mut failures = Vec::new();
    for (name, source) in &cases {
        let validate = pretty(&nichiyou_daiku_core::validate(source));
        let holes = nichiyou_daiku_core::holes(source).map(|h| pretty(&h));
        for (suffix, got) in [("validate.json", Some(validate)), ("holes.json", holes)] {
            let path = Path::new(DIR).join(format!("{name}.{suffix}"));
            if let Err(error) = check_golden(&path, got.as_deref()) {
                failures.push(error);
            }
        }
    }
    assert!(cases.len() >= 700, "only {} corpus cases", cases.len());
    assert_none(&failures, cases.len());
}
```
皿取りのテストの doc コメントは `/// Which screws are countersunk: on the head side, and only those without a counterbore.` にする（`python_holes` への言及を消す）。消すテスト: `validate_keys_come_in_the_python_order`（文字の一致が並びも見る）、`corpus_matches_the_python_version`、`a_fuller_expected_list_is_fine_but_a_shorter_one_is_not`、`hints_and_found_tokens_must_match_exactly`、`ids_without_names_are_compared_by_order`。`compare`・`compare_report`・`category`・`known_differences`・`key_order`・`python_form_holes` も消す。`git rm crates/nichiyou-daiku-core/tests/corpus/known_differences.toml`。`Cargo.toml` の dev-dependency `toml` が使われなくなれば消す。

`steps.rs` を全部これにする:
```rust
//! The parts and steps the viewer gets (`view`) for every corpus case that
//! assembles, against NAME.steps.json.

use std::path::Path;

use serde_json::{Map, Value};

mod common;
use common::{assert_none, check_golden, corpus, pretty};

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/corpus");
const KEYS: [&str; 4] = ["parts", "steps", "steps_declared", "steps_hint"];

fn steps(source: &str) -> Option<String> {
    let view = nichiyou_daiku_core::view(source);
    if !view["error"].is_null() {
        return None;
    }
    let picked: Map<String, Value> = KEYS
        .iter()
        .map(|key| (key.to_string(), view[*key].clone()))
        .collect();
    Some(pretty(&Value::Object(picked)))
}

#[test]
fn parts_and_steps_match_their_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in corpus(Path::new(DIR)) {
        let got = steps(&source);
        checked += usize::from(got.is_some());
        let path = Path::new(DIR).join(format!("{name}.steps.json"));
        if let Err(error) = check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= 600, "only {checked} cases assemble");
    assert_none(&failures, checked);
}
```

`parts.rs`: `facts` を `fn facts(source: &str) -> Option<Value>` にし、`parse(source).ok()?`・`Assembly::of(model).ok()?`、`common::python_holes` の行を消し、最後を `Some(json!({"parts": parts}))` にする。`one_line` の doc は `/// The title on one line.`。テストをこれにする:
```rust
#[test]
fn part_drawings_match_their_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in corpus(Path::new(DIR)) {
        let got = facts(&source).map(|f| pretty(&f));
        checked += usize::from(got.is_some());
        let path = Path::new(DIR).join(format!("{name}.parts.json"));
        if let Err(error) = check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= 600, "only {checked} cases assemble");
    assert_none(&failures, checked);
}
```
（`use common::{assert_none, check_golden, corpus, pretty};`、`HashMap`・`normalize`・`PathBuf`・`fs` の use を消す。モジュールの doc は `//! The part drawings' facts for every corpus case that assembles, against NAME.parts.json.`）

`chains.rs`: `chains_json` はそのまま。テストをこれにする:
```rust
#[path = "common/mod.rs"]
mod common;
use common::{assert_none, check_golden, corpus, pretty};

fn chains(source: &str) -> Option<String> {
    let model = nichiyou_daiku_core::dsl::parse(source).ok()?;
    let assembly = Assembly::of(model).ok()?;
    Some(pretty(&chains_json(&assembly)))
}

#[test]
fn drawing_chains_match_their_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in corpus(Path::new(DIR)) {
        let got = chains(&source);
        checked += usize::from(got.is_some());
        let path = Path::new(DIR).join(format!("{name}.chains.json"));
        if let Err(error) = check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= 600, "only {checked} cases assemble");
    assert_none(&failures, checked);
}
```
（`chains.rs` は今 `mod common;` を持たないので足す。`corpus.rs` などと同じ `mod common;` で読めるならそれでよい。モジュールの doc は `//! The technical drawing's chain dimensions for every corpus case that assembles, against NAME.chains.json.`）

- [ ] **Step 5: ほかのクレートのテストを書き換える**

`crates/nichiyou-daiku-cli/tests/golden.rs`: `same_output`・`toml_reason_hidden`・`golden`・`blessing`・`corpus_cases` を消し、`check_corpus` とテストをこれにする（`run`・`fixed_date`・`OptionCase`・`a_report_written_to_a_file_is_the_one_printed` は残す）:
```rust
//! What the CLI prints against the golden files: validate, validate --json
//! and report for every corpus case, and the option cases in tests/cli.

/// Runs `args` on the corpus cases `wanted` picks and compares the output
/// with NAME.<suffix>.
fn check_corpus(args: &[&str], suffix: &str, wanted: impl Fn(&str) -> bool) {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in common::corpus(Path::new(CORPUS)) {
        let got = wanted(&name).then(|| run(args, &source, Path::new(CORPUS)));
        checked += usize::from(got.is_some());
        let path = Path::new(CORPUS).join(format!("{name}.{suffix}"));
        if let Err(error) = common::check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    common::assert_none(&failures, checked);
}

#[test]
fn validate_prints_its_golden_files() {
    check_corpus(&["validate", "-"], "cli-validate.txt", |_| true);
}

#[test]
fn validate_json_prints_the_core_s_report() {
    // The core's tests write NAME.validate.json, which may be mid-rewrite
    if common::blessing() {
        return;
    }
    let cases = common::corpus(Path::new(CORPUS));
    let mut failures = Vec::new();
    for (name, source) in &cases {
        let path = Path::new(CORPUS).join(format!("{name}.validate.json"));
        let report = fs::read_to_string(&path).unwrap();
        let valid: serde_json::Value = serde_json::from_str(&report).unwrap();
        let code = if valid["valid"] == true { 0 } else { 1 };
        let want = format!("exit: {code}\n--- stdout\n{report}--- stderr\n");
        let got = run(&["validate", "--json", "-"], source, Path::new(CORPUS));
        if want != got {
            failures.push(format!("{name}:\n{got}"));
        }
    }
    common::assert_none(&failures, cases.len());
}

#[test]
fn validate_json_prints_its_golden_files() {
    check_corpus(&["validate", "--json", "-"], "cli-validate-json.txt", |name| {
        name.starts_with("example-")
    });
}

#[test]
fn report_prints_its_golden_files() {
    check_corpus(&["report", "-"], "cli-report.txt", |_| true);
}

#[test]
fn options_print_their_golden_files() {
    let cases: Vec<OptionCase> =
        serde_json::from_str(&fs::read_to_string(Path::new(CLI_DIR).join("cases.json")).unwrap())
            .unwrap();
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let mut failures = Vec::new();
    for case in &cases {
        let stdin = match (&case.file, &case.text) {
            (Some(file), _) => fs::read_to_string(root.join(file)).unwrap(),
            (None, Some(text)) => text.clone(),
            (None, None) => String::new(),
        };
        let args: Vec<&str> = case.args.iter().map(String::as_str).collect();
        let got = run(&args, &stdin, Path::new(CLI_DIR));
        let path = Path::new(CLI_DIR).join(format!("{}.txt", case.name));
        if let Err(error) = common::check_golden(&path, Some(&got)) {
            failures.push(error);
        }
    }
    common::assert_none(&failures, cases.len());
}
```
`a_report_written_to_a_file_is_the_one_printed` のコメント `// Python's write_text adds no final newline; click.echo does` は `// The file has no final newline; printing adds one` にする。

`crates/nichiyou-daiku-drawing/tests/render.rs` を全部これにする:
```rust
//! The check image's labels and note for the examples' and the docs'
//! designs, against NAME.render.json.

use std::path::Path;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_drawing::render::render_sheet;
use serde_json::{Value, json};

#[path = "../../nichiyou-daiku-core/tests/common/mod.rs"]
mod common;

const CORPUS: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../nichiyou-daiku-core/tests/corpus"
);

fn render(source: &str) -> String {
    let assembly = Assembly::of(nichiyou_daiku_core::dsl::parse(source).unwrap()).unwrap();
    let sheet = render_sheet(&assembly, "case.nd", 1400);
    let labels: serde_json::Map<String, Value> = sheet
        .labels
        .iter()
        .filter(|(_, ids)| !ids.is_empty())
        .map(|(caption, ids)| (caption.to_string(), json!(ids)))
        .collect();
    common::pretty(&json!({"labels": labels, "unlabelled": sheet.unlabelled, "note": sheet.note}))
}

#[test]
fn render_labels_and_notes_match_their_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in common::corpus(Path::new(CORPUS)) {
        let got = common::shown(&name).then(|| render(&source));
        checked += usize::from(got.is_some());
        let path = Path::new(CORPUS).join(format!("{name}.render.json"));
        if let Err(error) = common::check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= 20, "only {checked} shown cases");
    common::assert_none(&failures, checked);
}
```

`crates/nichiyou-daiku-drawing/tests/instructions.rs`: `image_names_are_wide_enough_for_every_number` は残し、もう 1 つをこれにする:
```rust
//! steps.md for every corpus case that assembles, against NAME.steps.md.

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
```

`crates/nichiyou-daiku-export/tests/solids.rs`: モジュールの doc を `//! Every piece of every design in the corpus is a closed solid, and the examples' volumes and boxes match NAME.solids.json.` にし、`solids_match_the_python_version` をこれに替える:
```rust
#[test]
fn solids_match_their_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (path, assembly) in designs() {
        let name = path.file_stem().unwrap().to_string_lossy().into_owned();
        let got = common::shown(&name).then(|| {
            let mut pieces = serde_json::Map::new();
            for solid in &model(&assembly).solids {
                let extreme = |i: usize, f: fn(f64, f64) -> f64, start: f64| {
                    round_mm(solid.vertices.iter().map(|v| v[i]).fold(start, f))
                };
                pieces.insert(
                    solid.name.clone(),
                    json!({
                        // To a thousandth of a mm³: the last bits of a sum vary between machines
                        "volume": (solid.volume * 1000.0).round() / 1000.0,
                        "min": (0..3).map(|i| extreme(i, f64::min, f64::MAX)).collect::<Vec<_>>(),
                        "max": (0..3).map(|i| extreme(i, f64::max, f64::MIN)).collect::<Vec<_>>(),
                    }),
                );
            }
            common::pretty(&json!({ "pieces": pieces }))
        });
        checked += usize::from(got.is_some());
        if let Err(error) = common::check_golden(&path.with_extension("solids.json"), got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= 20, "only {checked} shown cases");
    common::assert_none(&failures, checked);
}
```
（`HashMap`・`Value` の use が要らなくなれば消す。）

`git rm tools/make_goldens.py tools/capture_dsl.py`

Run: `cargo test 2>&1 | grep -E "^error|test result: FAILED|differs at line" | head`
Expected: コンパイルは通り、正解ファイルの比べ方のテストが `differs at line 1` などで落ちる（正解ファイルがまだ Python の 1 行の形）。Step 1 のテストは通る。

- [ ] **Step 6: 正解ファイルを書き直す**

Run: `ND_BLESS=1 cargo test -q 2>&1 | grep -E "test result" | grep -c FAILED; cargo test -q 2>&1 | grep -E "test result" | grep -c FAILED`
Expected: どちらも `0`（2 回目は書き直した正解ファイルとの比べ。すべて通る）

- [ ] **Step 7: 書き直しが決まった形か確かめる（Review Focus 3）**

Run: `git add -A crates && ND_BLESS=1 cargo test -q >/dev/null 2>&1; git status --short crates | wc -l`
Expected: `0`（2 回目の書き直しで何も変わらない）

Run: `git diff --cached --stat | tail -1; git diff --cached crates/nichiyou-daiku-core/tests/corpus/example-326a974702.validate.json | head -30`
Expected: 約 8,000 ファイルの変更。例の `validate.json` は値が同じで、形（字下げ）だけが変わっている。`holes.json` には皿取り（`countersink`）が入る例がある（`git diff --cached --stat -- '*.holes.json' | tail -1`）。

- [ ] **Step 8: コミットする**

```bash
make check && git add -A crates tools && git commit -m "test: Make the Rust output the golden files"
```

---

### Task 2: ドキュメントとプラグインのテストを Rust に移す

**Files:**
- Create: `crates/nichiyou-daiku-cli/tests/docs.rs`、`crates/nichiyou-daiku-cli/tests/plugin.rs`
- Modify: `crates/nichiyou-daiku-cli/Cargo.toml`（`[dev-dependencies] regex = "1"`）、`crates/nichiyou-daiku-core/src/presets.rs`（3 つの表を `pub const`）、`crates/nichiyou-daiku-cli/tests/plugin_bin.rs`、`Makefile`（`--cov-fail-under=90` を消す）
- Delete: `tests/test_docs.py`、`tests/test_plugin.py`

**Interfaces:**
- Produces: `nichiyou_daiku_core::presets::{DOWELS, SLIM_SCREWS, COARSE_SCREWS}`（`pub const [(f64, f64); N]`、直径と長さ）
- `plugin_bin.rs` の偽の実行ファイルは引数を `[…]` で囲んで出す（`prebuilt [validate] [t.nd]`）。Task 5 もこの形を使う。

- [ ] **Step 1: 表を公開する**

`presets.rs` の `const DOWELS`・`const SLIM_SCREWS`・`const COARSE_SCREWS` を `pub const` にする（docs.rs がドキュメントの表と比べる）。

- [ ] **Step 2: ドキュメントのテストを書く**

`crates/nichiyou-daiku-cli/Cargo.toml` の `[dev-dependencies]` に `regex = "1"` を足す。`crates/nichiyou-daiku-cli/tests/docs.rs`:
```rust
//! The docs stay true to the code: their .nd examples are sound, their
//! tables are the code's, the links and the paths they name exist, and the
//! CLI reference covers every command.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

use nichiyou_daiku_core::piece::PieceType;
use nichiyou_daiku_core::presets::{COARSE_SCREWS, DOWELS, SLIM_SCREWS};
use nichiyou_daiku_core::pyfmt::format_mm;
use regex::Regex;
use serde_json::Value;

fn root() -> PathBuf {
    Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../.."))
        .canonicalize()
        .unwrap()
}

fn walk(dir: &Path) -> Vec<PathBuf> {
    let mut files = Vec::new();
    for entry in fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            files.extend(walk(&path));
        } else {
            files.push(path);
        }
    }
    files
}

fn with_extension(files: Vec<PathBuf>, ext: &str) -> Vec<PathBuf> {
    files
        .into_iter()
        .filter(|p| p.extension().is_some_and(|e| e == ext))
        .collect()
}

/// The Markdown the tests read: docs/ (not its subfolders), the README and the skills.
fn markdown() -> Vec<PathBuf> {
    let root = root();
    let mut files = with_extension(
        fs::read_dir(root.join("docs"))
            .unwrap()
            .map(|e| e.unwrap().path())
            .collect(),
        "md",
    );
    files.push(root.join("README.md"));
    files.extend(with_extension(walk(&root.join("skills")), "md"));
    files.sort();
    files
}

fn spec() -> String {
    fs::read_to_string(root().join("docs/dsl-specification.md")).unwrap()
}

/// (line, language, body) of each fenced block, indented or not.
fn fences(text: &str) -> Vec<(usize, String, String)> {
    let opening = Regex::new(r"^(\s*)(`{3,}|~{3,})\s*([\w-]*)").unwrap();
    let lines: Vec<&str> = text.split_inclusive('\n').collect();
    let mut blocks = Vec::new();
    let mut i = 0;
    while i < lines.len() {
        let Some(open) = opening.captures(lines[i]) else {
            i += 1;
            continue;
        };
        let indent = open[1].to_string();
        let fence = &open[2];
        let closing = Regex::new(&format!(
            r"^\s*{}{{{},}}\s*$",
            regex::escape(&fence[..1]),
            fence.len()
        ))
        .unwrap();
        let mut body = String::new();
        let mut j = i + 1;
        while j < lines.len() && !closing.is_match(lines[j]) {
            body.push_str(lines[j].strip_prefix(indent.as_str()).unwrap_or(lines[j]));
            j += 1;
        }
        blocks.push((i + 1, open[3].to_string(), body));
        i = j + 1;
    }
    blocks
}

fn nd_blocks() -> Vec<(String, String)> {
    let root = root();
    let mut blocks = Vec::new();
    for path in markdown() {
        let rel = path.strip_prefix(&root).unwrap().display().to_string();
        for (line, language, body) in fences(&fs::read_to_string(&path).unwrap()) {
            if language == "nd" {
                blocks.push((format!("{rel}:{line}"), body));
            }
        }
    }
    blocks
}

/// What makes an example unsound: an error, or contradicting connections,
/// overlaps and fasteners that do not fit (an example may leave pieces
/// unconnected).
fn problems(source: &str) -> Vec<String> {
    let report = nichiyou_daiku_core::validate(source);
    if !report["error"].is_null() {
        return vec![report["error"]["message"].to_string()];
    }
    report["problems"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|p| matches!(p["kind"].as_str(), Some("conflict" | "overlap" | "fastener")))
        .map(|p| p["message"].to_string())
        .collect()
}

fn cli(args: &[&str], dir: &Path) -> Output {
    Command::new(env!("CARGO_BIN_EXE_nichiyou-daiku"))
        .args(args)
        .current_dir(dir)
        .output()
        .unwrap()
}

#[test]
fn every_nd_fence_is_collected() {
    // A parser slip would silently drop examples from the test below
    let opening = Regex::new(r"(?m)^\s*(`{3,}|~{3,})\s*nd\b").unwrap();
    let written: usize = markdown()
        .iter()
        .map(|p| opening.find_iter(&fs::read_to_string(p).unwrap()).count())
        .sum();
    let collected = nd_blocks().len();
    assert!(written > 0 && collected == written, "{collected} of {written}");
}

#[test]
fn nd_examples_in_the_docs_are_sound() {
    let unsound: Vec<String> = nd_blocks()
        .into_iter()
        .filter_map(|(at, source)| {
            let found = problems(&source);
            (!found.is_empty()).then(|| format!("{at}: {found:?}"))
        })
        .collect();
    assert!(unsound.is_empty(), "{unsound:#?}");
}

#[test]
fn example_files_are_sound() {
    let root = root();
    let mut files = with_extension(
        fs::read_dir(root.join("examples/nd_files"))
            .unwrap()
            .map(|e| e.unwrap().path())
            .collect(),
        "nd",
    );
    files.extend(with_extension(walk(&root.join("skills")), "nd"));
    assert!(files.len() >= 6);
    for file in files {
        let found = problems(&fs::read_to_string(&file).unwrap());
        assert!(found.is_empty(), "{}: {found:?}", file.display());
    }
}

/// The text from `heading` up to the next heading of any level below it.
fn section<'a>(text: &'a str, heading: &str) -> &'a str {
    let start = text.find(heading).unwrap_or_else(|| panic!("no {heading}")) + heading.len();
    let rest = &text[start..];
    &rest[..rest.find("\n#").unwrap_or(rest.len())]
}

#[test]
fn the_lumber_table_is_the_code_s() {
    let row = Regex::new(r"(?m)^\| `(\d+x\d+)` \| (\d+) \| (\d+) \|").unwrap();
    let spec = spec();
    let documented: BTreeMap<String, (f64, f64)> = row
        .captures_iter(section(&spec, "### Lumber Types"))
        .map(|c| (c[1].to_string(), (c[2].parse().unwrap(), c[3].parse().unwrap())))
        .collect();
    let code: BTreeMap<String, (f64, f64)> = PieceType::ALL
        .iter()
        .map(|t| (t.as_str().to_string(), t.cross_section()))
        .collect();
    assert_eq!(documented, code);
}

#[test]
fn the_preset_tables_are_the_code_s() {
    let spec = spec();
    let preset = |(d, l): &(f64, f64)| format!("{}x{}", format_mm(*d), format_mm(*l));
    // Lumber rows look like dowel rows: read only the dowel section
    let dowel_row = Regex::new(r"(?m)^\| `(\d+x\d+)` \| [\d.]+ \| [\d.]+ \|").unwrap();
    let documented: BTreeSet<String> = dowel_row
        .captures_iter(section(&spec, "### Dowel Connection"))
        .map(|c| c[1].to_string())
        .collect();
    assert_eq!(documented, DOWELS.iter().map(preset).collect());
    let screw_row = Regex::new(r"(?m)^\| `((?:Slim|Coarse):[\d.]+x[\d.]+)` \|").unwrap();
    let documented: BTreeSet<String> = screw_row.captures_iter(&spec).map(|c| c[1].to_string()).collect();
    let code: BTreeSet<String> = SLIM_SCREWS
        .iter()
        .map(|p| format!("Slim:{}", preset(p)))
        .chain(COARSE_SCREWS.iter().map(|p| format!("Coarse:{}", preset(p))))
        .collect();
    assert_eq!(documented, code);
}

#[test]
fn the_stock_file_example_reads_as_described() {
    let spec = spec();
    let tomls: Vec<String> = fences(&spec)
        .into_iter()
        .filter(|(_, language, _)| language == "toml")
        .map(|(_, _, body)| body)
        .collect();
    assert_eq!(tomls.len(), 1);
    let dir = std::env::temp_dir().join(format!("nd-docs-stock-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    fs::write(dir.join("stock.toml"), &tomls[0]).unwrap();
    fs::write(dir.join("d.nd"), "(a:1x4 =500)\n(b:2x6 =500)\n").unwrap();
    let out = cli(&["report", "d.nd", "--stock", "stock.toml"], &dir);
    let report = String::from_utf8(out.stdout).unwrap();
    assert!(report.contains("Saw kerf: 2mm per cut"), "{report}");
    assert!(report.contains("### 1x4 Lumber (Available: 910mm, 1820mm)"), "{report}");
    // Lumber types left out keep the defaults
    assert!(
        report.contains("### 2x6 Lumber (Available: 1820mm, 2440mm, 3050mm, 3650mm)"),
        "{report}"
    );
    fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn relative_links_point_at_existing_files() {
    let link = Regex::new(r#"\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)"#).unwrap();
    let reference = Regex::new(r#"(?m)^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+"[^"]*")?\s*$"#).unwrap();
    let mut missing = Vec::new();
    for path in markdown() {
        let text = fs::read_to_string(&path).unwrap();
        for target in link
            .captures_iter(&text)
            .chain(reference.captures_iter(&text))
            .map(|c| c[1].to_string())
        {
            if ["http:", "https:", "mailto:", "#"].iter().any(|p| target.starts_with(p)) {
                continue;
            }
            let file = target.split('#').next().unwrap();
            if !path.parent().unwrap().join(file).exists() {
                missing.push(format!("{}: {target}", path.display()));
            }
        }
    }
    assert!(missing.is_empty(), "{missing:#?}");
}

/// Repository paths a text names in code spans or prose, e.g.
/// `skills/design/SKILL.md`, that exist neither from the root nor from
/// `dir`. prompts/, src/ and tests/ stay listed so that naming what was
/// removed fails.
fn missing_mentions(text: &str, dir: &Path) -> Vec<String> {
    let path =
        Regex::new(r"(?:^|[^\w/.-])((?:docs|prompts|examples|skills|bin|src|tests|crates)/[\w./-]*[\w/])")
            .unwrap();
    let plugin = Regex::new(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]*[\w/])").unwrap();
    let root = root();
    let named = path
        .captures_iter(text)
        .map(|c| c[1].to_string())
        .filter(|m| !root.join(m).exists() && !dir.join(m).exists());
    let plugin_named = plugin
        .captures_iter(text)
        .map(|c| c[1].to_string())
        .filter(|m| !root.join(m).exists());
    named.chain(plugin_named).collect()
}

#[test]
fn missing_mentions_are_found() {
    let text = "Read `${CLAUDE_PLUGIN_ROOT}/docs/nope.md` and `prompts/system.md`.";
    assert_eq!(missing_mentions(text, &root()), ["prompts/system.md", "docs/nope.md"]);
}

#[test]
fn mentioned_repo_paths_exist() {
    let mut missing = Vec::new();
    for path in markdown() {
        for mention in missing_mentions(&fs::read_to_string(&path).unwrap(), path.parent().unwrap()) {
            missing.push(format!("{}: {mention}", path.display()));
        }
    }
    assert!(missing.is_empty(), "{missing:#?}");
}

#[test]
fn the_validate_json_example_is_what_the_cli_prints() {
    let file = "examples/nd_files/corner_angle_compact.nd";
    let blocks = fences(&spec());
    let at = blocks
        .iter()
        .position(|(_, _, body)| body.contains(&format!("validate --json {file}")))
        .expect("the example's command");
    let (_, language, documented) = &blocks[at + 1];
    assert_eq!(language, "json");
    let documented: Value = serde_json::from_str(documented).unwrap();
    let printed: Value = serde_json::from_slice(&cli(&["validate", "--json", file], &root()).stdout).unwrap();
    assert_eq!(documented, printed);
}

#[test]
fn every_command_is_in_the_cli_reference() {
    // The DSL specification is the CLI's reference
    let help = String::from_utf8(cli(&["--help"], &root()).stdout).unwrap();
    let commands: Vec<String> = help
        .split("Commands:\n")
        .nth(1)
        .unwrap()
        .lines()
        .take_while(|line| !line.trim().is_empty())
        .filter_map(|line| line.split_whitespace().next())
        .filter(|command| *command != "help")
        .map(str::to_string)
        .collect();
    let spec = spec();
    let missing: Vec<&String> = commands
        .iter()
        .filter(|c| !spec.contains(&format!("nichiyou-daiku {c}")))
        .collect();
    assert!(commands.len() >= 7 && missing.is_empty(), "{commands:?}: {missing:?}");
}
```

- [ ] **Step 3: プラグインのテストを書く**

`crates/nichiyou-daiku-cli/tests/plugin.rs`:
```rust
//! The Claude Code plugin's manifests and its design skill.

use std::fs;
use std::path::{Path, PathBuf};

use regex::Regex;
use serde_json::Value;

fn root() -> PathBuf {
    Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../.."))
        .canonicalize()
        .unwrap()
}

fn manifest(name: &str) -> Value {
    serde_json::from_str(&fs::read_to_string(root().join(".claude-plugin").join(name)).unwrap())
        .unwrap()
}

fn skill() -> String {
    fs::read_to_string(root().join("skills/design/SKILL.md")).unwrap()
}

#[test]
fn the_manifest_names_the_plugin_without_pinning_a_version() {
    let plugin = manifest("plugin.json");
    assert_eq!(plugin["name"], "nichiyou-daiku");
    assert!(plugin["description"].as_str().is_some_and(|d| !d.is_empty()));
    // A version pins users to it; without one they follow the commits
    assert!(plugin.get("version").is_none());
}

#[test]
fn the_marketplace_offers_the_repository_as_the_plugin() {
    let market = manifest("marketplace.json");
    assert_eq!(market["name"], "nichiyou-daiku");
    assert!(market["owner"]["name"].as_str().is_some_and(|n| !n.is_empty()));
    let plugins = market["plugins"].as_array().unwrap();
    assert_eq!(plugins.len(), 1);
    assert_eq!(plugins[0]["name"], manifest("plugin.json")["name"]);
    assert_eq!(plugins[0]["source"], "./");
}

#[test]
fn every_skill_names_and_describes_itself() {
    let header = Regex::new(r"(?s)\A---\n(.*?)\n---\n").unwrap();
    let field = Regex::new(r"(?m)^(\w+): (.+)$").unwrap();
    let skills: Vec<PathBuf> = fs::read_dir(root().join("skills"))
        .unwrap()
        .map(|e| e.unwrap().path().join("SKILL.md"))
        .filter(|p| p.is_file())
        .collect();
    assert!(skills.iter().any(|p| p.ends_with("design/SKILL.md")));
    for path in skills {
        let text = fs::read_to_string(&path).unwrap();
        let front = header.captures(&text).expect("a frontmatter")[1].to_string();
        let fields: Vec<(String, String)> = field
            .captures_iter(&front)
            .map(|c| (c[1].to_string(), c[2].to_string()))
            .collect();
        let get = |key: &str| fields.iter().find(|(k, _)| k == key).map(|(_, v)| v.clone()).unwrap();
        let folder = path.parent().unwrap().file_name().unwrap().to_string_lossy().into_owned();
        assert_eq!(get("name"), folder);
        assert!((1..=1024).contains(&get("description").len()));
    }
}

#[test]
fn the_skill_reads_the_specification_up_to_its_complete_examples() {
    // The examples, CLI, grammar and error sections after that line are not
    // needed to design, and every line read stays in the agent's context
    let found = Regex::new(r"its first (\d+) lines")
        .unwrap()
        .captures(&skill())
        .expect("SKILL.md names how many lines of the specification to read")[1]
        .parse::<usize>()
        .unwrap();
    let spec = fs::read_to_string(root().join("docs/dsl-specification.md")).unwrap();
    assert!(spec.lines().nth(found).unwrap().starts_with("## Complete Examples"));
}

#[test]
fn the_skill_does_not_rely_on_claude_code_s_plugin_root() {
    // Only Claude Code substitutes it: opencode and other tools read the
    // same skill, so files are linked relative to the skill instead
    let mut stack = vec![root().join("skills")];
    let mut literal = Vec::new();
    while let Some(dir) = stack.pop() {
        for entry in fs::read_dir(dir).unwrap() {
            let path = entry.unwrap().path();
            if path.is_dir() {
                stack.push(path);
            } else if fs::read_to_string(&path).is_ok_and(|t| t.contains("${CLAUDE_PLUGIN_ROOT}")) {
                literal.push(path.display().to_string());
            }
        }
    }
    assert!(literal.is_empty(), "{literal:?}");
}
```
（Python の `test_skill_tells_how_to_reinstall_the_cli`・`test_skill_covers_an_installed_cli_without_json`・`test_skill_covers_render_with_an_old_or_partial_install` は uv で入れ直す案内のテストで、R6 でその文を消すので移さない。代わりの文のテストは Task 7。）

- [ ] **Step 4: 入口のテストを足す**

`plugin_bin.rs` の `release` の偽の CLI を引数ごとに `[…]` で囲む形にし、今のテストの期待（`"prebuilt validate t.nd\n"` など）を `"prebuilt [validate] [t.nd]\n"` の形に直す:
```rust
    executable(
        &stage.join("nichiyou-daiku"),
        "#!/bin/sh\nprintf prebuilt\nfor arg in \"$@\"; do printf ' [%s]' \"$arg\"; done\necho\n",
    );
```
`run` を、動かすスクリプトを選べる形にする:
```rust
/// Runs `script` (the entry point or a copy or link of it) with only
/// `dir/bin` and the system's tools on PATH.
fn run_script(dir: &Path, script: &Path, args: &[&str]) -> Output {
    Command::new("sh")
        .arg(script)
        .args(args)
        .env_clear()
        .env("PATH", format!("{}:/usr/bin:/bin", dir.join("bin").display()))
        .env("HOME", dir)
        .env("XDG_CACHE_HOME", dir.join("cache"))
        .env(
            "NICHIYOU_DAIKU_RELEASES",
            format!("file://{}", dir.join("releases").display()),
        )
        .output()
        .unwrap()
}

fn run(dir: &Path, args: &[&str]) -> Output {
    run_script(dir, Path::new(ENTRY), args)
}

/// A copy of the entry point in a plugin root at `dir/name`, with the
/// version it reads.
fn plugin(dir: &Path, name: &str) -> PathBuf {
    let root = dir.join(name);
    fs::create_dir_all(root.join("bin")).unwrap();
    fs::copy(ENTRY, root.join("bin/nichiyou-daiku")).unwrap();
    fs::write(
        root.join("Cargo.toml"),
        format!("[workspace]\n\n[workspace.package]\nversion = \"{VERSION}\"\n"),
    )
    .unwrap();
    root
}

#[test]
fn the_entry_point_is_a_posix_shell_script() {
    assert!(fs::read_to_string(ENTRY).unwrap().starts_with("#!/bin/sh\n"));
}

#[test]
fn a_plugin_path_with_spaces_stays_whole() {
    let dir = folder("spaces", "Linux", "x86_64");
    release(&dir, "x86_64-unknown-linux-musl");
    let root = plugin(&dir, "my plugin");
    let out = run_script(&dir, &root.join("bin/nichiyou-daiku"), &["validate", "my table.nd"]);
    assert_eq!(text(&out.stdout), "prebuilt [validate] [my table.nd]\n", "{}", text(&out.stderr));
}

#[test]
fn a_link_to_the_entry_point_finds_its_plugin() {
    let dir = folder("link", "Linux", "x86_64");
    release(&dir, "x86_64-unknown-linux-musl");
    let root = plugin(&dir, "plugin");
    std::os::unix::fs::symlink(root.join("bin/nichiyou-daiku"), dir.join("nd")).unwrap();
    let out = run_script(&dir, &dir.join("nd"), &["validate"]);
    assert_eq!(text(&out.stdout), "prebuilt [validate]\n", "{}", text(&out.stderr));
}
```

- [ ] **Step 5: 通るのを確かめ、落ちうることも確かめる**

Run: `cargo test -p nichiyou-daiku-cli --test docs --test plugin --test plugin_bin 2>&1 | grep "test result"`
Expected: すべて通る（移したテストは今のドキュメントで通る）

移したテストが本当に落ちうるか、2 つ試して戻す:
Run: `sed -i 's/^| `2x4` | 89 | 38 |/| `2x4` | 90 | 38 |/' docs/dsl-specification.md && cargo test -q -p nichiyou-daiku-cli --test docs the_lumber 2>&1 | grep -c FAILED; git checkout docs/dsl-specification.md`
Expected: `1`
Run: `sed -i 's/"source": ".\/"/"source": "x"/' .claude-plugin/marketplace.json && cargo test -q -p nichiyou-daiku-cli --test plugin marketplace 2>&1 | grep -c FAILED; git checkout .claude-plugin/marketplace.json`
Expected: `1`

- [ ] **Step 6: Python のテストを消してコミットする**

`git rm tests/test_docs.py tests/test_plugin.py`。`Makefile` の `test` から `--cov-fail-under=90` を消す（Python の本体は Task 6 で消え、その docs のテストは Rust に移ったので、閾値に意味が無い）。

```bash
make check && git add -A crates tests Makefile && git commit -m "test: Check the docs and the plugin in Rust"
```

---

### Task 3: `--version` と、`validate --json` の `connections`・`steps`

**Files:**
- Modify: `crates/nichiyou-daiku-cli/src/main.rs`（`#[command(version)]`）
- Create: `crates/nichiyou-daiku-cli/tests/version.rs`
- Modify: `crates/nichiyou-daiku-core/src/diagnostics.rs`（`validation_report`・`failure_report`）
- Modify: `crates/nichiyou-daiku-core/tests/corpus.rs`（テスト）
- Modify: `docs/dsl-specification.md`（`--json` の例と説明、全体のオプション）
- Rewrite（生成）: `*.validate.json`・`*.cli-validate-json.txt`

**Interfaces:**
- Produces: `validate --json` のキーの順 `valid, error, overall_size, size_reference, pieces, connections, steps, problems`。`connections` は `[{"base": id, "target": id, "type": "vanilla"|"dowel"|"screw"}]`（宣言の順）、`steps` は整数。Task 4 の評価がこれを読む。
- Produces: `nichiyou-daiku --version` → `nichiyou-daiku 0.2.0\n`、終了 0。Task 5 の `install.sh` がこれで古い版を見分ける。

- [ ] **Step 1: 落ちるテストを書く**

`crates/nichiyou-daiku-cli/tests/version.rs`:
```rust
//! The CLI names itself and its version, which tells it from the Python
//! version (that has no --version).

use std::process::Command;

#[test]
fn version_names_the_cli_and_its_version() {
    let out = Command::new(env!("CARGO_BIN_EXE_nichiyou-daiku"))
        .arg("--version")
        .output()
        .unwrap();
    assert!(out.status.success());
    assert_eq!(
        String::from_utf8(out.stdout).unwrap(),
        format!("nichiyou-daiku {}\n", env!("CARGO_PKG_VERSION"))
    );
}
```
`crates/nichiyou-daiku-core/tests/corpus.rs` の `a_report_starts_with_whether_it_is_valid` の期待を `["valid", "error", "overall_size", "size_reference", "pieces", "connections", "steps", "problems"]` にし、足す:
```rust
const TABLE: &str = "(leg:2x4 =400)
(rail:2x4 =300)
(top:2x4 =300)
(board:1x4 =300)
leg -[FL<300 DF<0]- rail
leg -[TF<0 DF<0 D(:8x30)]- top
top -[FL<0 BL<0 S(Slim:3.3x45)]- board
steps {
  \"Frame\": leg, rail
  \"Top\": top, board
}
";

#[test]
fn a_report_lists_the_connections_and_counts_the_steps() {
    let report = nichiyou_daiku_core::validate(TABLE);
    assert_eq!(report["error"], serde_json::Value::Null);
    assert_eq!(
        report["connections"],
        serde_json::json!([
            {"base": "leg", "target": "rail", "type": "vanilla"},
            {"base": "leg", "target": "top", "type": "dowel"},
            {"base": "top", "target": "board", "type": "screw"},
        ])
    );
    assert_eq!(report["steps"], 2);
    let without = nichiyou_daiku_core::validate(TABLE.split("steps").next().unwrap());
    assert_eq!(without["steps"], 0);
}

#[test]
fn a_report_that_stops_has_no_connections_and_no_steps() {
    let report = nichiyou_daiku_core::validate("(leg:2x4 =)\n");
    assert_eq!(report["error"]["kind"], "syntax");
    assert_eq!(report["connections"], serde_json::json!([]));
    assert_eq!(report["steps"], 0);
}
```

- [ ] **Step 2: 落ちるのを確かめる**

Run: `cargo test -q -p nichiyou-daiku-cli --test version 2>&1 | grep -E "panicked|test result"; cargo test -q -p nichiyou-daiku-core --test corpus a_report 2>&1 | grep -E "test result"`
Expected: `version` は `--version` を知らずに落ちる、core の 3 つは落ちる

- [ ] **Step 3: 実装する**

`main.rs` の `#[command(name = "nichiyou-daiku", args_override_self = true)]` を `#[command(name = "nichiyou-daiku", version, args_override_self = true)]` にする。

`diagnostics.rs` の `use` に `crate::model::Model;` を足し、`validation_report` の上に:
```rust
/// Each connection's pieces and kind, in the order written.
fn connections(model: &Model) -> Value {
    model
        .connections
        .iter()
        .map(|connection| {
            let kind = match connection.kind {
                ConnectionType::Vanilla => "vanilla",
                ConnectionType::Dowel { .. } => "dowel",
                ConnectionType::Screw { .. } => "screw",
            };
            json!({
                "base": connection.base.piece.id,
                "target": connection.target.piece.id,
                "type": kind,
            })
        })
        .collect()
}
```
`validation_report` の `json!` の `"pieces": …,` の後に `"connections": connections(&assembly.model), "steps": assembly.model.steps.len(),` を足し、`failure_report` の `"pieces": [],` の後に `"connections": [], "steps": 0,` を足す。（`view_report` と `view_failure` は同じ名前のキーを自分の形で上書きするので、ビューアーの JSON の中身は変わらない。）

- [ ] **Step 4: 通るのを確かめ、正解ファイルを書き直す**

Run: `cargo test -q -p nichiyou-daiku-cli --test version && cargo test -q -p nichiyou-daiku-core --test corpus a_report 2>&1 | grep "test result"`
Expected: 通る

Run: `ND_BLESS=1 cargo test -q >/dev/null 2>&1; git status --short | sed 's/.*\.\([a-z-]*\.[a-z]*\)$/\1/' | sort | uniq -c`
Expected: `validate.json` 769 件と `cli-validate-json.txt` 9 件だけが変わる（`connections` と `steps` が入る）

- [ ] **Step 5: DSL 仕様の `--json` を直す**

`docs/dsl-specification.md`:
- 「CLI Tools」の最初の段落の最後に足す: ` \`nichiyou-daiku --version\` prints the version.`
- `validate --json examples/nd_files/corner_angle_compact.nd` の後の ```json の中身を、`cargo run -q -p nichiyou-daiku-cli -- validate --json examples/nd_files/corner_angle_compact.nd` の出力で置き換える。
- 項目の説明: `error` の行の `Then \`overall_size\` is null and \`pieces\` and \`problems\` are empty.` を `Then \`overall_size\` is null, \`pieces\`, \`connections\` and \`problems\` are empty and \`steps\` is 0.` にし、`pieces` の項目の後に足す:
```markdown
- `connections`: each connection in the order written, with its `base` and `target` piece IDs and its `type` (`vanilla`, `dowel` or `screw`).
- `steps`: how many steps the `steps` block has; 0 without one.
```

Run: `cargo test -q -p nichiyou-daiku-cli --test docs 2>&1 | grep "test result"`
Expected: 通る（`the_validate_json_example_is_what_the_cli_prints`）

- [ ] **Step 6: コミットする**

```bash
make check && git add -A crates docs && git commit -m "feat(cli): Print the version, and the connections and steps in validate --json"
```

---

### Task 4: 評価を CLI の JSON で動かす

**Files:**
- Move: `tests/evals/` → `evals/tests/`（`git mv`）
- Create: `evals/tests/conftest.py`
- Modify: `evals/design/checks.py`、`evals/design/agent.py`（`agent_env`）、`evals/design/run.py`（`build_cli`・`main`・`preflight`・`HIDDEN`・`ENVIRONMENTS` のコメント・`_uv_cache` を消す）
- Modify: `evals/tests/test_checks.py`・`test_agent.py`・`test_run.py`
- Modify: `tools/check_step.py`
- Delete: `tools/__init__.py`

**Interfaces:**
- Consumes: Task 3 の `validate --json`（`connections`・`steps`・`pieces[].faces`）。
- Produces: `checks.read_design(path) -> dict`、`checks.cli() -> str`（`NICHIYOU_DAIKU_BIN` か入口）、`run.build_cli(plugin: Path, into: Path) -> Path`、`agent_env(plugin: Path, cache: Path, cli: Path, venv: Path) -> dict[str, str]`（`NICHIYOU_DAIKU_BIN` を入れる）。

- [ ] **Step 1: テストを移し、落ちるテストに直す**

```bash
git mv tests/evals evals/tests
```
`evals/tests/conftest.py`:
```python
"""The checks run the nichiyou-daiku CLI: the one NICHIYOU_DAIKU_BIN names
(CI builds it), else this repository's debug build, built here if needed."""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).parents[2]


def pytest_configure(config):
    if os.environ.get("NICHIYOU_DAIKU_BIN"):
        return
    subprocess.run(
        ["cargo", "build", "--quiet", "-p", "nichiyou-daiku-cli"], cwd=REPO, check=True
    )
    os.environ["NICHIYOU_DAIKU_BIN"] = str(REPO / "target" / "debug" / "nichiyou-daiku")
```
`evals/tests/test_checks.py`: `from nichiyou_daiku.shell.diagnostics import …` を消し、`_flat` を辞書にする:
```python
def _flat(id: str, type: str, low: tuple, high: tuple) -> dict:
    """A board lying flat, as validate --json lists it: its front face up,
    its length along x."""
    return {
        "id": id,
        "type": type,
        "length": high[0] - low[0],
        "group": 0,
        "min": list(low),
        "max": list(high),
        "faces": {"top": "+x", "right": "+y", "front": "+z"},
    }
```
`test_a_level_of_a_few_narrow_boards_is_not_counted` の `ValidationReport.model_construct(pieces=…, overall_size=…)` を `{"pieces": [top_front, top_back, *shelves], "overall_size": [1200.0, 350.0, 400.0]}` にする。足す:
```python
def test_the_checks_read_what_validate_json_says(tmp_path):
    # The fasteners and the steps come from validate --json's connections
    # and steps, not from a model in Python
    report = read_design(SIDE_TABLE)
    assert {connection["type"] for connection in report["connections"]} <= {
        "vanilla",
        "dowel",
        "screw",
    }
    assert report["steps"] > 0
```
（`from evals.design.checks import …` に `read_design` を足す。）`evals/tests/test_agent.py` の `test_a_run_uses_the_plugin_s_own_cli` をこれにする:
```python
def test_a_run_uses_the_plugin_s_own_cli(monkeypatch):
    # As for a person who installed the plugin: its entry point on PATH,
    # running the CLI built from the plugin's source, never an installed
    # CLI or the developer's .venv, which make eval's uv run puts on PATH
    monkeypatch.setenv("PATH", "/repo/.venv/bin:/usr/bin")
    monkeypatch.setenv("VIRTUAL_ENV", "/repo/.venv")
    env = agent_env(Path("/plugin"), Path("/cache"), Path("/cache/nd"), Path("/repo/.venv"))
    assert env["PATH"] == "/plugin/bin:/usr/bin"
    assert "VIRTUAL_ENV" not in env
    assert env["NICHIYOU_DAIKU_BIN"] == "/cache/nd"
    assert env["XDG_CACHE_HOME"] == "/cache"
    assert "NICHIYOU_DAIKU_WRAPPED" not in env
```
`evals/tests/test_run.py`: `fake` の fixture に `monkeypatch.setattr(run, "build_cli", lambda plugin, into: Path(os.environ["NICHIYOU_DAIKU_BIN"]))` を足し（評価のテストで cargo を動かさない）、足す:
```python
def test_an_evaluation_without_cargo_stops_before_spending(fake, monkeypatch, tmp_path, capsys):
    def no_cargo(plugin, into):
        raise FileNotFoundError("cargo")

    monkeypatch.setattr(run, "build_cli", no_cargo)
    assert run.main(["--cases", "side-table", "--out", str(tmp_path / "out")]) == 2
    said = capsys.readouterr().err
    assert "could not build the plugin's CLI with cargo" in said
    assert "https://rustup.rs" in said
    assert fake == []
```
`test_the_preflight_names_what_does_not_work` の偽の CLI の文 `build123d is required` を `cannot read the design` に替える（期待も）。

- [ ] **Step 2: 落ちるのを確かめる**

Run: `uv run pytest evals/tests -q 2>&1 | tail -5`
Expected: `test_checks.py`（`read_design` が無い）、`test_agent.py`、`test_run.py` の新しいテストが落ちる

- [ ] **Step 3: checks.py を CLI の JSON で書き直す**

`evals/design/checks.py` の先頭から `_failed` の前までと、`_valid` 以降の関数で `ValidationReport`・`PiecePosition`・`Model` を使うところをこう直す（判定の中身と文は変えない）:
```python
"""Machine checks: read the design with the nichiyou-daiku CLI
(validate --json) and compare it with what the case asks for."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, NamedTuple

from .cases import Case

REPO = Path(__file__).resolve().parents[2]
# validate --json's report and one of its pieces
Report = dict[str, Any]
Piece = dict[str, Any]
```
（`CHECKS` から `_STEPS_FROM` と `Check` はそのまま。）
```python
def cli() -> str:
    """The CLI the checks run: NICHIYOU_DAIKU_BIN (an evaluation sets it to
    the CLI it built for the agent), else the plugin's entry point."""
    return os.environ.get("NICHIYOU_DAIKU_BIN") or str(REPO / "bin" / "nichiyou-daiku")


def read_design(path: Path) -> Report:
    """What validate --json says of the design at ``path``."""
    result = subprocess.run(
        [cli(), "validate", "--json", str(path)], capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        said = (result.stderr.strip().splitlines() or ["no output"])[-1]
        raise RuntimeError(
            f"{cli()} validate --json printed no report ({said}); build the CLI "
            "(cargo build -p nichiyou-daiku-cli) or set NICHIYOU_DAIKU_BIN"
        ) from None


def assembles(path: Path) -> bool:
    """Whether the design at ``path`` parses and assembles, so that it can
    be drawn."""
    return read_design(path)["error"] is None


def check_design(path: Path | None, case: Case) -> dict[str, Check]:
    """Every check of ``CHECKS`` for the design at ``path``."""
    asked = _asked(case)
    if path is None:
        return _failed(asked, "no .nd file in the working directory")
    report = read_design(path)
    if report["error"] is not None:
        message = report["error"]["message"] or report["error"]["kind"]
        return _failed(asked, f"{path.name} does not assemble: {message.splitlines()[0]}")
    pieces = report["pieces"]
    checks = {
        "valid": _valid(report),
        "size": _size(report, case),
        "orientation": _orientation(report, case),
        "lumber": _lumber(pieces, case),
        "legs": _legs(pieces, case),
        "shelves": _shelves(pieces, case),
        "levels": _levels(report, case),
        "fasteners": _fasteners(report, case),
        "steps": _steps(report),
    }
    return {
        name: check if name in asked else Check(None, "not asked")
        for name, check in checks.items()
    }
```
（`find_design`・`_asked`・`_failed`・`_close` はそのまま。`_assemble` は消す。）各関数の読み方を辞書に替える:
- `_valid(report: Report)`: `report["valid"]`、`{problem["kind"] for problem in report["problems"]}`
- `_size`・`_orientation`・`_levels`: `report["overall_size"]`、`report["pieces"]`
- `_lumber(pieces: list[Piece], …)`: `piece["type"]`
- `_upright(piece: Piece)`: `piece["faces"]["top"][1] == "z"`
- `_legs`・`_shelves`・`_holds_up`・`_level_tops`: `piece["min"]`・`piece["max"]`、型は `list[Piece]`
- `_flat_board` は断面の表を使わず、JSON の向きと箱から決める:
```python
def _flat_board(piece: Piece) -> bool:
    """A board lying flat: its front face up and its section wider than it
    is thick (a square section, 2x2, lying down is a rail)."""
    if piece["faces"]["front"][1] != "z":
        return False
    across = "xyz".index(piece["faces"]["right"][1])
    width = piece["max"][across] - piece["min"][across]
    return width > piece["max"][2] - piece["min"][2]
```
- `_fasteners` と `_steps`:
```python
def _fasteners(report: Report, case: Case) -> Check:
    wanted = case.fasteners
    if wanted is None:
        return Check(None, "not asked")
    kinds = {connection["type"] for connection in report["connections"]}
    missing = [
        name
        for name, asked, kind in (
            ("dowels", wanted.dowel, "dowel"),
            ("screws", wanted.screw, "screw"),
        )
        if asked and kind not in kinds
    ]
    if missing:
        return Check(False, f"no {' or '.join(missing)}")
    return Check(True, "asked fasteners used")


def _steps(report: Report) -> Check:
    count = len(report["pieces"])
    if count < _STEPS_FROM:
        return Check(True, f"{count} pieces: no steps block needed")
    steps = report["steps"]
    return Check(bool(steps), f"{steps} steps" if steps else "no steps block")
```
`evals/design/agent.py` の `nichiyou_daiku` の import を消す（`grep -n nichiyou_daiku evals/design/agent.py` で場所を見る）。

- [ ] **Step 4: 評価が手元のビルドを使うようにする**

`evals/design/agent.py` の `agent_env` をこれにする:
```python
def agent_env(plugin: Path, cache: Path, cli: Path, venv: Path) -> dict[str, str]:
    """The environment of a run, as a person who installed the plugin has
    it: the plugin's entry point first on PATH, running ``cli``, the CLI
    built from the plugin's source. Never an installed CLI or the
    developer's ``venv`` (the dev tools), which uv run puts on PATH."""
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    kept = [
        entry
        for entry in env.get("PATH", "").split(os.pathsep)
        if entry and Path(entry) != venv / "bin"
    ]
    env["PATH"] = os.pathsep.join([str(plugin / "bin"), *kept])
    env["NICHIYOU_DAIKU_BIN"] = str(cli)
    # Should the entry point look in its cache, the run's own
    env["XDG_CACHE_HOME"] = str(cache)
    return env
```
`evals/design/run.py`:
- `HIDDEN` から `"tests/evals/"` を消す（`evals/` が覆う）。
- `ENVIRONMENTS` のコメントを `# The plugin CLI's builds: cargo's target folder, kept between evaluations so that each builds only what changed` にする。
- `_uv_cache` を消す。
- `preflight` の文 `check that bin/nichiyou-daiku runs with uv` を `check that the CLI cargo built from the plugin runs` にし、docstring の `(which builds its environments once for all the runs)` を消す。
- 足す:
```python
def build_cli(plugin: Path, into: Path) -> Path:
    """The CLI built with cargo from the plugin's own source, copied into
    ``into``: edits to the repository during an evaluation do not reach it."""
    target = ENVIRONMENTS / "target"
    subprocess.run(
        ["cargo", "build", "--release", "--quiet", "-p", "nichiyou-daiku-cli"]
        + ["--manifest-path", str(plugin / "Cargo.toml")],
        env={**os.environ, "CARGO_TARGET_DIR": str(target)},
        check=True,
    )
    built = into / "nichiyou-daiku"
    shutil.copy2(target / "release" / "nichiyou-daiku", built)
    return built
```
- `main` の `env = agent_env(plugin, Path(cache), _uv_cache(), REPO / ".venv")` をこれにする:
```python
        try:
            cli = build_cli(plugin, Path(cache))
        except (OSError, subprocess.CalledProcessError) as e:
            print(
                f"could not build the plugin's CLI with cargo ({e}); install Rust "
                "(https://rustup.rs) and run the evaluation again",
                file=sys.stderr,
            )
            return 2
        # The checks read the designs with the CLI the agent runs
        os.environ["NICHIYOU_DAIKU_BIN"] = str(cli)
        env = agent_env(plugin, Path(cache), cli, REPO / ".venv")
```

- [ ] **Step 5: 道具を CLI の JSON にする**

`tools/check_step.py`: `from nichiyou_daiku.dsl import parse_dsl` を消し、使い方の docstring を
```python
"""Check a STEP the Rust CLI wrote (R5): every piece a valid solid, named
as the design names it, their volume the STL's.

    NICHIYOU_DAIKU_BIN=target/release/nichiyou-daiku \\
        uv run --with build123d tools/check_step.py design.nd model.step model.stl
"""
```
にし、部材を CLI から読む:
```python
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def piece_ids(design: str) -> list[str]:
    """The design's pieces, as validate --json lists them."""
    cli = os.environ.get("NICHIYOU_DAIKU_BIN") or str(ROOT / "bin" / "nichiyou-daiku")
    result = subprocess.run([cli, "validate", "--json", design], capture_output=True, text=True)
    return [piece["id"] for piece in json.loads(result.stdout)["pieces"]]
```
`main` の `pieces = list(parse_dsl(Path(design).read_text(encoding="utf-8")).pieces)` を `pieces = piece_ids(design)` にする。`git rm tools/__init__.py`。

- [ ] **Step 6: 通るのを確かめる**

Run: `uv run pytest evals/tests -q 2>&1 | tail -3 && uv run ruff check evals/ tools/ && uv run ruff format --check evals/ tools/ && uv run pyright evals 2>&1 | tail -1`
Expected: すべて通る

Run: `cargo build -q --release -p nichiyou-daiku-cli && for f in examples/nd_files/*.nd crates/nichiyou-daiku-core/tests/corpus/example-*.nd crates/nichiyou-daiku-core/tests/corpus/doc-*.nd ~/workspace/designs/file-wagon/file-wagon.nd; do ./target/release/nichiyou-daiku export $f -o /tmp/nd-chk.step 2>/dev/null && ./target/release/nichiyou-daiku export $f -o /tmp/nd-chk.stl 2>/dev/null && NICHIYOU_DAIKU_BIN=target/release/nichiyou-daiku uv run --with build123d tools/check_step.py $f /tmp/nd-chk.step /tmp/nd-chk.stl || echo "FAIL $f"; done | grep -v " parts, volume"`
Expected: 何も出ない（すべての例とワゴンで、部品の数・名前・正しい立体・体積が合う）

Run: `uv run python -m evals.design.run --self-check 2>&1 | tail -5`
Expected: 既知の設計の判定が変わらない（self-check が通る）。Claude を使うので、動かす前にユーザーに頼む（使う量が出る）。頼めないときは Task 8 でユーザーの確認と一緒に頼む。

- [ ] **Step 7: コミットする**

```bash
make check && git add -A evals tests tools && git commit -m "feat(evals): Check designs with the CLI's validate --json"
```

---

### Task 5: `install.sh` と、プラグイン自身の版だけを使う入口

**Files:**
- Create: `install.sh`（実行できる形で）
- Modify: `bin/nichiyou-daiku`（全体を書き換え）
- Create: `crates/nichiyou-daiku-cli/tests/release/mod.rs`（偽のリリースの道具を入口とインストールのテストで共有）
- Modify: `crates/nichiyou-daiku-cli/tests/plugin_bin.rs`
- Create: `crates/nichiyou-daiku-cli/tests/install.rs`

**Interfaces:**
- Consumes: Task 3 の `--version`。
- Produces: `install.sh` の関数（入口が `NICHIYOU_DAIKU_LIBRARY=1` で読み込む）: `detect`（`system machine os arch exe ext target` を決める）、`fetch URL OUT`、`sha256 FILE`、`download VERSION DIR`（`DIR/nichiyou-daiku$exe` に置く。失敗で `reason`）、`place FILE DIR`、`latest`（`version` を決める）。環境変数 `NICHIYOU_DAIKU_VERSION`・`NICHIYOU_DAIKU_INSTALL_DIR`・`NICHIYOU_DAIKU_RELEASES`・`NICHIYOU_DAIKU_LATEST`・`NICHIYOU_DAIKU_BIN`。

- [ ] **Step 1: 共有の道具を切り出す**

`plugin_bin.rs` の `executable`・`CURL`・`folder`・`release`・`text` を `crates/nichiyou-daiku-cli/tests/release/mod.rs` に移し、`release` に版を渡せるようにする:
```rust
//! A fake GitHub release and a system for the entry point's and
//! install.sh's tests: curl for file:// URLs and uname saying what we ask.

#![allow(dead_code)]

use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::Command;

pub fn executable(path: &Path, script: &str) { /* plugin_bin.rs のまま */ }

/// Stands in for `curl -fsL -o OUT URL` with a file:// URL, so the tests
/// need no curl (CI's container has none)
pub const CURL: &str = /* plugin_bin.rs のまま */;

pub fn folder(name: &str, system: &str, machine: &str) -> PathBuf { /* plugin_bin.rs のまま */ }

/// A release of `version` for `target` whose CLI prints what it was given,
/// each argument in brackets, with the right SHA256SUMS line. Returns the
/// archive's name.
pub fn release(dir: &Path, version: &str, target: &str) -> String {
    /* plugin_bin.rs の release で VERSION を version にしたもの（Task 2 の printf の偽の CLI） */
}

pub fn text(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).into_owned()
}
```
`plugin_bin.rs` は `mod release; use release::*;` で読み、`release(&dir, target)` の呼び出しを `release(&dir, VERSION, target)` にする。

Run: `cargo test -q -p nichiyou-daiku-cli --test plugin_bin 2>&1 | grep "test result"`
Expected: 通る（形を変えただけ）

- [ ] **Step 2: 落ちるテストを書く**

`plugin_bin.rs` の `a_cli_on_the_path_comes_first` をこれに替え、足す:
```rust
#[test]
fn a_cli_on_the_path_is_not_used() {
    // Such as the Python version installed with uv: the plugin runs its own
    let dir = folder("path", "Linux", "x86_64");
    executable(&dir.join("bin/nichiyou-daiku"), "#!/bin/sh\necho installed\n");
    release(&dir, VERSION, "x86_64-unknown-linux-musl");
    let out = run(&dir, &["validate", "t.nd"]);
    assert_eq!(text(&out.stdout), "prebuilt [validate] [t.nd]\n", "{}", text(&out.stderr));
}

#[test]
fn nichiyou_daiku_bin_runs_instead() {
    let dir = folder("bin", "Linux", "x86_64");
    executable(&dir.join("dev"), "#!/bin/sh\necho \"dev $*\"\n");
    let out = Command::new("sh")
        .arg(ENTRY)
        .arg("validate")
        .env_clear()
        .env("PATH", "/usr/bin:/bin")
        .env("NICHIYOU_DAIKU_BIN", dir.join("dev"))
        .output()
        .unwrap();
    assert_eq!(text(&out.stdout), "dev validate\n");
}
```
`a_missing_release_says_what_to_do` に足す（手で落としたものを置く場所を言う。PATH は見ないので「PATH に置く」は効かない）:
```rust
    assert!(
        err.contains(&format!("and put it at {}", cached(&dir).display())),
        "{err}"
    );
```
`plugin` の道具に `install.sh` の写しを足す: `fs::copy(concat!(env!("CARGO_MANIFEST_DIR"), "/../../install.sh"), root.join("install.sh")).unwrap();`

`crates/nichiyou-daiku-cli/tests/install.rs`:
```rust
//! install.sh puts the newest release's CLI, or the version asked, in a
//! folder, checked against SHA256SUMS, and says what keeps it from running.
#![cfg(unix)]

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};

mod release;
use release::*;

const INSTALL: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../install.sh");

/// Runs install.sh with `args`, PATH being dir/bin, `extra` and the system's tools.
fn install(dir: &Path, extra: &[PathBuf], args: &[&str]) -> Output {
    let mut path = vec![dir.join("bin")];
    path.extend(extra.iter().cloned());
    let path: Vec<String> = path.iter().map(|p| p.display().to_string()).collect();
    Command::new("sh")
        .arg(INSTALL)
        .args(args)
        .env_clear()
        .env("PATH", format!("{}:/usr/bin:/bin", path.join(":")))
        .env("HOME", dir)
        .env("NICHIYOU_DAIKU_RELEASES", format!("file://{}", dir.join("releases").display()))
        .env("NICHIYOU_DAIKU_LATEST", format!("file://{}", dir.join("latest.json").display()))
        .output()
        .unwrap()
}

fn newest(dir: &Path, version: &str) {
    fs::write(
        dir.join("latest.json"),
        format!("{{\n  \"url\": \"x\",\n  \"tag_name\": \"v{version}\",\n  \"name\": \"v{version}\"\n}}\n"),
    )
    .unwrap();
}

fn runs(binary: &Path) -> String {
    text(&Command::new(binary).arg("validate").output().unwrap().stdout)
}

#[test]
fn installs_the_newest_release() {
    let dir = folder("newest", "Linux", "x86_64");
    newest(&dir, "9.9.9");
    release(&dir, "9.9.9", "x86_64-unknown-linux-musl");
    let to = dir.join("tools");
    let out = install(&dir, &[to.clone()], &["--to", to.to_str().unwrap()]);
    let err = text(&out.stderr);
    assert!(out.status.success(), "{err}");
    assert_eq!(
        err,
        format!("nichiyou-daiku: installed v9.9.9 for x86_64-unknown-linux-musl in {}\n", to.display())
    );
    assert_eq!(runs(&to.join("nichiyou-daiku")), "prebuilt [validate]\n");
}

#[test]
fn installs_the_version_asked() {
    let dir = folder("asked", "Darwin", "arm64");
    release(&dir, "1.2.3", "aarch64-apple-darwin");
    let to = dir.join("tools");
    for asked in ["1.2.3", "v1.2.3"] {
        let out = install(&dir, &[to.clone()], &["--version", asked, "--to", to.to_str().unwrap()]);
        assert!(out.status.success(), "{}", text(&out.stderr));
    }
    assert_eq!(runs(&to.join("nichiyou-daiku")), "prebuilt [validate]\n");
}

#[test]
fn a_wrong_checksum_installs_nothing() {
    let dir = folder("checksum", "Linux", "x86_64");
    let name = release(&dir, "1.2.3", "x86_64-unknown-linux-musl");
    fs::write(dir.join("releases/v1.2.3/SHA256SUMS"), format!("{}  {name}\n", "0".repeat(64))).unwrap();
    let to = dir.join("tools");
    let out = install(&dir, &[to.clone()], &["--version", "1.2.3", "--to", to.to_str().unwrap()]);
    assert_eq!(out.status.code(), Some(1));
    let err = text(&out.stderr);
    assert!(err.contains("could not install v1.2.3 (its checksum does not match SHA256SUMS)"), "{err}");
    assert!(err.contains("https://github.com/ar90n/nichiyou-daiku/releases"), "{err}");
    assert!(!to.join("nichiyou-daiku").exists());
}

#[test]
fn an_unknown_system_is_named() {
    let dir = folder("unknown", "Plan9", "pdp11");
    let out = install(&dir, &[], &["--version", "1.2.3"]);
    assert_eq!(out.status.code(), Some(1));
    let err = text(&out.stderr);
    assert!(err.contains("no prebuilt nichiyou-daiku for Plan9 pdp11"), "{err}");
    assert!(err.contains("build it from source"), "{err}");
}

#[test]
fn a_folder_off_the_path_is_named() {
    let dir = folder("off", "Linux", "x86_64");
    release(&dir, "1.2.3", "x86_64-unknown-linux-musl");
    let to = dir.join("tools");
    let out = install(&dir, &[], &["--version", "1.2.3", "--to", to.to_str().unwrap()]);
    let err = text(&out.stderr);
    assert!(
        err.contains(&format!("{} is not on PATH; add it", to.display())),
        "{err}"
    );
    // By default it goes to ~/.local/bin
    let out = install(&dir, &[], &["--version", "1.2.3"]);
    assert!(out.status.success(), "{}", text(&out.stderr));
    assert!(dir.join(".local/bin/nichiyou-daiku").is_file());
}

#[test]
fn an_older_python_cli_on_the_path_is_named() {
    let dir = folder("python", "Linux", "x86_64");
    release(&dir, "1.2.3", "x86_64-unknown-linux-musl");
    let old = dir.join("old");
    fs::create_dir_all(&old).unwrap();
    // click answers an unknown option with exit 2
    executable(&old.join("nichiyou-daiku"), "#!/bin/sh\necho 'Error: No such option: --version' >&2\nexit 2\n");
    let to = dir.join("tools");
    let out = install(&dir, &[old.clone(), to.clone()], &["--version", "1.2.3", "--to", to.to_str().unwrap()]);
    let err = text(&out.stderr);
    assert!(out.status.success(), "{err}");
    assert!(
        err.contains(&format!(
            "{} is an older nichiyou-daiku (the Python version); remove it with: uv tool uninstall nichiyou-daiku",
            old.join("nichiyou-daiku").display()
        )),
        "{err}"
    );
}

#[test]
fn piped_into_sh_it_installs() {
    // As in curl -fsSL …/install.sh | sh -s -- --to DIR
    let dir = folder("piped", "Linux", "x86_64");
    release(&dir, "1.2.3", "x86_64-unknown-linux-musl");
    let to = dir.join("tools");
    let mut child = Command::new("sh")
        .args(["-s", "--", "--version", "1.2.3", "--to", to.to_str().unwrap()])
        .env_clear()
        .env("PATH", format!("{}:{}:/usr/bin:/bin", dir.join("bin").display(), to.display()))
        .env("HOME", &dir)
        .env("NICHIYOU_DAIKU_RELEASES", format!("file://{}", dir.join("releases").display()))
        .stdin(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child.stdin.take().unwrap().write_all(&fs::read(INSTALL).unwrap()).unwrap();
    let out = child.wait_with_output().unwrap();
    assert!(out.status.success(), "{}", text(&out.stderr));
    assert_eq!(runs(&to.join("nichiyou-daiku")), "prebuilt [validate]\n");
}
```

- [ ] **Step 3: 落ちるのを確かめる**

Run: `cargo test -q -p nichiyou-daiku-cli --test install --test plugin_bin 2>&1 | grep -E "test result|panicked" | head`
Expected: `install.rs` はすべて落ちる（`install.sh` が無い）。`plugin_bin.rs` の `a_cli_on_the_path_is_not_used`・`nichiyou_daiku_bin_runs_instead`・`a_missing_release_says_what_to_do` が落ちる

- [ ] **Step 4: install.sh を書く**

`install.sh`（`chmod +x`）:
```sh
#!/bin/sh
# Installs the nichiyou-daiku CLI: the prebuilt one for this system from a
# GitHub release, checked against the release's SHA256SUMS.
#
#   curl -fsSL https://raw.githubusercontent.com/ar90n/nichiyou-daiku/main/install.sh | sh
#   sh install.sh --version 0.2.0 --to ~/bin
#
# The plugin's entry point (bin/nichiyou-daiku) reads this file with
# NICHIYOU_DAIKU_LIBRARY set, for its functions only
set -eu

releases_page=https://github.com/ar90n/nichiyou-daiku/releases

# Sets system, machine, os, arch, exe, ext and target; os or arch stays
# empty where no prebuilt CLI is made
detect() {
  system=$(uname -s)
  machine=$(uname -m)
  exe=
  ext=tar.gz
  case $system in
    Linux) os=unknown-linux-musl ;;
    Darwin) os=apple-darwin ;;
    MINGW* | MSYS* | CYGWIN*) os=pc-windows-msvc exe=.exe ext=zip ;;
    *) os= ;;
  esac
  case $machine in
    x86_64 | amd64) arch=x86_64 ;;
    aarch64 | arm64) arch=aarch64 ;;
    *) arch= ;;
  esac
  target=$arch-$os
}

fetch() {
  if command -v curl >/dev/null 2>&1; then
    # Quiet: the reason we give says what failed
    curl -fsL -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2" "$1"
  else
    reason="neither curl nor wget is installed"
    return 1
  fi
}

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d ' ' -f 1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d ' ' -f 1
  else
    return 1
  fi
}

# Moves the CLI $1 into folder $2 whole: a run stopped halfway leaves none
place() {
  mkdir -p "$2" &&
    cp "$1" "$2/nichiyou-daiku$exe.part.$$" &&
    chmod +x "$2/nichiyou-daiku$exe.part.$$" &&
    mv -f "$2/nichiyou-daiku$exe.part.$$" "$2/nichiyou-daiku$exe"
}

# Puts version $1's CLI for this system in folder $2. On failure, $reason
# says why
download() {
  if [ -z "$os" ] || [ -z "$arch" ]; then
    reason="no prebuilt nichiyou-daiku for $system $machine"
    return 1
  fi
  work=$(mktemp -d) || { reason="cannot make a temporary folder"; return 1; }
  if unpack "$1" "$2"; then
    rm -rf "$work"
    return 0
  fi
  rm -rf "$work"
  return 1
}

unpack() {
  name=nichiyou-daiku-$1-$target.$ext
  base=${NICHIYOU_DAIKU_RELEASES:-$releases_page/download}/v$1
  reason="cannot fetch $base/$name"
  fetch "$base/$name" "$work/$name" || return 1
  reason="cannot fetch $base/SHA256SUMS"
  fetch "$base/SHA256SUMS" "$work/SHA256SUMS" || return 1
  want=$(awk -v n="$name" '$2 == n || $2 == "*" n { print $1 }' "$work/SHA256SUMS")
  if ! got=$(sha256 "$work/$name"); then
    reason="neither sha256sum nor shasum is installed to check it"
    return 1
  fi
  if [ -z "$want" ] || [ "$want" != "$got" ]; then
    reason="its checksum does not match SHA256SUMS"
    return 1
  fi
  mkdir "$work/out"
  # set -e does not reach into a function called as an if's condition
  case $ext in
    zip) unzip -q "$work/$name" -d "$work/out" ;;
    *) tar -xzf "$work/$name" -C "$work/out" ;;
  esac || { reason="cannot unpack $name"; return 1; }
  place "$work/out/nichiyou-daiku$exe" "$2" || { reason="cannot put it in $2"; return 1; }
}

# Sets version to the newest release's. On failure, $reason says why
latest() {
  url=${NICHIYOU_DAIKU_LATEST:-https://api.github.com/repos/ar90n/nichiyou-daiku/releases/latest}
  page=$(mktemp) || { reason="cannot make a temporary file"; return 1; }
  reason="cannot fetch $url"
  if ! fetch "$url" "$page"; then
    rm -f "$page"
    return 1
  fi
  version=$(sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' "$page" | head -n 1)
  rm -f "$page"
  if [ -z "$version" ]; then
    reason="$url names no release"
    return 1
  fi
}

fail() {
  printf 'nichiyou-daiku: %s\n' "$1" >&2
  exit 1
}

# Says what would keep the new CLI from running: its folder off PATH, or an
# older nichiyou-daiku (the Python version, which has no --version) on PATH
advise() {
  case :$PATH: in
    *":$1:"*) ;;
    *) printf 'nichiyou-daiku: %s is not on PATH; add it, e.g. with export PATH="%s:$PATH" in your shell profile\n' "$1" "$1" >&2 ;;
  esac
  set -f
  saved_ifs=$IFS
  IFS=:
  for dir in $PATH; do
    if [ -n "$dir" ] && [ "$dir" != "$1" ] && [ -x "$dir/nichiyou-daiku" ] &&
      ! "$dir/nichiyou-daiku" --version >/dev/null 2>&1; then
      printf 'nichiyou-daiku: %s is an older nichiyou-daiku (the Python version); remove it with: uv tool uninstall nichiyou-daiku\n' "$dir/nichiyou-daiku" >&2
      break
    fi
  done
  IFS=$saved_ifs
  set +f
}

main() {
  version=${NICHIYOU_DAIKU_VERSION:-}
  to=${NICHIYOU_DAIKU_INSTALL_DIR:-$HOME/.local/bin}
  while [ $# -gt 0 ]; do
    case $1 in
      --version | --to)
        [ $# -ge 2 ] || fail "$1 needs a value: install.sh [--version VERSION] [--to FOLDER]"
        case $1 in --version) version=$2 ;; *) to=$2 ;; esac
        shift 2
        ;;
      *) fail "unknown option $1: install.sh [--version VERSION] [--to FOLDER]" ;;
    esac
  done
  version=${version#v}
  reason=
  detect
  if [ -z "$os" ] || [ -z "$arch" ]; then
    fail "no prebuilt nichiyou-daiku for $system $machine; build it from source as the README says"
  fi
  if [ -z "$version" ]; then
    latest || fail "cannot find the newest release ($reason); see $releases_page"
  fi
  download "$version" "$to" || fail "could not install v$version ($reason); see $releases_page"
  printf 'nichiyou-daiku: installed v%s for %s in %s\n' "$version" "$target" "$to" >&2
  advise "$to"
}

if [ -z "${NICHIYOU_DAIKU_LIBRARY:-}" ]; then
  main "$@"
fi
```

- [ ] **Step 5: 入口を書き換える**

`bin/nichiyou-daiku` を全部これにする:
```sh
#!/bin/sh
# The nichiyou-daiku CLI for the Claude Code plugin: this plugin's version,
# downloaded once from its GitHub release into the cache, else built from
# the plugin's source when cargo is there. Never a CLI found on PATH, which
# may be another version (or the Python one): the skill is written for this
# one. NICHIYOU_DAIKU_BIN names a CLI to run instead (a development build)
set -eu

if [ -n "${NICHIYOU_DAIKU_BIN:-}" ]; then
  exec "$NICHIYOU_DAIKU_BIN" "$@"
fi

# Follow symlinks so a link to this script still finds the plugin root
real_path() {
  target=$1
  while [ -L "$target" ]; do
    link=$(readlink -- "$target")
    case $link in
      /*) target=$link ;;
      *) target=$(dirname -- "$target")/$link ;;
    esac
  done
  printf '%s/%s\n' "$(CDPATH='' cd -P -- "$(dirname -- "$target")" && pwd -P)" "$(basename -- "$target")"
}

root=$(dirname -- "$(dirname -- "$(real_path "$0")")")

version=$(sed -n '/^\[workspace\.package\]/,/^\[/s/^version *= *"\(.*\)"/\1/p' "$root/Cargo.toml" | head -n 1)
if [ -z "$version" ]; then
  printf 'nichiyou-daiku: cannot read the version from %s; reinstall the plugin.\n' "$root/Cargo.toml" >&2
  exit 127
fi

NICHIYOU_DAIKU_LIBRARY=1
. "$root/install.sh"
detect

cache=${XDG_CACHE_HOME:-$HOME/.cache}/nichiyou-daiku/$version
binary=$cache/nichiyou-daiku$exe
if [ -x "$binary" ]; then
  exec "$binary" "$@"
fi

reason=
if download "$version" "$cache"; then
  printf 'nichiyou-daiku: downloaded v%s for %s\n' "$version" "$target" >&2
  exec "$binary" "$@"
fi
what="v$version for $target"
if [ -z "$os" ] || [ -z "$arch" ]; then
  what="v$version"
fi

if command -v cargo >/dev/null 2>&1; then
  printf 'nichiyou-daiku: could not download %s (%s); building it from source, which takes a few minutes\n' "$what" "$reason" >&2
  CARGO_TARGET_DIR=$cache/build cargo build --release --quiet -p nichiyou-daiku-cli --manifest-path "$root/Cargo.toml" >&2
  place "$cache/build/release/nichiyou-daiku$exe" "$cache"
  exec "$binary" "$@"
fi

printf '%s\n' \
  "nichiyou-daiku: could not download $what ($reason), and cargo is not installed to build it." \
  "Download the CLI for your system from $releases_page/tag/v$version and put it at $binary," \
  "or install Rust (https://rustup.rs) and run the command again." >&2
exit 127
```

- [ ] **Step 6: 通るのを確かめる**

Run: `chmod +x install.sh && cargo test -q -p nichiyou-daiku-cli --test install --test plugin_bin 2>&1 | grep "test result"`
Expected: すべて通る

Run: `sh -n install.sh && sh -n bin/nichiyou-daiku && (command -v shellcheck >/dev/null && shellcheck -s sh install.sh bin/nichiyou-daiku || echo "shellcheck not installed")`
Expected: 文法の誤りが無い（shellcheck があれば警告も無い、または理由のある警告だけ）

- [ ] **Step 7: コミットする**

```bash
make check && git add install.sh bin/nichiyou-daiku crates && git commit -m "feat: Install the CLI with install.sh, and run the plugin's own version"
```

---

### Task 6: Python 版を消す

**Files:**
- Delete: `src/`、`tests/`、`examples/*.py`、`docs/api-specification.md`、（使われていなければ）`docs/images/simple_table_3d.png`、`.github/workflows/release-drafter.yml`（と `.github/release-drafter.yml` があれば）
- Modify（全体を書き換え）: `pyproject.toml`、`Makefile`、`ci/dagger_pipeline.py`、`.github/workflows/ci.yml`
- Modify: `uv.lock`（`uv lock`）、`README.md`（API 仕様へのリンクの行だけ）

**Interfaces:**
- Consumes: Task 4 の `evals/tests`（`NICHIYOU_DAIKU_BIN` か cargo のビルド）。

- [ ] **Step 1: 消す**

```bash
git rm -r -q src tests docs/api-specification.md .github/workflows/release-drafter.yml
git rm -q examples/*.py
git ls-files .github | grep -i drafter | xargs -r git rm -q
git grep -n "simple_table_3d" -- . ':!docs/superpowers' || git rm -q docs/images/simple_table_3d.png
```
`README.md` の `- [Python API](docs/api-specification.md): …` の行を消す（リンクのテストのため。README の残りは Task 7）。

- [ ] **Step 2: pyproject.toml・Makefile・CI を書き換える**

`pyproject.toml`:
```toml
[project]
name = "nichiyou-daiku-dev"
version = "0.2.0"
description = "Development tools for nichiyou-daiku: the design skill's evaluation, the CI pipeline and checks"
requires-python = ">=3.13"
dependencies = [
    "pydantic>=2.11.7",  # the evaluation's cases
]

[tool.uv]
# Not a package: the product is the Rust CLI (crates/)
package = false

[dependency-groups]
dev = [
    "pytest>=8.4.0",
    "ruff>=0.11.13",
    "pyright>=1.1.402",
]
ci = [
    "dagger-io>=0.18.11",
    "anyio>=4.9.0",
]

[tool.ruff]
# Agents may leave scripts in their evaluation run directories
extend-exclude = ["evals/design/runs"]

[tool.pyright]
exclude = ["evals/design/runs"]
```
`Makefile` の `check`・`test`・`lint`・`format`・`ci-setup`・`clean` をこれにする（`rust-check`・`wasm…`・`web…`・`eval…`・`ci-local` はそのまま、`.PHONY` も同じ並び）:
```make
check: lint test rust-check web-check  ## Lint and test everything; run before every commit (~3min)

test:  ## Test the evaluation (its checks run the CLI, built if needed)
	uv run pytest evals/tests -q

lint:  ## Lint the evaluation's, the tools' and CI's Python
	uv run ruff format --check evals/ tools/ ci/
	uv run ruff check evals/ tools/ ci/
	uv run pyright evals

format:  ## Format code
	uv run ruff format evals/ tools/ ci/
	cargo fmt --all

ci-setup:  ## Install the Python tools CI and the evaluation use
	uv sync --group ci --group dev

clean:  ## Clean build artifacts
	cargo clean
	rm -rf web/dist
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +
```
`ci/dagger_pipeline.py` を全部これにする（`rust_pipeline` と `web_pipeline` の中身は今のまま）:
```python
#!/usr/bin/env python3
"""The CI pipeline in Dagger: the Rust crates, the viewer, and the
evaluation's, tools' and CI's Python."""

import sys

import anyio
import dagger
from dagger import Config, Container, Directory

WASM_BINDGEN_VERSION = "0.2.130"


async def rust_pipeline(client: dagger.Client, source_dir: Directory) -> Container:
    """Check, test and build the Rust crates."""
    # 今の rust_pipeline の本体


async def web_pipeline(client: dagger.Client, source_dir: Directory) -> Container:
    """Build the core as WebAssembly, then check, test and build the viewer."""
    # 今の web_pipeline の本体


async def evals_pipeline(
    client: dagger.Client, source_dir: Directory, rust: Container
) -> Container:
    """Lint the Python, and test the evaluation with the CLI the Rust
    pipeline built: its checks run validate --json."""
    cli = rust.with_exec(["cargo", "build", "-p", "nichiyou-daiku-cli"]).file(
        "/src/target/debug/nichiyou-daiku"
    )
    return (
        client.container()
        .from_("python:3.13-slim")
        .with_mounted_directory("/src", source_dir)
        .with_workdir("/src")
        .with_exec(["apt-get", "update", "-qq"])
        .with_exec(
            [
                "apt-get",
                "install",
                "-y",
                "--no-install-recommends",
                "git",
                # pyright runs on this Node; the one it downloads by itself
                # fails when Node's release index lists an alpha version
                "nodejs",
            ]
        )
        .with_exec(["pip", "install", "uv"])
        .with_exec(["uv", "sync", "--group", "dev"])
        .with_file("/usr/local/bin/nichiyou-daiku", cli)
        .with_env_variable("NICHIYOU_DAIKU_BIN", "/usr/local/bin/nichiyou-daiku")
        .with_exec(["uv", "run", "ruff", "format", "--check", "evals/", "tools/", "ci/"])
        .with_exec(["uv", "run", "ruff", "check", "evals/", "tools/", "ci/"])
        .with_exec(["uv", "run", "pyright", "evals"])
        .with_exec(["uv", "run", "pytest", "evals/tests", "-q"])
    )


async def main() -> None:
    config = Config(log_output=sys.stdout)
    async with dagger.Connection(config) as client:
        source = client.host().directory(
            ".",
            exclude=[
                ".venv/",
                "__pycache__/",
                ".pytest_cache/",
                ".ruff_cache/",
                ".git/",
                "*.pyc",
                # Evaluation runs hold designs, transcripts and images
                "evals/design/runs/",
                # Rust build output
                "target/",
                # The viewer's dependencies and what it builds
                "web/node_modules/",
                "web/dist/",
                "web/src/wasm/",
            ],
        )
        rust = await rust_pipeline(client, source)
        checks = {
            "🦀 Rust": rust,
            "🌐 Viewer": await web_pipeline(client, source),
            "🐍 Evaluation": await evals_pipeline(client, source, rust),
        }
        failed = False
        for name, container in checks.items():
            print(f"\n{name}:")
            try:
                await container.stdout()
            except Exception as e:
                print(f"❌ {name} failed: {e}")
                failed = True
        if failed:
            print("\n❌ CI pipeline failed!")
            sys.exit(1)
        print("\n✅ All CI checks passed!")


if __name__ == "__main__":
    anyio.run(main)
```
`.github/workflows/ci.yml` を全部これにする:
```yaml
name: Quality Assurance Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  quality-assurance:
    name: "QA Pipeline"
    runs-on: ubuntu-latest

    steps:
      - name: 📥 Checkout Repository
        uses: actions/checkout@v4

      - name: 🐍 Setup Python for Dagger
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: 📦 Install CI Dependencies
        run: |
          pip install uv
          uv sync --group ci

      - name: 🚀 Execute Dagger Pipeline
        run: uv run python ci/dagger_pipeline.py
        env:
          DAGGER_CLOUD_TOKEN: ${{ secrets.DAGGER_CLOUD_TOKEN }}
```

- [ ] **Step 3: 環境を作り直して確かめる**

Run: `uv lock && uv sync --group dev --group ci && make check > /tmp/r6-check.log 2>&1; echo "exit=$?"; grep -E "FAILED|[1-9][0-9]* failed|^error" /tmp/r6-check.log | head`
Expected: `exit=0`、失敗の行が無い

Run: `git grep -nE "nichiyou_daiku\b|build123d|from click|import click" -- . ':!docs/superpowers' ':!crates/nichiyou-daiku-core/tests/corpus' ':!evals/design/runs' | grep -v "^tools/check_step.py" | head`
Expected: README（Task 7 で直す）と `skills/design/SKILL.md`（同）と `docs/dsl-specification.md`（同）の行だけ

Run: `make ci-local > /tmp/r6-ci.log 2>&1; echo "exit=$?"; tail -3 /tmp/r6-ci.log`
Expected: `✅ All CI checks passed!`（評価のコンテナで Rust の CLI が動かなければ（glibc の違い）、`rust:1.99-slim` と `python:3.13-slim` の Debian の版を見比べ、合わなければ評価のテストを Rust のコンテナで uv を入れて動かす形に替え、Ruling に書く）

- [ ] **Step 4: コミットする**

```bash
git add -A . && git status --short | grep -v "^D \|^M \|^R " ; git commit -m "chore: Remove the Python version"
```
（`git status` の行で、意図しないファイル（`.venv` など）が入っていないか見てからコミットする。）

---

### Task 7: ドキュメントを Rust 版にする

**Files:**
- Modify: `README.md`（全体）、`docs/dsl-specification.md`（CLI の節）、`skills/design/SKILL.md`（6 と「The CLI」）、`evals/design/README.md`
- Modify: `crates/nichiyou-daiku-cli/tests/docs.rs`・`plugin.rs`（テスト）
- Modify（git 管理外、コミットしない）: `CLAUDE.md`

- [ ] **Step 1: 落ちるテストを書く**

`docs.rs` に足す:
```rust
#[test]
fn the_docs_need_no_python() {
    // The Python version (v0.1.0) is gone: no build123d, no viz extra, no
    // install with uv but the line that points to v0.1.0
    let mut found = Vec::new();
    for path in markdown() {
        for (n, line) in fs::read_to_string(&path).unwrap().lines().enumerate() {
            let python = ["build123d", "viz extra", "[viz]", "Python API"]
                .iter()
                .any(|w| line.contains(w))
                || (line.contains("uv tool install") && !line.contains("@v0.1.0"));
            if python {
                found.push(format!("{}:{}: {line}", path.display(), n + 1));
            }
        }
    }
    assert!(found.is_empty(), "{found:#?}");
}

#[test]
fn the_readme_installs_with_install_sh() {
    let readme = fs::read_to_string(root().join("README.md")).unwrap();
    assert!(readme.contains(
        "curl -fsSL https://raw.githubusercontent.com/ar90n/nichiyou-daiku/main/install.sh | sh"
    ));
    assert!(root().join("install.sh").is_file());
}
```
`plugin.rs` に足す:
```rust
#[test]
fn the_skill_says_what_to_do_when_the_cli_cannot_be_downloaded() {
    // The entry point downloads the plugin's own CLI; when it cannot, the
    // user downloads it by hand where the message says or installs Rust
    let skill = skill();
    assert!(skill.contains("could not download"), "{skill}");
    assert!(skill.contains("https://rustup.rs"), "{skill}");
    assert!(!skill.contains("cairo"), "{skill}");
}
```

Run: `cargo test -q -p nichiyou-daiku-cli --test docs --test plugin 2>&1 | grep -E "test result|panicked"`
Expected: 3 つが落ちる

- [ ] **Step 2: DSL 仕様の CLI の節を直す**

`docs/dsl-specification.md`:
- 「Validation」の `It exits with 1 if there is any problem and does not need build123d.` を `It exits with 1 if there is any problem.` にする。
- 「### 3D View (requires build123d)」の節を全部これにする:
````markdown
### Viewer

```bash
nichiyou-daiku view furniture.nd
nichiyou-daiku view furniture.nd --host 0.0.0.0 --port 8080 --no-open
```

Opens the design in the browser viewer, served from this machine: the 3D model with its holes, the problems `validate` finds, the assembly steps and the printable manual. The page follows the file: save it and the page shows the new design, keeping its tab, step and camera. `--host` and `--port` choose where to serve (127.0.0.1 and a free port by default; 0.0.0.0 or this machine's address lets another machine's browser in), and `--no-open` prints the address without opening a browser. Ctrl-C stops it.
````
- 「### Export (requires build123d)」の節を全部これにする:
````markdown
### Export

```bash
nichiyou-daiku export furniture.nd -f stl            # furniture.stl
nichiyou-daiku export furniture.nd -f step -o model.step
```

Writes the 3D model: each piece a square-edged box with its holes (pilot, dowel, counterbore and countersink), as one binary STL or as STEP (AP214), where each piece is a part named as the design names it. The format comes from `-f` (`stl`, `step` or `stp`) or from the output file's extension; without `-o`, the file is the input's with the format's extension, and the input is never written over. A hole that runs into another one or breaks out of the side of its piece is left out of the 3D, with a warning that says how to fix it. `--fillet-radius` is accepted and ignored.
````
- `### Technical Drawing (requires build123d)`・`### Check Image (requires build123d)`・`### Assembly Steps (requires build123d)` の見出しから ` (requires build123d)` を消す。
- 「Check Image」の `Shapes are those of \`export\` and \`drawing\`, including holes and \`--fillet-radius\`.` を `Shapes are those of \`export\` and \`drawing\`, square-edged with their holes.` にする。
- 「Assembly Steps」の最後の `\`--fillet-radius\` is that of \`export\`.` を `\`--fillet-radius\` is accepted and ignored, as by \`export\`.` にする。

- [ ] **Step 3: 設計スキルを直す**

`skills/design/SKILL.md`:
- 6 の最後の文 `The first run installs build123d and can take a few minutes; tell the user.` を消す。
- 「## The CLI」の節を全部これにする:
```markdown
## The CLI

`nichiyou-daiku` runs this plugin's own version of the CLI, which it downloads the first time (a few seconds; tell the user). If it says it could not download it, tell the user what it said: they can download the CLI by hand from the release it names and put it where it says, or install Rust (https://rustup.rs) so that it builds the CLI from the plugin's source; then run the command again.
```

- [ ] **Step 4: README を書き直す**

`README.md` を全部これにする（「Viewer」の節の 3 段落目以降、Steps タブ・Dimensions・Drawing・Manual の説明は今の文のまま入れる）:
````markdown
# nichiyou-daiku (日曜大工)

[![Quality Assurance](https://github.com/ar90n/nichiyou-daiku/actions/workflows/ci.yml/badge.svg)](https://github.com/ar90n/nichiyou-daiku/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
![Built with vibe coding](https://img.shields.io/badge/built%20with-vibe%20coding-ff69b4)

A domain-specific CAD system for DIY woodworking, built on the [MO-CAD (Manufacturing Oriented CAD)](https://caddi.tech/archives/4104) concept. Design furniture using a simple DSL that represents real-world construction techniques with standard lumber sizes.

Following the "Worse Is Better" philosophy, nichiyou-daiku prioritizes practical usability over theoretical perfection, making it easy to design and build furniture that can actually be constructed with common tools and materials.

## Quick Example

A corner joint of two 2x4s, written in the DSL:

```nd
(corner_piece_a:2x4 =400)
(corner_piece_b:2x4 =400)

corner_piece_a -[TF<0 BD<0]- corner_piece_b
```

```bash
nichiyou-daiku validate corner.nd            # syntax, placement, overlaps, fasteners
nichiyou-daiku report corner.nd -o report.md # bill of materials, shopping list, cut list
nichiyou-daiku view corner.nd                # the 3D model, the steps and the manual in your browser
nichiyou-daiku export corner.nd -f step      # 3D model (STEP or STL)
nichiyou-daiku drawing corner.nd             # technical drawing PDF with dimensions
nichiyou-daiku render corner.nd              # check image PNG, four labelled views
nichiyou-daiku steps corner.nd               # assembly steps: Markdown, part drawings and step images
```

See [`examples/nd_files/`](examples/nd_files/) for complete designs, such as a table written with variables ([`simple_table_parametric.nd`](examples/nd_files/simple_table_parametric.nd)) and one whose apron length is solved from the legs ([`simple_table_unknowns.nd`](examples/nd_files/simple_table_unknowns.nd)).

## Features

- 📝 A small DSL for furniture: pieces, connections, variables and arithmetic
- 🧩 Unknown lengths (`=?`) and sliding connections (`?` offsets) solved from the other connections
- 📐 Exact placement from all connections at once; contradictions and overlaps are reported
- 🔩 Dowels and screws laid out in the contact area, with preset sizes, counterbores and countersinks
- 📑 Markdown reports: bill of materials, shopping list with hardware and drill bits, cut list for your store's board lengths and saw kerf
- 🖼️ Technical drawings, check images and assembly instructions with a drawing of each drilled part
- 🎯 STL and STEP export with every hole
- 🌐 A browser viewer: the 3D model, the assembly steps and a printable manual
- 🪵 Standard lumber: 1x4, 1x6, 1x8, 2x2, 2x4, 2x6
- 📦 One executable for Linux, macOS and Windows

## Use with Claude Code

Add this repository as a plugin marketplace and install the plugin:

```text
/plugin marketplace add ar90n/nichiyou-daiku
/plugin install nichiyou-daiku@nichiyou-daiku
```

Then ask for furniture, e.g. "Design a 500 x 400 x 600 side table from 2x4". The `nichiyou-daiku:design` skill writes the `.nd` file, checks it with the CLI until it is sound and reports the size and the lumber to buy. The plugin downloads its own version of the CLI from this repository's releases the first time (a few seconds).

## Installation

On Linux and macOS (x86_64 or arm64):

```bash
curl -fsSL https://raw.githubusercontent.com/ar90n/nichiyou-daiku/main/install.sh | sh
```

It installs the newest release's CLI into `~/.local/bin`, checked against the release's checksums, and says if that folder is not on your PATH. `--version 0.2.0` installs another version and `--to <folder>` another place (`... | sh -s -- --to ~/bin`). Run it again to update. On Windows, download `nichiyou-daiku-<version>-x86_64-pc-windows-msvc.zip` from the [releases](https://github.com/ar90n/nichiyou-daiku/releases) and put `nichiyou-daiku.exe` on your PATH. `nichiyou-daiku --version` tells which version you have.

If you installed the Python version with uv, remove it: `uv tool uninstall nichiyou-daiku`. It stays available, with its Python API, as v0.1.0: `uv tool install "git+https://github.com/ar90n/nichiyou-daiku@v0.1.0"`.

To build it from source, with Rust and Node.js 24 or later:

```bash
git clone https://github.com/ar90n/nichiyou-daiku.git
cd nichiyou-daiku
make web                                        # the viewer that view serves
cargo install --path crates/nichiyou-daiku-cli
```

## Viewer

`nichiyou-daiku view design.nd` opens the design in your browser, served from your machine: the 3D model with its holes, what `validate` finds and the source beside it. The page follows the file as you save it. Nothing leaves your machine.

The viewer is also a static site: `make web` builds it into `web/dist` (`make web-dev` serves it while you work on it). Open a file with **Open** or by dropping it on the page, or open a URL: `?src=<URL of an .nd>` opens it when the page loads, so the address can be shared. The server must let other sites read the file; on GitHub, use the raw file (`raw.githubusercontent.com`) or a gist's raw URL. The `Viewer on GitHub Pages` workflow publishes the viewer when started by hand (choose "GitHub Actions" as the Pages source first).

（今の README の「The **Steps** tab …」から「… **Print** puts just those pages on paper.」までの 5 段落をここに入れる）

## Documentation

- [DSL specification](docs/dsl-specification.md): pieces, faces and offsets, connections, variables, unknowns, fasteners, CLI, grammar, errors
- [Design skill](skills/design/SKILL.md): the Claude Code skill that designs furniture and checks it with the CLI

## Development

```bash
git clone https://github.com/ar90n/nichiyou-daiku.git
cd nichiyou-daiku
uv sync --group dev --group ci   # the Python of the evaluation and CI

make check             # Rust, the viewer and the evaluation; run before every commit
make ci-local          # the full CI pipeline in Dagger; run before merging into main or pushing
make format
ND_BLESS=1 cargo test  # after changing what the CLI prints: rewrite the golden files, then review the diff
```

To release, push a tag `v<version>` with the version in `Cargo.toml`: the Release workflow builds the CLI for five systems into a draft release. Publish it after checking it, and before that version reaches main, since the plugin downloads its own version.

Design decisions are recorded in [`docs/superpowers/specs/`](docs/superpowers/specs/).

## Contributing

1. Fork the repository and create a feature branch
2. Write tests first (TDD), then implement
3. Run `make check`
4. Open a pull request titled `<type>: <description>`, where type is one of `feat`, `fix`, `docs`, `refactor`, `style`, `chore` or `test`

## License

Apache 2.0 License - see LICENSE file for details
````

- [ ] **Step 5: 評価の README と CLAUDE.md**

`evals/design/README.md` の使い方のコマンドの後に足す:
```markdown
Each evaluation builds the CLI with cargo from a copy of the plugin (later ones build only what changed) and runs the agent with it: the plugin's entry point runs the CLI that `NICHIYOU_DAIKU_BIN` names. The checks read the designs with the same CLI (`validate --json`). Install Rust (https://rustup.rs) to run it.
```
（README に uv で CLI を作る説明があれば消す。）

`CLAUDE.md`（git 管理外）を全部これにする:
````markdown
# CLAUDE.md — nichiyou-daiku（日曜大工）

DIY 木工 CAD。SPF 材（1x4・1x6・1x8・2x2・2x4・2x6）の部材を「接続のグラフ」で表し、配置・留め具・木取り・
レポート・3D（STL/STEP）・図面・組み立て手順を出す。家具は `.nd`（DSL）で書く。Rust の CLI と、ブラウザの
ビューアー（WASM）と、Claude Code のプラグイン（設計スキル）。開発はエージェント前提。

## コマンド

```bash
make check             # Rust（fmt・clippy・test・WASM）・web（型・テスト・ビルド）・評価の lint とテスト。コミット前に必ず
make ci-local          # Dagger で CI 全体（4〜5分）。main に入れる前・push 前に必ず（先に make ci-setup）
make format
ND_BLESS=1 cargo test  # 動きを変えたら正解ファイルを書き直し、差分を読んで意図どおりか確かめる
make web-dev           # ビューアーを手元で開く
cargo run -q -p nichiyou-daiku-cli -- validate|report|render|steps|drawing|export|view design.nd
```

## 決まり

- コミットと push はユーザーに頼まれたときだけ。main で直接作業せずブランチを切る。
- ドットファイル（`.claude/` など）はコミットしない（例外: `.github/` と、プラグインの `.claude-plugin/`）。この CLAUDE.md も git 管理外。
- TDD: テストが正しい理由で落ちるのを見てから実装する。
- 設計の判断は `docs/superpowers/specs/YYYY-MM-DD-*-design.md` に「決定と理由」で残す。実行済みの計画書は残さない。
- コメントは最小限・英語・Why を書く。エラーメッセージは「何が悪く、どう直すか」を書く。
- 正解ファイル（`crates/nichiyou-daiku-core/tests/corpus/`、`crates/nichiyou-daiku-cli/tests/cli/`）は Rust の出力。書き直したら差分を読む。
- 複数エージェントで並行作業するときは git worktree を分ける（同じツリーだと変更が混ざる）。
- opencode を使うときは `opencode-go/…` だけ（サブスク）。

## 構成と責務

- `crates/nichiyou-daiku-core`（純粋な計算。serde だけに頼り、WASM でも動く）
  - `piece.rs`: 材種と断面。唯一の表で、DSL の文法・エラーの候補・既定の定尺はここから作る。`presets.rs`: ダボとねじ
  - `dsl/`: 自前の字句解析とパーサー、変数と式、エラーの文
  - `anchor.rs`・`connection.rs`: アンカーと接続、その検証
  - `model.rs`（部材と接続、1 ペア 1 接続）、`placement.rs`（配置ソルバー）、`resolve.rs`（未知数 `=?`・`?` を解く）
  - `assembly.rs`: `Assembly::of` が未知数の解決・配置・留め具・下穴・座掘り・皿取りをまとめる
  - `steps.rs`（組み立て手順）、`parts.rs`（部品と部品図の題名）、`dimensioning.rs`（寸法の区切り）、`cutting.rs`（木取り）、`resources.rs`（レポートの中身）、`diagnostics.rs`（`validate --json` とビューアーの JSON）
- `crates/nichiyou-daiku-drawing`: 隠れ線、部品図・手順の図・確認の絵・図面（SVG）。字幅の表
- `crates/nichiyou-daiku-export`: 3D（箱と穴の B-rep、STL、STEP）
- `crates/nichiyou-daiku-wasm`: ビューアー向けの WASM
- `crates/nichiyou-daiku-cli`: CLI（clap）。PNG（resvg）・PDF（svg2pdf）・`view` のサーバー（`web/dist` を組み込む）。入出力とエラー表示
- `web/`: ブラウザのビューアー（Vite・TypeScript・three.js）
- プラグイン: `.claude-plugin/`、`skills/design/`（設計スキル）、`bin/nichiyou-daiku`（プラグインと同じ版を Releases から落とす。`install.sh` と同じ処理）
- 開発の道具（Python・uv）: `evals/design`（設計スキルの評価。設計は CLI の `validate --json` で確かめる）、`ci/dagger_pipeline.py`、`tools/check_step.py`（STEP を OpenCASCADE で読み直す）

## 設計の原則

- 全接続を同時に厳密に解く（最小二乗はしない）。回転は 90° 刻み、位置はワールド軸ごとの差分制約（重み付き Union-Find）。
  長さ方向の軸では各部材の下端・上端を別の点にし、既知の長さで結ぶ。
- 矛盾は先に宣言した接続を優先し、矛盾した拘束だけを報告する。`validate` はエラー、ほかのコマンドは警告して続行
  （レポートには Warnings 節）。
- 面: top/down は木口、front/back は幅の面、left/right は厚みの面。`FromMin`（`<`）は down/left/back 側から測る。
- 留め具は接触面の重なりに自動で置く（短辺の中央、長辺の 1/4・3/4 か中央に 1 本）。穴は部材を貫通させない。
  部材の中で穴がぶつかれば報告する。
- 未知数は解いて数値のモデルにする（`dsl::parse` と `Assembly::of` が自動で行う）。下流は数値のモデルだけを扱う。
  検証は未知の値を使う検査だけを飛ばし（`shape_for_checks`）、解いた後にすべて走り直す。

## ドキュメントの置き場所

- DSL と CLI: `docs/dsl-specification.md`（英語のみで正本）
- 設計スキル: `skills/design/SKILL.md`（手順）、`patterns.md`（作例と規則）
- 例: `examples/nd_files/*.nd`（`simple_table_parametric.nd` は変数、`simple_table_unknowns.nd` は未知数）
- 機能を足したら DSL 仕様と、作例を変えるなら `patterns.md` を直す。例・表・リンクは `crates/nichiyou-daiku-cli/tests/docs.rs` が確かめる

## リリース

- 版は `Cargo.toml` の `[workspace.package] version`。`v<版>` のタグを push すると `release.yml` が 5 つの OS 向けを下書きのリリースに置く。確かめて公開してから、その版を main に入れる（プラグインは自分の版を落とす）。

## ロードマップ

経緯と詳細はメモリ（`~/workspace/memory/projects/nichiyou-daiku.md`）。
````

- [ ] **Step 6: 通るのを確かめる**

Run: `cargo test -q -p nichiyou-daiku-cli --test docs --test plugin 2>&1 | grep "test result"`
Expected: 通る（`the_skill_reads_the_specification_up_to_its_complete_examples` も。CLI の節は 487 行目より後なので行数は変わらない）

- [ ] **Step 7: コミットする**

```bash
make check && git add README.md docs skills evals crates && git commit -m "docs: Describe the Rust version"
```

---

### Task 8: 仕上げ

- [ ] **Step 1:** `make ci-local` が通ることを確かめ、ledger に書く。
- [ ] **Step 2:** 最終レビュー: fable（Agent、model fable、作業用は `/tmp/nd-fable-scratch-<HEAD7>`）と deepseek（`opencode run -m opencode-go/deepseek-v4.1-flash --agent plan`、`opencode-go/` 以外は使わない）。deepseek の作業ツリーは `/tmp/nd-deepseek-review-<HEAD7>` で、資料（差分・計画・ledger・指示）はその中の `.review/` に置く（plan エージェントは作業ツリーの外を読めない）。読むだけと伝え、「必ず結論で終える」を足す。結論を書かずに終わったら `opencode run -c … "Stop reading: make no more tool calls. Write your review now…"`。差分は正解ファイルと `Cargo.lock`・`uv.lock` を除いたもの。Review Focus を渡す。Critical と Important を TDD で直す。
- [ ] **Step 3:** ユーザーに確かめてもらう: 評価の self-check（Task 4 の Step 6 で動かしていなければ。Claude を使う）、README の入れ方の説明、`nichiyou-daiku view` で開く（Tailscale 経由）。
- [ ] **Step 4:** superpowers:finishing-a-development-branch で `next` に入れる。

### Task 9: 届ける（その都度ユーザーに頼んでから）

- [ ] **Step 1: Python 版にタグを付ける**

ユーザーに頼んでから:
```bash
git tag -a v0.1.0 6868f53 -m "nichiyou-daiku 0.1.0: the Python version"
git push origin v0.1.0
```

- [ ] **Step 2: Rust 版のリリースを作る**

ユーザーに頼んでから:
```bash
git tag -a v0.2.0 next -m "nichiyou-daiku 0.2.0: the Rust version"
git push origin v0.2.0
gh run list --workflow release.yml --limit 1
gh run watch "$(gh run list --workflow release.yml --limit 1 --json databaseId -q '.[0].databaseId')"
gh release view v0.2.0 --json isDraft,assets -q '.isDraft, (.assets[].name)'
```
Expected: 下書きのリリースに 5 つのアーカイブと `SHA256SUMS`。ユーザーが中身を確かめて公開する（ユーザーが頼めば `gh release edit v0.2.0 --draft=false`）。

- [ ] **Step 3: 公開されたリリースで確かめる**

```bash
curl -fsSL https://raw.githubusercontent.com/ar90n/nichiyou-daiku/v0.2.0/install.sh | sh -s -- --to /tmp/nd-install-check
/tmp/nd-install-check/nichiyou-daiku --version
XDG_CACHE_HOME=$(mktemp -d) sh bin/nichiyou-daiku --version
```
Expected: 両方 `nichiyou-daiku 0.2.0`（入口は `downloaded v0.2.0 for …` も出す）

- [ ] **Step 4: main を入れ替える**

ユーザーに頼んでから:
```bash
git checkout main && git merge --ff-only next && git push origin main
gh run watch "$(gh run list --workflow ci.yml --branch main --limit 1 --json databaseId -q '.[0].databaseId')"
curl -fsSL https://raw.githubusercontent.com/ar90n/nichiyou-daiku/main/install.sh | sh -s -- --to /tmp/nd-install-main
```
Expected: main の CI が通る、main の `install.sh` で 0.2.0 が入る。

- [ ] **Step 5: 片付け**

ユーザーにリモートの `next` と `next-r4c-distribution` を消してもらう（`git push origin --delete` は私からはできない）。メモリ（`~/workspace/memory/projects/nichiyou-daiku.md`）に R6 の完了を書く。
