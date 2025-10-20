
Most recent dicussed topics can be found on:
- Hackmd documentation, [here](https://hackmd.io/@M5L90mu5TQykNiqmWuLAYA/H1LG3Tshee/edit).

- MURAVES Indico Agenda, [here](https://agenda.infn.it/category/730/)


From detector to data files: the essential
===
:blue_book: *This section describes a few fundamental concepts necessary to understand the data collected by the MURAVES experiment.*

### Coordinate system

*x*: direction traversing the vulcano \
*yz*: detector front view \
*xy*: detector upper view \
*zx*: detector side view 



### Detector composition
The MURAVES experiment is composed by 3 detectors (hodoscopes): ROSSO, BLU and NERO. They are placed in the same contaner on the Vesuvius but looking at different directions.\
Each hodoscope has 3 planes ($P_n$, n = 1,2,3) composed by 2 subdetectors each, Pn_z and $Pn_y$. $Pn_z$ and $Pn_y$ are 64 plastic scintellator bars, 32 lying on $y$ direction and 32 lying on $z$ direction. 

### Trigger
And among 3 planes of an hodoscope and signal must be above 6 photoelectrons ([FAQ](#why-6-photoelectrons-is-the-threshold-of-the-trigger)): 

$$P1 ~\& ~P2~ \& ~P3~ \& ~signal > 6~phe$$


In particular when refering to a plane: $P1(2,3)$ the trigger is set on the logic OR among the 64 scintillating bars composing a plane:

$$ (P1z~ \cup ~P1y) \cap~ (P2z~ \cup ~P2y) \cap~ (P3z~ \cup ~P3y)$$

### Runs
The definition of the run changes depending on the type of run:
- **Pedestal**: $50\,000$ random trigger events.
No coincidences are required among the planes. This run gives a picture of the Front End electronic. Everything that arrives from the data acquisition system is registered. 
    - *Objective:* Calibration ADC counts to photoelectrons
- **Cosmic**: $40\,000$ trigger events. The trigger applied is that described above ([Trigger](#trigger))

### Data quality monitoring
:warning: <span style="color:red"> Nothing is implemented in this regard at the moment.</span>

- **To Do**: 
  - Create a set of rules to accept or not runs. At the moment good and bad runs are all together.
  - The trigger rate is a goot test to select and discard bad runs.


From *raw* to *parsered* data
=====
:blue_book: *This section describes the steps that goes from the raw data to the human readable data format, called "parsered data".*

### Raw data
- **Extention:** Raw data are available as compressed files (`*.gz`). Although it is compressed, each of the `.gz` files contains just one file.
- **Format:** Row data are in exadecimal format. Furthermore, an event is broaded on 16 rows (one per each readout borad). An example of how raw data looks like is shown here:
![image](documentation/raw_data.png)


- **Path**: The path should contain the name of the hodoscope (NERO, BLU, ROSSO)
- **Filename**: ``<ped/slave>Data_evts#_run#_sr#``\
  - ``pedData`` stands for pedestal dataset ([pedestal-run](#runs))
  - ``slaveData`` stands for cosmic dataset ([cosmic-run](#runs)). The name slave derive by the fact that the SiPMTs are connected to 16 slaves readout boards.
  - `evts`: total number of events, so either $40\,000$ (slave) or $50\,000$ (pedestal).
  - `run`: run number
  - `sr`: subrun

- :warning: For each run number there are several subruns. Therefore the total number of events expected for an entire run is divided among several files (3 or 4 usually, identified by the same run number and different subrun number)
- Raw data need to undergo a procedure that makes the file easier to handle: parsing procedure, described below.

### Parsing the data
A **parser** function converts the information of the raw data. In particular the exadecimal number are converted in decimal and the information of an event is collected under just one raw.  After the parsing procedure a ``slaveData``(``pedData``)file should have $40\,000$($50\,000$) rows each fully describing a single event: board number, temperature time stamp, and 32 ADC values of each slave board. \

The parsing procedure for 1 single run, *e.g.* `slaveData_evts40000_run12345_sr*.gz`, reads as it follows:
- Extract all the subruns available from their `.gz` extension. The files extracted doesn't have any extension anymore.
- The parser script ``tracks_reconstruction/1_Parser``, can be lunched as it follow:
  ```
  python evtParserGP_<color>.py <raw_data_file> <output_filename> <events_number> <rows_to_combine>
  ```
  - ``<raw_data_file>``: absolute path of the raw data
  - ``<output_filename>``: name of the output. It should be: `ADC_run#.txt`
  - ``<events_number>``: number of events in the file, usually $10\,000$ for a slave data. This is the number of events in a single subrun.
  - ``<rows_to_combine>``: The raw dataset has informations coming from all the 16 slave boards that needs to be combined, therefore i put 16. 
 
- In this example the bash line would be:
  ```
  python evtParserGP_<color>.py  slaveData_evts40000_run12345_sr1  ADC_run12345.txt  10000  16
  ```
- This script will create the outputfile ADC_run12345.txt and fill it with the first $10\,000$ events.
- In orther to parse the other subruns, one should run the same line changing only the number of the rubrun:
  ```
  python evtParserGP_<color>.py  slaveData_evts40000_run12345_sr2  ADC_run12345.txt  10000  16
  ```
  ```
  python evtParserGP_<color>.py  slaveData_evts40000_run12345_sr3  ADC_run12345.txt  10000  16
  ```
  ```
  python evtParserGP_<color>.py  slaveData_evts40000_run12345_sr4  ADC_run12345.txt  10000  16
  ```
- After the first time, where the file ``ADC_run12345.txt`` is generated, the following time is just opened and the new raws appended.
- Once the parsing procedure is applied to all the subrun, the output files containes the information about the $40\,000$ events of a slave dataset.


An example of how parsed data looks like is shown here:
![image](documentation/parsed_data.png)

Reconstruction workflow
===

### Pre-reconstruction
The pre-reconstruction can be run launching `2_PreRec/script_Preanalysis` as it follows:
```
python script_Preanalysis.py <start_run> <end_run>
```
- check that you gave the correct path where to search for the parsered file modifying the variable: `parseredPATH` inside the script.
- `2_PreRec/script_Preanalysis` will call `MakePedestalTree.py`
- <span style="color:green"> Runs without errors, the tree in the root file is filled.</span>
- <span style="color:yellow">**To be understood:**  The output from the available pre-reconstruction script has less branches as what is suppose to have.</span>

<span style="color:yellow">**NB:** </span> The number of board was set to 12, why?  I brought it to 16.

### Pedestal analysis
Pedestal analysis can be run by using two scripts that do the same thing: computes the value on 1phe.
- `OnePhe_evaluator.cpp`
  - Generate a configuration file for each board. Each of the script has 31 channel values and their corrispondend pedestal and 1phe values.
  - Genetare a root file with SLOWCONTROL information  such as temperature, WorkingPOint, TriggerRate, ..., and the values of pedestal and 1phe for each board.
  - Generate a root file with canvas having all the ADC histogram. They are grouped by board.
- `OnePhe_evaluator.py`
  - Generate a configuration file for each board. Each of the script has 31 channel values and their corrispondend pedestal and 1phe values.
  
#### Using `OnePhe_evaluator.cpp`
-   Generate executable by running: 
``` bash
g++ -std=c++20 OnePhe_evaluator.cpp -o OnePhe_evaluator.exe     $(root-config --cflags --libs) -lSpectrum     -I/home/biolchini/miniforge3/envs/muraves/include/python3.11     -L/home/biolchini/miniforge3/envs/muraves/lib -lpython3.11
```
-   To run the pedestal analysis script one should run the following:
``` bash
bash MURAVES_PedestalAnalysis.sh <color> <start_run> <end_run>
```
In my case I had to do a few modification in order to be able to run the script locally:
-   Changed path of `PED_File_name` to my local path
-   Changed `Pedestal_File` to my local path to the PreAnalysed root file
-   :warning: Found internal **unconsistency** of the name of the tree of the PreAnalysed data: PreAnalysis saves it as `ped_tree`, the script searches as `PEDtree`.
-   :warning: **Suboptimal for debugging** the name of the tree is repeated several time instead of defining a variable.


#### Using `OnePhe_evaluator.py`
- Run the following command:
  ``` bash
  python OnePhE_evaluator.py <color> <number_of_runs> <delta_around_central_runID> <central_runID>
  ```
  *e.g.* running the pedestal analysis for one run only of the ROSSO hodoscope
  ``` bash
  python OnePhE_evaluator.py ROSSO 1 0 15012
  ```

### Main Reconstruction
In order to run the main reconstruction run the following command to compile the `.cpp` and create the executable:
```
g++ -std=c++20 MURAVES_reco_v2.cpp -o MURAVES_reco_v2.exe     $(root-config --cflags --libs) -lSpectrum     -I/home/biolchini/miniforge3/envs/muraves/include/python3.11     -L/home/biolchini/miniforge3/envs/muraves/lib -lpython3.11

```
Main script: `MURAVES_reco_v2`. A few parameters are harcoded in the script directly:
-   **Spacial resolution values** 
-   **Detector positions** 
-   **Hardware information** (number of boards, `nInfo`, `nChInfo`, ...)
-   **Filepaths**
A better way to approach this is to create a configuration file with all these parameters.
This approach minimises the interations and the changes to the main reconstruction script. 
In particular this is very important to have a flexible reconstruction script that can run from every path specifed.

  <span style="color:red"> **Missing files:** </span>Several dependences missing (still on Muripper only):
- "EvaluateAngularCoordinates.cpp"
- "ClusterLists.cpp"
- "ReadEvent.cpp"
- "Tracking.cpp"


### Golden selection

# FAQ

### Why 6 photoelectrons is the threshold of the trigger?
Studies have been performed demonstrating that this is a good trade off between dark counts (noise) and signal. :warning: <span style="color:yellow"> Documentation unavailable</span>

# Question to be answered

### What's "slow control"? 
This is mentioned both in Pedestal analysis and in the main reconstruction script. It access specific files on Muripper (`/media/muraves3/VESUVIO/datiVesuvio/`) called `SLOWCONTROL_*.txt`

### What's "spiroc hybrid map"?
In the main reconstruction script a file called `"../../ANALYSIS/ReconstructionTracks_from3to4/config/spiroc-hybrid-map.cfg"` is required. What's this needed for, what's in it?

### Telescope configuration file 
This file is used, what's in it? There were some values, related to the telescope, hardcoded in the script. 
`/home/muraves/Desktop/MURAVES/ANALYSIS/ReconstructionTracks_from3to4/config/telescope`