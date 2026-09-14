import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

def ts_plotter(df, date_column:str, value_column:list[str], title='Time Series Visaulization'):
    df[date_column] = pd.to_datetime(df[date_column])
    df.set_index(date_column, inplace=True)
    print('yes')
    for series in value_column:
        df[series].plot(figsize=(10, 5), linewidth=2)

    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Values', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.show()
    return