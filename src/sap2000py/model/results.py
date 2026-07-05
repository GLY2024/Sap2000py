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
from ..enums import ItemTypeElm
from ..errors import SapApiError, SapNameNotFoundError
from ..handles import Handle
from ._base import Manager
from .frames import FrameHandle
from .groups import GroupHandle
from .points import PointHandle

_NO_OUTPUT_SELECTED_HINT = (
    "No SAP2000 output cases or combinations are selected. "
    "Call m.results.select_output(cases=[...], combos=[...]) before reading results."
)

_ResultStrategy = Literal["objects", "temporary_group"]
_ObjectRequestKind = Literal["frame_forces", "joint_reactions", "joint_displacements"]
_TempGroupRequestKind = Literal[
    "frame_forces_temp_group",
    "joint_reactions_temp_group",
    "joint_displacements_temp_group",
]
_RequestKind = Literal[
    "frame_forces",
    "frame_forces_temp_group",
    "joint_reactions",
    "joint_reactions_temp_group",
    "joint_displacements",
    "joint_displacements_temp_group",
    "modal_periods",
]
_ResultObjectColumn = Literal["frame", "joint"]


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
    kind: _RequestKind
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
        single: Any | None = None,
        manager: Any,
        group: GroupHandle | str | None = None,
        selection: bool = False,
    ) -> _Target:
        chosen = sum(value is not None for value in (single, group)) + int(selection)
        if chosen != 1:
            raise ValueError("provide exactly one result target.")
        if single is not None:
            return _Target(manager.ref(single).name, ItemTypeElm.OBJECT_ELM)
        if group is not None:
            return _Target(self._results._model.groups.ref(group).name, ItemTypeElm.GROUP_ELM)
        return _Target("", ItemTypeElm.SELECTION_ELM)

    def _register_targets(
        self,
        *,
        kind: _ObjectRequestKind,
        temp_group_kind: _TempGroupRequestKind,
        single: Any | None,
        many: Sequence[Any] | None,
        many_label: str,
        manager: Any,
        group: GroupHandle | str | None,
        selection: bool,
        key: str | None,
        strategy: _ResultStrategy,
    ) -> ResultBatch:
        self._validate_strategy(strategy)
        if many is not None:
            if single is not None or group is not None or selection:
                raise ValueError(f"{many_label}= cannot be combined with another result target.")
            targets = tuple(
                _Target(manager.ref(item).name, ItemTypeElm.OBJECT_ELM) for item in many
            )
            request_kind: _RequestKind = kind if strategy == "objects" else temp_group_kind
        else:
            targets = (
                self._single_target(
                    single=single,
                    manager=manager,
                    group=group,
                    selection=selection,
                ),
            )
            request_kind = kind
        self._requests.append(_Request(request_kind, self._key(key, kind), targets))
        return self

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
        return self._register_targets(
            kind="frame_forces",
            temp_group_kind="frame_forces_temp_group",
            single=frame,
            many=frames,
            many_label="frames",
            manager=self._results._model.frames,
            group=group,
            selection=selection,
            key=key,
            strategy=strategy,
        )

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
        return self._register_targets(
            kind="joint_reactions",
            temp_group_kind="joint_reactions_temp_group",
            single=point,
            many=points,
            many_label="points",
            manager=self._results._model.points,
            group=group,
            selection=selection,
            key=key,
            strategy=strategy,
        )

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
        return self._register_targets(
            kind="joint_displacements",
            temp_group_kind="joint_displacements_temp_group",
            single=point,
            many=points,
            many_label="points",
            manager=self._results._model.points,
            group=group,
            selection=selection,
            key=key,
            strategy=strategy,
        )

    def modal_periods(self, *, key: str | None = None) -> ResultBatch:
        """Register modal period extraction."""
        self._requests.append(_Request("modal_periods", self._key(key, "modal_periods")))
        return self

    def collect(self) -> dict[str, ResultTable]:
        """Execute all registered reads and return tables by key."""
        restore_selection: tuple[tuple[str, ...], tuple[str, ...]] | None = None
        try:
            if self._cases is not None or self._combos is not None:
                restore_selection = self._results._selected_output()
                self._results.select_output(cases=self._cases, combos=self._combos)
            return self._collect_requests()
        finally:
            if restore_selection is not None:
                cases, combos = restore_selection
                self._results.select_output(cases=cases, combos=combos)

    def _collect_requests(self) -> dict[str, ResultTable]:
        tables: dict[str, ResultTable] = {}
        for request in self._requests:
            if request.kind == "modal_periods":
                tables[request.key] = self._results.modal_periods()
            elif request.kind == "frame_forces_temp_group":
                self._validate_targets(request.targets, manager=self._results._model.frames)
                tables[request.key] = self._collect_frame_temp_group(request.targets)
            elif request.kind == "joint_reactions_temp_group":
                self._validate_targets(request.targets, manager=self._results._model.points)
                tables[request.key] = self._collect_point_temp_group(
                    request.targets, kind="joint_reactions"
                )
            elif request.kind == "joint_displacements_temp_group":
                self._validate_targets(request.targets, manager=self._results._model.points)
                tables[request.key] = self._collect_point_temp_group(
                    request.targets, kind="joint_displacements"
                )
            else:
                tables[request.key] = self._collect_object_request(request)
        return tables

    def _collect_object_request(self, request: _Request) -> ResultTable:
        if request.kind == "frame_forces":
            self._validate_targets(request.targets, manager=self._results._model.frames)
        else:
            self._validate_targets(request.targets, manager=self._results._model.points)

        reads: list[ResultTable] = []
        for target in request.targets:
            if request.kind == "frame_forces":
                table = self._results._frame_forces(target.name, target.item_type)
                self._ensure_target_rows(table, target, column="frame")
            elif request.kind == "joint_reactions":
                table = self._results._joint_reactions(target.name, target.item_type)
                self._ensure_target_rows(table, target, column="joint")
            else:
                table = self._results._joint_displacements(target.name, target.item_type)
                self._ensure_target_rows(table, target, column="joint")
            reads.append(table)
        return _merge_tables(reads)

    def _validate_targets(self, targets: Sequence[_Target], *, manager: Any) -> None:
        object_names = [
            target.name for target in targets if target.item_type is ItemTypeElm.OBJECT_ELM
        ]
        if object_names:
            self._validate_names(object_names, manager=manager)
        group_names = [
            target.name for target in targets if target.item_type is ItemTypeElm.GROUP_ELM
        ]
        if group_names:
            self._validate_names(group_names, manager=self._results._model.groups)

    def _validate_names(self, names: Sequence[str], *, manager: Any) -> None:
        available = manager.names()
        missing = [name for name in names if name not in available]
        if missing:
            raise SapNameNotFoundError(missing[0], kind=manager._kind, available=available)

    def _ensure_target_rows(
        self,
        table: ResultTable,
        target: _Target,
        *,
        column: _ResultObjectColumn,
    ) -> None:
        if target.item_type is ItemTypeElm.SELECTION_ELM:
            return
        if target.item_type is ItemTypeElm.GROUP_ELM:
            if len(table) == 0:
                raise ValueError(
                    f"result batch returned no {column} rows for group target {target.name!r}."
                )
            return
        self._ensure_targets_rows(table, [target], column=column)

    def _collect_frame_temp_group(self, targets: Sequence[_Target]) -> ResultTable:
        group_name = f"__sap2000py_results_{uuid4().hex}"
        group: GroupHandle | None = None
        try:
            group = self._results._model.groups.add(group_name)
            for target in targets:
                self._results._model.frames.ref(target.name).group(group)
            table = self._results._frame_forces(group_name, ItemTypeElm.GROUP_ELM)
            self._ensure_targets_rows(table, targets, column="frame")
            return table
        finally:
            if group is not None:
                group.delete()

    def _collect_point_temp_group(
        self,
        targets: Sequence[_Target],
        *,
        kind: Literal["joint_reactions", "joint_displacements"],
    ) -> ResultTable:
        group_name = f"__sap2000py_results_{uuid4().hex}"
        group: GroupHandle | None = None
        try:
            group = self._results._model.groups.add(group_name)
            for target in targets:
                self._results._model.points.ref(target.name).group(group)
            if kind == "joint_reactions":
                table = self._results._joint_reactions(group_name, ItemTypeElm.GROUP_ELM)
            else:
                table = self._results._joint_displacements(group_name, ItemTypeElm.GROUP_ELM)
            self._ensure_targets_rows(table, targets, column="joint")
            return table
        finally:
            if group is not None:
                group.delete()

    def _ensure_targets_rows(
        self,
        table: ResultTable,
        targets: Sequence[_Target],
        *,
        column: _ResultObjectColumn,
    ) -> None:
        returned = {str(name) for name in table[column]}
        missing = [target.name for target in targets if target.name not in returned]
        if missing:
            joined = ", ".join(repr(name) for name in missing)
            raise ValueError(f"result batch returned no {column} rows for targets: {joined}.")


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

    def _selected_output(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        selected_cases: list[str] = []
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
                selected_cases.append(str(case))

        selected_combos: list[str] = []
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
                selected_combos.append(str(combo))

        return tuple(selected_cases), tuple(selected_combos)

    def _call_result_with_output_hint(
        self, com_func: Any, api_name: str, args: tuple[Any, ...]
    ) -> Any:
        try:
            return self._g.call(com_func, *args, api_name=api_name)
        except SapApiError as exc:
            try:
                has_selected_output = self._has_selected_output()
            except SapApiError:
                has_selected_output = None
            if has_selected_output is None:
                raise
            if has_selected_output:
                raise
            raise SapApiError(api_name, args, exc.code, hint=_NO_OUTPUT_SELECTED_HINT) from exc

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
        result = self._call_result_with_output_hint(
            self._raw.Results.JointReact,
            "Results.JointReact",
            args,
        )
        (_n, obj, _elm, case, _st, step, f1, f2, f3, m1, m2, m3) = result
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
        result = self._call_result_with_output_hint(
            self._raw.Results.JointDispl,
            "Results.JointDispl",
            args,
        )
        (_n, obj, _elm, case, _st, step, u1, u2, u3, r1, r2, r3) = result
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
        result = self._call_result_with_output_hint(
            self._raw.Results.FrameForce,
            "Results.FrameForce",
            args,
        )
        (_n, obj, obj_sta, _elm, _elm_sta, case, _st, step, p, v2, v3, t, m2, m3) = result
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
