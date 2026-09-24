import os
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

def ts_plotter(df, date_column:str, value_column:list[str], title='Time Series Visualization', out_dir='plots'):
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column])
    df.set_index(date_column, inplace=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    for series in value_column:
        df[series].plot(ax=ax, linewidth=2, label=series)

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Values', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend()
    fig.tight_layout()

    # always save to disk so there's output even when no GUI window can open
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, '_'.join(value_column) + '.png')
    fig.savefig(path, dpi=150)
    print(f'saved plot -> {path} (backend: {matplotlib.get_backend()})')

    plt.show()
    return
