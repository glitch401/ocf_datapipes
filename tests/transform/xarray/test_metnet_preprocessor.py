from ocf_datapipes.transform.xarray import PreProcessMetNet
from ocf_datapipes.select import DropGSP, LocationPicker

def test_metnet_preprocess_satellite(sat_datapipe, nwp_datapipe, gsp_datapipe):
    gsp_datapipe = DropGSP(gsp_datapipe, gsps_to_keep=[0])
    gsp_datapipe = LocationPicker(gsp_datapipe)
    datapipe = PreProcessMetNet([sat_datapipe, nwp_datapipe],
                                location_datapipe=gsp_datapipe,
                                center_width=10000,
                                center_height=10000,
                                context_height=100_000,
                                context_width=100_000,
                                output_width_pixels=100,
                                output_height_pixels=100)
    data = next(iter(datapipe))
    print(data)
    print(data.shape)
