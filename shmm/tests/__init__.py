from pkg_resources import resource_filename

import pytest

import shmm

def test(*args):
    options = [resource_filename('shmm', 'tests')]
    options.extend(list(args))
    return pytest.main(options)
