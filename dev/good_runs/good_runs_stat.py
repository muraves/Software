from glob import glob
from muraves_lib import run_manager
import pandas as pd
from pathlib import Path
import os
import matplotlib.pyplot as plt
import numpy as np

parsed_files_path = '/data/PARSED'
hodoscope = 'BLU'
version = 'v0'
type = 'PIEDISTALLI'

assert type in ["PIEDISTALLI", "ADC", "ALL"], f"Unexpected type: {type}. Expected 'PIEDISTALLI', 'ADC' or 'ALL'."
assert hodoscope in ["NERO", "BLU", "ROSSO"], f"Unexpected color: {hodoscope}. Expected 'ROSSO', 'BLU', 'NERO'."


pkl_filename = Path(f'results_{hodoscope}_{version}.pkl')
if pkl_filename.exists():
    #print(f"File {pkl_filename} already exists. Opening it...")
    with open(pkl_filename, 'rb') as f:
        result_df = pd.read_pickle(f)
    print(f"Existing DataFrame loaded with {len(result_df)} entries.")
else:
    path = f'{parsed_files_path}/{hodoscope}/{version}/'
    file_list = glob(f"{path}/*.json")
    print(f"Found {len(file_list)} files in {path}")
    # Lista per raccogliere i risultati
    from concurrent.futures import ThreadPoolExecutor
    results = [] 
    def process_file(file):
        run = Path(file).stem.split('run')[-1]
        result = run_manager.read_summary_file(file)

        return {
            "type": result.type,
            "run": int(run),
            "is_run_ok": result.is_run_ok,
            "missing_run": result.missing_run,
            "parsing_failed": result.is_parsing_failed,
            "has_less_events": result.has_less_events,
            "has_mismatches": result.has_mismatches,
            "has_unrecoverable_mismatches": result.has_unrecoverable_mismatches,
            "mismatch_counter": result.mismatch_counter,
            "unrecoverable_mismatch_counter": result.unrecoverable_mismatch_counter,
            "bit_flip_counter": result.bit_flip_counter,
            "bit_missing_counter": result.bit_missing_counter,
            "block_idxs": result.mismatch_blockindex,
            "unrecoverable_mismatches_details": result.unrecoverable_mismatches_details
        }

    cores = 4
    print(f"Processing files with {cores} threads...")
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process_file, file_list))
    print(f"Files processed.")
    # Crea il DataFrame alla fine, con tutti i risultati
    result_df = pd.DataFrame(results)
    #Save df as pkl
    print("Saving dataframe...")
    result_df.to_pickle(pkl_filename)

PIEDISTALLI_only=None
if type != "ALL":
    result_df = result_df[result_df['type'] == type]
    print(f"Using only runs of type {type}. Total runs: {len(result_df)}")
    
