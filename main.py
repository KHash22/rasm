from util.filehandler   import merge_parquests
from util.plotter       import ts_plotter
from util.market_parser import MarketParser
import pandas as pd
import os
from dotenv             import load_dotenv

load_dotenv()

## merge_parquests(directory="market")

re = pd.read_csv('data/DEU_CentralAll15Min_Prices.csv')
column_date = os.getenv('COL_Date')
column_da   = os.getenv('COL_DA')
re[column_date] = pd.to_datetime(re[column_date], format='%d/%m/%Y %H:%M')
re = re[(re[column_date] >= '2025-01-01') & (re[column_date] < '2027-01-01')]  # slice out only relevant data
re1 = MarketParser().da_hour_mean(db=re, col_date=column_date, col_da=column_da)
print(re1.head())
re1.to_csv('output.csv', index=False)

ts_plotter(re1, column_date, [column_da])

df = pd.read_csv('data/merged.csv')
print(df.head)

ts_plotter(df, 'Interval Start', ['LMP'])