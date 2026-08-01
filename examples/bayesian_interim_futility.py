"""Apply a published Bayesian interim-futility design with an exact engine.

The heart-disease and heart-failure examples check the agent's *regression* code against real datasets.
This one tests the agent's *Bayesian go/no-go* engine, which reasons over response counts rather than
a table of rows. It applies a design and hypothetical stopping-boundary case from a published methods
paper, then checks the independently computed predictive probability against a locked engine value.

    Reference : Chen D.-G., Chen J.D. (2019), "Application of Bayesian predictive probability for
                interim futility analysis in single-arm phase II trial", Translational Cancer Research
                8(Suppl 4):S404-S411.  https://pmc.ncbi.nlm.nih.gov/articles/PMC6711387/
    The design : single-arm phase II, binary response. A treatment is worth pursuing only if the true
                response rate exceeds p0 = 30%. Success at the final analysis is declared when the
                posterior probability P(rate > 0.30) exceeds 0.95, under a non-informative Beta(1,1)
                prior. Planned enrolment is 50, with one interim look after 25 patients.
    The case  : The paper's hypothetical first-interim stopping boundary is 8 or fewer responses among
                25 patients. At 8/25, 13 or more of the remaining 25 must respond to reach the final
                efficacy boundary of 21/50. The paper does not report a predictive-probability value
                for this case; the engine independently computes it.

The agent's own interim engine (`modeling.fit_interim`, the same calculation the app uses for an
interim question) is handed that boundary case and must return the locked deterministic result.

Run:  .venv/bin/python examples/bayesian_interim_futility.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run as a standalone script
from agent import bayes, modeling  # noqa: E402

EXPECTED_ENGINE_PPOS = 0.1045  # Rounded value returned by this entry point; not reported by the paper.
GO_BOUNDARY = 21               # Published final responders needed to declare success.


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

    print("Publication boundary and independently computed result")
    print("-" * 62)
    prior = bayes.Prior("Vague", "beta", (1.0, 1.0), "non-informative Beta(1,1)")
    rule = bayes.DecisionRule(tv=0.30, lrv=0.30, gate_tv=0.95, gate_lrv=0.95, stop_lrv=0.0)
    go = bayes.go_grid_binary(prior, 50, rule)
    checks = [
        (f"Engine PPoS matches its locked reference {EXPECTED_ENGINE_PPOS:.4f}",
         abs(ppos - EXPECTED_ENGINE_PPOS) < 1e-12),
        (f"Published final success boundary is {GO_BOUNDARY} of 50 responders",
         next(r for r in range(51) if go[r] == 1) == GO_BOUNDARY),
    ]
    for label, ok in checks:
        print(f"   [{'PASS' if ok else 'FAIL'}] {label}")
    print(f"\nThe agent independently computes PPoS = {ppos:.4f} for the paper's hypothetical 8/25 "
          "boundary case. Chen & Chen do not report this numerical probability.")


if __name__ == "__main__":
    main()
