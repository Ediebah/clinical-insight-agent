# Landing page (served via GitHub Pages)

`index.html` is a standalone, self-contained landing page for the Clinical Insight Agent. No build step
and no external assets: all CSS and JS are inline, the method visuals (assurance curve, odds-ratio forest,
Kaplan-Meier curves, A/B lift, model-selection leaderboard, decision curve) are drawn on `<canvas>`, and
it is theme-aware (light/dark).

Published via **GitHub Pages** (Settings → Pages → Source: `main` / `docs`) at
<https://ediebah.github.io/clinical-insight-agent/>. `.nojekyll` disables Jekyll so the raw HTML is
served as-is.

Preview locally:

```bash
python -m http.server -d docs 8000   # then open http://localhost:8000/
```

It presents the agent end to end: the Bayesian go/no-go decision layer, the wider method suite with live
example outputs, the model-selection engine, the self-healing pipeline, the clinical-evaluation lenses
(decision curve + failure analysis), and the CI-enforced real-data validation.
