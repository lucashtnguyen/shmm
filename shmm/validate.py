from matplotlib import pyplot


def axes_object(ax):
    """ Checks if a value if an Axes. If None, a new one is created.
    Both the figure and axes are returned (in that order).

    """

    if ax is None:
        ax = pyplot.gca()
        fig = ax.figure
    elif isinstance(ax, pyplot.Axes):
        fig = ax.figure
    else:
        msg = "`ax` must be a matplotlib Axes instance or None"
        raise ValueError(msg)

    return fig, ax
