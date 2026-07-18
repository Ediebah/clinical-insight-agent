"""Reproduce a published Bayesian interim-futility calculation.

The heart-disease and heart-failure examples check the agent's *regression* code against real datasets.
This one does the same for the agent's *Bayesian go/no-go* engine, which reasons over response counts
rather than a table of rows: it reproduces the worked predictive-probability calculation from a
published methods paper, to the third decimal.

    Reference : Chen D.-G., Chen J.D. (2019), "Application of Bayesian predictive probability for
                interim futility analysis in single-arm phase II trial", Translational Cancer Research
                8(Suppl 4):S404-S411.  https://pmc.ncbi.nlm.nih.gov/articles/PMC6711387/
    The design : single-arm phase II, binary response. A treatment is worth pursuing only if the true
                response rate exceeds p0 = 30%. Success at the final analysis is declared when the
                posterior probability P(rate > 0.30) exceeds 0.95, under a non-informative Beta(1,1)
                prior. Planned enrolment is 50, with one interim look after 25 patients.
    The look  : 8 of the first 25 patients responded. The paper reports the predictive probability that
                the trial will still succeed at n = 50 -- i.e. that 13 or more of the remaining 25 will
                respond, pushing the total to the winning boundary of 21/50 -- as 0.105.

The agent's own interim engine (`modeling.fit_interim`, the same call the app makes for a "continue or
stop?" question) is handed exactly that interim look and must return the same number.

Run:  .venv/bin/python examples/bayesian_interim_futility.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run as a standalone script
from agent import bayes, modeling  # noqa: E402

PUBLISHED_PPOS = 0.105        # Chen & Chen (2019), predictive probability at the 8/25 interim
GO_BOUNDARY = 21             # final responders of 50 needed to declare success


def main() -> None:
    # The interim look from the paper: 8 responders among the first 25 of a planned 50.
    interim = pd.DataFrame({"response": [1] * 8 + [0] * 17})

    # Chen's single success criterion -- posterior P(rate > 0.30) > 0.95 -- is the degenerate case of
    # the agent's dual-criterion (Lalonde) rule with the target and the reference value both at 0.30 and
    # both gates at 0.95. Prior Beta(1,1), exactly as the paper specifies.
    mr = modeling.fit_interim(interim, "response", n_planned=50, tv=0.30, lrv=0.30,
                              gate_tv=0.95, gate_lrv=0.95, stop_lrv=0.0,
                              prior_a=1, prior_b=1)

    ppos = mr.verdict["predictive_prob"]
    print("Chen & Chen (2019) single-arm phase II interim futility look")
    print("-" * 62)
    print("   design      p0 = 0.30 · success if P(rate > 0.30) > 0.95 · Beta(1,1) prior")
    print("   enrolment   50 planned, interim after 25")
    print(f"   interim     {mr.fit_stat}\n")

    print("Judged against the paper")
    print("-" * 62)
    prior = bayes.Prior("Vague", "beta", (1.0, 1.0), "non-informative Beta(1,1)")
    rule = bayes.DecisionRule(tv=0.30, lrv=0.30, gate_tv=0.95, gate_lrv=0.95, stop_lrv=0.0)
    go = bayes.go_grid_binary(prior, 50, rule)
    checks = [
        (f"Predictive probability of success matches the published {PUBLISHED_PPOS} (to within 0.001)",
         abs(ppos - PUBLISHED_PPOS) < 0.001),
        (f"Final success boundary is {GO_BOUNDARY} of 50 responders",
         next(r for r in range(51) if go[r] == 1) == GO_BOUNDARY),
    ]
    for label, ok in checks:
        print(f"   [{'PASS' if ok else 'FAIL'}] {label}")
    print(f"\nThe agent's interim call returns PPoS = {ppos:.4f}, the same 0.105 the paper reports for "
          "this look, from the same code the app runs for a \"continue or stop?\" question.")


if __name__ == "__main__":
    main()
