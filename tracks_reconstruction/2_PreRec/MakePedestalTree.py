from ROOT  import TFile
from ROOT import TTree
from array import array
import sys
import argparse as argp
import functools

Description = ' This code takes as input the data from ADC and unpacks them to obtain a track collection '
parser = argp.ArgumentParser(description = Description)
parser.add_argument('-data', '--ADCfile', type = open, required = True, help = 'This file cointains data taken by ADCs')
parser.add_argument('-r','--run', required=True, help = 'run number')
parser.add_argument('-type','--ADCorPED',required=True)
args = parser.parse_args()
runnumber = str(args.run)
fileADC = args.ADCfile
datalines = fileADC.readlines()
isADCorPED= args.ADCorPED
nBoards = 12
nInfoBoard = 39
nChannels=32

####################################################### Reading File ################################################# 
def Board(n,data):
    board = {}
    board['trigger'] = int(data[n*nInfoBoard + 1])
    board['boardNumber'] = int(data[n*nInfoBoard +2])
    board['timeStamp'] = int(data[n*nInfoBoard+35])
    board['temperature'] = int(data[n*nInfoBoard+36])
    board['timeExp'] = int(data[n*nInfoBoard+37])
    board['parity'] = int(data[n*nInfoBoard+38])
    board['FastOr'] = data[n*nInfoBoard+39]
    channels = []
    for nCh in range(nChannels):
        channels.append(int(data[3+n*nInfoBoard + nCh]))
    board['channels'] = channels
    return board

def Event(ADCline):
    data  = ADCline.split()
    # The 'Event' container contains nBoards dictionaries, one for each board, and describes a single event
    # (a single line in the ADC file)                                                                                                                                                                                                    
    Event = [] #list of dictionaries; each dictionary is a board                                                                                                                                                        
    Event = list(map(functools.partial(Board,data=data),range(nBoards)))
    return Event

Events = list(map(Event,datalines))
args.ADCfile.close()

###########################################################################################################################

################ Make the Tree #####################


#filePED =  TFile("/media/muraves2/CILINDRO/PREANALYZED/"+isADCorPED+"_CILINDRO_run_"+str(runnumber)+".root","recreate")
#filePED =  TFile("/media/muraves3/CILINDRO/IAEA/PREANALYZED/WP_100Hz/"+isADCorPED+"_CILINDRO_run_"+str(runnumber)+".root","recreate")
#filePED =  TFile("/media/muraves3/CILINDRO/IAEA/PREANALYZED/FREESKY_NUC/"+isADCorPED+"_CILINDRO_run_"+str(runnumber)+".root","recreate")
filePED =  TFile("/media/muraves3/MURAY/PREANALYSIS/"+isADCorPED+"_run_"+str(runnumber)+".root","recreate")
tree = TTree("ped_tree","tree pedestal")

scheda =array('i',[0]) 
adc_0 = array('i',[0])
adc_1 = array('i',[0])
adc_2 = array('i',[0])
adc_3 = array('i',[0])
adc_4 = array('i',[0])
adc_5 = array('i',[0])
adc_6 = array('i',[0])
adc_7 = array('i',[0])
adc_8 = array('i',[0])
adc_9 = array('i',[0])
adc_10 = array('i',[0])
adc_11 = array('i',[0])
adc_12 = array('i',[0])
adc_13 = array('i',[0])
adc_14 = array('i',[0])
adc_15 = array('i',[0])
adc_16 = array('i',[0])
adc_17 = array('i',[0])
adc_18 = array('i',[0])
adc_19 = array('i',[0])
adc_20 = array('i',[0])
adc_21 = array('i',[0])
adc_22 = array('i',[0])
adc_23 = array('i',[0])
adc_24 = array('i',[0])
adc_25 = array('i',[0])
adc_26 = array('i',[0])
adc_27 = array('i',[0])
adc_28 = array('i',[0])
adc_29 = array('i',[0])
adc_30 = array('i',[0])
adc_31 = array('i',[0])

