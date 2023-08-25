"""Select PV systems based off their capacity"""
from typing import Union

import numpy as np
import xarray as xr
from torchdata.datapipes import functional_datapipe
from torchdata.datapipes.iter import IterDataPipe


@functional_datapipe("select_pv_systems_on_capacity")
class SelectPVSystemsOnCapacityIterDataPipe(IterDataPipe):
    """Select PV systems based off their capacity"""

    def __init__(
        self,
        source_datapipe: IterDataPipe,
        min_capacity_watts: Union[int, float] = 0.0,
        max_capacity_watts: Union[int, float] = np.inf,
    ):
        """
        Select PV systems based off their capacity

        Args:
            source_datapipe: Datapipe of PV data
            min_capacity_watts: Threshold of PV system power in watts. Systems with capacity lower
                than this are dropped.
            max_capacity_watts: Threshold of PV system power in watts. Systems with capacity higher
                than this are dropped.
        """
        self.source_datapipe = source_datapipe
        self.min_capacity_watts = min_capacity_watts
        self.max_capaciity_watts = max_capacity_watts

    def __iter__(self) -> Union[xr.DataArray, xr.Dataset]:
        for ds in self.source_datapipe:
            too_low = ds.capacity_watt_power < self.min_capacity_watts
            too_high = ds.capacity_watt_power > self.max_capacity_watts
            mask = np.logical_or(too_low, too_high)
            yield ds.where(~mask, drop=True)
