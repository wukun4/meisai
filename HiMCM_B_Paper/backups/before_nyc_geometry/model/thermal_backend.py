"""SI psychrometrics and SET for a shaded, warm-weather bus-stop model.

All public relative humidities are fractions (0--1), temperatures are deg C,
pressures are Pa, humidity ratios are kg water / kg dry air, and enthalpies are
J / kg dry air. Only the internal pythermalcomfort call uses RH in percent.
The default pressure is 101325 Pa. Functions accept scalar values.

PsychroLib supplies ASHRAE saturation-pressure and thermodynamic wet-bulb
calculations. The algebraic moisture and enthalpy balances use the same ASHRAE
SI coefficients, but preserve exactly zero water rather than imposing the
library's 1e-7 humidity-ratio floor. SET is delegated to pythermalcomfort; this
module does not implement or modify its physiological model.

Primary software/reference documentation:
https://psychrometrics.github.io/psychrolib/api_docs.html
https://psychrometrics.github.io/psychrolib/_modules/psychrolib.html
https://pythermalcomfort.readthedocs.io/en/stable/documentation/models.html
https://handbook.ashrae.org/handbooks/S20/SI/s20_ch41/s20_ch41_si.aspx
https://handbook.ashrae.org/Handbooks/A23/SI/A23_Ch53/a23_ch53_si.aspx

These are reduced, steady/quasi-steady calculations, not CFD, measured device
performance, a heat-health safety threshold, or a human exposure-history model.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import importlib.metadata
import json
import math

import psychrolib
from pythermalcomfort.models import set_tmp


DEFAULT_PRESSURE_PA = 101325.0
MOLECULAR_MASS_RATIO = 0.621945
CP_DRY_AIR = 1006.0
CP_VAPOR = 1860.0
LATENT_REFERENCE = 2501000.0

psychrolib.SetUnitSystem(psychrolib.SI)


@dataclass(frozen=True)
class AirState:
    """A consistent scalar gas-phase state, on a dry-air mass basis."""

    t_c: float
    rh: float
    w: float
    h_j_kg_da: float
    p_pa: float = DEFAULT_PRESSURE_PA


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite; received {value}")
    return value


def _fraction(name: str, value: float) -> float:
    value = _finite(name, value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be a fraction in [0, 1]; received {value}")
    return value


def _pressure(p_pa: float) -> float:
    p_pa = _finite("p_pa", p_pa)
    if p_pa <= 0.0:
        raise ValueError("p_pa must be positive")
    return p_pa


def _check_si() -> None:
    # PsychroLib has a process-global unit setting; fail if another caller alters it.
    # In 2.5.0 its optional Numba loop incorrectly vectorizes GetUnitSystem,
    # a zero-argument function; that accessor segfaults with this runtime.
    # Read the same stored enum directly. Thermodynamic functions are unchanged.
    if psychrolib.PSYCHROLIB_UNITS != psychrolib.SI:
        raise RuntimeError("PsychroLib units changed: this backend requires SI")


@lru_cache(maxsize=8192)
def saturation_vapor_pressure_pa(t_c: float) -> float:
    """ASHRAE saturation pressure [Pa], delegated to PsychroLib."""
    _check_si()
    return float(psychrolib.GetSatVapPres(_finite("t_c", t_c)))


@lru_cache(maxsize=32768)
def humidity_ratio(t_c: float, rh: float, p_pa: float = DEFAULT_PRESSURE_PA) -> float:
    """Humidity ratio [kg water/kg dry air] from T and RH fraction."""
    rh, p_pa = _fraction("rh", rh), _pressure(p_pa)
    pv = rh * saturation_vapor_pressure_pa(t_c)
    if pv >= p_pa:
        raise ValueError("Water-vapor partial pressure must be below total pressure")
    return MOLECULAR_MASS_RATIO * pv / (p_pa - pv)


def relative_humidity(t_c: float, w: float, p_pa: float = DEFAULT_PRESSURE_PA) -> float:
    """RH fraction; values above 1 identify a supersaturated proposed state."""
    w, p_pa = _finite("w", w), _pressure(p_pa)
    if w < 0.0:
        raise ValueError("Humidity ratio must be nonnegative")
    pv = p_pa * w / (MOLECULAR_MASS_RATIO + w)
    return pv / saturation_vapor_pressure_pa(t_c)


def enthalpy_j_kg_da(t_c: float, w: float) -> float:
    """Moist-air enthalpy [J/kg dry air], ASHRAE's conventional zero reference."""
    t_c, w = _finite("t_c", t_c), _finite("w", w)
    if w < 0.0:
        raise ValueError("Humidity ratio must be nonnegative")
    return CP_DRY_AIR * t_c + w * (LATENT_REFERENCE + CP_VAPOR * t_c)