else:
    print(f"-----------type ALL-------------->>>CONSIDERATIONS-------------------- \n Using all types of runs (PIEDISTALLI and ADC). Total runs: {len(result_df)}")
    df_new = (
    result_df.assign(
        ADC=result_df["type"].eq("ADC"),
        PIEDISTALLI=result_df["type"].eq("PIEDISTALLI")
    )
    .groupby("run", as_index=False)[["ADC", "PIEDISTALLI"]]
    .any()
    .rename(columns={"run": "run_number"})
    )
    print(".")
    print(".")
    print(".")
    print("[START SANITY CHECKS]")
    print("Number of slave runs: ", df_new['ADC'].sum())
    #Sanity check. By Constructions all runs have both PIEDISTALLI AND ADC files, but let's check it anyway
    if len(df_new.query('ADC == True and PIEDISTALLI == False')) == 0:
        print("[Check ok]: All slave have a pedestal")
    else: print("[Check failed]: Some slave runs don't have a pedestal. By construction they should be the same.")

    PIEDISTALLI_only = df_new.query('ADC == False and PIEDISTALLI == True')
    print(f"Pedestal only: Number of runs: {len(PIEDISTALLI_only)}") 
    print("[END SANITY CHECKS]")
    print(".")
    print(".")
    print(".")
    

    print("Status before quality checks:")
    result_df_starting_check = result_df.query('missing_run == False')
    df_new = (
        result_df_starting_check.assign(
            ADC=result_df_starting_check["type"].eq("ADC"),
            PIEDISTALLI=result_df_starting_check["type"].eq("PIEDISTALLI")
        )
        .groupby("run", as_index=False)[["ADC", "PIEDISTALLI"]]
        .any()
        .rename(columns={"run": "run_number"})
        )
    good_for_both = df_new.query('ADC == True and PIEDISTALLI == True')
    print(f"Slave & pedestal: {len(good_for_both)} runs") #, Runs List: {list(good_for_both['run'])}")
    good_for_ADC_only = df_new.query('ADC == True and PIEDISTALLI == False')
    print(f"Slave only:           {len(good_for_ADC_only)} runs") #, Runs List: {list(good_for_ADC_only['run'])}")
    good_for_PIEDISTALLI_only = df_new.query('ADC == False and PIEDISTALLI == True')
    print(f"Pedestal only:            {len(good_for_PIEDISTALLI_only)} runs") # " Runs List: {list(good_for_PIEDISTALLI_only['run'])}")
    assert len(good_for_both)*2 + len(good_for_ADC_only) + len(good_for_PIEDISTALLI_only) == len(result_df_starting_check), "Something is wrong in the classification!"
    total_slave_runs = len(good_for_both) + len(good_for_ADC_only)
    print(f"Total number of available runs (raw file level): {len(good_for_both) + len(good_for_ADC_only) + len(good_for_PIEDISTALLI_only)}")
    print(f"<<<-----------type ALL--------------CONSIDERATIONS--------------------")

#probabilità che una riga contenga almeno un valore corrotto
result_df["mismatch_prob"] = (
    result_df["mismatch_counter"] *625 /
    (np.where(result_df["type"] == "ADC", 40000, 50000) *16)
)
#print(result_df[["mismatch_prob", "mismatch_counter"]])
#import pdb; pdb.set_trace()
result_df["mismatch_test_passed"] = (result_df["has_mismatches"] == False) | ( (result_df["has_mismatches"] == True) & (result_df["has_unrecoverable_mismatches"] == False) )
total_runs = len(result_df)
new_total = total_runs

missing_run = len(result_df.query('missing_run == True'))
relative_total_missing_run = missing_run / new_total * 100
print(f"Missing runs: {missing_run} out of {new_total} ({relative_total_missing_run:.2f}%)")
new_total = new_total - missing_run

parsing_failed_count = len(result_df.query("parsing_failed == True"))
print(f"Fail parsing: {parsing_failed_count} out of {new_total} ({parsing_failed_count/new_total*100:.2f}%)")
new_total = new_total - parsing_failed_count

has_less_events_count = len(result_df.query('has_less_events == True'))
relative_total_has_less_events = has_less_events_count / new_total * 100
print(f"Fails total number of events check: {has_less_events_count} out of {new_total} ({relative_total_has_less_events:.2f}%)")
new_total = new_total - has_less_events_count
print(f"Runs that pass the first three checks: {new_total} out of {total_runs} ({new_total/total_runs*100:.2f}%)")
print(f"[INFO] {missing_run+parsing_failed_count+has_less_events_count} files were excluded from the following checks because they either failed to parse, have missing run or have less events than expected.")


