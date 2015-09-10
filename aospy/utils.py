"""aospy.utils: utility functions for the aospy module."""
import numpy as np
import xray

from . import user_path
from .constants import grav


def load_user_data(name):
    """Load user data from aospy_path for given module name.

    File must be located in the `aospy_path` directory and be the same name
    as the desired aospy module subpackage, namely one of `regions`, `calcs`,
    `variables`, and `projects`.
    """
    import imp
    return imp.load_source(
        name, '/'.join([user_path, name, '__init__.py']).replace('//', '/')
    )


def robust_bool(obj):
    try:
        return bool(obj)
    except ValueError:
        return obj.any()


def get_parent_attr(obj, attr, strict=False):
    """
    Check if the object has the given attribute and it is non-empty.  If not,
    check each parent object for the attribute and use the first one found.
    """
    attr_val = getattr(obj, attr, False)
    if robust_bool(attr_val):
        return attr_val

    else:
        for parent in ('parent', 'var', 'run', 'model', 'proj'):
            parent_obj = getattr(obj, parent, False)
            if parent_obj:
                return get_parent_attr(parent_obj, attr, strict=strict)

        if strict:
            raise AttributeError('Attribute %s not found in parent of %s'
                                 % (attr, obj))
        else:
            return None


def dict_name_keys(objs):
    """Create dict whose keys are the 'name' attr of the objects."""
    assert isinstance(objs, (tuple, list, dict))
    if isinstance(objs, (tuple, list)):
        try:
            return {obj.name: obj for obj in objs}
        except AttributeError:
            raise AttributeError
    else:
        return objs


def to_radians(field):
    if np.max(np.abs(field)) > 2*np.pi:
        return np.deg2rad(field)
    else:
        return field


def to_pascal(field):
    # For dp fields, this won't work if the input data is already Pascals and
    # the largest level thickness is < 1200 Pa, i.e. 12 hPa.  This will almost
    # never come up in practice for data interpolated to pressure levels, but
    # could come up in sigma data if model has sufficiently high vertical
    # resolution.
    if np.max(np.abs(field)) < 1200.:
        field *= 100.
    return field


def to_hpa(field):
    """Convert pressure array from Pa to hPa (if needed)."""
    if np.max(np.abs(field)) > 1200.:
        field /= 100.
    return field


def level_thickness(p):
    """
    Calculates the thickness, in Pa, of each pressure level.

    Assumes that the pressure values given are at the center of that model
    level, except for the lowest value (typically 1000 hPa), which is the
    bottom boundary. The uppermost level extends to 0 hPa.

    """
    # Bottom level extends from p[0] to halfway betwen p[0]
    # and p[1].
    p = to_pascal(p)
    dp = [0.5*(p[0] - p[1])]
    # Middle levels extend from halfway between [k-1], [k] and [k], [k+1].
    for k in range(1, p.size-1):
        dp.append(0.5*(p[k-1] - p[k+1]))
    # Top level extends from halfway between top two levels to 0 hPa.
    dp.append(0.5*(p[-2] + p[-1]))
    # Convert to numpy array and from hectopascals (hPa) to Pascals (Pa).
    return np.array(dp)

def level_thickness_xray(p):
    """
    Calculates the thickness, in Pa, of each pressure level.

    Assumes that the pressure values given are at the center of that model
    level, except for the lowest value (typically 1000 hPa), which is the
    bottom boundary. The uppermost level extends to 0 hPa.

    """
    # Bottom level extends from p[0] to halfway betwen p[0]
    # and p[1].
    p = to_pascal(p)
    dp = [0.5*(p[0] - p[1])]
    # Middle levels extend from halfway between [k-1], [k] and [k], [k+1].
    for k in range(1, p.size-1):
        dp.append(0.5*(p[k-1] - p[k+1]))
    # Top level extends from halfway between top two levels to 0 hPa.
    dp.append(0.5*(p[-2] + p[-1]))
    # Convert to numpy array and from hectopascals (hPa) to Pascals (Pa).
    return xray.DataArray(dp, coords=[p/100.0], dims=['level'])
    
def phalf_from_sigma(bk, pk, ps):
    """
    Compute pressure at sigma half levels from the sigma coordinate arrays and
    the surface pressure.

    Assume pk, bk, and ps are in Pa, unitless, and Pa, respectively.  Assume
    pk[-1] and bk[-1] are at surface where pressure equals ps and pk[0] and
    bk[0] are at top of atmosphere where pressure equals zero.  pk and bk are
    1-d arrays; ps has last two dimensions (lat, lon) but may also have time as
    first dimension.  Assume pk and bk include both endpoints, i.e. the surface
    and TOA, such that the number of sigma layers is one less than the length
    of either pk or bk.
    """
    # 3D ps array assumed to be (time, lat, lon).
    if ps.ndim in (3, 4):
        bk = bk[np.newaxis,:,np.newaxis,np.newaxis]
        pk = pk[np.newaxis,:,np.newaxis,np.newaxis]
        if ps.ndim == 3:
            ps = ps[:,np.newaxis,:,:]
    # 2D ps array assumed to be (lat, lon).
    elif ps.ndim == 2:
        bk = bk[:,np.newaxis,np.newaxis]
        pk = pk[:,np.newaxis,np.newaxis]
        ps = ps[np.newaxis,:,:]
    return np.squeeze(pk + ps*bk)

def phalf_from_sigma_xray(bk, pk, ps):
    """
    This should work. 
    """
    return (ps*bk + pk)

