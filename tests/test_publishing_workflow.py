"""Guard the proposed release workflow's authorization and artifact boundaries."""
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.fixture(params=[
    ("publish.yml", "caveat", "caveat-0.1.2-py3-none-any.whl", "caveat-0.1.2.tar.gz"),
    ("publish-assurance.yml", "clinical-insight-assurance",
     "clinical_insight_assurance-0.2.0-py3-none-any.whl", "clinical_insight_assurance-0.2.0.tar.gz"),
])
def release(request):
    filename, package, wheel, source = request.param
    path = Path(__file__).resolve().parents[1] / ".github/workflows" / filename
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader), package, wheel, source


def test_publishing_is_manual_and_separates_oidc_from_the_build(release):
    workflow, _, _, _ = release
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


def test_candidate_build_checks_reviewed_source_artifacts_and_runs_tests(release):
    workflow, package, _, _ = release
    dispatch = workflow["on"]["workflow_dispatch"]["inputs"]
    assert dispatch["package"]["options"] == [package]
    assert dispatch["approval"]["required"] == "true"
    steps = workflow["jobs"]["build-and-verify"]["steps"]
    assert steps[0]["with"]["ref"] == "0dff8a848724c08a23ecae6c3a9ad14f08ffc22d"
    assert steps[0]["with"]["persist-credentials"] == "false"
    script = steps[2]["run"]
    assert "PUBLISH REVIEWED ARTIFACTS" in script
    assert "sha256sum -c -" in script
    assert "-m pytest" in script
    assert "*) echo 'Unsupported package'" in script


def test_build_refuses_missing_approval_and_unknown_package(tmp_path, release):
    workflow, package, _, _ = release
    script = workflow["jobs"]["build-and-verify"]["steps"][2]["run"]
    other_package = "clinical-insight-assurance" if package == "caveat" else "caveat"
    for package, approval in (
        (package, "not approved"),
        ("unexpected", "PUBLISH REVIEWED ARTIFACTS"),
        (other_package, "PUBLISH REVIEWED ARTIFACTS"),
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


def test_prepublication_check_refuses_tampered_or_extra_files(tmp_path, release):
    workflow, package, wheel, source = release
    script = workflow["jobs"]["publish"]["steps"][1]["run"]
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / wheel).write_text("tampered")
    (dist / source).write_text("tampered")
    env = {**os.environ, "PACKAGE": package}
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
