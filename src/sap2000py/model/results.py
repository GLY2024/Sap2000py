"""Analysis result extraction and a light tabular container.

:class:`ResultTable` stores results as named columns and converts to a pandas
DataFrame on demand (pandas is an optional ``tables`` extra, so the core stays
light). The :class:`Results` manager wraps the ``cAnalysisResults`` calls and
the output-selection setup.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from .._optional import require
from ..enums import ItemType, ItemTypeElm
from ..errors import SapApiError
from ..handles import Handle
from ._base import Manager
from .frames import FrameHandle
from .groups import GroupHandle
from .points import PointHandle

_NO_OUTPUT_SELECTED_HINT = (
    "No SAP2000 output cases or combinations are selected. "
    "Call m.results.select_output(cases=[...], combos=[...]) before reading results."
)


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


def _merge_tables(tables: Sequence[ResultTable]) -> ResultTable:
    if not tables:
        return ResultTable({})
    names = tables[0].names
    merged: dict[str, list[Any]] = {name: [] for name in names}
    for table in tables:
        if table.names != names:
            raise ValueError("cannot merge result tables with different columns.")
        for name in names:
            merged[name].extend(table[name])
    return ResultTable({name: tuple(values) for name, values in merged.items()})


@dataclass(frozen=True)
class _Target:
    name: str
    item_type: ItemTypeElm


@dataclass(frozen=True)
class _Request:
    kind: Literal[
        "frame_forces",
        "frame_forces_temp_group",
        "joint_reactions",
        "joint_reactions_temp_group",
        "joint_displacements",
        "joint_displacements_temp_group",
        "modal_periods",
    ]
    key: str
    targets: tuple[_Target, ...] = ()


@dataclass
class ResultBatch:
    """A delayed batch of result reads executed by :meth:`collect`."""

    _results: Results
    _cases: Sequence[str] | None = None
    _combos: Sequence[str] | None = None
    _requests: list[_Request] = field(default_factory=list)

    def _key(self, key: str | None, default: str) -> str:
        resolved = key or default
        if any(request.key == resolved for request in self._requests):
            raise ValueError(f"duplicate result batch key {resolved!r}.")
        return resolved

    def _validate_strategy(self, strategy: str) -> None:
        if strategy not in {"objects", "temporary_group"}:
            raise ValueError("strategy must be 'objects' or 'temporary_group'.")

    def _single_target(
        self,
        *,
        frame: FrameHandle | str | None = None,
        point: PointHandle | str | None = None,
        group: GroupHandle | str | None = None,
        selection: bool = False,
    ) -> _Target:
        chosen = sum(value is not None for value in (frame, point, group)) + int(selection)
        if chosen != 1:
            raise ValueError("provide exactly one result target.")
        if frame is not None:
            return _Target(self._results._model.frames.ref(frame).name, ItemTypeElm.OBJECT_ELM)
        if point is not None:
            return _Target(self._results._model.points.ref(point).name, ItemTypeElm.OBJECT_ELM)
        if group is not None:
            return _Target(self._results._model.groups.ref(group).name, ItemTypeElm.GROUP_ELM)
        return _Target("", ItemTypeElm.SELECTION_ELM)

    def frame_forces(
        self,
        *,
        frame: FrameHandle | str | None = None,
        frames: Sequence[FrameHandle | str] | None = None,
        group: GroupHandle | str | None = None,
        selection: bool = False,
        key: str | None = None,
        strategy: Literal["objects", "temporary_group"] = "objects",
    ) -> ResultBatch:
        """Register frame force extraction."""
        self._validate_strategy(strategy)
        if frames is not None:
            if frame is not None or group is not None or selection:
                raise ValueError("frames= cannot be combined with another result target.")
            targets = tuple(
                _Target(self._results._model.frames.ref(item).name, ItemTypeElm.OBJECT_ELM)
                for item in frames
            )
            request_kind: Literal["frame_forces", "frame_forces_temp_group"] = (
                "frame_forces" if strategy == "objects" else "frame_forces_temp_group"
            )
        else:
            targets = (self._single_target(frame=frame, group=group, selection=selection),)
            request_kind = "frame_forces"
        self._requests.append(_Request(request_kind, self._key(key, "frame_forces"), targets))
        return self

    def joint_reactions(
        self,
        *,
        point: PointHandle | str | None = None,
        points: Sequence[PointHandle | str] | None = None,
        group: GroupHandle | str | None = None,
        selection: bool = False,
        key: str | None = None,
        strategy: Literal["objects", "temporary_group"] = "objects",
    ) -> ResultBatch:
        """Register joint reaction extraction."""
        self._validate_strategy(strategy)
        if points is not None:
            if point is not None or group is not None or selection:
                raise ValueError("points= cannot be combined with another result target.")
            targets = tuple(
                _Target(self._results._model.points.ref(item).name, ItemTypeElm.OBJECT_ELM)
                for item in points
            )
            request_kind: Literal["joint_reactions", "joint_reactions_temp_group"] = (
                "joint_reactions" if strategy == "objects" else "joint_reactions_temp_group"
            )
        else:
            targets = (self._single_target(point=point, group=group, selection=selection),)
            request_kind = "joint_reactions"
        self._requests.append(
            _Request(request_kind, self._key(key, "joint_reactions"), targets)
        )
        return self

    def joint_displacements(
        self,
        *,
        point: PointHandle | str | None = None,
        points: Sequence[PointHandle | str] | None = None,
        group: GroupHandle | str | None = None,
        selection: bool = False,
        key: str | None = None,
        strategy: Literal["objects", "temporary_group"] = "objects",
    ) -> ResultBatch:
        """Register joint displacement extraction."""
        self._validate_strategy(strategy)
        if points is not None:
            if point is not None or group is not None or selection:
                raise ValueError("points= cannot be combined with another result target.")
            targets = tuple(
                _Target(self._results._model.points.ref(item).name, ItemTypeElm.OBJECT_ELM)
                for item in points
            )
            request_kind: Literal["joint_displacements", "joint_displacements_temp_group"] = (
                "joint_displacements"
                if strategy == "objects"
                else "joint_displacements_temp_group"
            )
        else:
            targets = (self._single_target(point=point, group=group, selection=selection),)
            request_kind = "joint_displacements"
        self._requests.append(
            _Request(request_kind, self._key(key, "joint_displacements"), targets)
        )
        return self

    def modal_periods(self, *, key: str | None = None) -> ResultBatch:
        """Register modal period extraction."""
        self._requests.append(_Request("modal_periods", self._key(key, "modal_periods")))
        return self

    def collect(self) -> dict[str, ResultTable]:
        """Execute all registered reads and return tables by key."""
        if self._cases is not None or self._combos is not None:
            self._results.select_output(cases=self._cases, combos=self._combos)

        tables: dict[str, ResultTable] = {}
        for request in self._requests:
            if request.kind == "modal_periods":
                tables[request.key] = self._results.modal_periods()
                continue
            if request.kind == "frame_forces_temp_group":
                tables[request.key] = self._collect_frame_temp_group(request.targets)
                continue
            if request.kind == "joint_reactions_temp_group":
                tables[request.key] = self._collect_point_temp_group(
                    request.targets, kind="joint_reactions"
                )
                continue
            if request.kind == "joint_displacements_temp_group":
                tables[request.key] = self._collect_point_temp_group(
                    request.targets, kind="joint_displacements"
                )
                continue

            reads: list[ResultTable] = []
            for target in request.targets:
                if request.kind == "frame_forces":
                    reads.append(self._results._frame_forces(target.name, target.item_type))
                elif request.kind == "joint_reactions":
                    reads.append(self._results._joint_reactions(target.name, target.item_type))
                else:
                    reads.append(self._results._joint_displacements(target.name, target.item_type))
            tables[request.key] = _merge_tables(reads)
        return tables

    def _collect_frame_temp_group(self, targets: Sequence[_Target]) -> ResultTable:
        group_name = f"__sap2000py_results_{uuid4().hex}"
        created = False
        try:
            self._results._g.call(
                self._results._raw.GroupDef.SetGroup,
                group_name,
                api_name="GroupDef.SetGroup",
            )
            created = True
            for target in targets:
                self._results._g.call(
                    self._results._raw.FrameObj.SetGroupAssign,
                    target.name,
                    group_name,
                    False,
                    int(ItemType.OBJECT),
                    api_name="FrameObj.SetGroupAssign",
                )
            return self._results._frame_forces(group_name, ItemTypeElm.GROUP_ELM)
        finally:
            if created:
                self._results._g.call(
                    self._results._raw.GroupDef.Delete,
                    group_name,
                    api_name="GroupDef.Delete",
                )

    def _collect_point_temp_group(
        self,
        targets: Sequence[_Target],
        *,
        kind: Literal["joint_reactions", "joint_displacements"],
    ) -> ResultTable:
        group_name = f"__sap2000py_results_{uuid4().hex}"
        created = False
        try:
            self._results._g.call(
                self._results._raw.GroupDef.SetGroup,
                group_name,
                api_name="GroupDef.SetGroup",
            )
            created = True
            for target in targets:
                self._results._g.call(
                    self._results._raw.PointObj.SetGroupAssign,
                    target.name,
                    group_name,
                    False,
                    int(ItemType.OBJECT),
                    api_name="PointObj.SetGroupAssign",
                )
            if kind == "joint_reactions":
                return self._results._joint_reactions(group_name, ItemTypeElm.GROUP_ELM)
            return self._results._joint_displacements(group_name, ItemTypeElm.GROUP_ELM)
        finally:
            if created:
                self._results._g.call(
                    self._results._raw.GroupDef.Delete,
                    group_name,
                    api_name="GroupDef.Delete",
                )


class Results(Manager[Handle]):
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

    def _has_selected_output(self) -> bool:
        _case_count, case_names = self._g.call(
            self._raw.LoadCases.GetNameList, api_name="LoadCases.GetNameList"
        )
        for case in case_names or ():
            selected = self._g.call(
                self._raw.Results.Setup.GetCaseSelectedForOutput,
                case,
                False,
                api_name="Results.Setup.GetCaseSelectedForOutput",
            )
            if bool(selected):
                return True

        _combo_count, combo_names = self._g.call(
            self._raw.RespCombo.GetNameList, api_name="RespCombo.GetNameList"
        )
        for combo in combo_names or ():
            selected = self._g.call(
                self._raw.Results.Setup.GetComboSelectedForOutput,
                combo,
                False,
                api_name="Results.Setup.GetComboSelectedForOutput",
            )
            if bool(selected):
                return True

        return False

    def _ensure_output_selected(self, api_name: str, args: tuple[Any, ...]) -> None:
        if self._has_selected_output():
            return
        raise SapApiError(api_name, args, 1, hint=_NO_OUTPUT_SELECTED_HINT)

    def batch(
        self,
        *,
        cases: Sequence[str] | None = None,
        combos: Sequence[str] | None = None,
    ) -> ResultBatch:
        """Create a delayed result batch.

        If both ``cases`` and ``combos`` are omitted, ``collect()`` reads the
        current SAP2000 output selection without clearing or changing it.
        """
        return ResultBatch(self, _cases=cases, _combos=combos)

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

    def _joint_reactions(self, name: str, item_type: ItemTypeElm) -> ResultTable:
        args = (name, int(item_type))
        self._ensure_output_selected("Results.JointReact", args)
        (_n, obj, _elm, case, _st, step, f1, f2, f3, m1, m2, m3) = self._g.call(
            self._raw.Results.JointReact,
            *args,
            api_name="Results.JointReact",
        )
        return ResultTable(
            _columns(
                ["joint", "case", "step", "F1", "F2", "F3", "M1", "M2", "M3"],
                [obj, case, step, f1, f2, f3, m1, m2, m3],
            )
        )

    def joint_reactions(self, point: PointHandle | str) -> ResultTable:
        """Joint reaction forces/moments for one point. Wraps ``Results.JointReact``."""
        point_ref = self._model.points.ref(point)
        return self._joint_reactions(point_ref.name, ItemTypeElm.OBJECT_ELM)

    def _joint_displacements(self, name: str, item_type: ItemTypeElm) -> ResultTable:
        args = (name, int(item_type))
        self._ensure_output_selected("Results.JointDispl", args)
        (_n, obj, _elm, case, _st, step, u1, u2, u3, r1, r2, r3) = self._g.call(
            self._raw.Results.JointDispl,
            *args,
            api_name="Results.JointDispl",
        )
        return ResultTable(
            _columns(
                ["joint", "case", "step", "U1", "U2", "U3", "R1", "R2", "R3"],
                [obj, case, step, u1, u2, u3, r1, r2, r3],
            )
        )

    def joint_displacements(self, point: PointHandle | str) -> ResultTable:
        """Joint displacements/rotations for one point. Wraps ``Results.JointDispl``."""
        point_ref = self._model.points.ref(point)
        return self._joint_displacements(point_ref.name, ItemTypeElm.OBJECT_ELM)

    def _frame_forces(self, name: str, item_type: ItemTypeElm) -> ResultTable:
        args = (name, int(item_type))
        self._ensure_output_selected("Results.FrameForce", args)
        (_n, obj, obj_sta, _elm, _elm_sta, case, _st, step, p, v2, v3, t, m2, m3) = self._g.call(
            self._raw.Results.FrameForce,
            *args,
            api_name="Results.FrameForce",
        )
        return ResultTable(
            _columns(
                ["frame", "station", "case", "step", "P", "V2", "V3", "T", "M2", "M3"],
                [obj, obj_sta, case, step, p, v2, v3, t, m2, m3],
            )
        )

    def frame_forces(self, frame: FrameHandle | str) -> ResultTable:
        """Frame internal forces along output stations for one frame."""
        frame_ref = self._model.frames.ref(frame)
        return self._frame_forces(frame_ref.name, ItemTypeElm.OBJECT_ELM)
