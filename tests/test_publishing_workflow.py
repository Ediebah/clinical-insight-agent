"""Guard the proposed release workflow's authorization and artifact boundaries."""
import os
import re
import subprocess
from pathlib import Path

import yaml


def _workflow():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/publish.yml"
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


def test_publishing_is_manual_and_separates_oidc_from_the_build():
    workflow = _workflow()
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    build = workflow["jobs"]["build-and-verify"]
    publish = workflow["jobs"]["publish"]
    assert "permissions" not in build
    assert publish["needs"] == "build-and-verify"
    assert publish["environment"] == "pypi"
    assert publish["permissions"] == {"id-token": "write"}
    for job in (build, publish):
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])


def test_candidate_build_checks_reviewed_source_artifacts_and_runs_tests():
    workflow = _workflow()
    dispatch = workflow["on"]["workflow_dispatch"]["inputs"]
    assert dispatch["package"]["options"] == ["caveat", "clinical-insight-assurance"]
    assert dispatch["approval"]["required"] == "true"
    steps = workflow["jobs"]["build-and-verify"]["steps"]
    assert steps[0]["with"]["ref"] == "0dff8a848724c08a23ecae6c3a9ad14f08ffc22d"
    assert steps[0]["with"]["persist-credentials"] == "false"
    script = steps[2]["run"]
    assert "PUBLISH REVIEWED ARTIFACTS" in script
    assert "sha256sum -c -" in script
    assert "-m pytest" in script
    assert "*) echo 'Unsupported package'" in script


def test_build_refuses_missing_approval_and_unknown_package(tmp_path):
    script = _workflow()["jobs"]["build-and-verify"]["steps"][2]["run"]
    for package, approval in (
        ("caveat", "not approved"),
        ("unexpected", "PUBLISH REVIEWED ARTIFACTS"),
    ):
        result = subprocess.run(
            ["bash", "-c", script],
            cwd=tmp_path,
            env={**os.environ, "PACKAGE": package, "APPROVAL": approval},
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0
        assert not (tmp_path / "dist").exists()


def test_prepublication_check_refuses_tampered_or_extra_files(tmp_path):
    script = _workflow()["jobs"]["publish"]["steps"][1]["run"]
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "caveat-0.1.2-py3-none-any.whl").write_text("tampered")
    (dist / "caveat-0.1.2.tar.gz").write_text("tampered")
    env = {**os.environ, "PACKAGE": "caveat"}
    result = subprocess.run(
        ["bash", "-c", script], cwd=tmp_path, env=env, capture_output=True, check=False
    )
    assert result.returncode != 0
    assert b"FAILED" in result.stdout
    (dist / "unexpected.txt").write_text("unexpected")
    result = subprocess.run(
        ["bash", "-c", script], cwd=tmp_path, env=env, capture_output=True, check=False
    )
    assert result.returncode != 0
    assert result.stdout == b""  # The file-count guard stops before the checksum check.
