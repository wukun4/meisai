"""Zero-storage local delivery stream; scalar transport and speed are independent.

beta is the delivered-stream dry-air fraction, not an occupied-area fraction.
The entrainment ratio r=(1-beta)/beta is prescribed, not measured. beta=0 is
the infinite-entrainment diagnostic limit; it need not erase prescribed speed.
No method here changes the background or adds a second global heat/moisture source.
"""
from pathlib import Path
import math
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model'))
from thermal_backend import air_state_from_hw, mix_air_streams


def entrainment_ratio(beta):
    beta = float(beta)
    if not math.isfinite(beta) or not 0 <= beta <= 1:
        raise ValueError('beta must be a finite dry-air mass fraction in [0,1]')
    return math.inf if beta == 0 else (1-beta)/beta


def mixed_hw(background_h, background_w, outlet_h, outlet_w, beta):
    """Conserved specific enthalpy and humidity ratio, scalar or array inputs."""
    entrainment_ratio(beta)
    if beta == 0:
        return background_h, background_w
    if beta == 1:
        return outlet_h, outlet_w
    return ((1-beta)*background_h + beta*outlet_h,
            (1-beta)*background_w + beta*outlet_w)


def heat_outlet(outlet, power_w=0., supply_kg_da_s=None, alpha=0.):
    """Add alpha of device power before local delivery, with no extra water.

    alpha=1 is the conservative assumption that all electricity is dissipated
    into the supply before it reaches passengers. The bulk model counts the
    full power once, independently of this diagnostic allocation.
    """
    if not 0 <= alpha <= 1 or power_w < 0:
        raise ValueError('alpha must be in [0,1] and power nonnegative')
    if alpha*power_w == 0:
        return outlet
    if supply_kg_da_s is None or supply_kg_da_s <= 0:
        raise ValueError('Positive dry-air supply flow is required for local heat')
    return air_state_from_hw(outlet.h_j_kg_da + alpha*power_w/supply_kg_da_s,
                             outlet.w, outlet.p_pa)


def local_delivery(background, pure_outlet, beta, power_w=0.,
                   supply_kg_da_s=None, alpha=0.):
    """Common bus/station map: background plus optionally heated supply."""
    entrainment_ratio(beta)
    if beta == 0:
        return background
    heated = heat_outlet(pure_outlet, power_w, supply_kg_da_s, alpha)
    # Reuse the original backend's exact boundary handling and phase guard.
    return mix_air_streams(background, heated, beta)


def closure_checks():
    from thermal_backend import air_state, direct_evaporative
    background = air_state(34., .7)
    outlet = direct_evaporative(34., .7, .7, max_drop_c=5.)
    checks = {}; max_h = 0.; max_w = 0.
    md = .6; power = 1200.
    for alpha in (0., .5, 1.):
        heated = heat_outlet(outlet, power, md, alpha)
        for beta in (.25, .5, .75, 1.):
            r = entrainment_ratio(beta); me = r*md
            local = local_delivery(background, outlet, beta, power, md, alpha)
            # Return all mixed supply to the bulk; subtract both bulk withdrawals.
            h_net = (md+me)*local.h_j_kg_da-(md+me)*background.h_j_kg_da
            w_net = (md+me)*local.w-(md+me)*background.w
            h_expected = md*(outlet.h_j_kg_da-background.h_j_kg_da)+alpha*power
            w_expected = md*(outlet.w-background.w)
            max_h=max(max_h,abs(h_net-h_expected));max_w=max(max_w,abs(w_net-w_expected))
            assert abs((md+me)*local.h_j_kg_da-md*heated.h_j_kg_da-me*background.h_j_kg_da)<1e-8
            assert abs((md+me)*local.w-md*heated.w-me*background.w)<1e-12
            assert abs(h_net+(1-alpha)*power-(md*(outlet.h_j_kg_da-background.h_j_kg_da)+power))<1e-8
    checks['stream_enthalpy_and_water_closure']=max_h<1e-8 and max_w<1e-12
    checks['return_net_source_and_total_heat_once']=checks['stream_enthalpy_and_water_closure']
    checks['beta_zero_exact_background']=local_delivery(background,outlet,0.,power,md,1.)==background
    checks['fixed_background_alpha_zero_exact_legacy_mix']=all(local_delivery(background,outlet,beta)==mix_air_streams(background,outlet,beta) for beta in (0.,.1,.45,.8,1.))
    return {'checks':checks,'max_return_enthalpy_residual_w':max_h,'max_return_water_residual_kg_s':max_w}
