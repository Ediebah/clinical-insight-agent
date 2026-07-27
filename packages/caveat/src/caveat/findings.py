"""What a check produces, and what analyze() hands back."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

SEVERITIES = ("info", "warn", "caution")


@dataclass
class Finding:
    """One statistical caveat. `kind` is a stable machine key; `message` is prose for a human."""
    kind: str
    severity: str      # info | warn | caution
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Skip:
    """A check that could not run, and what would let it.

    The reason this type exists: the heuristics can silently identify nothing, and a report with no
    findings then looks identical to a clean bill of health. Saying "the contrast check never ran
    because no denominator column was identified" is the difference between a tool you can trust
    and one that is quietly asleep.
    """
    check: str
    reason: str
    fix: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        return f"{self.check}: {self.reason}" + (f" ({self.fix})" if self.fix else "")


@dataclass
class Report:
    """Findings, plus the column roles used and every check that could not run.

    Iterating a Report yields its findings, so `for f in analyze(df)` reads naturally.
    """
    findings: list[Finding] = field(default_factory=list)
    roles: object = None
    skipped: list[Skip] = field(default_factory=list)
    tests_run: int = 0   # hypothesis tests performed, so a Session can accumulate multiplicity

    def __iter__(self):
        return iter(self.findings)

    def __len__(self) -> int:
        return len(self.findings)

    def __bool__(self) -> bool:
        # A report is truthy when it HAS findings, so `if report:` means "something was flagged".
        return bool(self.findings)

    def kinds(self) -> list[str]:
        return [f.kind for f in self.findings]

    def of_kind(self, kind: str) -> list[Finding]:
        return [f for f in self.findings if f.kind == kind]

    def worst(self) -> str | None:
        """The highest severity present, or None for a clean report."""
        for sev in reversed(SEVERITIES):
            if any(f.severity == sev for f in self.findings):
                return sev
        return None

    def as_dict(self) -> dict:
        return {
            "findings": [f.as_dict() for f in self.findings],
            "roles": self.roles.as_dict() if hasattr(self.roles, "as_dict") else None,
            "skipped": [s.as_dict() for s in self.skipped],
        }


_ICON = {"info": "i", "warn": "!", "caution": "!!"}


def render(findings, *, icons: dict | None = None, show_skipped: bool = False) -> str:
    """Plain-text rendering. Accepts a Report or a bare list of Findings.

    `icons` overrides the severity markers — the default is ASCII so output is safe in any
    terminal, log or CI panel; pass emoji if the destination renders them.
    """
    ic = {**_ICON, **(icons or {})}
    items = findings.findings if isinstance(findings, Report) else list(findings)
    lines = [f"{ic.get(f.severity, '-')} [{f.kind}] {f.message}" for f in items]
    if show_skipped and isinstance(findings, Report):
        lines += [f"- [skipped] {s}" for s in findings.skipped]
    return "\n".join(lines)
