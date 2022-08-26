import torchdata.datapipes as dp
from torchdata.datapipes.iter import IterDataPipe

from ocf_datapipes.utils.consts import BatchKey
from ocf_datapipes.transform.numpy import (
    AddSunPosition,
    AddTopographicData,
    AlignGSPto5Min,
    EncodeSpaceTime,
    SaveT0Time,
ExtendTimestepsToFuture,
)
from ocf_datapipes.batch import MergeNumpyExamplesToBatch, MergeNumpyModalities
from ocf_datapipes.convert import (
    ConvertGSPToNumpyBatch,
    ConvertNWPToNumpyBatch,
    ConvertPVToNumpyBatch,
    ConvertSatelliteToNumpyBatch,
)
from ocf_datapipes.select import (
    LocationPicker,
    SelectSpatialSliceMeters,
    SelectSpatialSlicePixels,
    SelectTimeSlice,
    SelectLiveT0Time,
SelectLiveTimeSlice
)
from ocf_datapipes.transform.xarray import (
    ConvertToNWPTargetTime,
    AddT0IdxAndSamplePeriodDuration,
    ConvertSatelliteToInt8,
    EnsureNPVSystemsPerExample,
    ReprojectTopography,
Downsample
)
from datetime import timedelta

class GSPIterator(IterDataPipe):
    def __init__(self, source_dp: IterDataPipe):
        super().__init__()
        self.source_dp = source_dp

    def __iter__(self):
        for xr_dataset in self.source_dp:
            # Iterate through all locations in dataset
            for location_idx in range(len(xr_dataset["x_osgb"])):
                yield xr_dataset.isel(gsp_id=slice(location_idx, location_idx + 1))

