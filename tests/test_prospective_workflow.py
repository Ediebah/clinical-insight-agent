"""Paid evaluation must remain manual and explicitly confirmed."""
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/prospective-eval.yml"


def test_paid_challenge_is_manual_and_requires_exact_confirmation():
    assert WORKFLOW.exists(), "manual prospective evaluation workflow is missing"
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["on"]["workflow_dispatch"]["inputs"]["confirmation"]["required"] == "true"
    job = workflow["jobs"]["evaluate"]
    assert "OPENAI_API_KEY" not in job.get("env", {})
    eval_step = next(step for step in job["steps"] if step.get("name") == "Run frozen synthetic challenge")
    assert eval_step["env"]["OPENAI_API_KEY"] == "${{ secrets.OPENAI_API_KEY }}"
    checks = "\n".join(step.get("run", "") for step in job["steps"])
    assert "RUN SYNTHETIC EVALUATION" in checks
    assert "prospective_eval" in checks
    assert workflow["permissions"] == {"contents": "read"}
