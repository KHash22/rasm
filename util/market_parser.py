import pandas as pd

class MarketParser:
    def __init__(self):
        return

    def da_hour_mean(self, db:pd.DataFrame, col_date:str, col_da:str, dt_format='%d/%m/%Y %H:%M'):
        df = pd.DataFrame(db[[col_date, col_da]])
        df[col_date] = pd.to_datetime(df[col_date], format=dt_format)
        result = df.groupby(df[col_date].dt.floor("h")).mean(numeric_only=True).reset_index()
        return result