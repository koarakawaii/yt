"""
Title: answer_tests.py
Purpose: Contains answer tests that are used by yt's various frontends
"""
import os
import tempfile

import hashlib
import matplotlib.image as mpimg
import numpy as np

from yt.analysis_modules.cosmological_observation.api import \
     LightCone
from yt.analysis_modules.halo_analysis.api import HaloCatalog
from yt.analysis_modules.halo_mass_function.api import HaloMassFcn
from yt.utilities.on_demand_imports import \
    _h5py as h5py
from . import utils
import yt.visualization.plot_window as pw


def grid_hierarchy_test(ds):
    result = {}
    result['grid_dimensions'] = ds.index.grid_dimensions
    result['grid_left_edge'] = ds.index.grid_left_edge
    result['grid_right_edge'] = ds.index.grid_right_edge
    result['grid_levels'] = ds.index.grid_levels
    result['grid_particle_count'] = ds.index.grid_particle_count
    return result

def parentage_relationships_test(ds):
    parents = []
    children = []
    for g in ds.index.grids:
        p = g.Parent
        if p is None:
            parents.append(-1)
        elif hasattr(p, "id"):
            parents.append(p.id)
        else:
            parents = parents + [pg.id for pg in p]
        children = children + [c.id for c in g.Children]
    result = np.array(parents + children)
    return result 

def grid_values_test(ds, field):
    # The hashing is done here so that there is only one entry for
    # the test that contains info about all of the grids as opposed
    # to having a separate 'grid_id : grid_hash' pair for each grid
    # since that makes the answer file much larger
    result = None
    for g in ds.index.grids:
        if result is None:
            result = hashlib.md5(bytes(g.id) + g[field].tobytes())
        else:
            result.update(bytes(g.id) + g[field].tobytes())
        g.clear_data()
    return result.hexdigest()

def projection_values_test(ds, axis, field, weight_field, dobj_type):
    if dobj_type is not None:
        dobj = utils.create_obj(ds, dobj_type)
    else:
        dobj = None
    if ds.domain_dimensions[axis] == 1:
        # This originally returned None, but None can't be converted
        # to a bytes array (for hashing), so use -1 as a string,
        # since ints can't be converted to bytes either
        return bytes(str(-1).encode('utf-8'))
    proj = ds.proj(field,
                axis,
                weight_field=weight_field,
                data_source=dobj
            )
    # This is to try and remove python-specific anchors in the yaml
    # answer file. Also, using __repr__() results in weird strings
    # of strings that make comparison fail even though the data is
    # the same
    result = None 
    for k, v in proj.field_data.items():
        k = k.__repr__().encode('utf8')
        if result is None:
            result = hashlib.md5(k + v.tobytes())
        else:
            result.update(k + v.tobytes())
    return result.hexdigest()

def field_values_test(ds, field, obj_type=None, particle_type=False):
    # If needed build an instance of the dataset type
    obj = utils.create_obj(ds, obj_type)
    determined_field = obj._determine_fields(field)[0]
    # Get the proper weight field depending on if we're looking at
    # particles or not
    if particle_type:
        weight_field = (determined_field[0], "particle_ones")
    else:
        weight_field = ("index", "ones")
    # Get the average, min, and max
    avg = obj.quantities.weighted_average_quantity(
        determined_field,
        weight=weight_field)
    minimum, maximum = obj.quantities.extrema(field)
    # Return as a hashable bytestring
    return np.array([avg, minimum, maximum])

def pixelized_projection_values_test(ds, axis, field,
    weight_field=None, dobj_type=None):
    if dobj_type is not None:
        obj = utils.create_obj(ds, dobj_type)
    else:
        obj = None
    proj = ds.proj(field, axis, weight_field=weight_field, data_source=obj)
    frb = proj.to_frb((1.0, 'unitary'), 256)
    frb[field]
    if weight_field is not None:
        frb[weight_field]
    d = frb.data
    for f in proj.field_data:
        # Sometimes f will be a tuple.
        d["%s_sum" % (f,)] = proj.field_data[f].sum(dtype="float64")
    # This is to try and remove python-specific anchors in the yaml
    # answer file. Also, using __repr__() results in weird strings
    # of strings that make comparison fail even though the data is
    # the same
    result = None 
    for k, v in d.items():
        k = k.__repr__().encode('utf8')
        if result is None:
            result = hashlib.md5(k + v.tobytes())
        else:
            result.update(k + v.tobytes())
    return result.hexdigest()


