#!/usr/bin/env python3
"""The CI pipeline in Dagger: the Rust crates, the viewer, and the
evaluation's, tools' and CI's Python."""

import sys

import anyio
import dagger
from dagger import Config, Container, Directory

WASM_BINDGEN_VERSION = "0.2.130"
# One Debian release for both: the evaluation runs the CLI the Rust image
# builds, which needs the C library it was linked against
RUST_IMAGE = "rust:1.99-slim-trixie"
PYTHON_IMAGE = "python:3.13-slim-trixie"


async def rust_pipeline(client: dagger.Client, source_dir: Directory) -> Container:
    """Check, test and build the Rust crates (the next generation)."""
    return (
        client.container()
        .from_(RUST_IMAGE)
        .with_mounted_directory("/src", source_dir)
        .with_workdir("/src")
        .with_exec(["rustup", "component", "add", "rustfmt", "clippy"])
        .with_exec(["rustup", "target", "add", "wasm32-unknown-unknown"])
        .with_exec(["cargo", "fmt", "--all", "--check"])
        .with_exec(["cargo", "clippy", "--all-targets", "--", "-D", "warnings"])
        .with_exec(["cargo", "test"])
        .with_exec(
            [
                "cargo",
                "build",
                "-p",
                "nichiyou-daiku-core",
                "--target",
                "wasm32-unknown-unknown",
            ]
        )
    )


async def web_pipeline(client: dagger.Client, source_dir: Directory) -> Container:
    """Build the core as WebAssembly, then check, test and build the viewer."""
    wasm = (
        client.container()
        .from_(RUST_IMAGE)
        .with_mounted_directory("/src", source_dir)
        .with_workdir("/src")
        # Compiling wasm-bindgen's CLI takes minutes; keep it between runs
        .with_mounted_cache(
            "/opt/wasm-bindgen",
            client.cache_volume(f"wasm-bindgen-cli-{WASM_BINDGEN_VERSION}"),
        )
        .with_exec(["rustup", "target", "add", "wasm32-unknown-unknown"])
        .with_exec(
            [
                "cargo",
                "install",
                "wasm-bindgen-cli",
                "--version",
                WASM_BINDGEN_VERSION,
                "--locked",
                "--root",
                "/opt/wasm-bindgen",
            ]
        )
        .with_exec(
            [
                "cargo",
                "build",
                "-p",
                "nichiyou-daiku-wasm",
                "--target",
                "wasm32-unknown-unknown",
                "--release",
            ]
        )
        .with_exec(
            [
                "/opt/wasm-bindgen/bin/wasm-bindgen",
                "--target",
                "web",
                "--out-dir",
                "web/src/wasm",
                "target/wasm32-unknown-unknown/release/nichiyou_daiku_wasm.wasm",
            ]
        )
    )
    return (
        client.container()
        .from_("node:24-slim")
        .with_directory("/src", source_dir)
        .with_directory("/src/web/src/wasm", wasm.directory("/src/web/src/wasm"))
        .with_workdir("/src/web")
        .with_exec(["npm", "ci", "--no-audit", "--no-fund"])
        .with_exec(["npm", "run", "typecheck"])
        .with_exec(["npm", "test"])
        .with_exec(["npm", "run", "build"])
    )


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
        .from_(PYTHON_IMAGE)
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
        .with_exec(
            ["uv", "run", "ruff", "format", "--check", "evals/", "tools/", "ci/"]
        )
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
            except dagger.ExecError as e:
                # What the command said, or the log shows only its exit code
                said = (e.stderr or e.stdout)[-6000:]
                print(f"❌ {name} failed: {e}\n{said}")
                failed = True
            except Exception as e:
                print(f"❌ {name} failed: {e}")
                failed = True
        if failed:
            print("\n❌ CI pipeline failed!")
            sys.exit(1)
        print("\n✅ All CI checks passed!")


if __name__ == "__main__":
    anyio.run(main)
