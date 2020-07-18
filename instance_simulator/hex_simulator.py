#from typing import Tuple

import h3 
from shapely.geometry import Point, Polygon 
import numpy as np
import json
from copy import deepcopy
from typing import List


def test_get_random_inner_point():
    hex_key = h3.geo_to_h3(0, 0, 9)
    random_point = get_random_inner_point(hex_key)
    assert random_point.within(Polygon(h3.h3_to_geo_boundary(hex_key)))

def multipolygon_2_poligon_list(geo_json):
    """function that convert a multipoligon dict to a list of poligons
    
    Arguments:
        geo_json {dict} -- from a geojson file the geojson_file['geometry'] subdict 
    
    Raises:
        ValueError: [description]
    
    Returns:
        list -- list of Polygons{type='Polygon','coordinates'=[]}
    """
    if 'type' not in geo_json.keys():
        raise ValueError('geo_json not in correct format')
    if geo_json['type'] != 'MultiPolygon':
        raise ValueError('geo_json is not the correct type')
    
    result = []
    poli_obj = dict()
    for set_cor in geo_json['coordinates']:
        poli_obj['type']='Polygon'
        poli_obj['coordinates']=set_cor
        result.append(deepcopy(poli_obj))
        
    return result
    

def geojson_to_hex(filename:str,
                   res=9,
                   geo_json_conformant=True) -> List[str]:
    """ loads a geojson file and convert it to a hexa cluster. In case of multifeatures will only convert the first one.
    
    Arguments:
        filename {str} -- path to designated geojson file to convert to hex
    
    Keyword Arguments:
        res {int} -- hex resolution (default: {9})
        geo_json_conformant {bool} -- geo_json_conformant from 3core.polyfill function (default: {True})
    
    Returns:
        [str] -- json 
    """
    with open(filename) as json_file:
        data = json.load(json_file)
    
    if 'geometry' in data.keys():    
        geo_json = data['geometry']
    elif 'features' in data.keys():    
        geo_json = data['features'][0]['geometry']
    
    to_hexacluster = []
    if geo_json['type']=='Polygon':
        to_hexacluster = list(h3.polyfill(geo_json, res, geo_json_conformant))
    elif geo_json['type']=='MultiPolygon':
        for poligon in multipolygon_2_poligon_list(geo_json):
            new_hex = list(h3.polyfill(poligon, 9, geo_json_conformant))
            to_hexacluster = list(set(to_hexacluster + new_hex))    
    return json.dumps(to_hexacluster)


def get_random_inner_point(hex_key:str)->Point:
    """ function to get a random point inside a hexagon

    Args:
        hex_key (str): hex key value 

    Returns:
        Point: shapely.geometry.Point with the (x,y) pair on the hexagon 
    """    
    hex_polygon = Polygon(h3.h3_to_geo_boundary(hex_key))
    cordinates = hex_polygon.exterior.coords
    w_random = np.random.rand(1,7)
    w = w_random/w_random.sum()
    random_point = Point((cordinates.xy[0] * w).sum(), (cordinates.xy[1] * w).sum())
    return random_point
    
def get_cat_random_time(cat:str)-> float:
    
    cat_map = { # time in minutes
        'low_demand': 40,
        'min_demand': 25,
        'high_demand':10,
    }
    assert cat in cat_map.keys(), f'category must be on {list(cat_map.keys())}'
    return np.random.exponential(cat_map[cat])

if __name__ == "__main__":
    
    #1. fill geojson 
    geojson_file_path = '/Users/pablo/github/predictive-vrp-example/instance_simulator/geojson/santiago.geojson'
    hex_cluster = geojson_to_hex(filename = geojson_file_path , res = 9)