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
        .with_exec(["apt-get", "install", "-y", "--no-install-recommends", "git"])
        .with_exec(["pip", "install", "--upgrade", "pip"])
        .with_exec(["pip", "install", "uv"])
        .with_exec(["uv", "sync", "--dev", "--no-install-project-extras"])
    )
    
    # Run docstring tests
    doctest_result = python.with_exec([
        "uv", "run", "python", "-m", "doctest",
        "src/nichiyou_daiku/core/piece.py",
        "-v"
    ])
    
    # Run pytest with coverage
    test_result = doctest_result.with_exec([
        "uv", "run", "pytest", 
        "tests/",
        "--cov=nichiyou_daiku",
        "--cov-report=term-missing",
        "--cov-report=xml",
        "--cov-fail-under=90",  # Fail if coverage is less than 90%
        "-v"
    ])
    
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
        .with_exec(["apt-get", "install", "-y", "--no-install-recommends", "git"])
        .with_exec(["pip", "install", "--upgrade", "pip"])
        .with_exec(["pip", "install", "uv"])
        .with_exec(["uv", "sync", "--dev", "--no-install-project-extras"])
    )
    
    # Run black check
    black_check = python.with_exec([
        "uv", "run", "black", 
        "--check", 
        "src/", 
        "tests/"
    ])
    
    # Run ruff
    ruff_check = black_check.with_exec([
        "uv", "run", "ruff", 
        "check", 
        "src/", 
        "tests/"
    ])
    
    # Run mypy
    mypy_check = ruff_check.with_exec([
        "uv", "run", "mypy", 
        "src/nichiyou_daiku"
    ])
    
    return mypy_check


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
        .with_exec(["uv", "sync", "--no-install-project-extras"])
    )
    
    # Build the package
    build_result = python.with_exec([
        "python", "-m", "build"
    ])
    
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
        source = client.host().directory(".", exclude=[
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
        ])
        
        # Run pipelines for each Python version
        test_results = []
        lint_results = []
        build_results = []
        
        for py_version in python_versions:
            print(f"\n🐍 Running CI for Python {py_version}")
            
            # Run tests
            print(f"  📋 Running tests...")
            test_result = await test_pipeline(client, source, py_version)
            test_results.append(test_result)
            
            # Run linting (only on one version to save time)
            if py_version == python_versions[0]:
                print(f"  🔍 Running linting...")
                lint_result = await lint_pipeline(client, source, py_version)
                lint_results.append(lint_result)
            
            # Build package
            print(f"  📦 Building package...")
            build_result = await build_pipeline(client, source, py_version)
            build_results.append(build_result)
        
        # Execute all pipelines
        print("\n🚀 Executing all pipelines...")
        
        has_failures = False
        
        # Execute test results
        for i, (py_version, test_result) in enumerate(zip(python_versions, test_results)):
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
        for i, (py_version, build_result) in enumerate(zip(python_versions, build_results)):
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