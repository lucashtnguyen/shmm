# shmm
shmm: Originally conceived as a way to read shapefiles and then write SWMM .inp, this frame work as been expanded to read, modify, and write SWMM input files. 

# Writing SWMM Based Files

Use the following classes to load SWMM's input and report file: 
```python
import shmm

# load a template file to start from a fresh SWMM file, adding data from other sources:
new_inp = shmm.load_tempalate()

# or load an existing model to modify:
new_inp = shmm.INP('example.inp')
```

Once a model file is loaded, each card in SWMM's input file is represented as a pandas dataframe. 
Rows may be appended or modified to add or edit features in the model. 
```python
new_inp.conduits = new_inp.conduits.append(example_conduits)
new_inp.conduits.head()
```
```
Name	Inlet_Node	Outlet_Node	Length	Manning_N	Inlet_Offset	Outlet_Offset	Init_Flow	Max_Flow
135524	18H3-004C	18H3-014C	445.0	0.013	448.3	447.7	0	0.0
135524a	18H3-014C	18H3-605C	675.0	0.013	447.7	446.6	0	0.0
135525	18H1-366C	18H4-105C	280.0	0.013	449.32	448.88	0	0.0
135525a	18H4-105C	18H3-004C	455.0	0.013	448.88	448.3	0	0.0
135527a	18H1-143C	18H1-366C	510.0	0.013	450.01	449.32	0	0.0
```

While not needed to run a model, spatial information is nice to have in the SWMM GUI.
```python
new_inp.coordinates = simple_inp.coordinates.append(coordinates)
```

Once all the needed cards in the .inp are represented, the model is easily written to disk:
```python
simple_inp.write_SWMMInp('output/modified_example.inp')
```
---------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage

