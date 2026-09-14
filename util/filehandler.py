import pandas as pd
from pathlib import Path
import sys

def merge_parquests(directory:str, output:str='merged.csv'):
    folder = Path(directory)
    files = sorted(folder.glob("*.parquet"))

    if not files:
        sys.exit(1)

    dfs = []
    for f in files:
        df = pd.read_parquet(f)
        dfs.append(df)

    merged = pd.concat(dfs,ignore_index=True)
    merged.to_csv(output, index = False)