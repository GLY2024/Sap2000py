"""Enumerations and small value helpers shared across the library.

These are the single source of truth for values that the old code repeated by
hand in many places (the unit table, the ``{"U1": 0, ...}`` DOF dictionaries,
item-type magic numbers). Centralizing them here is what lets us delete ~14
copy-pasted DOF conversion blocks.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import IntEnum

#: Canonical order of the six degrees of freedom in the OAPI.
DOF_NAMES: tuple[str, ...] = ("U1", "U2", "U3", "R1", "R2", "R3")


class Units(IntEnum):
    """SAP2000 ``eUnits`` enumeration (force_length_temperature).

    Values match the OAPI integer ids exactly, so ``int(Units.KN_M_C)`` can be
    passed straight to ``SetPresentUnits``.
    """

    LB_IN_F = 1
    LB_FT_F = 2
    KIP_IN_F = 3
    KIP_FT_F = 4
    KN_MM_C = 5
    KN_M_C = 6
    KGF_MM_C = 7
    KGF_M_C = 8
    N_MM_C = 9
    N_M_C = 10
    TON_MM_C = 11
    TON_M_C = 12
    KN_CM_C = 13
    KGF_CM_C = 14
    N_CM_C = 15
    TON_CM_C = 16


class ItemType(IntEnum):
    """SAP2000 ``eItemType`` — selects the target of an assignment.

    Used by ``Set*``/``Assign`` methods.
    """

    OBJECT = 0
    GROUP = 1
    SELECTED = 2


class ItemTypeElm(IntEnum):
    """SAP2000 ``eItemTypeElm`` — selects the target of a results query."""

    OBJECT_ELM = 0
    ELEMENT_ELM = 1
    GROUP_ELM = 2
    SELECTION_ELM = 3


class MatType(IntEnum):
    """SAP2000 ``eMatType`` material classification."""

    STEEL = 1
    CONCRETE = 2
    NO_DESIGN = 3
    ALUMINUM = 4
    COLD_FORMED = 5
    REBAR = 6
    TENDON = 7
    MASONRY = 8


class LoadPatternType(IntEnum):
    """SAP2000 ``eLoadPatternType`` — the common load-pattern types."""

    DEAD = 1
    SUPER_DEAD = 2
    LIVE = 3
    REDUCE_LIVE = 4
    QUAKE = 5
    WIND = 6
    SNOW = 7
    OTHER = 8
    MOVE = 9
    TEMPERATURE = 10
    PRESTRESS = 12


def dof_mask(names: Iterable[str]) -> list[bool]:
    """Convert DOF names to the 6-element boolean mask the OAPI expects.

    Replaces the ``{"U1": 0, "U2": 1, ...}`` + loop pattern that the old code
    duplicated in ``SapSection``, ``SapConstraints`` and elsewhere.

    Parameters
    ----------
    names:
        Any iterable of DOF names drawn from :data:`DOF_NAMES`
        (``"U1"`` .. ``"R3"``), case-insensitive.

    Returns
    -------
    list[bool]
        ``[U1, U2, U3, R1, R2, R3]`` with ``True`` where present.

    Raises
    ------
    ValueError
        If a name is not a recognized DOF.

    Examples
    --------
    >>> dof_mask(["U1", "R3"])
    [True, False, False, False, False, True]
    """
    index = {name: i for i, name in enumerate(DOF_NAMES)}
    mask = [False] * 6
    for raw in names:
        key = raw.upper()
        if key not in index:
            raise ValueError(f"{raw!r} is not a valid DOF; expected one of {DOF_NAMES}.")
        mask[index[key]] = True
    return mask


def to_dof_mask(
    spec: str | Sequence[str] | Sequence[bool] | None, *, default: bool = False
) -> list[bool]:
    """Normalize a DOF spec to ``[U1, U2, U3, R1, R2, R3]`` booleans."""
    if spec is None:
        return [default] * 6
    if isinstance(spec, str):
        return dof_mask([spec])
    values = list(spec)
    if all(isinstance(v, str) for v in values):
        return dof_mask(values)  # type: ignore[arg-type]
    if all(isinstance(v, bool) for v in values):
        if len(values) != 6:
            raise ValueError(f"expected 6 elements [U1..R3], got {len(values)}.")
        return [bool(v) for v in values]
    raise ValueError("DOF spec must be a DOF name, DOF name sequence, 6-bool mask, or None.")


class DOF:
    """Convenience constructors for the 6-element restraint/release mask.

    All methods return a fresh ``list[bool]`` ``[U1, U2, U3, R1, R2, R3]``.
    """

    @staticmethod
    def fixed() -> list[bool]:
        """All six DOF restrained."""
        return [True] * 6

    @staticmethod
    def free() -> list[bool]:
        """No DOF restrained."""
        return [False] * 6

    @staticmethod
    def pinned() -> list[bool]:
        """Translations restrained, rotations free."""
        return [True, True, True, False, False, False]

    @staticmethod
    def of(*names: str) -> list[bool]:
        """Restrain exactly the named DOF, e.g. ``DOF.of("U1", "U3")``."""
        return dof_mask(names)
