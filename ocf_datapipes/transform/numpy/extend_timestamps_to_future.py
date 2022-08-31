import numpy as np
import pandas as pd
from torchdata.datapipes import functional_datapipe
from torchdata.datapipes.iter import IterDataPipe

from ocf_datapipes.utils.consts import BatchKey, NumpyBatch
from ocf_datapipes.utils.utils import datetime64_to_float


@functional_datapipe("extend_timesteps_to_future")
class ExtendTimestepsToFutureIterDataPipe(IterDataPipe):
    def __init__(self, source_dp: IterDataPipe, forecast_duration, sample_period_duration):
        """This assumes that the current time_utc array only covers history + now, so just extends it further into the future"""
        self.source_dp = source_dp
        self.forecast_duration = forecast_duration
        self.sample_period_duration = sample_period_duration
        self.num_future_timesteps = int(self.forecast_duration / self.sample_period_duration)

    def __iter__(self) -> NumpyBatch:
        for np_batch in self.source_dp:
            all_time_dims: dict[BatchKey, np.ndarray] = {
                key: value for key, value in np_batch.items() if key.name.endswith("time_utc")
            }  # NWP should already cover the future, ones with no future are GSP, PV, and HRV
            # Take the current past ones and just append more to the future
            for time_dim_key in all_time_dims.keys():
                # Get last time stamp = now
                times = list(all_time_dims[time_dim_key])
                timestep_diff = abs(times[-1] - times[-2])
                # Assumes they are all the same distance apart, just then add to itself n many times
                for future_step in range(self.num_future_timesteps):
                    times.append(times[-1] + timestep_diff)
                # Now re-numpify it and update the original
                times = np.asarray(times, dtype=np.float64)
                all_time_dims[time_dim_key] = times
            np_batch.update(all_time_dims)
            yield np_batch