import numpy as np
from torchdata.datapipes import functional_datapipe
from torchdata.datapipes.iter import IterDataPipe


@functional_datapipe("location_picker")
class LocationPickerIterDataPipe(IterDataPipe):
    def __init__(self, source_dp: IterDataPipe, return_all_locations: bool = False):
        super().__init__()
        self.source_dp = source_dp
        self.return_all_locations = return_all_locations

    def __iter__(self):
        for xr_dataset in self.source_dp:
            if self.return_all_locations:
                # Iterate through all locations in dataset
                for location_idx in range(len(xr_dataset["x_osgb"])):
                    location = (
                        xr_dataset["x_osgb"][location_idx],
                        xr_dataset["y_osgb"][location_idx],
                    )
                    yield location
            else:
                # Assumes all datasets have osgb coordinates for selecting locations
                # Pick 1 random location from the input dataset
                location_idx = np.random.randint(0, len(xr_dataset["x_osgb"]))
                location = (xr_dataset["x_osgb"][location_idx], xr_dataset["y_osgb"][location_idx])
                yield location