failing_df = result_df.query('missing_run == True or parsing_failed == True or has_less_events == False')
if PIEDISTALLI_only is not None and len(PIEDISTALLI_only) > 0:
    print(f"----------->>>type ALL--------------CONSIDERATIONS--------------------")
    print(".")
    print(".")
    print(".")
    print("[SANITY CHECK 2]")
    print("Since there were piedistally only runs, let's investigate...By construction we parse the same number of runs for ADC and PIEDISTALLI, so probably a mistake, hence they should get here.")
    is_piedistalli_only_failing = PIEDISTALLI_only['run_number'].isin(failing_df['run'])
    print(f"Number of runs that are only PIEDISTALLI and fail the first checks: {is_piedistalli_only_failing.sum()} out of {len(PIEDISTALLI_only)} ({is_piedistalli_only_failing.sum()/len(PIEDISTALLI_only)*100:.2f}%)")
    is_piedistalli_only_missing = PIEDISTALLI_only['run_number'].isin(result_df.query('missing_run == True')['run'])
    print(f"Number of runs that are only PIEDISTALLI and have missing run: {is_piedistalli_only_missing.sum()} out of {len(PIEDISTALLI_only)} ({is_piedistalli_only_missing.sum()/len(PIEDISTALLI_only)*100:.2f}%)")
    is_piedistalli_only_failing_parsing = PIEDISTALLI_only['run_number'].isin(result_df.query('parsing_failed == True')['run'])
    print(f"Number of runs that are only PIEDISTALLI and fail parsing: {is_piedistalli_only_failing_parsing.sum()} out of {len(PIEDISTALLI_only)} ({is_piedistalli_only_failing_parsing.sum()/len(PIEDISTALLI_only)*100:.2f}%)")
    is_piedistalli_only_failing_events = PIEDISTALLI_only['run_number'].isin(result_df.query('has_less_events == True')['run'])
    print(f"Number of runs that are only PIEDISTALLI and fail events check: {is_piedistalli_only_failing_events.sum()} out of {len(PIEDISTALLI_only)} ({is_piedistalli_only_failing_events.sum()/len(PIEDISTALLI_only)*100:.2f}%)")
    print("[SANITY CHECK 2]")
    print(".")
    print(".")
    print(".")
    print(f"<<<-----------type ALL--------------CONSIDERATIONS--------------------")

# Prima di continuare vorrei correggere il df in modo che i check successivi siamo True o False solo per i run che esestono, che hanno corretto numero di eventi e che superano il parsing, altrimenti li metto a None
mask = result_df[['parsing_failed','missing_run','has_less_events']].any(axis=1)
result_df.loc[mask, [ 'has_mismatches', 'has_unrecoverable_mismatches', 'mismatch_test_passed']] = None

has_mismatches_count = len(result_df.query('has_mismatches == True'))
relative_total_has_mismatches = has_mismatches_count / new_total * 100
print(f"Runs with at least 1 mismatch: {has_mismatches_count} out of {new_total} ({relative_total_has_mismatches:.2f}%)")
unrecoverable_mismatch_count = len(result_df.query('mismatch_test_passed == False'))
relative_total_unrecoverable_mismatch = unrecoverable_mismatch_count / new_total * 100
print(f"Runs with at least 1 mismatch not recoverable: {unrecoverable_mismatch_count} out of {new_total} ({relative_total_unrecoverable_mismatch:.2f}%)")


#List of runs that pass all checks
runs_basic_checks = result_df.query('parsing_failed == False and has_less_events == False and missing_run==False')
runs_mismatch_check = runs_basic_checks.query('(mismatch_test_passed == True)')

print(f"Runs that pass mismatch test: {len(runs_mismatch_check)} out of {new_total} ({len(runs_mismatch_check)/new_total*100:.2f}%)")
print(f"Runs that pass all the checks (without considering missing runs): {len(runs_mismatch_check)} out of {len(result_df.query('missing_run==False'))} ({len(runs_mismatch_check)/len(result_df.query('missing_run==False'))*100:.2f}%)")
#How many runs that passes all the tests have more than 5% mismatch probability?
n_runs_mismatch_prob_grater_5pc = len(runs_mismatch_check.query('mismatch_prob > 0.05'))
print(f"Runs with mismatch probability > 5%: {n_runs_mismatch_prob_grater_5pc}")
n_runs_mismatch_prob_grater_1pc = len(runs_mismatch_check.query('mismatch_prob > 0.01'))
print(f"Runs with mismatch probability > 1%: {n_runs_mismatch_prob_grater_1pc}")


