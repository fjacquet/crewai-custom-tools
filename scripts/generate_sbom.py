#!/usr/bin/env python3
"""Generates a standardized CycloneDX JSON Software Bill of Materials (SBOM)."""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ImportError:
    import pip._vendor.tomli as tomllib


def get_package_version(name: str) -> str:
    """Retrieve installed version of a package, falling back to a default."""
    try:
        import importlib.metadata
        return importlib.metadata.version(name)
    except Exception:
        return "latest"


def dep_url_to_name(dep: str) -> str:
    """Helper to extract clean name (e.g. 'requests>=2.31.0' -> 'requests')."""
    return dep.split(">=")[0].split("<")[0].split("==")[0].strip().split("[")[0]


def dep_ver_cleanup(dep: str) -> str:
    """Helper to extract clean version constraint or installed version."""
    name = dep_url_to_name(dep)
    installed = get_package_version(name)
    if installed != "latest":
        return installed
    parts = dep.split(">=")
    if len(parts) > 1:
        return parts[1].strip()
    return "latest"


def generate_sbom(project_dir: Path) -> dict:
    """Generate a valid CycloneDX JSON v1.5 SBOM."""
    pyproject_path = project_root = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        pyproject_path = project_dir / "pyproject.toml"

    if not pyproject_path.exists():
        print(f"Error: pyproject.toml not found in {project_dir}", file=sys.stderr)
        sys.exit(1)

    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    project = config.get("project", {})
    name = project.get("name", "crew-custom-tools")
    version = project.get("version", "0.1.0")
    description = project.get("description", "")
    dependencies = project.get("dependencies", [])

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": {
                "name": name,
                "version": version,
                "type": "library",
                "bom-ref": f"pkg:pypi/{name}@{version}",
                "description": description,
                "licenses": [
                    {"license": {"id": "MIT"}}
                ]
            }
        },
        "components": []
    }

    # Add core dependencies to the SBOM components list
    for dep in dependencies:
        clean_dep_name = dep_url_to_name(dep)
        clean_ver = dep_ver_cleanup(dep)
        
        comp_dict = {
            "name": clean_dep_name,
            "version": clean_ver,
            "type": "library",
            "purl": f"pkg:pypi/{clean_dep_name}@{clean_ver}",
            "bom-ref": f"pkg:pypi/{clean_dep_name}@{clean_ver}"
        }
        sbom["components"].append(comp_dict)

    return sbom


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    sbom_data = generate_sbom(root)
    
    output_path = root / "sbom.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sbom_data, f, indent=2)
    print(f"Successfully generated SBOM at {output_path}")
