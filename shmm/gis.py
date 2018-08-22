import pandas as pd

def make_vertices(conduits, index_col='index'):

    lines = pd.DataFrame(columns=['X_Coord', 'Y_Coord', 'z'])
    df = conduits.reset_index().set_index(index_col)
    for name, g in df.groupby(df.index):
        line = g.geometry[0]

        lines = lines.append(
            pd.DataFrame(list(line.coords), columns=['X_Coord', 'Y_Coord', 'z'])
                .assign(Link=name)

        )

    return lines.drop('z', axis=1).set_index('Link')

def make_polygon(catchments, index_col='index'):

    polygons = pd.DataFrame(columns=['X_Coord', 'Y_Coord', 'z'])
    df = catchments.reset_index().set_index(index_col)
    for name, g in df.groupby(df.index):
        subcatchment = g.geometry[0]

        polygons = polygons.append(
            pd.DataFrame(list(subcatchment.exterior.coords), columns=['X_Coord', 'Y_Coord', 'z'])
                .assign(Subcatchment=name)

        )

    return polygons.drop('z', axis=1).set_index('Subcatchment')


def make_coordinates(df, index_col='index'):
    return (
        df.reset_index()
            .set_index(index_col)
            .assign(X_Coord=lambda df: df.geometry.apply(lambda x: x.coords[0][0]),
                    Y_Coord=lambda df: df.geometry.apply(lambda x: x.coords[0][1]))
            .loc[:, ['X_Coord', 'Y_Coord']]
    )
