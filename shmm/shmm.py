from pkg_resources import resource_filename

import pandas


def load_example_data():
    """
    Loads example data for shmm.

    Parameters
    ----------
    None

    Returns
    -------
    example : pandas.DataFrame
        The example data for shmm

    Example
    -------
    >>> shmm
    >>> data = shmm.load_example_data()
    >>> print(data)
       A  B  C  D
    a  1  2  3  4
    b  5  6  7  8
    c  9  0  1  2

    """

    folder = 'shmm.tests.data'
    filename = 'example_data.csv'
    csv = resource_filename(folder, filename)
    return pandas.read_csv(csv, index_col=[0])


def transpose_square(df):
    """
    Transposes and numerically squares a dataframe

    Parameters
    ----------
    df : pandas.DataFrame
        The dataframe whose values will be squared and transposed.

    Returns
    -------
    trans_sqrd : pandas.DataFrame
        A modified copy of the original dataframe

    Examples
    --------
    >>> import shmm
    >>> data = shmm.load_example_data()
    >>> print(data)
       A  B  C  D
    a  1  2  3  4
    b  5  6  7  8
    c  9  0  1  2

    >>> shmm.transpose_square(data)
        a   b   c
    A   1  25  81
    B   4  36   0
    C   9  49   1
    D  16  64   4

    """

    return df.transpose() ** 2


def format_as_pct(value, decimal=2):
    """
    Formats any value as a percentage.

    Parameters
    ----------
    value : int or float
        The value you want to format as a percentage.
    decimal : int, optional
        The number of decimal places the output should have. The default
        value is 2.

    Returns
    -------
    pct : string
        The value formatted as a string and percentage.

    Examples
    --------
    >>> import shmm
    >>> shmm.format_as_pct(0.15678)
    '15.68%'
    >>> shmm.format_as_pct(0.15678, decimal=1)
    '15.7%'

    """

    fmt = '{0:.%df}%%' % decimal
    return fmt.format(float(value) * 100)
