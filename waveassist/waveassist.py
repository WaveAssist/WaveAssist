import requests
import pandas as pd
from waveassist.utils import call_api

class WAHelper:
    def __init__(self, uid):
        self.uid = uid

    def get_dataframe(self, project_key, data_key, environment_key=None):
        data = {}
        if environment_key is None:
            environment_key = project_key + '_default'
        data["uid"] = self.uid  # Always include UID in the request.
        data['output_data_type'] = 'json'
        data['project_key'] = project_key
        data['data_key'] = data_key
        data['data_run_key'] = environment_key

        path = 'data/fetch_data_for_key/'
        response_dict = call_api(path, data)
        try:
            data_dict = response_dict[data_key]
            df = pd.DataFrame(data_dict)
            return df
        except Exception as e:
            raise ValueError(f"Error fetching dataframe: {e}")

    def set_dataframe(self, df, project_key, data_key, environment_key=None) -> bool:

        ##Check if df is a dataframe
        if not isinstance(df, pd.DataFrame):
            raise ValueError("The argument must be a DataFrame.")

        data = {}
        if environment_key is None:
            environment_key = project_key + '_default'

        df_data = df.to_json(orient='records')
        data["uid"] = self.uid
        data['data_type'] = 'json'
        data['json_data'] = df_data
        data['project_key'] = project_key
        data['data_key'] = data_key
        data['data_run_key'] = environment_key

        path = 'data/set_data_for_key/'
        response = call_api(path, data)
        return True