@lru_cache(maxsize=32768)
def wet_bulb_c(t_c: float, rh: float, p_pa: float = DEFAULT_PRESSURE_PA) -> float:
    """Thermodynamic wet bulb [deg C]; PsychroLib's SI tolerance is 0.001 K."""
    _check_si()
    t_c, rh, p_pa = _finite("t_c", t_c), _fraction("rh", rh), _pressure(p_pa)
    humidity_ratio(t_c, rh, p_pa)  # Also validates vapor pressure versus total pressure.
    return float(psychrolib.GetTWetBulbFromRelHum(t_c, rh, p_pa))


@lru_cache(maxsize=32768)
def air_state(t_c: float, rh: float, p_pa: float = DEFAULT_PRESSURE_PA) -> AirState:
    """Construct a gas-phase air state from temperature and RH fraction."""
    t_c, rh, p_pa = _finite("t_c", t_c), _fraction("rh", rh), _pressure(p_pa)
    w = humidity_ratio(t_c, rh, p_pa)
    return AirState(t_c, rh, w, enthalpy_j_kg_da(t_c, w), p_pa)


def air_state_from_hw(h_j_kg_da: float, w: float,
                      p_pa: float = DEFAULT_PRESSURE_PA) -> AirState:
    """Invert the enthalpy balance; reject condensation instead of hiding it."""
    h_j_kg_da, w = _finite("h_j_kg_da", h_j_kg_da), _finite("w", w)
    p_pa = _pressure(p_pa)
    if w < 0.0:
        raise ValueError("Humidity ratio must be nonnegative")
    t_c = (h_j_kg_da - LATENT_REFERENCE * w) / (CP_DRY_AIR + CP_VAPOR * w)
    rh = relative_humidity(t_c, w, p_pa)
    if rh > 1.0 + 1e-10:
        raise ValueError("Mixture is supersaturated; a condensation model is required")
    # Only a floating-point saturation-boundary correction is allowed.
    return AirState(t_c, min(rh, 1.0), w, h_j_kg_da, p_pa)


