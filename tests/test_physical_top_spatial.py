"""Native hydraulic capacity stays distinct from explicit physical-top GIS evidence.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-16
Synthetic model and coordinates only; no private project interpretation.
"""
from hashlib import sha256
import json
import pytest
from shmm import GISAnnotation,GISFlag,GISPhysicalTop,export_shapefiles
from test_spatial import document,records,MODEL


def top(**overrides):
    return GISPhysicalTop(**{'depth':12.345,'category':'placeholder','basis':'Fictional physical-depth placeholder, not surveyed rim','source_key':'synthetic/original/P','evidence':{'original_depth_literal':'12.345','source_sha256':'a'*64},**overrides})


def test_physical_top_retains_placeholder_and_native_capacity_separately(tmp_path):
    model=document(MODEL.replace('S 0 5 0 FUNCTIONAL 1 0 1','S 0 1011.345 0 FUNCTIONAL 0 0 .1 0 0'))
    # First five positional arguments keep their historical meaning.
    a=GISAnnotation('node','S',[GISFlag('numerical_pressure_capacity','assumption')],'partial','legacy/source',top())
    result=export_shapefiles(model,tmp_path/'gis',crs=3857,annotations=[a],annotation_model_sha256=sha256(model.data).hexdigest())
    row=records(tmp_path/'gis/nodes')['S']
    assert row['MAX_DEPTH']==1011.345 and row['PHYS_DPH']==12.345 and row['PHYS_TOP']==12.345
    assert row['PHYS_KIND']=='placeholder' and row['PHYS_ASS']==1 and row['PLACEHOLDR']==1
    assert row[result['flag_fields']['physical_top_placeholder']]==1
    raw=json.loads((tmp_path/'gis/qa_features.json').read_text());e=next(r for r in raw if r['object_id']=='S' and r['family']=='node')
    assert e['model_tokens'][2]=='1011.345' and e['physical_top']['evidence']['original_depth_literal']=='12.345'
    assert e['physical_top']['source_key']=='synthetic/original/P'


def test_no_physical_evidence_is_unknown_even_for_small_native_depth(tmp_path):
    export_shapefiles(document(),tmp_path/'gis',crs=3857)
    row=records(tmp_path/'gis/nodes')['001']
    assert row['MAX_DEPTH']==12.345
    assert row['PHYS_DPH'] is None and row['PHYS_TOP'] is None and row['PHYS_ASS']==-1 and row['PHYS_KIND']=='unknown'


@pytest.mark.parametrize('category,assumed',[('observed',0),('assumption',1),('placeholder',1),('provisional',1)])
def test_physical_top_categories_and_actual_floor_sum(tmp_path,category,assumed):
    model=document();a=GISAnnotation('node','001',physical_top=top(depth=4,category=category))
    export_shapefiles(model,tmp_path/'gis',crs=3857,annotations=[a],annotation_model_sha256=sha256(model.data).hexdigest())
    row=records(tmp_path/'gis/nodes')['001']
    assert row['PHYS_TOP']==14 and row['PHYS_DPH']==4 and row['PHYS_ASS']==assumed and row['PHYS_KIND']==category


@pytest.mark.parametrize('overrides',[{'depth':float('nan')},{'depth':float('inf')},{'depth':-1},{'depth':True},{'depth':'12.345'},{'category':'surveyed'},{'basis':''},{'source_key':''},{'evidence':{}},{'evidence':{'bad':float('nan')}}])
def test_invalid_physical_top_fails_closed(tmp_path,overrides):
    model=document();a=GISAnnotation('node','001',physical_top=top(**overrides))
    with pytest.raises(ValueError):export_shapefiles(model,tmp_path/'bad',crs=3857,annotations=[a],annotation_model_sha256=sha256(model.data).hexdigest())
    assert not (tmp_path/'bad').exists()


def test_physical_top_stale_hash_or_link_annotation_rejected(tmp_path):
    model=document();a=GISAnnotation('node','001',physical_top=top())
    with pytest.raises(ValueError,match='hash'):export_shapefiles(model,tmp_path/'stale',crs=3857,annotations=[a])
    with pytest.raises(ValueError,match='node GISPhysicalTop'):export_shapefiles(model,tmp_path/'link',crs=3857,annotations=[GISAnnotation('link','P',physical_top=top())],annotation_model_sha256=sha256(model.data).hexdigest())
