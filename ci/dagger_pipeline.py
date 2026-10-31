#!/usr/bin/env python3
"""Dagger CI pipeline for nichiyou-daiku project."""

import sys
from typing import Optional

import anyio
import dagger
from dagger import Config, Container, Directory


async def test_pipeline(
    client: dagger.Client,
    source_dir: Directory,
    python_version: str = "3.11",
) -> Container:
    """Run tests with pytest and coverage."""
    python = (
        client.container()
        .from_(f"python:{python_version}-slim")
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
                "libgl1-mesa-dev",
                "libcairo2-dev",
            ]
        )
        .with_exec(["pip", "install", "--upgrade", "pip"])
        .with_exec(["pip", "install", "uv"])
        .with_exec(["uv", "sync", "--dev", "--all-extras"])
    )

    # Run pytest with coverage
    test_result = python.with_exec(
        [
            "uv",
            "run",
            "pytest",
            "src/",
            "tests/",
            "--doctest-modules",
            "--cov=nichiyou_daiku",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "--cov-fail-under=90",  # Fail if coverage is less than 90%
            "-v",
        ]
    )

    return test_result


async def lint_pipeline(
    client: dagger.Client,
    source_dir: Directory,
    python_version: str = "3.11",
) -> Container:
    """Run linting and type checking."""
    python = (
        client.container()
        .from_(f"python:{python_version}-slim")
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
                "libgl1-mesa-dev",
                "libcairo2-dev",
                # pyright runs on this Node; the one it downloads by itself
                # fails when Node's release index lists an alpha version
                "nodejs",
            ]
        )
        .with_exec(["pip", "install", "--upgrade", "pip"])
        .with_exec(["pip", "install", "uv"])
        .with_exec(["uv", "sync", "--dev", "--all-extras"])
    )

    # Run ruff format
    format_check = python.with_exec(
        ["uv", "run", "ruff", "format", "--check", "src/", "tests/", "evals/"]
    )

    # Run ruff
    ruff_check = format_check.with_exec(
        ["uv", "run", "ruff", "check", "src/", "tests/", "evals/"]
    )

    # Run pyright
    pyright_check = ruff_check.with_exec(
        ["uv", "run", "pyright", "src/nichiyou_daiku", "evals"]
    )

    return pyright_check


async def rust_pipeline(client: dagger.Client, source_dir: Directory) -> Container:
    """Check, test and build the Rust crates (the next generation)."""
    return (
        client.container()
        .from_("rust:1.99-slim")
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


WASM_BINDGEN_VERSION = "0.2.130"


async def web_pipeline(client: dagger.Client, source_dir: Directory) -> Container:
    """Build the core as WebAssembly, then check, test and build the viewer."""
    wasm = (
        client.container()
        .from_("rust:1.99-slim")
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


async def build_pipeline(
    client: dagger.Client,
    source_dir: Directory,
    python_version: str = "3.11",
) -> Container:
    """Build the package."""
    python = (
        client.container()
        .from_(f"python:{python_version}-slim")
        .with_mounted_directory("/src", source_dir)
        .with_workdir("/src")
        .with_exec(["apt-get", "update", "-qq"])
        .with_exec(["apt-get", "install", "-y", "--no-install-recommends", "git"])
        .with_exec(["pip", "install", "--upgrade", "pip"])
        .with_exec(["pip", "install", "uv", "build"])
        .with_exec(["uv", "sync"])
    )

    # Build the package
    build_result = python.with_exec(["python", "-m", "build"])

    return build_result


async def main(
    python_versions: Optional[list[str]] = None,
) -> None:
    """Main CI pipeline orchestrator."""
    if python_versions is None:
        python_versions = ["3.13"]

    config = Config(log_output=sys.stdout)

    async with dagger.Connection(config) as client:
        # Get source directory
        source = client.host().directory(
            ".",
            exclude=[
                ".venv/",
                "dist/",
                "build/",
                "*.egg-info/",
                "__pycache__/",
                ".pytest_cache/",
                ".mypy_cache/",
                ".ruff_cache/",
                ".git/",
                "*.pyc",
                ".coverage",
                "coverage.xml",
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

        # Run pipelines for each Python version
        test_results = []
        lint_results = []
        build_results = []

        for py_version in python_versions:
            print(f"\n🐍 Running CI for Python {py_version}")

            # Run tests
            print("  📋 Running tests...")
            test_result = await test_pipeline(client, source, py_version)
            test_results.append(test_result)

            # Run linting (only on one version to save time)
            if py_version == python_versions[0]:
                print("  🔍 Running linting...")
                lint_result = await lint_pipeline(client, source, py_version)
                lint_results.append(lint_result)

            # Build package
            print("  📦 Building package...")
            build_result = await build_pipeline(client, source, py_version)
            build_results.append(build_result)

        print("\n🦀 Checking the Rust crates...")
        rust_result = await rust_pipeline(client, source)

        print("\n🌐 Checking the viewer...")
        web_result = await web_pipeline(client, source)

        # Execute all pipelines
        print("\n🚀 Executing all pipelines...")

        has_failures = False

        print("\n🦀 Rust results:")
        try:
            await rust_result.stdout()
        except Exception as e:
            print(f"❌ Rust checks failed: {e}")
            has_failures = True

        print("\n🌐 Viewer results:")
        try:
            await web_result.stdout()
        except Exception as e:
            print(f"❌ Viewer checks failed: {e}")
            has_failures = True

        # Execute test results
        for i, (py_version, test_result) in enumerate(
            zip(python_versions, test_results)
        ):
            print(f"\n📋 Test results for Python {py_version}:")
            try:
                await test_result.stdout()
                # Export coverage.xml for GitHub Actions
                await test_result.file("/src/coverage.xml").export("./coverage.xml")
            except Exception as e:
                print(f"❌ Tests failed for Python {py_version}: {e}")
                has_failures = True

        # Execute linting results
        if lint_results:
            print("\n🔍 Linting results:")
            try:
                await lint_results[0].stdout()
            except Exception as e:
                print(f"❌ Linting failed: {e}")
                has_failures = True

        # Execute build results
        for i, (py_version, build_result) in enumerate(
            zip(python_versions, build_results)
        ):
            print(f"\n📦 Build results for Python {py_version}:")
            try:
                await build_result.stdout()
                # Export built artifacts
                dist_dir = build_result.directory("/src/dist")
                await dist_dir.export(f"./dist-py{py_version}")
            except Exception as e:
                print(f"❌ Build failed for Python {py_version}: {e}")
                has_failures = True

        if has_failures:
            print("\n❌ CI pipeline failed!")
            sys.exit(1)
        else:
            print("\n✅ All CI checks passed!")


if __name__ == "__main__":
    # Parse command line arguments
    python_versions = None
    if len(sys.argv) > 1:
        python_versions = sys.argv[1].split(",")

    anyio.run(main, python_versions)