def simulated_halo_mass_function_test(ds, finder):
    hc = HaloCatalog(data_ds=ds, finder_method=finder)
    hc.create()
    hmf = HaloMassFcn(halos_ds=hc.halos_ds)
    result = np.empty((2, hmf.masses_sim.size))
    result[0] = hmf.masses_sim.d
    result[1] = hmf.n_cumulative_sim.d
    return result

def analytic_halo_mass_function_test(ds, fit):
    hmf = HaloMassFcn(simulation_ds=ds, fitting_function=fit)
    result = np.empty((2, hmf.masses_analytic.size))
    result[0] = hmf.masses_analytic.d
    result[1] = hmf.n_cumulative_analytic.d
    return result

def small_patch_amr(ds, field, weight, axis, ds_obj):
    hex_digests = {} 
    # Grid hierarchy test
    gh_hd = grid_hierarchy_test(ds)
    hex_digests['grid_hierarchy'] = gh_hd
    # Parentage relationships test
    pr_hd = parentage_relationships_test(ds)
    hex_digests['parentage_relationships'] = pr_hd
    # Grid values, projection values, and field values tests
    gv_hd = grid_values_test(ds, field)
    hex_digests['grid_values'] = gv_hd
    fv_hd = field_values_test(ds, field, ds_obj)
    hex_digests['field_values'] = fv_hd
    pv_hd = projection_values_test(ds, axis, field, weight, ds_obj)
    hex_digests['projection_values'] = pv_hd
    return hex_digests

def big_patch_amr(ds, field, weight, axis, ds_obj):
    hex_digests = {} 
    # Grid hierarchy test
    gh_hd = grid_hierarchy_test(ds)
    hex_digests['grid_hierarchy'] = gh_hd
    # Parentage relationships test
    pr_hd = parentage_relationships_test(ds)
    hex_digests['parentage_relationships'] = pr_hd
    # Grid values, projection values, and field values tests
    gv_hd = grid_values_test(ds, field)
    hex_digests['grid_values'] = gv_hd
    ppv_hd = pixelized_projection_values_test(ds, axis, field, weight, ds_obj)
    hex_digests['pixelized_projection_values'] = ppv_hd 
    return hex_digests

def generic_array_test(func, args=None, kwargs=None):
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}
    return func(*args, **kwargs)

def sph_answer(ds, ds_str_repr, ds_nparticles, field, weight, ds_obj, axis):
    # Make sure we're dealing with the right dataset
    assert str(ds) == ds_str_repr
    # Set up keys of test names
    hex_digests = {} 
    dd = ds.all_data()
    assert dd["particle_position"].shape == (ds_nparticles, 3)
    tot = sum(dd[ptype, "particle_position"].shape[0]
              for ptype in ds.particle_types if ptype != "all")
    # Check
    assert tot == ds_nparticles
    dobj = utils.create_obj(ds, ds_obj)
    s1 = dobj["ones"].sum()
    s2 = sum(mask.sum() for block, mask in dobj.blocks)
    assert s1 == s2
    if field[0] in ds.particle_types:
        particle_type = True
    else:
        particle_type = False
    if particle_type is False:
        ppv_hd = pixelized_projection_values_test(ds, axis, field, weight, ds_obj)
        hex_digests['pixelized_projection_values'] = ppv_hd
    fv_hd = field_values_test(ds, field, ds_obj, particle_type=particle_type)
    hex_digests['field_values'] = fv_hd
    return hex_digests

def yt_field_test(ds, field, geometric):
    if geometric:
        obj = ds.all_data()
    else:
        obj = ds.data
    return np.array([obj[field].size, obj[field].mean()])

