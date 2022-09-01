from datetime import timedelta

from ocf_datapipes.convert import ConvertPVToNumpyBatch
from ocf_datapipes.transform.xarray import AddT0IdxAndSamplePeriodDuration
from ocf_datapipes.utils.consts import BatchKey


def test_convert_passiv_to_numpy_batch(passiv_dp):
    passiv_dp = AddT0IdxAndSamplePeriodDuration(
        passiv_dp,
        sample_period_duration=timedelta(minutes=5),
        history_duration=timedelta(minutes=60),
    )
    passiv_dp = ConvertPVToNumpyBatch(passiv_dp)
    data = next(iter(passiv_dp))
    assert BatchKey.pv in data
    assert BatchKey.pv_t0_idx in data


def test_convert_pvoutput_to_numpy_batch(pvoutput_dp):
    pvoutput_dp = AddT0IdxAndSamplePeriodDuration(
        pvoutput_dp,
        sample_period_duration=timedelta(minutes=5),
        history_duration=timedelta(minutes=60),
    )

    pvoutput_dp = ConvertPVToNumpyBatch(pvoutput_dp)

    data = next(iter(pvoutput_dp))
    assert BatchKey.pv in data
    assert BatchKey.pv_t0_idx in data