tree.Branch("scheda",scheda,"scheda/I")
tree.Branch("adc_0",adc_0,"adc_0/I")
tree.Branch("adc_1",adc_1,"adc_1/I")
tree.Branch("adc_2",adc_2,"adc_2/I")
tree.Branch("adc_3",adc_3,"adc_3/I")
tree.Branch("adc_4",adc_4,"adc_4/I")
tree.Branch("adc_5",adc_5,"adc_5/I")
tree.Branch("adc_6",adc_6,"adc_6/I")
tree.Branch("adc_7",adc_7,"adc_7/I")
tree.Branch("adc_8",adc_8,"adc_8/I")
tree.Branch("adc_9",adc_9,"adc_9/I")
tree.Branch("adc_10",adc_10,"adc_10/I")
tree.Branch("adc_11",adc_11,"adc_11/I")
tree.Branch("adc_12",adc_12,"adc_12/I")
tree.Branch("adc_13",adc_13,"adc_13/I")
tree.Branch("adc_14",adc_14,"adc_14/I")
tree.Branch("adc_15",adc_15,"adc_15/I")
tree.Branch("adc_16",adc_16,"adc_16/I")
tree.Branch("adc_17",adc_17,"adc_17/I")
tree.Branch("adc_18",adc_18,"adc_18/I")
tree.Branch("adc_19",adc_19,"adc_19/I")
tree.Branch("adc_20",adc_20,"adc_20/I")
tree.Branch("adc_21",adc_21,"adc_21/I")
tree.Branch("adc_22",adc_22,"adc_22/I")
tree.Branch("adc_23",adc_23,"adc_23/I")
tree.Branch("adc_24",adc_24,"adc24/I")
tree.Branch("adc_25",adc_25,"adc_25/I")
tree.Branch("adc_26",adc_26,"adc_26/I")
tree.Branch("adc_27",adc_27,"adc_27/I")
tree.Branch("adc_28",adc_28,"adc_28/I")
tree.Branch("adc_29",adc_29,"adc_29/I")
tree.Branch("adc_30",adc_30,"adc_30/I")
tree.Branch("adc_31",adc_31,"adc_31/I")



for  ev in Events:
    for board in range(nBoards):
        scheda[0] = int(ev[board]['boardNumber'])
        adc_0[0]= ev[board]['channels'][0]
        adc_1[0] = ev[board]['channels'][1]
        adc_2[0] = ev[board]['channels'][2]
        adc_3[0] = ev[board]['channels'][3]
        adc_4[0] = ev[board]['channels'][4]
        adc_5[0] = ev[board]['channels'][5]
        adc_6[0] = ev[board]['channels'][6]
        adc_7[0] = ev[board]['channels'][7]
        adc_8[0] = ev[board]['channels'][8]
        adc_9[0] = ev[board]['channels'][9]
        adc_10[0] = ev[board]['channels'][10]
        adc_11[0] = ev[board]['channels'][11]
        adc_12[0] = ev[board]['channels'][12]
        adc_13[0] = ev[board]['channels'][13]
        adc_14[0] = ev[board]['channels'][14]
        adc_15[0] = ev[board]['channels'][15]
        adc_16[0] = ev[board]['channels'][16]
        adc_17[0] = ev[board]['channels'][17]
        adc_18[0] = ev[board]['channels'][18]
        adc_19[0] = ev[board]['channels'][19]
        adc_20[0] = ev[board]['channels'][20]
        adc_21[0] = ev[board]['channels'][21]
        adc_22[0] = ev[board]['channels'][22]
        adc_23[0] = ev[board]['channels'][23]
        adc_24[0] = ev[board]['channels'][24]
        adc_25[0] = ev[board]['channels'][25]
        adc_26[0] = ev[board]['channels'][26]
        adc_27[0] = ev[board]['channels'][27]
        adc_28[0] = ev[board]['channels'][28]
        adc_29[0] = ev[board]['channels'][29]
        adc_30[0] = ev[board]['channels'][30]
        adc_31[0] = ev[board]['channels'][31]

        tree.Fill()
tree.Write()
filePED.Close()
