import matplotlib.pyplot as plt
import numpy as np
import utils
import plots

def time_plot(var, time, **kwargs):
    ref = kwargs.get('ref', None)
    xaxis = kwargs.get('xaxis', None)
    yaxis = kwargs.get('yaxis', None)
    title = kwargs.get('title', None)
    plt.figure(figsize=(10,5))
    plt.plot(time, var, marker='o')
    if ref is not None:
        plt.plot(time,ref, marker='',  color='gray', linestyle='--')

    plt.xlabel(xaxis['label']) if xaxis else  plt.xlabel("Time")
    plt.ylabel(yaxis['label']) if yaxis else plt.ylabel("a.u.")
    plt.ylim(yaxis['range']) if yaxis and 'range' in yaxis else None
        

    if title: plt.title(title)
    plt.gcf().autofmt_xdate()   # rotate date labels
    plt.grid(True)
    plt.show()




def run_plots(
    run_range,
    parsed_files_path,
    temperature=True,
    humidity=True,
    trigger_rate=True,
    accidental_rate=True
):
    info_list = []
    runs = []

    for run in run_range:
        runs.append(run)
        info = utils.read_run_info_from_json(
           parsed_files_path + f'ADC_run{run}.json'
        )
        info_list.append(info)

    trs = utils.extract_var("trigger_rate", info_list)
    ars = utils.extract_var("accidental_rate", info_list)
    times = utils.extract_time(info_list)
    temperatures = utils.extract_var("temperature", info_list)
    wps = utils.extract_var("working_point", info_list)

    if trigger_rate:
        plots.time_plot(np.array(trs), np.array(runs),
                        xaxis={'label': 'Run', 'range': (0, None)},
                        yaxis={'label': 'Trigger Rate'})

    if accidental_rate:
        plots.time_plot(np.array(ars), np.array(runs),
                        xaxis={'label': 'Run'},
                        yaxis={'label': 'Accidental Rate'})

    if temperature:
        plots.time_plot(np.array(temperatures), np.array(times),
                        ref=np.array(wps),
                        xaxis={'label': 'Time'},
                        yaxis={'label': 'Temperature (°C)'})