def test_power_perceiver_production(sat_hrv_dp, passiv_dp, topo_dp, gsp_dp, nwp_dp):
    ####################################
    #
    # Equivalent to PP's loading and filtering methods
    #
    #####################################

    # TODO Do the PV filtering here
    topo_dp = ReprojectTopography(topo_dp)
    sat_dp = ConvertSatelliteToInt8(sat_hrv_dp)
    sat_dp = AddT0IdxAndSamplePeriodDuration(
        sat_dp, sample_period_duration=timedelta(minutes=5), history_duration=timedelta(minutes=60)
    )
    pv_dp = AddT0IdxAndSamplePeriodDuration(
        passiv_dp, sample_period_duration=timedelta(minutes=5), history_duration=timedelta(minutes=60)
    )
    gsp_dp = AddT0IdxAndSamplePeriodDuration(
        gsp_dp, sample_period_duration=timedelta(minutes=30), history_duration=timedelta(hours=2)
    )
    nwp_dp = AddT0IdxAndSamplePeriodDuration(
        nwp_dp, sample_period_duration=timedelta(hours=1), history_duration=timedelta(hours=2)
    )

    ####################################
    #
    # Equivalent to PP's xr_batch_processors and normal loading/selecting
    #
    #####################################

    location_dp1, location_dp2, location_dp3 = LocationPicker(gsp_dp, return_all_locations=True).fork(
        3)  # Its in order then
    pv_dp = SelectSpatialSliceMeters(
        pv_dp, location_datapipe=location_dp1, roi_width_meters=960_000, roi_height_meters=960_000
    )  # Has to be large as test PV systems aren't in first 20 GSPs it seems
    pv_dp, pv_t0_dp = EnsureNPVSystemsPerExample(pv_dp, n_pv_systems_per_example=8).fork(2)
    sat_dp, sat_t0_dp = SelectSpatialSlicePixels(
        sat_dp,
        location_datapipe=location_dp2,
        roi_width_pixels=256,
        roi_height_pixels=128,
        y_dim_name="y_geostationary",
        x_dim_name="x_geostationary",
    ).fork(2)
    nwp_dp, nwp_t0_dp = SelectSpatialSlicePixels(
        nwp_dp,
        location_datapipe=location_dp3,
        roi_width_pixels=64,
        roi_height_pixels=64,
        y_dim_name="y_osgb",
        x_dim_name="x_osgb"
    ).fork(2)
    nwp_dp = Downsample(nwp_dp, y_coarsen=16, x_coarsen=16)
    nwp_t0_dp = SelectLiveT0Time(nwp_t0_dp, dim_name="init_time_utc")
    nwp_dp = ConvertToNWPTargetTime(nwp_dp, t0_datapipe=nwp_t0_dp, sample_period_duration=timedelta(hours=1),
                                    history_duration=timedelta(hours=2),
                                    forecast_duration=timedelta(hours=3))
    gsp_t0_dp = SelectLiveT0Time(gsp_dp)
    gsp_dp = SelectLiveTimeSlice(gsp_dp, t0_datapipe=gsp_t0_dp,
                                 history_duration=timedelta(hours=2), )
    sat_t0_dp = SelectLiveT0Time(sat_t0_dp)
    sat_dp = SelectLiveTimeSlice(sat_dp, t0_datapipe=sat_t0_dp, history_duration=timedelta(hours=1), )
    passiv_t0_dp = SelectLiveT0Time(pv_t0_dp)
    pv_dp = SelectLiveTimeSlice(pv_dp, t0_datapipe=passiv_t0_dp,
                                history_duration=timedelta(hours=1), )
    gsp_dp = GSPIterator(gsp_dp)

    # TODO Normalize the data

    ####################################
    #
    # Equivalent to PP's np_batch_processors
    #
    #####################################

    sat_dp = ConvertSatelliteToNumpyBatch(sat_dp, is_hrv=True)
    sat_dp = MergeNumpyExamplesToBatch(sat_dp, n_examples_per_batch=4)
    sat_dp = ExtendTimestepsToFuture(
        sat_dp,
        forecast_duration=timedelta(hours=2),
        sample_period_duration=timedelta(minutes=5),
    )
    pv_dp = ConvertPVToNumpyBatch(pv_dp)
    pv_dp = MergeNumpyExamplesToBatch(pv_dp, n_examples_per_batch=4)
    pv_dp = ExtendTimestepsToFuture(
        pv_dp,
        forecast_duration=timedelta(hours=2),
        sample_period_duration=timedelta(minutes=5),
    )
    gsp_dp = ConvertGSPToNumpyBatch(gsp_dp)
    gsp_dp = MergeNumpyExamplesToBatch(gsp_dp, n_examples_per_batch=4)
    gsp_dp = ExtendTimestepsToFuture(
        gsp_dp,
        forecast_duration=timedelta(hours=8),
        sample_period_duration=timedelta(minutes=30),
    )
    # Don't need to do NWP as it does go into the future
    nwp_dp = ConvertNWPToNumpyBatch(nwp_dp)
    nwp_dp = MergeNumpyExamplesToBatch(nwp_dp, n_examples_per_batch=4)
    combined_dp = MergeNumpyModalities([gsp_dp, pv_dp, sat_dp, nwp_dp])

    combined_dp = AlignGSPto5Min(
        combined_dp, batch_key_for_5_min_datetimes=BatchKey.hrvsatellite_time_utc
    )
    combined_dp = EncodeSpaceTime(combined_dp)
    combined_dp = SaveT0Time(combined_dp)
    combined_dp = AddSunPosition(combined_dp, modality_name="hrvsatellite")
    combined_dp = AddSunPosition(combined_dp, modality_name="pv")
    combined_dp = AddSunPosition(combined_dp, modality_name="gsp")
    combined_dp = AddSunPosition(combined_dp, modality_name="gsp_5_min")
    combined_dp = AddSunPosition(combined_dp, modality_name="nwp_target_time")
    combined_dp = AddTopographicData(combined_dp, topo_dp)

    batch = next(iter(combined_dp))

    assert len(batch[BatchKey.hrvsatellite_time_utc]) == 37