@lru_cache(maxsize=32768)
def direct_evaporative(t_c: float, rh: float, epsilon: float,
                       p_pa: float = DEFAULT_PRESSURE_PA,
                       max_drop_c: float | None = None) -> AirState:
    """Direct-evaporative outlet with effectiveness epsilon and near-isenthalpy.

    T_out = T_in - min(epsilon*(T_in - T_wb), max_drop_c), when the optional
    rated temperature-drop ceiling is given. A rating is a ceiling, not a
    climate-independent achieved drop or evidence for a particular epsilon.
    Water vapor is solved from h_out = h_in. This neglects liquid-water inlet
    enthalpy, fan/pump heat, pressure drop, and liquid carryover. It applies to
    liquid-water cooling with T_wb >= 0 C. The thermodynamic wet-bulb and exact
    isenthalpic saturation temperatures differ slightly; neither is silently
    substituted for the other.
    """
    inlet = air_state(t_c, rh, p_pa)
    epsilon = _fraction("epsilon", epsilon)
    if max_drop_c is not None:
        max_drop_c = _finite("max_drop_c", max_drop_c)
        if max_drop_c < 0.0:
            raise ValueError("max_drop_c must be nonnegative")
    if epsilon == 0.0 or inlet.rh == 1.0 or max_drop_c == 0.0:
        return inlet
    twb = wet_bulb_c(inlet.t_c, inlet.rh, inlet.p_pa)
    if twb < 0.0:
        raise ValueError("This liquid-water evaporative model requires wet bulb >= 0 C")
    drop = epsilon * max(inlet.t_c - twb, 0.0)
    if max_drop_c is not None:
        drop = min(drop, max_drop_c)
    outlet_t = inlet.t_c - drop
    outlet_w = (inlet.h_j_kg_da - CP_DRY_AIR * outlet_t) / (
        LATENT_REFERENCE + CP_VAPOR * outlet_t
    )
    return air_state_from_hw(inlet.h_j_kg_da, outlet_w, inlet.p_pa)


def mix_air_streams(first: AirState, second: AirState,
                    second_fraction: float) -> AirState:
    """Adiabatic gas mixing; second_fraction is its DRY-AIR mass-flow fraction.

    Enthalpy and humidity ratio are conserved. RH and dry-bulb temperature
    are recovered afterwards, not linearly averaged. No condensation, external
    heat, momentum, radiation, or fan effects are represented by this function.
    """
    fraction = _fraction("second_fraction", second_fraction)
    if not math.isclose(first.p_pa, second.p_pa, rel_tol=1e-9, abs_tol=1e-6):
        raise ValueError("Air streams must have the same pressure before mixing")
    if fraction == 0.0:
        return first
    if fraction == 1.0:
        return second
    h = (1.0 - fraction) * first.h_j_kg_da + fraction * second.h_j_kg_da
    w = (1.0 - fraction) * first.w + fraction * second.w
    return air_state_from_hw(h, w, first.p_pa)


def mix_by_dry_air_mass_flow(first: AirState, second: AirState,
                             first_kg_da_s: float, second_kg_da_s: float) -> AirState:
    """Convenience interface for two nonnegative dry-air flows [kg dry air/s]."""
    m1 = _finite("first_kg_da_s", first_kg_da_s)
    m2 = _finite("second_kg_da_s", second_kg_da_s)
    if m1 < 0.0 or m2 < 0.0 or m1 + m2 <= 0.0:
        raise ValueError("Mass flows must be nonnegative and their sum positive")
    return mix_air_streams(first, second, m2 / (m1 + m2))


@lru_cache(maxsize=65536)
def set_temperature(t_c: float, tr_c: float, v_m_s: float, rh: float,
                    met: float = 1.2, clo: float = 0.5,
                    p_pa: float = DEFAULT_PRESSURE_PA,
                    position: str = "standing") -> float:
    """Unrounded SET [deg C], with pythermalcomfort applicability limits active.

    RH is a fraction here. MRT (tr_c), local air speed, clothing, and activity
    must be specified consistently for baseline and intervention. Values out of
    the library's applicability domain raise, rather than being extrapolated.
    This scalar convenience wrapper is cached for repeated scenario states.
    """
    t_c, tr_c, v_m_s = (_finite("t_c", t_c), _finite("tr_c", tr_c),
                       _finite("v_m_s", v_m_s))
    rh, met, clo = _fraction("rh", rh), _finite("met", met), _finite("clo", clo)
    p_pa = _pressure(p_pa)
    if v_m_s < 0.0 or met <= 0.0 or clo < 0.0:
        raise ValueError("Air speed/clothing must be nonnegative; met must be positive")
    result = float(set_tmp(tdb=t_c, tr=tr_c, v=v_m_s, rh=100.0 * rh,
                           met=met, clo=clo, p_atm=p_pa, position=position,
                           limit_inputs=True, round_output=False).set)
    if not math.isfinite(result):
        raise ValueError("SET inputs outside pythermalcomfort applicability limits: "
                         f"tdb={t_c}, tr={tr_c}, v={v_m_s}, met={met}, clo={clo}")
    return result


