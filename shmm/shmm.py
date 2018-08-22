from io import StringIO

from .utils import template
from .inp import INP


def load_template(remove_dummies=True):
    return INP(StringIO(template), remove_dummies=remove_dummies)
