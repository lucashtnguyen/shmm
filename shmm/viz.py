from matplotlib import pyplot

from shmm import validate


def demo_plotting_function(x, y, ax=None):
    fig, ax = validate.axes_object(ax)
    ax.plot(x, y, 'bo', label='Fake Data')
    ax.set_xlabel('Test X Label')
    ax.set_ylabel('Test Y Label')
    ax.legend()
    return fig
