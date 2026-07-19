# Landing page

`go-no-go-landing.html` — a standalone, self-contained landing page for the Clinical Insight Agent.
No build step and no external assets: all CSS and JS are inline, the method visuals (assurance curve,
odds-ratio forest, Kaplan-Meier curves, A/B lift, model-selection leaderboard) are drawn on `<canvas>`,
and it is theme-aware (light/dark).

Open it directly in a browser, or serve the folder:

```bash
python -m http.server -d docs/landing 8000   # then open http://localhost:8000/go-no-go-landing.html
```

It presents the agent end to end: the Bayesian go/no-go decision layer, the wider method suite with live
example outputs, the model-selection engine, the self-healing pipeline, and the real-data validation
(each number CI-enforced in `tests/test_validation.py`).
