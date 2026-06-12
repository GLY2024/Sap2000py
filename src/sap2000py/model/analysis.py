"""Run control: set which cases run, run the analysis, report status."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..errors import SapAnalysisError, SapError
from ._base import Manager

# SAP2000 case-status codes from Analyze.GetCaseStatus.
_STATUS = {1: "not run", 2: "could not start", 3: "not finished", 4: "finished"}
_FINISHED = 4


@dataclass(frozen=True)
class AnalysisReport:
    """Outcome of an analysis run: each case name mapped to its status string."""

    status: dict[str, str]

    @property
    def all_finished(self) -> bool:
        return all(s == "finished" for s in self.status.values())


class Analysis(Manager):
    """Control and run the analysis. Wraps ``cAnalyze``."""

    def set_run_flags(self, cases: Sequence[str] | None = None, *, run: bool = True) -> None:
        """Choose which load cases run.

        ``cases=None`` sets every case to ``run``. Otherwise all cases are first
        turned off and only ``cases`` are set to ``run``. Wraps
        ``Analyze.SetRunCaseFlag``.
        """
        if cases is None:
            self._g.call(
                self._raw.Analyze.SetRunCaseFlag, "", run, True, api_name="Analyze.SetRunCaseFlag"
            )
            return
        self._g.call(
            self._raw.Analyze.SetRunCaseFlag, "", False, True, api_name="Analyze.SetRunCaseFlag"
        )
        for case in cases:
            self._g.call(
                self._raw.Analyze.SetRunCaseFlag,
                case,
                run,
                False,
                api_name="Analyze.SetRunCaseFlag",
            )

    def case_status(self) -> dict[str, str]:
        """Map each case name to its status string. Wraps ``Analyze.GetCaseStatus``."""
        _count, names, statuses = self._g.call(
            self._raw.Analyze.GetCaseStatus, api_name="Analyze.GetCaseStatus"
        )
        if not names:
            return {}
        return {
            name: _STATUS.get(int(code), "unknown")
            for name, code in zip(names, statuses, strict=False)
        }

    def run(self, *, cases: Sequence[str] | None = None) -> AnalysisReport:
        """Set run flags, run the analysis, and verify the requested cases finished.

        Raises :class:`~sap2000py.errors.SapAnalysisError` if any requested case
        did not finish. Wraps ``Analyze.RunAnalysis``.

        The model must be saved to a file first — SAP2000 writes its analysis
        files alongside the ``.sdb`` — otherwise a clear error is raised instead
        of SAP2000's opaque status code.
        """
        filename = self._g.value(self._raw.GetModelFilename, api_name="GetModelFilename")
        if not filename:
            raise SapError(
                "The model must be saved to a file before running analysis "
                "(use model.files.save(path)); SAP2000 writes analysis files "
                "alongside the .sdb."
            )
        self.set_run_flags(cases)
        self._g.call(self._raw.Analyze.RunAnalysis, api_name="Analyze.RunAnalysis")
        status = self.case_status()
        requested = set(cases) if cases is not None else set(status)
        failed = {
            name: state
            for name, state in status.items()
            if name in requested and state != "finished"
        }
        if failed:
            raise SapAnalysisError(failed)
        return AnalysisReport(status)