def pfull_from_phalf(phalf):
    """
    Compute data at full sigma levels from the values at half levels.

    Could be the pressure array itself, but it could also be any other data
    defined at half levels.
    """
    # 4D array assumed to be (time, p, lat, lon).
    if phalf.ndim == 4:
        return 0.5*(phalf[:,1:] + phalf[:,:-1])
    # Anything else assumed to have p as first dimension.
    else:
        return 0.5*(phalf[1:] + phalf[:-1])

def pfull_from_phalf_xray(phalf, pfull_coord):
    """
    Compute data at full sigma levels from the values at the half levels.
    """
    # We will need to be smart in how we set the coordinates so that we can
    # add things gracefully within xray.
    phalf_top = phalf.isel(phalf=slice(1,None))
    phalf_top = phalf_top.rename({'phalf' : 'pfull'})
    phalf_top['pfull'] = pfull_coord
 
    phalf_bot = phalf.isel(phalf=slice(None,-1))
    phalf_bot = phalf_bot.rename({'phalf' : 'pfull'})
    phalf_bot['pfull'] = pfull_coord

    return 0.5*(phalf_bot + phalf_top)

def phalf_from_pfull(pfull, val_toa=0, val_sfc=0):
    """
    Compute data at half sigma levels from the values at full levels, given the
    specified top and bottom boundary conditions.

    Could be the pressure array itself, but it could also be any other data
    defined at pressure levels.
    """
    phalf = np.empty((pfull.shape[0] + 1, pfull.shape[1], pfull.shape[2]))
    phalf[0] = val_toa
    phalf[-1] = val_sfc
    phalf[1:-1] = 0.5*(pfull[:-1] + pfull[1:])
    return phalf

def pfull_from_sigma_xray(bk, pk, ps, pfull_coord):
    return pfull_from_phalf_xray(phalf_from_sigma_xray(bk, pk, ps), pfull_coord)

def pfull_from_sigma(bk, pk, ps):
    """
    Compute pressure at full sigma levels from the sigma coordinate arrays and
    surface pressure.
    """
    return pfull_from_phalf(phalf_from_sigma(bk, pk, ps))


def dp_from_phalf(phalf):
    """Compute pressure-depth of vertical levels from level edge pressures."""
    # If 4D, assume dimensions (time, p, lat, lon).
    if phalf.ndim == 4:
        return phalf[:,1:] - phalf[:,:-1]
    # Otherwise assume first dimension is p.
    else:
        return phalf[1:] - phalf[:-1]

def dp_from_phalf_xray(phalf, pfull_coord):
    # We need to make sure dp is on a pfull coord.
    dp = phalf.diff(dim='phalf', n=1)
    dp = dp.rename({'phalf' : 'pfull'})
    dp['pfull'] = pfull_coord
    return dp

def dp_from_sigma(bk, pk, ps):
    """Compute sigma layer pressure thickness."""
    return dp_from_phalf(phalf_from_sigma(bk, pk, ps))

def dp_from_sigma_xray(bk, pk, ps, pfull_coord):
    return dp_from_phalf_xray(phalf_from_sigma_xray(bk, pk, ps), pfull_coord)

def weight_by_delta(integrand, delta):
    """
    Weight the `integrand` by `delta`, usually for subsequent integration.

    `delta` array may be one dimension or three; if the latter it is assumed to
    be of shape (vertical, lat, lon).  `integrand` is assumed to be 3 or 4
    dimensions, with time 1st if 4-D.  Both are assumed to be numpy arrays.
    """
    try:
        return integrand*delta
    except ValueError:
        delta = delta[np.newaxis,:,np.newaxis, np.newaxis]
    return integrand*delta


def integrate(integrand, delta, axis):
    """Integrate the array along the given axis using the given delta array."""
    prod = weight_by_delta(integrand, delta)
    # Override axis specified if input is integrand is a singleton.
    if isinstance(integrand, (int, float)):
        axis = 0
    return np.ma.sum(prod, axis=axis)


def int_dp_g(integrand, dp, start=0., end=None, axis=-3):
    """Integrate vertically in pressure."""
    # Assume pressure is 3rd to last axis.
    dp = to_pascal(dp)
    return integrate(integrand, dp, axis) * (1. / grav)


def dp_from_p(p, ps):
    """Get level thickness of pressure data, incorporating surface pressure."""
    # Top layer goes to 0 hPa; bottom layer goes to 1100 hPa.
    p = to_pascal(p)[np.newaxis,:,np.newaxis,np.newaxis]
    p_top = np.array([0])[np.newaxis,:,np.newaxis,np.newaxis]
    p_bot = np.array([1.1e5])[np.newaxis,:,np.newaxis,np.newaxis]

    # Layer edges are halfway between the given pressure levels.
    p_edges_interior = 0.5*(p[:,:-1] + p[:,1:])
    p_edges = np.concatenate((p_bot, p_edges_interior, p_top), axis=1)
    p_edge_above = p_edges[:, 1:]
    p_edge_below = p_edges[:, :-1]
    dp_interior = p_edge_below - p_edge_above

    ps = to_pascal(ps)[:,np.newaxis,:,:]
    # If ps < p_edge_below, then ps becomes the layer's bottom boundary.
    dp_adj_sfc = ps - p_edge_above[np.newaxis,:,np.newaxis,np.newaxis]
    dp = np.where(np.sign(ps - p_edge_below) > 0, dp_interior, dp_adj_sfc)
    # Mask where ps is less than the p.
    return np.ma.masked_where(ps < p, dp)

def vert_coord_name_xray(dp):
    for name in ['level', 'pfull']:
        if name in dp.coords:
            return name
    return None    
