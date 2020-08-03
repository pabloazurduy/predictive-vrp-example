from datetime import datetime, timedelta
import json
import random
from copy import deepcopy
from typing import Dict, List, Tuple

import h3
import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon


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
    return to_hexacluster

def test_get_random_inner_point():
    hex_key = h3.geo_to_h3(0, 0, 9)
    random_point = get_random_inner_point(hex_key)
    assert random_point.within(Polygon(h3.h3_to_geo_boundary(hex_key)))
     

def get_random_inner_point(hex_key:str)->Point:
    """ function to get a random point inside a hexagon

    Args:
        hex_key (str): hex key value 

    Returns:
        Point: shapely.geometry.Point with the (x,y) pair on the hexagon 
    """    
    hex_polygon = Polygon(h3.h3_to_geo_boundary(hex_key))
    minx, miny, maxx, maxy = hex_polygon.bounds
    while True:
        random_point = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
        if hex_polygon.contains(random_point):
            return random_point
    
def get_random_time(lambda_value:float)-> float:
    return np.random.exponential(lambda_value)

def create_smother_demand_mapper(hex_cluster:List[str], 
                                         day_intervals:[str, dict] = 'default',
                                         hex_with_high_demand:[str, dict] = 'default',
                                         cat_lambda_map:[str, dict] = 'default',
                                         ) -> Dict[Tuple[str, int], float] :
    if day_intervals == 'default':
        day_intervals_dict = {'morning': [7,10], 
                              'mid_morning':[11,15],
                              'afternoon':[16,18],
                              'night':[19,22]
                              }
    else:
        day_intervals_dict = deepcopy(day_intervals)
    if hex_with_high_demand == 'default':                
        hex_with_high_demand_dict = {
            'morning': 1,
            'mid_morning':3,
            'afternoon':1,
            'night':3
        }
    else:
        hex_with_high_demand_dict = deepcopy(hex_with_high_demand)
    if cat_lambda_map == 'default':                
        cat_lambda_map_dict = { 'low_demand': 900, # time in minutes
                                'mid_demand': 360,
                                'high_demand': 120,
        }
    else:
        cat_lambda_map_dict = deepcopy(cat_lambda_map)

    demand_map_sim = {}
    for day_window in day_intervals_dict.keys():
        # select n peaks 
        hex_peak_list = random.sample(hex_cluster, hex_with_high_demand_dict[day_window]) 
        # expand n peaks to k ring = 2
        hex_high_demand = set(hex_peak_list)
        for high_peak_hex in hex_peak_list:
            neighborhood = h3.k_ring(high_peak_hex, k=1)
            hex_high_demand.update(neighborhood)
        # expand to mid_demand
        hex_mid_demand = set()
        for high_peak_hex in hex_high_demand:
            neighborhood = h3.k_ring(high_peak_hex, k=2)
            outer_hex = set(neighborhood).difference(hex_high_demand)
            hex_mid_demand.update(outer_hex)
        
        # iterate over hours 
        window_low_bound = day_intervals_dict[day_window][0]
        window_up_bound = day_intervals_dict[day_window][1] +1  

        for hour in range(window_low_bound,window_up_bound ):
            for hex in hex_cluster:
                if hex in hex_high_demand:
                    demand_map_sim[tuple([hex,hour])] = cat_lambda_map_dict['high_demand']
                elif hex in hex_mid_demand:
                    demand_map_sim[tuple([hex,hour])] = cat_lambda_map_dict['mid_demand']
                else:
                    demand_map_sim[tuple([hex,hour])] = cat_lambda_map_dict['low_demand']
    return demand_map_sim

def create_simulation_log(demand_map_sim:Dict[Tuple[str, int], float], 
                              start_date:[str,datetime] = '2020-01-01',
                              days:int = 1) ->pd.DataFrame:
    # create hex list
    hex_list = list(set([ hex for (hex,hour) in demand_map_sim.keys() ]))
    hour_list = list(set([ hour for (hex,hour) in demand_map_sim.keys() ]))
    start_hour = min(hour_list)
    end_hour = max(hour_list)
    
    if isinstance(start_date, str):
        start_timestamp = datetime.strptime(start_date,'%Y-%m-%d')
    elif isinstance(start_date, datetime):
        start_timestamp = start_date
    
    log_rows = []
    for n_day in range(days): # iterate over all days 
        start_timestamp = start_timestamp + timedelta(days=n_day) # add days
        start_timestamp = start_timestamp.replace(hour=start_hour)

        
        last_request = {hex: start_timestamp for hex in hex_list } # hex: timestamp of the last registed request 
        end_time = start_timestamp.replace(hour=end_hour, minute=59, second=59) 
        while True:
            for hex in hex_list:
                lambda_value = demand_map_sim[(hex, min(last_request[hex],end_time).hour )]
                minutes_to_add = get_random_time(lambda_value)
                request_timestamp = last_request[hex] + timedelta(minutes=minutes_to_add) # get time 
                request_point = get_random_inner_point(hex) # get point 
                last_request[hex] = request_timestamp # update last request
                if request_timestamp <= end_time:
                    log_rows.append({'lat':request_point.x,
                                    'long':request_point.y,
                                    'hex': hex,
                                    'timestamp': request_timestamp,
                                    })
            if min(req_time for req_time in  last_request.values()) >= end_time:
                break
    log_df = pd.DataFrame(log_rows)       
    return log_df


if __name__ == "__main__":
    
    #1. fill geojson 
    geojson_file_path = '/Users/pablo/github/predictive-vrp-example/instance_simulator/geojson/santiago.geojson'
    hex_cluster = geojson_to_hex(filename = geojson_file_path , res = 9)
    #2. create mapper simulation week
    demand_map_sim_weekday = create_smother_demand_mapper(hex_cluster)
    #2.1 create mapper simulation weekend 
    hex_with_high_demand = {'morning': 1,
                            'mid_morning':2,
                            'afternoon':1,
                            'night':0
    }
    cat_lambda_map = { 'low_demand': 1000, # time in minutes
                        'mid_demand': 400,
                        'high_demand': 200,
    }
    demand_map_sim_weekend = create_smother_demand_mapper(hex_cluster, 
                                                          hex_with_high_demand=hex_with_high_demand,
                                                          cat_lambda_map = cat_lambda_map)
    # create 12 weeks of data 
    start_date = datetime(year=2020,month=1,day=1)
    daily_log_list = []
    for date_day in (start_date + timedelta(n) for n in range(84)):
        print(f'doing {date_day}')
        if date_day.weekday() <= 4: # weekday  
            log_df = create_simulation_log(demand_map_sim_weekday, start_date=date_day , days = 1)
        else:
            log_df = create_simulation_log(demand_map_sim_weekend, start_date=date_day , days = 1)
        daily_log_list.append(log_df)
    # export simulation to csv
    final_log_df = pd.concat(daily_log_list)
    final_log_df.to_csv('simulations/sim_santiago_01.csv', index=False)