#save on txt file, good run list
if type!="ALL":
    runs_mismatch_check_sorted = runs_mismatch_check.sort_values(by='run')
    good_runs_list = runs_mismatch_check_sorted.query("mismatch_prob < 0.05")['run'].to_numpy()
    with open(f"{hodoscope}_type{type}_GOODRUNS_list_prob_below_5pc.txt", 'w') as f:
        f.writelines(f"{item}\n" for item in good_runs_list)


#import pdb; pdb.set_trace()
if type == "ALL":
    print(f"----------->>>type ALL--------------CONSIDERATIONS--------------------")


    df_new = (
        runs_mismatch_check.assign(
            ADC=runs_mismatch_check["type"].eq("ADC"),
            PIEDISTALLI=runs_mismatch_check["type"].eq("PIEDISTALLI")
        )
        .groupby("run", as_index=False)[["ADC", "PIEDISTALLI"]]
        .any()
        .rename(columns={"run": "run_number"})
    )
    #import pdb; pdb.set_trace()
    #Count how many runs are good for both types, and how many are good only for one type
    good_for_both = df_new.query('ADC == True and PIEDISTALLI == True')
    print(f"Slave & pedestal: Number of runs: {len(good_for_both)}") #, Runs List: {list(good_for_both['run'])}")
    good_for_ADC_only = df_new.query('ADC == True and PIEDISTALLI == False')
    print(f"Slave only: Number of runs: {len(good_for_ADC_only)}") #, Runs List: {list(good_for_ADC_only['run'])}")
    good_for_PIEDISTALLI_only = df_new.query('ADC == False and PIEDISTALLI == True')
    print(f"Pedestal only: Number of runs: {len(good_for_PIEDISTALLI_only)}") # " Runs List: {list(good_for_PIEDISTALLI_only['run'])}")

    print(f'Total good slave runs: {len(good_for_both) + len(good_for_ADC_only)} out of {total_slave_runs}, ({(len(good_for_both) + len(good_for_ADC_only))/total_slave_runs*100:.2f}%)' )
    print(f'Percentage of slave files without pedestal run: {len(good_for_ADC_only)/(len(good_for_both) + len(good_for_ADC_only))*100:.2f}%' )
    print(f"<<<-----------type ALL--------------CONSIDERATIONS--------------------")

run_min = result_df['run'].min()
run_max = result_df['run'].max()


#-------------- GOD RUNS STATISTICS --------------
# define bins in log space
bins = np.linspace(
    1,
    runs_mismatch_check['mismatch_counter'].max(),
    60
)
recoverable_mismatches = runs_mismatch_check#runs_basic_checks.query('has_mismatches == True and has_unrecoverable_mismatches == False')
# add stantard deviation to the histogram of mismatches per run, with error bars, and save it as png
st_dev = recoverable_mismatches['mismatch_counter'].std()
mean = recoverable_mismatches['mismatch_counter'].mean()
mean_error = st_dev/np.sqrt(len(recoverable_mismatches))
tot_n_runs = len(recoverable_mismatches)
plt.figure(figsize=(10,6))
plt.hist(recoverable_mismatches['mismatch_counter'].to_numpy(), bins=bins, alpha=0.5, label='Recoverable Mismatches')
plt.text(0.95, 0.95, f'Mean: {mean:.2f} +/- {mean_error:.2f}  \nStd Dev: {st_dev:.2f} \nEntries: {tot_n_runs}',size=16, horizontalalignment='right', verticalalignment='top', transform=plt.gca().transAxes)
plt.xlabel('Number of mismatches per file (per run)')
plt.ylabel('run counts')
plt.title(f'{hodoscope}, type {type} RECOVERABLE RUNS')
plt.legend()
plt.savefig(f'{hodoscope}_type{type}_GOODRUNS_n_mismatches_per_run_histogram.png')
plt.close()

bins = np.linspace(
    1,
    runs_mismatch_check['mismatch_counter'].max(),
    60
)
plt.figure(figsize=(10,6))
plt.hist(runs_mismatch_check['bit_missing_counter'].dropna().to_numpy(), bins=bins, alpha=0.5, label='Bit Missing')
plt.hist(runs_mismatch_check['bit_flip_counter'].dropna().to_numpy(), bins=bins, alpha=0.5, label='Bit Flips')  

