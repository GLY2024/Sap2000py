"""Analysis result extraction and a light tabular container.

:class:`ResultTable` stores results as named columns and converts to a pandas
DataFrame on demand (pandas is an optional ``tables`` extra, so the core stays
light). The :class:`Results` manager wraps the ``cAnalysisResults`` calls and
the output-selection setup.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .._optional import require
from ..enums import ItemTypeElm
from ..handles import Handle, as_name
from ._base import Manager


@dataclass(frozen=True)
class ResultTable:
    """Column-oriented analysis results.

    Access a column by name (``table["period"]``), iterate rows as dicts
    (``table.rows()``), or convert to a DataFrame (``table.to_pandas()``).
    """

    columns: dict[str, tuple[Any, ...]]

    def __len__(self) -> int:
        if not self.columns:
            return 0
        return len(next(iter(self.columns.values())))

    def __getitem__(self, key: str) -> tuple[Any, ...]:
        return self.columns[key]

    @property
    def names(self) -> list[str]:
        """Column names."""
        return list(self.columns)

    def rows(self) -> list[dict[str, Any]]:
        """Results as a list of ``{column: value}`` dicts."""
        keys = list(self.columns)
        return [
            dict(zip(keys, values, strict=False))
            for values in zip(*self.columns.values(), strict=False)
        ]

    def to_pandas(self) -> Any:
        """Return a pandas ``DataFrame`` (requires the ``tables`` extra)."""
        pd = require("pandas", feature="ResultTable.to_pandas", extra="tables")
        return pd.DataFrame({k: list(v) for k, v in self.columns.items()})


def _columns(names: Sequence[str], arrays: Sequence[Any]) -> dict[str, tuple[Any, ...]]:
    return {name: tuple(arr) if arr else () for name, arr in zip(names, arrays, strict=True)}


class Results(Manager):
    """Select output and extract analysis results. Wraps ``cAnalysisResults``."""

    # -- output selection ---------------------------------------------------

    def select_output(
        self,
        *,
        cases: Sequence[str] | None = None,
        combos: Sequence[str] | None = None,
    ) -> None:
        """Choose which cases/combos results are reported for.

        Deselects everything first, then selects the given cases and combos.
        Wraps ``Results.Setup.DeselectAllCasesAndCombosForOutput`` +
        ``SetCaseSelectedForOutput`` / ``SetComboSelectedForOutput``.
        """
        self._g.call(
            self._raw.Results.Setup.DeselectAllCasesAndCombosForOutput,
            api_name="Results.Setup.DeselectAllCasesAndCombosForOutput",
        )
        for case in cases or ():
            self._g.call(
                self._raw.Results.Setup.SetCaseSelectedForOutput,
                case,
                True,
                api_name="Results.Setup.SetCaseSelectedForOutput",
            )
        for combo in combos or ():
            self._g.call(
                self._raw.Results.Setup.SetComboSelectedForOutput,
                combo,
                True,
                api_name="Results.Setup.SetComboSelectedForOutput",
            )

    # -- extraction ---------------------------------------------------------

    def modal_periods(self) -> ResultTable:
        """Modal periods and frequencies. Wraps ``Results.ModalPeriod``."""
        (_n, case, _steptype, mode, period, freq, circ, eigen) = self._g.call(
            self._raw.Results.ModalPeriod, api_name="Results.ModalPeriod"
        )
        return ResultTable(
            _columns(
                ["case", "mode", "period", "frequency", "circ_freq", "eigenvalue"],
                [case, mode, period, freq, circ, eigen],
            )
        )

    def joint_reactions(
        self, joint: Handle | str, *, item_type: ItemTypeElm = ItemTypeElm.OBJECT_ELM
    ) -> ResultTable:
        """Joint reaction forces/moments. Wraps ``Results.JointReact``."""
        (_n, obj, _elm, case, _st, step, f1, f2, f3, m1, m2, m3) = self._g.call(
            self._raw.Results.JointReact,
            as_name(joint),
            int(item_type),
            api_name="Results.JointReact",
        )
        return ResultTable(
            _columns(
                ["joint", "case", "step", "F1", "F2", "F3", "M1", "M2", "M3"],
                [obj, case, step, f1, f2, f3, m1, m2, m3],
            )
        )

    def joint_displacements(
        self, joint: Handle | str, *, item_type: ItemTypeElm = ItemTypeElm.OBJECT_ELM
    ) -> ResultTable:
        """Joint displacements/rotations. Wraps ``Results.JointDispl``."""
        (_n, obj, _elm, case, _st, step, u1, u2, u3, r1, r2, r3) = self._g.call(
            self._raw.Results.JointDispl,
            as_name(joint),
            int(item_type),
            api_name="Results.JointDispl",
        )
        return ResultTable(
            _columns(
                ["joint", "case", "step", "U1", "U2", "U3", "R1", "R2", "R3"],
                [obj, case, step, u1, u2, u3, r1, r2, r3],
            )
        )

    def frame_forces(
        self, frame: Handle | str, *, item_type: ItemTypeElm = ItemTypeElm.OBJECT_ELM
    ) -> ResultTable:
        """Frame internal forces along output stations. Wraps ``Results.FrameForce``."""
        (_n, obj, obj_sta, _elm, _elm_sta, case, _st, step, p, v2, v3, t, m2, m3) = self._g.call(
            self._raw.Results.FrameForce,
            as_name(frame),
            int(item_type),
            api_name="Results.FrameForce",
        )
        return ResultTable(
            _columns(
                ["frame", "station", "case", "step", "P", "V2", "V3", "T", "M2", "M3"],
                [obj, obj_sta, case, step, p, v2, v3, t, m2, m3],
            )
        )
