#from typing import Tupleimport h3 from shapely.geometry import Point, Polygon import numpy as npdef test_get_random_inner_point():    hex_key = h3.geo_to_h3(0, 0, 9)    random_point = get_random_inner_point(hex_key)    assert random_point.within(Polygon(h3.h3_to_geo_boundary(hex_key)))    def get_random_inner_point(hex_key:str)->Point:    hex_polygon = Polygon(h3.h3_to_geo_boundary(hex_key))    cordinates = hex_polygon.exterior.coords    w_random = np.random.rand(1,7)    w = w_random/w_random.sum()    random_point = Point((cordinates.xy[0] * w).sum(), (cordinates.xy[1] * w).sum())    return random_point    