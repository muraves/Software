
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

$$P1 ~\& ~P2~ \& ~P3~ \& ~signal > 6~phe $$


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


From *raw* to *parsed* data
=====
:blue_book: *This section describes steps that goes from the raw data to the human readable data format, called "parsed data".*

### Raw data
Row data are available in exadecimal format. Furthermore, an event is broaded on 16 rows (one per each readout borad). An example of how raw data looks like is shown here:
![image](documentation/raw_data.png)


**path**: The path should contain the name of the hodoscope (NERO, BLU, ROSSO)
**filename**: ``<ped/slave>Data_evts#_run#_sr#``\
- ``pedData`` stands for pedestal dataset ([pedestal-run](#runs))
- ``slaveData`` stands for cosmic dataset ([cosmic-run](#runs)). The name slave derive by the fact that the SiPMTs are connected to 16 slaves readout boards.

Raw data need to undergo a procedure that makes the file easier to handle: parsing procedure, described below.

### Parsing the data
A **parser** function converts the information of the raw data. In particular the exadecimal number are converted in decimal and the information of an event is collected under just one raw. <span style="color:yellow"> Following information needs to be double checked. [ </span> After the parsing procedure a ``slaveData``(``pedData``)file should have $40\,000$($50\,000$) rows each fully describing a single event: board number, temperature time stamp, and 32 ADC values of each slave board. \
The parser script ``tracks_reconstruction/1_Parser``, can be lunched as it follow
```
python evtParserGPBLU.py <raw_data_filename> <output_filename> <events_number> <rows_to_combine>
```
- ``<raw_data_file>``: absolute path of the raw data
- ``<output_filename>``: name of the output
- ``<events_number>``: number of events in the file, usually $50\,000$ or $40\,000$ and is indicated on the raw data file.
- ``<rows_to_combine>``: The raw dataset has informations coming from all the 16 slave boards that needs to be combined, therefore i put 16. 
 <span style="color:yellow"> ] The raw file that I processed after the parsing procedure has $10\,000$ rows. This makes me wonder if 16 is correct. However there is no number that could give $50\,000$.</span>

**filename**: 
Among other thing is put ADC_0 to ADC_31 counts all aligned in one raw to define an event. 

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
- <span style="color:yellow">**To be understood:**  The branches of the tree are  `ADC_0`, `ADC_1`, ..., `ADC_31`, is this expected? *Giulio said that there should be already track related variables.*</span>

### Pedestal analysis
-   Generated executable by running: 
```
g++ -std=c++20 OnePhe_evaluator.cpp -o OnePhe_evaluator.exe     $(root-config --cflags --libs) -lSpectrum     -I/home/biolchini/miniforge3/envs/muraves/include/python3.11     -L/home/biolchini/miniforge3/envs/muraves/lib -lpython3.11
```
-   To run the pedestal analysis script one should run the following:
```
bash MURAVES_PedestalAnalysis.sh <color> <start_run> <end_run>
```
In my case I had to do a few modification in order to be able to run the script locally:
-   Changed path of `PED_File_name` to my local path
-   Changed `Pedestal_File` to my local path to the PreAnalysed root file
-   :warning: Found internal **unconsistency** of the name of the tree of the PreAnalysed data: PreAnalysis saves it as `ped_tree`, the script searches as `PEDtree`.
-   :warning: **Suboptimal for debugging** the name of the tree is repeated several time instead of defining a variable.
-  <span style="color:yellow">**To be understood:** </span> The script is searching for files that I don't know what they are:
  ```
  SysError in <TFile::TFile>: file /media/muraves2/MURAVES_DATA///PEDanalysis/TREES/PEDdata_/_run11196.root can not be opened No such file or directory
SysError in <TFile::TFile>: file /media/muraves2/MURAVES_DATA///PEDanalysis/CANVAS/SpectrumANDpeaks_/_run11196.root can not be opened No such file or directory

```

What I run (for myself to rememeber): 
```
bash MURAVES_PedestalAnalysis.sh / 11196 11196

```



### Main Reconstruction
Main script: `MURAVES_reco_v2`. A few parameters are harcoded in the script directly:
-   **Spacial resolution values** 
-   **Detector positions** 
-   **Hardware information** (number of boards, `nInfo`, `nChInfo`, ...)
-   **Filepaths**
A better way to approach this is to create a configuration file with all these parameters.
This approach minimises the interations and the changes to the main reconstruction script. 
In particular this is very important to have a flexible reconstruction script that can run from every path specifed.

  <span style="color:red"> **Missing files:** </span>Several dependences missing (still on Muripper only):
- #include "EvaluateAngularCoordinates.h"
- #include "ClusterLists.h"
- #include "ReadEvent.h"
- #include "Tracking.h"


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