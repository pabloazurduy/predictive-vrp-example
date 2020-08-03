from datetime import datetime

import h3
import pandas as pd
from fbprophet import Prophet
from fbprophet.diagnostics import performance_metrics
from fbprophet.diagnostics import cross_validation
import logging


class PredictiveModel():
    def __init__(self):
        self.fited_on = datetime.now() 
        self.model_dict = {}
        self.is_fitted = False

    def fit_model(self, simulation_file:str, k_ring_factor:float = 0.4, k_k_ring:float=1):        
        sim_data = pd.read_csv(f'simulations/{simulation_file}', parse_dates=['timestamp'])

        # regular_sampling for time series analysis 
        sim_data_reg = pd.DataFrame(sim_data.groupby(['hex']).resample('5T', on='timestamp')['lat'].count())
        sim_data_reg.reset_index(inplace=True)
        sim_data_reg.rename(columns = {'lat':'dem'}, inplace=True)
        
        #k-ring "convolution"
        for hex_id in sim_data_reg.hex.unique():
            # data from hexagon 
            hex_data =  sim_data_reg[sim_data_reg.hex == hex_id].copy()
            
            # data from kring 
            kring_hex_list = [hex for hex in h3.k_ring(hex_id , k=k_k_ring) if hex!= hex_id]
            kring_data = sim_data_reg[sim_data_reg.hex.isin(kring_hex_list)]
            kring_data_agg = kring_data.groupby('timestamp', as_index =False ).dem.sum()
            kring_data_agg.rename(columns = {'dem':'kring_dem'}, inplace=True)
            
            # merge both 
            hex_data_kring = pd.merge(left = hex_data, right = kring_data_agg , how='outer', on = 'timestamp')
            hex_data_kring.fillna({'hex':hex_id, 'dem':0, 'kring_dem':0}, inplace=True)
            
            # build ponderate demand
            hex_data_kring['y'] = hex_data_kring['dem'] * (1-k_ring_factor) + (hex_data_kring['kring_dem'] * k_ring_factor)
            # fit hex model 
            hex_model = self.fit_hex_model(hex_data_kring)
            
            self.model_dict[hex_id] = hex_model

        self.is_fitted = True 


    @staticmethod
    def fit_hex_model(hex_data:pd.DataFrame) -> Prophet:     
        fit_data = hex_data[['timestamp','y']].copy()
        fit_data.rename(columns={'timestamp':'ds'}, inplace=True)
        fit_data['cap']=1
        fit_data['floor'] = 0
        model = Prophet(n_changepoints = 0, growth='logistic')
        forecaster = model.fit(fit_data, algorithm='Newton')
        df_cv = cross_validation(model, initial='40 days', period='7 days', horizon = '7 days')
        df_metrics = performance_metrics(df_cv)
        print(df_metrics.mdape.mean())

    def probability_15m(self, hex_id:str, time:datetime) -> float:
        raise NotImplementedError




if __name__ == "__main__":
    logging.getLogger('fbprophet').setLevel(logging.WARNING)
    fm = PredictiveModel()
    fm.fit_model(simulation_file='sim_santiago_01.csv')
