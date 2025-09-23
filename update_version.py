#!/usr/bin/env python3
"""
Version update script for reforge-python SDK.
Updates both VERSION file and pyproject.toml to keep them in sync.

Usage:
    python update_version.py 0.13.0
    python update_version.py --current  # Show current version
"""

import argparse
import re
import sys
from pathlib import Path


def get_current_version():
    """Get current version from VERSION file."""
    version_file = Path(__file__).parent / "sdk_reforge" / "VERSION"
    try:
        return version_file.read_text().strip()
    except FileNotFoundError:
        return "unknown"


def update_version_file(new_version: str):
    """Update the VERSION file."""
    version_file = Path(__file__).parent / "sdk_reforge" / "VERSION"
    version_file.write_text(new_version + "\n")
    print(f"✓ Updated {version_file}")


def update_pyproject_toml(new_version: str):
    """Update the version in pyproject.toml."""
    toml_file = Path(__file__).parent / "pyproject.toml"
    content = toml_file.read_text()

    # Update version line
    updated_content = re.sub(
        r'^version = ".*"$',
        f'version = "{new_version}"',
        content,
        flags=re.MULTILINE
    )

    if content == updated_content:
        print(f"⚠ No version found in {toml_file}")
        return False

    toml_file.write_text(updated_content)
    print(f"✓ Updated {toml_file}")
    return True


def validate_version(version: str) -> bool:
    """Validate version format (semantic versioning)."""
    pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9\-\.]+)?$'
    return bool(re.match(pattern, version))


def main():
    parser = argparse.ArgumentParser(description="Update reforge-python SDK version")
    parser.add_argument("version", nargs="?", help="New version number (e.g., 0.13.0)")
    parser.add_argument("--current", action="store_true", help="Show current version")

    args = parser.parse_args()

    if args.current:
        current = get_current_version()
        print(f"Current version: {current}")
        return

    if not args.version:
        print("Error: Version number required (or use --current)")
        print("Usage: python update_version.py 0.13.0")
        sys.exit(1)

    new_version = args.version.strip()

    if not validate_version(new_version):
        print(f"Error: Invalid version format '{new_version}'")
        print("Expected format: MAJOR.MINOR.PATCH (e.g., 0.13.0)")
        sys.exit(1)

    current = get_current_version()
    print(f"Updating version: {current} → {new_version}")

    try:
        update_version_file(new_version)
        update_pyproject_toml(new_version)
        print(f"\n✅ Successfully updated to version {new_version}")
        print("\nDon't forget to:")
        print("1. Commit the changes")
        print("2. Tag the release: git tag v" + new_version)
        print("3. Push with tags: git push --tags")
    except Exception as e:
        print(f"\n❌ Error updating version: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()