from gridstatus import IESO
import pandas as pd


def get_DA(start_date:str="2026-03-01", end_date: str="2026-09-01"):
    ieso = IESO()
    months = pd.date_range(start_date, end_date, freq="MS")  # month starts

    for i in range(len(months) - 1):
        start = months[i]
        end = months[i + 1]
        print(f"Fetching {start.date()} to {end.date()}...")

        df = ieso.get_lmp_day_ahead_hourly_ontario_zonal(
            date=start, end=end, verbose=True,
        )
        df.to_parquet(f"market//da_ozp_{start.strftime('%Y%m')}.parquet")

    return