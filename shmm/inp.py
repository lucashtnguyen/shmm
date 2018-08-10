# -*- coding: utf-8 -*-

"""Main module."""

from copy import deepcopy
from textwrap import dedent
from io import StringIO

import numpy
import pandas

from hymo import SWMMInpFile


class INP(SWMMInpFile):
    def __init__(self, path):
        SWMMInpFile.__init__(self, path)

        self._blacklist = ['copy', 'evaporation',
                           'endline', 'map', 'options',
                           'path', 'pollutants', 'raingages',
                           'report', 'symbols', 'temperature', 'title',
                           'pos', 'startswith'
                          ]

        self.startswith = '!' # template params to remove
        self._modified_file = self.orig_file.copy()
        self._pos = None

    @property
    def modified_file(self):
        self._update_inp()
        return self._modified_file

    @property
    def known_attributes(self):

        ka = [_ for _ in dir(self) if '_' not in _ and _.islower() and _ not in self._blacklist]

        attr = []

        for k in  ka:
            try:
                if self[k].shape[0] > 0:
                    attr.append(k)
                else:
                    None
            except(NotImplementedError):
                next

        return attr

    def __getitem__(self, key):
        return self.__getattribute__(key)

    def __setitem__(self, key, value):
        self.__dict__['_' + key] = value

    def copy(self):
        return deepcopy(self)

    def _update_element(self, element, value):
        str_kwrgs = dict(header=False, index=False, col_space=10, justify='left', na_rep='')

        skiprows = self.find_block(element, lookup=self._modified_file)
        skipfooter = self._find_end(skiprows, self.endline, lookup=self._modified_file)

        self[element] = value
        self._modified_file[skiprows:-skipfooter] = [self[element].reset_index().to_string(**str_kwrgs) + '\n'*2]

    def _update_inp(self):
        for ka in self.known_attributes:
            self._update_element(ka, self[ka])

    def clean_template(self):
        for ka in self.known_attributes:

            cleaned_df = self[ka].loc[self[ka].index.map(lambda x: not x.startswith('!'))]

            if cleaned_df.shape[0] == 0:
                cleaned_df.loc[' '] = [' ']*cleaned_df.shape[1]

            self._update_element(ka, cleaned_df)

    def write_SWMMInp(self, path):
        s = (''.join(self.modified_file))

        with open(path, 'w') as openfile:
            openfile.write(s)

    def validate_setter(self, attribute, value):
        if isinstance(value, pandas.DataFrame):
            assert numpy.all(value.columns == self[attribute].columns)
            return value
        else:
            raise(ValueError)

    @property
    def pos(self):
        if self._pos is None:
            try:
                polygons = (self.polygons
                                .groupby(self.polygons.index)
                                .mean()
                )
            except(DataError):
                polygons = None

            pos = (self.coordinates
                       .append(polygons)
                  )
            self._pos = pos
        return self._pos

    @SWMMInpFile.title.setter
    def title(self, val):
        new_val = self.validate_setter('title', val)
        self._title = new_val

    @SWMMInpFile.options.setter
    def options(self, val):
        new_val = self.validate_setter('options', val)
        self._options = new_val

    @SWMMInpFile.evaporation.setter
    def evaporation(self, val):
        new_val = self.validate_setter('evaporation', val)
        self._evaporation = new_val

    @SWMMInpFile.temperature.setter
    def temperature(self, val):
        new_val = self.validate_setter('temperature', val)
        self._temperature = new_val

    @SWMMInpFile.raingages.setter
    def raingages(self, val):
        new_val = self.validate_setter('raingages', val)
        self._raingages = new_val

    @SWMMInpFile.subcatchments.setter
    def subcatchments(self, val):
        new_val = self.validate_setter('subcatchments', val)
        self._subcatchments = new_val

    @SWMMInpFile.subareas.setter
    def subareas(self, val):
        new_val = self.validate_setter('subareas', val)
        self._subareas = new_val

    @SWMMInpFile.infiltration.setter
    def infiltration(self, val):
        new_val = self.validate_setter('infiltration', val)
        self._infiltration = new_val

    @SWMMInpFile.lid_controls.setter
    def lid_controls(self, val):
        new_val = self.validate_setter('lid_controls', val)
        self._lid_controls = new_val

    @SWMMInpFile.lid_usage.setter
    def lid_usage(self, val):
        new_val = self.validate_setter('lid_usage', val)
        self._lid_usage = new_val

    @SWMMInpFile.aquifers.setter
    def aquifers(self, val):
        new_val = self.validate_setter('aquifers', val)
        self._aquifers = new_val

    @SWMMInpFile.groundwater.setter
    def groundwater(self, val):
        new_val = self.validate_setter('groundwater', val)
        self._groundwater = new_val

    @SWMMInpFile.junctions.setter
    def junctions(self, val):
        new_val = self.validate_setter('junctions', val)
        self._junctions = new_val

    @SWMMInpFile.outfalls.setter
    def outfalls(self, val):
        new_val = self.validate_setter('outfalls', val)
        self._outfalls = new_val

    @SWMMInpFile.storage.setter
    def storage(self, val):
        new_val = self.validate_setter('storage', val)
        self._storage = new_val

    @SWMMInpFile.conduits.setter
    def conduits(self, val):
        new_val = self.validate_setter('conduits', val)
        self._conduits = new_val

    @SWMMInpFile.orifices.setter
    def orifices(self, val):
        new_val = self.validate_setter('orifices', val)
        self._orifices = new_val

    @SWMMInpFile.outlets.setter
    def outlets(self, val):
        new_val = self.validate_setter('outlets', val)
        self._outlets = new_val

    @SWMMInpFile.weirs.setter
    def weirs(self, val):
        new_val = self.validate_setter('weirs', val)
        self._weirs = new_val

    @SWMMInpFile.xsections.setter
    def xsections(self, val):
        new_val = self.validate_setter('xsections', val)
        self._xsections = new_val

    @SWMMInpFile.transects.setter
    def transects(self, val):
        new_val = self.validate_setter('transects', val)
        self._transects = new_val

    @SWMMInpFile.losses.setter
    def losses(self, val):
        new_val = self.validate_setter('losses', val)
        self._losses = new_val

    @SWMMInpFile.curves.setter
    def curves(self, val):
        new_val = self.validate_setter('curves', val)
        self._curves = new_val

    @SWMMInpFile.timeseries.setter
    def timeseries(self, val):
        new_val = self.validate_setter('timeseries', val)
        self._timeseries = new_val

    @SWMMInpFile.report.setter
    def report(self, val):
        new_val = self.validate_setter('report', val)
        self._report = new_val

    @SWMMInpFile.tags.setter
    def tags(self, val):
        new_val = self.validate_setter('tags', val)
        self._tags = new_val

    @SWMMInpFile.map.setter
    def map(self, val):
        new_val = self.validate_setter('map', val)
        self._map = new_val

    @SWMMInpFile.coordinates.setter
    def coordinates(self, val):
        new_val = self.validate_setter('coordinates', val)
        self._coordinates = new_val

    @SWMMInpFile.vertices.setter
    def vertices(self, val):
        new_val = self.validate_setter('vertices', val)
        self._vertices = new_val

    @SWMMInpFile.polygons.setter
    def polygons(self, val):
        new_val = self.validate_setter('polygons', val)
        self._polygons = new_val

    @SWMMInpFile.symbols.setter
    def symbols(self, val):
        new_val = self.validate_setter('symbols', val)
        self._symbols = new_val

    @SWMMInpFile.pollutants.setter
    def pollutants(self, val):
        new_val = self.validate_setter('pollutants', val)
        self._pollutants = new_val