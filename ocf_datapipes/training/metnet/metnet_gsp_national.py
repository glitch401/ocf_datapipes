"""Create the training/validation datapipe for training the national MetNet/-2 Model"""

import datetime
import logging
from pathlib import Path
from typing import Union

import xarray
from torch.utils.data.datapipes.datapipe import IterDataPipe

from ocf_datapipes.convert import ConvertGSPToNumpy
from ocf_datapipes.select import FilterGSPIDs, PickLocations
from ocf_datapipes.training.common import (
    add_selected_time_slices_from_datapipes,
    get_and_return_overlapping_time_periods_and_t0,
    open_and_return_datapipes,
)
from ocf_datapipes.training.metnet.metnet_preprocessor import (
    PreProcessMetNetIterDataPipe as PreProcessMetNet,
)
from ocf_datapipes.utils.consts import RSS_MEAN, RSS_STD, UKV_MEAN, UKV_STD

xarray.set_options(keep_attrs=True)
logger = logging.getLogger("metnet_datapipe")
logger.setLevel(logging.DEBUG)


def normalize_gsp(x):  # So it can be pickled
    """
    Normalize the GSP data

    Args:
        x: Input DataArray

    Returns:
        Normalized DataArray
    """
    return x / x.nominal_capacity_mwp


def normalize_pv(x):  # So it can be pickled
    """
    Normalize the GSP data

    Args:
        x: Input DataArray

    Returns:
        Normalized DataArray
    """
    return x / x.observed_capacity_wp


def _select_non_nan_times(x):
    return x.fillna(0.0)


def metnet_national_datapipe(
    configuration_filename: Union[Path, str],
    use_sun: bool = True,
    use_nwp: bool = True,
    use_sat: bool = True,
    use_hrv: bool = True,
    use_pv: bool = False,
    use_gsp: bool = True,
    use_topo: bool = True,
    output_size: int = 256,
    gsp_in_image: bool = False,
    start_time: datetime.datetime = datetime.datetime(2014, 1, 1),
    end_time: datetime.datetime = datetime.datetime(2023, 1, 1),
) -> IterDataPipe:
    """
    Make GSP national data pipe

    Currently only has GSP and NWP's in them

    Args:
        configuration_filename: the configruation filename for the pipe
        use_sun: Whether to add sun features or not
        use_pv: Whether to use PV input or not
        use_hrv: Whether to use HRV Satellite or not
        use_sat: Whether to use non-HRV Satellite or not
        use_nwp: Whether to use NWP or not
        use_topo: Whether to use topographic map or not
        use_gsp: Whether to use GSP history
        start_time: Start time to select on
        end_time: End time to select from
        output_size: Size, in pixels, of the output image
        gsp_in_image: Add GSP history as channels in MetNet image

    Returns: datapipe
    """

    # load datasets
    used_datapipes = open_and_return_datapipes(
        configuration_filename=configuration_filename,
        use_nwp=use_nwp,
        use_topo=use_topo,
        use_sat=use_sat,
        use_hrv=use_hrv,
        use_gsp=use_gsp,
        use_pv=use_pv,
    )
    # Load GSP national data
    used_datapipes["gsp"] = used_datapipes["gsp"].filter_times(start_time, end_time)

    # Now get overlapping time periods
    used_datapipes = get_and_return_overlapping_time_periods_and_t0(used_datapipes)

    # And now get time slices
    used_datapipes = add_selected_time_slices_from_datapipes(used_datapipes)

    # Now do the extra processing
    gsp_history = used_datapipes["gsp"].normalize(normalize_fn=normalize_gsp)
    gsp_datapipe = used_datapipes["gsp_future"].normalize(normalize_fn=normalize_gsp)
    # Split into GSP for target, only national, and one for history
    gsp_datapipe = FilterGSPIDs(gsp_datapipe, gsps_to_keep=[0])

    if "nwp" in used_datapipes.keys():
        # take nwp time slices
        logger.debug("Take NWP time slices")
        nwp_datapipe = used_datapipes["nwp"].normalize(mean=UKV_MEAN, std=UKV_STD)

    if "sat" in used_datapipes.keys():
        logger.debug("Take Satellite time slices")
        # take sat time slices
        sat_datapipe = used_datapipes["sat"].normalize(mean=RSS_MEAN, std=RSS_STD)

    if "hrv" in used_datapipes.keys():
        logger.debug("Take HRV Satellite time slices")
        sat_hrv_datapipe = used_datapipes["hrv"].normalize(
            mean=RSS_MEAN.sel(channel="HRV"), std=RSS_STD.sel(channel="HRV")
        )

    if "topo" in used_datapipes.keys():
        topo_datapipe = used_datapipes["topo"].map(_select_non_nan_times)

    # Now combine in the MetNet format
    modalities = []
    if gsp_in_image and "hrv" in used_datapipes.keys():
        sat_hrv_datapipe, sat_gsp_datapipe = sat_hrv_datapipe.fork(2)
        gsp_history = gsp_history.filter_gsp_ids(gsps_to_keep=[0]).create_gsp_image(
            image_datapipe=sat_gsp_datapipe
        )
    elif gsp_in_image and "sat" in used_datapipes.keys():
        sat_datapipe, sat_gsp_datapipe = sat_datapipe.fork(2)
        gsp_history = gsp_history.filter_gsp_ids(gsps_to_keep=[0]).create_gsp_image(
            image_datapipe=sat_gsp_datapipe
        )
    elif gsp_in_image and "nwp" in used_datapipes.keys():
        nwp_datapipe, nwp_gsp_datapipe = nwp_datapipe.fork(2)
        gsp_history = gsp_history.filter_gsp_ids(gsps_to_keep=[0]).create_gsp_image(
            image_datapipe=nwp_gsp_datapipe, image_dim="osgb"
        )
    if "nwp" in used_datapipes.keys():
        modalities.append(nwp_datapipe)
    if "hrv" in used_datapipes.keys():
        modalities.append(sat_hrv_datapipe)
    if "sat" in used_datapipes.keys():
        modalities.append(sat_datapipe)
    if "topo" in used_datapipes.keys():
        modalities.append(topo_datapipe)
    if gsp_in_image:
        modalities.append(gsp_history)

    gsp_datapipe, gsp_loc_datapipe = gsp_datapipe.fork(2, buffer_size=5)

    location_datapipe = PickLocations(gsp_loc_datapipe)

    metnet_datapipe = PreProcessMetNet(
        modalities,
        location_datapipe=location_datapipe,
        center_width=500_000,
        center_height=1_000_000,
        context_height=10_000_000,
        context_width=10_000_000,
        output_width_pixels=output_size,
        output_height_pixels=output_size,
        add_sun_features=use_sun,
    )
    gsp_datapipe = ConvertGSPToNumpy(gsp_datapipe)

    if not gsp_in_image:
        gsp_history = gsp_history.map(_select_non_nan_times)
        gsp_history = ConvertGSPToNumpy(gsp_history, return_id=True)
        return metnet_datapipe.zip_ocf(gsp_history, gsp_datapipe)  # Makes (Inputs, Label) tuples
    else:
        return metnet_datapipe.zip(gsp_datapipe)
