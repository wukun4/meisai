"""Gross shelter geometry and occupancy accounting; no airflow solver.

Dimensions define equal spatial strips. A local field supplied for a strip is
an input, not a field inferred from its dimensions or from the source drawing.
"""
import math


def _nonnegative_vector(values, size, label):
    if not isinstance(values, (list, tuple)) or len(values) != size:
        raise ValueError(f'{label} must contain exactly {size} values')
    try:
        result = [float(v) for v in values]
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{label} must contain finite nonnegative numbers') from exc
    if any(not math.isfinite(v) or v < 0 for v in result):
        raise ValueError(f'{label} must contain finite nonnegative numbers')
    return result


def shelter_zones(cfg):
    """Return the three equal x-strips, in metres and gross square metres.

    The origin is at the assumed device end, and y spans the full width.
    Bench and frame areas are not subtracted; height is not treated as a
    closed cooled volume. Other dimensions can be used for counterfactuals.
    """
    g = cfg['geometry']
    dims = [float(g[key]) for key in ('length_m', 'width_m', 'height_m')]
    if any(not math.isfinite(v) or v <= 0 for v in dims):
        raise ValueError('Shelter length, width and height must be finite and positive')
    length, width, _ = dims
    names = cfg['zone_names']
    if len(names) != 3 or len(set(names)) != 3:
        raise ValueError('This reduced model requires three uniquely named zones')
    zones = []
    for i, name in enumerate(names):
        xmin, xmax = length * i / 3, length * (i + 1) / 3
        zones.append(dict(zone=name, x_min_m=xmin, x_max_m=xmax,
                          y_min_m=0.0, y_max_m=width,
                          center_x_m=(xmin+xmax)/2, center_y_m=width/2,
                          gross_area_m2=(xmax-xmin)*width))
    return zones


def occupancy_counts(cfg, occupancy):
    """Resolve mean simultaneous people without counting floor area twice.

    Each scenario accepts a list of people (legacy form), {'people': [...]},
    or {'gross_density_people_m2': [...]}. The two dictionary forms are
    mutually exclusive. Gross density does not imply capacity or usable space.
    """
    zones = shelter_zones(cfg)
    spec = cfg['occupancies'][occupancy]
    if isinstance(spec, dict):
        if set(spec) == {'people'}:
            return _nonnegative_vector(spec['people'], len(zones), 'people')
        if set(spec) == {'gross_density_people_m2'}:
            rho = _nonnegative_vector(spec['gross_density_people_m2'], len(zones), 'gross density')
            return [r * z['gross_area_m2'] for r, z in zip(rho, zones)]
        raise ValueError('Specify exactly one occupancy basis: people or gross_density_people_m2')
    return _nonnegative_vector(spec, len(zones), 'people')


def occupancy_rows(cfg):
    """Report geometry and implied gross density for every occupancy scenario."""
    zones = shelter_zones(cfg)
    rows = []
    for name, spec in cfg['occupancies'].items():
        basis = 'gross_density_people_m2' if isinstance(spec, dict) and 'gross_density_people_m2' in spec else 'people'
        for zone, people in zip(zones, occupancy_counts(cfg, name)):
            rows.append(dict(occupancy=name, input_basis=basis, **zone,
                             mean_people=people,
                             gross_density_people_m2=people/zone['gross_area_m2']))
    return rows
