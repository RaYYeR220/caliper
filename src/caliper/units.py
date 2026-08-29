"""Unit conversion for laboratory values.

Two rules govern this module. First, a conversion that is not in the table does not happen —
`convert` returns None and the criterion goes unresolved, because a wrong unit is a wrong dose of
confidence. Second, mass and substance units cannot be interconverted without knowing *what* was
measured, so the molar bridge is keyed by the analyte's LOINC code rather than by the unit alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from caliper.ir import Code

# Every entry is a factor to the family's base unit.
_MASS_PER_VOLUME = {  # base: mg/L
    "g/l": 1000.0,
    "g/dl": 10000.0,
    "mg/l": 1.0,
    "mg/dl": 10.0,
    "ug/l": 0.001,
    "ug/dl": 0.01,
    "mcg/dl": 0.01,
}

_SUBSTANCE_PER_VOLUME = {  # base: umol/L
    "mol/l": 1_000_000.0,
    "mmol/l": 1000.0,
    "umol/l": 1.0,
    "nmol/l": 0.001,
}

_ALIASES = {
    "µmol/l": "umol/l",
    "μmol/l": "umol/l",
    "µg/dl": "ug/dl",
    "μg/dl": "ug/dl",
    "mg/dl.": "mg/dl",
}


@dataclass(frozen=True)
class Analyte:
    """What we need to know about a substance to cross between mass and molar units."""

    molar_mass_g_per_mol: float


# Keyed by LOINC. Deliberately short: an analyte we have not vetted is an analyte we do not convert.
ANALYTES: dict[str, Analyte] = {
    "2160-0": Analyte(molar_mass_g_per_mol=113.12),  # Creatinine, serum
    "38483-4": Analyte(molar_mass_g_per_mol=113.12),  # Creatinine, blood
    "1975-2": Analyte(molar_mass_g_per_mol=584.66),  # Bilirubin, total
    "2345-7": Analyte(molar_mass_g_per_mol=180.16),  # Glucose, serum
    "2093-3": Analyte(molar_mass_g_per_mol=386.65),  # Cholesterol, total
}


def normalise_unit(unit: str) -> str:
    cleaned = unit.strip().casefold().replace(" ", "")
    return _ALIASES.get(cleaned, cleaned)


def _family(unit: str) -> tuple[str, float] | None:
    if unit in _MASS_PER_VOLUME:
        return "mass", _MASS_PER_VOLUME[unit]
    if unit in _SUBSTANCE_PER_VOLUME:
        return "substance", _SUBSTANCE_PER_VOLUME[unit]
    return None


def _analyte_for(codes: tuple[Code, ...]) -> Analyte | None:
    for code in codes:
        if code.system == "LOINC" and code.code in ANALYTES:
            return ANALYTES[code.code]
    return None


def convert(
    value: float, from_unit: str, to_unit: str, codes: tuple[Code, ...] = ()
) -> float | None:
    """Convert `value` into `to_unit`, or return None when we cannot do it honestly."""
    src, dst = normalise_unit(from_unit), normalise_unit(to_unit)
    if src == dst:
        return value

    src_family, dst_family = _family(src), _family(dst)
    if src_family is None or dst_family is None:
        return None

    src_kind, src_factor = src_family
    dst_kind, dst_factor = dst_family
    if src_kind == dst_kind:
        return value * src_factor / dst_factor

    analyte = _analyte_for(codes)
    if analyte is None:
        return None

    # mg/L divided by g/mol gives mmol/L; scale to the umol/L base used above.
    if src_kind == "mass":
        mg_per_l = value * src_factor
        umol_per_l = mg_per_l / analyte.molar_mass_g_per_mol * 1000.0
        return umol_per_l / dst_factor
    umol_per_l = value * src_factor
    mg_per_l = umol_per_l * analyte.molar_mass_g_per_mol / 1000.0
    return mg_per_l / dst_factor
