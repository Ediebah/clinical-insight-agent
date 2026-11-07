"""Key-free `caveat` example: a rate-only table has no denominator.

Run from the repository root after installing the local package:

    python -m pip install ./packages/caveat
    python examples/caveat_missing_denominator.py

The three rows are constructed for illustration; they are not patient data. See
caveat_missing_denominator.md for the expected output and what it does and does not show.
"""
import caveat
import pandas as pd

rates = pd.DataFrame({
    "clinic": ["North", "South", "East"],
    "screening_rate_pct": [62.5, 48.0, 71.0],
})

report = caveat.analyze(rates, "Which clinic has the highest screening rate?")

print(report.roles)
print(caveat.render(report, show_skipped=True))