plt.xlabel('Number of bit flips/missing per file (per run)')
plt.ylabel('run counts')
plt.title(f'{hodoscope}, type {type} RECOVERABLE RUNS')
plt.legend()
plt.savefig(f'{hodoscope}_type{type}_GOODRUNS_n_bit_flips-or-missing_per_run_histogram.png')
plt.close()

print("merging board index of mismatched. It may take some time...")
from itertools import chain
merged_block_idx = list(chain.from_iterable(runs_mismatch_check["block_idxs"].dropna().tolist()))
plt.figure(figsize=(10,6))
plt.hist(merged_block_idx, bins=20, alpha=0.5, label='Mismatches board Index')  
plt.xlabel('Block Index of Mismatches')
plt.ylabel('total counts')
plt.title(f'{hodoscope}, type {type} RECOVERABLE RUNS')
plt.legend()
plt.savefig(f'{hodoscope}_type{type}_GOODRUNS_block_index_of_mismatches_histogram.png')
plt.close()



#---------- ALL RUNS STATISTICS --------------

# define bins in log space
bins = np.logspace(
    np.log10(1),  # minimum bin (avoid 0 because log10(0) is undefined)
    np.log10(result_df['mismatch_counter'].max()),
    60            # number of bins
)

# Plot mismatched, with orizontal axes in log scale, and save it as png
#mismatch_counter_log = result_df['mismatch_counter'].apply(lambda x: np.log10(x) if x > 0 else 0)
recoverable_mismatches = result_df.query('has_mismatches == True and has_unrecoverable_mismatches == False')
plt.figure(figsize=(10,6))
plt.hist(recoverable_mismatches['mismatch_counter'].to_numpy(), bins=bins, alpha=0.5, label='Recoverable Mismatches')
plt.hist(result_df['unrecoverable_mismatch_counter'].to_numpy(), bins=bins, alpha=0.5, label='Unrecoverable Mismatches')
plt.xscale('log')
plt.yscale('log')
plt.xlabel('Number of mismatches per file (per run)')
plt.ylabel('run counts')
plt.title(f'{hodoscope}, type {type} RECOVERABLE OR UNRECOVERABLE RUNS')
plt.legend()
plt.savefig(f'{hodoscope}_type{type}_ALLRUNS_n_mismatches_per_run_histogram.png')
plt.close()

bins = np.logspace(
    np.log10(1),  # minimum bin (avoid 0 because log10(0) is undefined)
    np.log10(runs_mismatch_check['mismatch_counter'].max()),
    60            # number of bins
)
plt.figure(figsize=(10,6))
plt.hist(result_df['bit_missing_counter'].dropna().to_numpy(), bins=bins, alpha=0.5, label='Bit Missing')
plt.hist(result_df['bit_flip_counter'].dropna().to_numpy(), bins=bins, alpha=0.5, label='Bit Flips')  
plt.xlabel('Number of bit flips/missing per file (per run)')
plt.ylabel('run counts')
plt.xscale('log')
plt.yscale('log')
plt.title(f'{hodoscope}, type {type} RECOVERABLE OR UNRECOVERABLE RUNS')
plt.legend()
plt.savefig(f'{hodoscope}_type{type}_ALLRUNS_n_bit_flips-or-missing_per_run_histogram.png')
plt.close()

#
#print("merging board index of mismatched. It may take some time...")
#from itertools import chain
#merged_block_idx = list(chain.from_iterable(result_df["block_idxs"].dropna().tolist()))
#plt.figure(figsize=(10,6))
#plt.hist(merged_block_idx, bins=20, alpha=0.5, label='Mismatches board Index')  
#plt.xlabel('Block Index of Mismatches')
#plt.ylabel('total counts')
#plt.title(f'{hodoscope}, type {type} RECOVERABLE OR UNRECOVERABLE RUNS')
#plt.legend()
#plt.savefig(f'{hodoscope}_type{type}_ALLRUNS_block_index_of_mismatches_histogram.png')
#plt.close()







