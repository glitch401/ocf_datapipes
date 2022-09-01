import xarray as xr
import numpy as np
from typing import Optional, Union, Callable
from torchdata.datapipes import functional_datapipe
from torchdata.datapipes.iter import IterDataPipe


@functional_datapipe("normalize")
class NormalizeIterDataPipe(IterDataPipe):
    """Normalize the data in various methods"""
    def __init__(
        self,
        source_dp: IterDataPipe,
        mean: Optional[Union[xr.Dataset, xr.DataArray, np.ndarray]]=None,
        std: Optional[Union[xr.Dataset, xr.DataArray, np.ndarray]]=None,
        max_value: Optional[Union[int, float]]=None,
        calculate_mean_std_from_example: bool = False,
        normalize_fn: Optional[Callable] = None,
    ):
        """
        Normalize the data with either given mean/std, calculated from the example itself, or a function

        This is essentially a nice wrapper instead of using the Map DataPipe

        Args:
            source_dp: Datapipe emitting the datasets
            mean: Means
            std: Standard Deviations
            max_value: Max value for dividing the entire example by
            calculate_mean_std_from_example: Whether to calculate the mean/std from the input data or not
            normalize_fn: Callable function to apply to the data to normalize it
        """
        self.source_dp = source_dp
        self.mean = mean
        self.std = std
        self.max_value = max_value
        self.calculate_mean_std_from_example = calculate_mean_std_from_example
        self.normalize_fn = normalize_fn

    def __iter__(self) -> Union[xr.Dataset, xr.DataArray]:
        """Normalize the data depending on the init arguments"""
        for xr_data in self.source_dp:
            if self.mean is not None and self.std is not None:
                xr_data = xr_data - self.mean
                xr_data = xr_data / self.std
            elif self.max_value is not None:
                xr_data = xr_data / self.max_value
            elif self.calculate_mean_std_from_example:
                # For Topo data for example
                xr_data -= xr_data.mean().item()
                xr_data /= xr_data.std().item()
            else:
                xr_data = self.normalize_fn(xr_data)
            yield xr_data
