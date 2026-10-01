import pandas as pd
from pathlib import Path
import sys
import json

class FileHandler:

    def __init__(self):
        return

    def merge_parquests(self, directory:str, output:str='merged.csv'):
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

    def reader_json(self, filepath):
        with open(filepath, "r") as file:
            data_list = json.load(file)
        return data_list