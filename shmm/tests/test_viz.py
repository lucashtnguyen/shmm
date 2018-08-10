import numpy
from matplotlib import pyplot

import pytest

from shmm import viz
from . import helpers


BASELINE_DIR = 'baseline_images/test_viz'
TOLERANCE = 15


@pytest.fixture
def plot_data():
    data = numpy.array([
         3.113,   3.606,   4.046,   4.046,   4.710,   6.140,   6.978,
         2.000,   4.200,   4.620,   5.570,   5.660,   5.860,   6.650,
         6.780,   6.790,   7.500,   7.500,   7.500,   8.630,   8.710,
         8.990,   9.850,  10.820,  11.250,  11.250,  12.200,  14.920,
        16.770,  17.810,  19.160,  19.190,  19.640,  20.180,  22.970,
    ])
    return data


@pytest.mark.mpl_image_compare(baseline_dir=BASELINE_DIR, tolerance=TOLERANCE)
@helpers.seed
def test_demo_plotting_function(plot_data):
    x = numpy.random.uniform(size=len(plot_data))
    fig = viz.demo_plotting_function(x, plot_data, ax=None)
    assert isinstance(fig, pyplot.Figure)
    return fig
