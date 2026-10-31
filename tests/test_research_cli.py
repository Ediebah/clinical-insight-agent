import json
import os
import subprocess
import sys


def test_caveat_cli_runs_without_api_key(tmp_path):
    table = tmp_path / "table.csv"
    table.write_text("arm,cases,total\nA,4,20\nB,7,20\n")
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    result = subprocess.run([sys.executable, "-m", "agent.cli", "caveat", "--csv", str(table),
                             "--question", "Compare rates"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "findings" in json.loads(result.stdout)


def test_assurance_cli_requires_explicit_decision_inputs(tmp_path):
    params = tmp_path / "design.json"
    params.write_text(json.dumps({"n": 30, "tv": .3, "lrv": .2}))
    result = subprocess.run([sys.executable, "-m", "agent.cli", "assurance", "--json", str(params)],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert "threshold" in result.stderr.lower()


def test_caveat_cli_does_not_import_scipy(tmp_path):
    table = tmp_path / "table.csv"
    table.write_text("arm,cases,total\nA,4,20\nB,7,20\n")
    code = ("import builtins,sys; old=builtins.__import__; "
            "builtins.__import__=lambda name,*a,**k: (_ for _ in ()).throw(ImportError('blocked scipy')) "
            "if name.startswith('scipy') else old(name,*a,**k); "
            "from agent.cli import main; sys.exit(main(['caveat','--csv',sys.argv[1]]))")
    result = subprocess.run([sys.executable, "-c", code, str(table)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
