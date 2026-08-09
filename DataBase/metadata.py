import os
import gzip
import ROOT
from datetime import datetime, timezone

# Create ROOT file and TTree
output_file = ROOT.TFile("Metadata_NERO.root", "RECREATE")
tree = ROOT.TTree("Metadata", "Run Metadata")

# Variables
run_number = ROOT.std.vector('int')()
year, month, day, hour, minute, second = (ROOT.std.vector('int')() for _ in range(6))
temperature_lab = ROOT.std.vector('float')()
humidity_lab = ROOT.std.vector('float')()
WP = ROOT.std.vector('float')()
dac10_thresholds = ROOT.std.vector('int')()
sipm_bias_voltage = ROOT.std.vector('float')()
trigger_mux = ROOT.std.vector('string')()
trigger_rate = ROOT.std.vector('float')()
accidental_rate = ROOT.std.vector('float')()
dark_noise = ROOT.std.vector('float')()

# Define branches
tree.Branch("run_number", run_number)
tree.Branch("year", year)
tree.Branch("month", month)
tree.Branch("day", day)
tree.Branch("hour", hour)
tree.Branch("minute", minute)
tree.Branch("second", second)
tree.Branch("temperature_lab", temperature_lab)
tree.Branch("humidity_lab", humidity_lab)
tree.Branch("temp_sipm", WP)
tree.Branch("dac10_thresholds", dac10_thresholds)
tree.Branch("sipm_bias_voltage", sipm_bias_voltage)
tree.Branch("trigger_mux", trigger_mux)
tree.Branch("trigger_rate", trigger_rate)
tree.Branch("accidental_rate", accidental_rate)
tree.Branch("dark_noise", dark_noise)

broken_runs = open("NotComplete_NERO.txt", "w")

# Path to directory containing gz files
directory = '.'

# Process each gz file
for filename in os.listdir(directory):
    if filename.startswith("SLOWCONTROL_run") and filename.endswith(".gz"):
        filepath = os.path.join(directory, filename)
        with gzip.open(filepath, 'rt') as file:
            for line in file:
                parts = line.strip().split()
                if len(parts) != 61:
                    broken_runs.write(f"{float(parts[0]) + 1}\n")
                    continue

                run_num = int(parts[0]) + 1
                run_number.push_back(run_num)

                ts = int(parts[1])/1000
                dt = datetime.fromtimestamp(ts, timezone.utc)
                year.push_back(dt.year)
                month.push_back(dt.month)
                day.push_back(dt.day)
                hour.push_back(dt.hour)
                minute.push_back(dt.minute)
                second.push_back(dt.second)

                temperature_lab.push_back(float(parts[3]))
                humidity_lab.push_back(float(parts[4]))
                WP.push_back(float(parts[5]))

                dac10_thresholds.clear()
                dac10_thresholds.reserve(16)
                for val in parts[6:22]:
                    dac10_thresholds.push_back(int(val))

                sipm_bias_voltage.clear()
                sipm_bias_voltage.reserve(16)
                for val in parts[22:38]:
                    sipm_bias_voltage.push_back(float(val))

                trigger_mux.clear()
                trigger_mux.reserve(5)
                for val in parts[38:43]:
                    trigger_mux.push_back(val)

                trigger_rate.push_back(float(parts[43]))
                accidental_rate.push_back(float(parts[44]))

                dark_noise.clear()
                dark_noise.reserve(16)
                for val in parts[45:61]:
                    dark_noise.push_back(float(val))

                tree.Fill()

                # Clear vectors for next line
                for v in [run_number, year, month, day, hour, minute, second,
                          temperature_lab, humidity_lab, WP,
                          dac10_thresholds, sipm_bias_voltage,
                          trigger_mux, trigger_rate, accidental_rate, dark_noise]:
                    v.clear()

# Write and close
output_file.Write()
output_file.Close()

print("Metadata ROOT file created successfully.")