def physical_self_check() -> dict:
    """Small conservation/boundary checks plus the official SET example."""
    baseline = air_state(35.0, 0.4)
    cooled = direct_evaporative(35.0, 0.4, 0.8)
    assert direct_evaporative(35.0, 0.4, 0.0) == baseline
    assert mix_air_streams(baseline, cooled, 0.0) == baseline
    assert mix_air_streams(baseline, cooled, 1.0) == cooled
    mix = mix_air_streams(baseline, cooled, 0.35)
    assert math.isclose(mix.w, 0.65 * baseline.w + 0.35 * cooled.w, abs_tol=1e-12)
    assert math.isclose(mix.h_j_kg_da, baseline.h_j_kg_da, abs_tol=1e-8)
    different_enthalpy = air_state(28.0, 0.6)
    general_mix = mix_by_dry_air_mass_flow(baseline, different_enthalpy, 2.0, 1.0)
    assert math.isclose(3.0 * general_mix.h_j_kg_da,
                        2.0 * baseline.h_j_kg_da + different_enthalpy.h_j_kg_da,
                        abs_tol=1e-8)
    capped = direct_evaporative(35.0, 0.4, 1.0, max_drop_c=5.0)
    assert math.isclose(capped.t_c, 30.0, abs_tol=1e-10)
    saturated = air_state(35.0, 1.0)
    assert direct_evaporative(35.0, 1.0, 1.0) == saturated
    assert math.isclose(wet_bulb_c(35.0, 1.0), 35.0, abs_tol=0.001)
    assert math.isclose(relative_humidity(baseline.t_c, baseline.w), baseline.rh,
                        abs_tol=1e-12)
    for t_c in (25.0, 30.0, 35.0, 39.0):
        for rh in (0.1, 0.4, 0.8, 0.95, 1.0):
            for eps in (0.0, 0.5, 0.8, 1.0):
                state = direct_evaporative(t_c, rh, eps)
                assert 0.0 <= state.rh <= 1.0
                assert state.t_c <= t_c + 1e-10
                assert state.t_c >= wet_bulb_c(t_c, rh) - 1e-9
                assert state.w >= humidity_ratio(t_c, rh) - 1e-12
                assert math.isclose(state.h_j_kg_da,
                                    enthalpy_j_kg_da(t_c, humidity_ratio(t_c, rh)),
                                    abs_tol=1e-8)
    reference_set = set_temperature(25.0, 25.0, 0.1, 0.5)
    assert round(reference_set, 1) == 24.3  # Official API documentation example.
    try:
        set_temperature(45.0, 45.0, 0.2, 0.5)
    except ValueError:
        outside_domain_rejected = True
    else:
        raise AssertionError("SET domain guard failed")
    return {
        "checks": "passed",
        "psychrolib_version": importlib.metadata.version("psychrolib"),
        "pythermalcomfort_version": importlib.metadata.version("pythermalcomfort"),
        "pressure_pa": DEFAULT_PRESSURE_PA,
        "saturation_pressure_35c_pa": saturation_vapor_pressure_pa(35.0),
        "wet_bulb_35c_rh40_c": wet_bulb_c(35.0, 0.4),
        "evap_eps_0_8_35c_rh40": cooled.__dict__,
        "set_official_example_c": reference_set,
        "outside_set_domain_rejected": outside_domain_rejected,
        "psychrolib_unit_guard": "Read PSYCHROLIB_UNITS directly: avoid 2.5.0 zero-argument Numba accessor crash; physical routines unchanged",
    }


if __name__ == "__main__":
    print(json.dumps(physical_self_check(), indent=2))
