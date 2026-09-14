from util.filehandler import merge_parquests
from util.plotter     import ts_plotter
import pandas as pd

## merge_parquests(directory="market")

df = pd.read_csv('merged.csv')
print(df.head)

ts_plotter(df, 'Interval Start', ['LMP'])