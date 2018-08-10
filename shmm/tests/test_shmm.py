import pandas

import pytest
import pandas.util.testing as pdtest


from shmm import shmm


@pytest.fixture
def data():
    return pandas.DataFrame({
        'A': [1, 5, 9],
        'B': [2, 6, 0],
        'C': [3, 7, 1],
        'D': [4, 8, 2],
    }, index=list('abc'))


def test_load_example_data(data):
    result = shmm.load_example_data()
    expected = data.copy()
    pdtest.assert_frame_equal(result, expected)


def test_transpose_square(data):
    result = shmm.transpose_square(data)
    expected = pandas.DataFrame({
        'a': {'A':  1, 'B':  4, 'C':  9, 'D': 16},
        'b': {'A': 25, 'B': 36, 'C': 49, 'D': 64},
        'c': {'A': 81, 'B':  0, 'C':  1, 'D':  4}
    })
    pdtest.assert_frame_equal(result, expected)


@pytest.mark.parametrize(('value', 'decimal', 'expected'), [
    (0.03010, 2,  '3.01%'), (0.020000, 3,   '2.000%'),
    (0.10000, 2, '10.00%'), (5.000120, 3, '500.012%'),
    ('junk', 2, None),
])
def test_format_as_pct(value, decimal, expected):
    if expected is None:
        with pytest.raises(ValueError):
            shmm.format_as_pct(value)
    else:
        result = shmm.format_as_pct(value, decimal=decimal)
        assert result == expected


@pytest.fixture
def response():
    """Sample pytest fixture.
    See more at: http://doc.pytest.org/en/latest/fixture.html
    """
    # import requests
    # return requests.get('https://github.com/audreyr/cookiecutter-pypackage')


def test_content(response):
    """Sample pytest test function with the pytest fixture as an argument.
    """
    # from bs4 import BeautifulSoup
    # assert 'GitHub' in BeautifulSoup(response.content).title.string