def plot_window_attribute_test(ds, plot_field, plot_axis, attr_name,
    attr_args, plot_type='SlicePlot', callback_id='', callback_runners=[]):
    plot = utils._create_plot_window_attribute_plot(ds, plot_type, plot_field, plot_axis, {})
    for r in callback_runners:
        r(plot_field, plot)
    attr = getattr(plot, attr_name)
    attr(*attr_args[0], **attr_args[1])
    tmpfd, tmpname = tempfile.mkstemp(suffix='.png')
    os.close(tmpfd)
    plot.save(name=tmpname)
    image = mpimg.imread(tmpname)
    os.remove(tmpname)
    return image

def phase_plot_attribute_test(ds_fn, x_field, y_field, z_field,
             attr_name, attr_args, plot_type='PhasePlot',
             plot_kwargs={}):
    data_source = ds_fn.all_data()
    plot = utils._create_phase_plot_attribute_plot(data_source, x_field, y_field,
                            z_field, plot_type, plot_kwargs)
    attr = getattr(plot, attr_name)
    attr(*attr_args[0], **attr_args[1])
    tmpfd, tmpname = tempfile.mkstemp(suffix='.png')
    os.close(tmpfd)
    plot.save(name=tmpname)
    image = mpimg.imread(tmpname)
    os.remove(tmpname)
    return image

def generic_image_test(img_fname):
    img_data = mpimg.imread(img_fname)
    return img_data

def axial_pixelization_test(ds):
    r"""
    This test is typically used once per geometry or coordinates type.
    Feed it a dataset, and it checks that the results of basic pixelization
    don't change.
    """
    for i, axis in enumerate(ds.coordinates.axis_order):
        (bounds, center, display_center) = \
                pw.get_window_parameters(axis, ds.domain_center, None, ds)
        slc = ds.slice(axis, center[i])
        xax = ds.coordinates.axis_name[ds.coordinates.x_axis[axis]]
        yax = ds.coordinates.axis_name[ds.coordinates.y_axis[axis]]
        pix_x = ds.coordinates.pixelize(axis, slc, xax, bounds, (512, 512))
        pix_y = ds.coordinates.pixelize(axis, slc, yax, bounds, (512, 512))
        # Wipe out all NaNs
        pix_x[np.isnan(pix_x)] = 0.0
        pix_y[np.isnan(pix_y)] = 0.0
        pix_x
        pix_y
    return pix_x, pix_y 

def light_cone_projection_test(parameter_file, simulation_type):
    lc = LightCone(
        parameter_file, simulation_type, 0., 0.1,
        observer_redshift=0.0, time_data=False)
    lc.calculate_light_cone_solution(
        seed=123456789, filename="LC/solution.txt")
    lc.project_light_cone(
        (600.0, "arcmin"), (60.0, "arcsec"), "density",
        weight_field=None, save_stack=True)
    fh = h5py.File("LC/LightCone.h5")
    data = fh["density_None"].value
    units = fh["density_None"].attrs["units"]
    assert units == "g/cm**2"
    fh.close()
    mean = data.mean()
    mi = data[data.nonzero()].min()
    ma = data.max()
    return np.array([mean, mi, ma])

def extract_connected_sets_test(ds_fn, data_source, field, num_levels, min_val, max_val):
    n, all_sets = data_source.extract_connected_sets(
        field, num_levels, min_val, max_val)
    result = []
    for level in all_sets:
        for set_id in all_sets[level]:
            result.append([all_sets[level][set_id]["cell_mass"].size,
                           all_sets[level][set_id]["cell_mass"].sum()])
    result = np.array(result)
    return result

def VR_image_comparison_test(scene):
    tmpfd, tmpname = tempfile.mkstemp(suffix='.png')
    os.close(tmpfd)
    scene.render()
    scene.save(tmpname, sigma_clip=1.0)
    image = mpimg.imread(tmpname)
    os.remove(tmpname)
    return image
