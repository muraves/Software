import pandas as pd
from muraves_lib import run_manager

df = run_manager.create_database(raw_gz_path='/data/RAW_GZ', output_filename='data_scan_blu', suffix='', color_list=['BLU'])

print(df.head())
#print(list(df["timestamp"]))