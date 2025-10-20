from ROOT import TH1F
from ROOT import TFile
from ROOT import TSpectrum
from ROOT import TCanvas
import sys
import matplotlib.pyplot as plt
import glob
import numpy as  np
import math as mt
import subprocess

##################################
color = sys.argv[1]
nRuns = int(sys.argv[2])
deltaRuns = int(sys.argv[3])
path = '/home/biolchini/Documents/muography/MURAVES/RawData/'
### choose if you want to evaluate ped for a single run or a group of runs ####
# if nRuns  = 1  --> singleRun
# if nRuns = 2  --->  group of runs
Runs=[]
for  i in range(nRuns):
    Runs.append(int(sys.argv[i+4]))
##########################################################
##### Directory create  ####
#subprocess.call(['mkdir', '/home/muraves/Desktop/MURAVES/ANALYSIS/ReconstructionTracks_from3to4/config/ped'+color+'/ped_run'+str(Runs[0])])
                
############### Fill Histograms for visualization function #############
def FillVector(color, INrun):
    boardALL = []
    for j in range(16):
        boardALL.append([])
    for run in range(INrun-deltaRuns,INrun+deltaRuns+1):
        filename = path+f'/{color}'+'/prereconstructed_data/PIEDISTALLI_run_'+str(run)+'.root'
        #print(filename)
        files =glob.glob(filename)
        #files =glob.glob(path+color+'/PreANALYZED/ADC*run'+str(run)+'_'+'*root')
        if  len(files) >0:
            fileName = files[0]
            print(fileName)
            fileADC = TFile(fileName)
            ttree = fileADC.Get("ped_tree")
            #ttree = fileADC.Get("ADCtree")
            for event in ttree:
                board=[]
                for i in range(16):
                    board.append([])
                    if  ttree.scheda == i:
                        board[i].append(ttree.adc_0)
                        board[i].append(ttree.adc_1)
                        board[i].append(ttree.adc_2)
                        board[i].append(ttree.adc_3)
                        board[i].append(ttree.adc_4)
                        board[i].append(ttree.adc_5)
                        board[i].append(ttree.adc_6)
                        board[i].append(ttree.adc_7)
                        board[i].append(ttree.adc_8)
                        board[i].append(ttree.adc_9)
                        board[i].append(ttree.adc_10)
                        board[i].append(ttree.adc_11)
                        board[i].append(ttree.adc_12)
                        board[i].append(ttree.adc_13)
                        board[i].append(ttree.adc_14)
                        board[i].append(ttree.adc_15)
                        board[i].append(ttree.adc_16)
                        board[i].append(ttree.adc_17)
                        board[i].append(ttree.adc_18)
                        board[i].append(ttree.adc_19)
                        board[i].append(ttree.adc_20)
                        board[i].append(ttree.adc_21)
                        board[i].append(ttree.adc_22)
                        board[i].append(ttree.adc_23)
                        board[i].append(ttree.adc_24)
                        board[i].append(ttree.adc_25)
                        board[i].append(ttree.adc_26)
                        board[i].append(ttree.adc_27)
                        board[i].append(ttree.adc_28)
                        board[i].append(ttree.adc_29)
                        board[i].append(ttree.adc_30)
                        board[i].append(ttree.adc_31)
                        boardALL[i].append(board[i])

    return boardALL
###########################################################################################

AllRuns = []

################################### Fill Arrays  ###########################################

for run in range(len(Runs)):
    print(f'===========================run {Runs[run]} ========================')

    boardALL = FillVector(color, Runs[run])
    print(len(boardALL))
    boardT = []
    for nBoard in range(16):
        boardT.append(np.array(boardALL[nBoard]).transpose())
    AllRuns.append(boardT)
    print("LEN(boardALL):")
   

    print(len(boardALL))
    for b in range(16):
        print(f"Board {b}: entries = {len(boardALL[b])}")
    import pdb; pdb.set_trace()
    del boardALL
    del boardT



OnePhes = []
PedValues = []

#histoRootFile = TFile(color+"_runs_Histograms_peacked.root","recreate")



for board in range(16):
    print('Board: ',board)
    OnePhes_singleBoard = []
    PedValues_singleBoard = []
    for i in range(0,8):
        for j in range(0,4):

            OnePhes_channel = []
            PedValues_channel = []
            for run in  range(len(AllRuns)):
                ################### Peacks searching ###########################
                histo = TH1F("Ped_run_"+str(Runs[run])+"_board_"+str(board)+"_ch_"+str(4*i+j),"PED distribution",300,1450,1750)
                histo2 = TH1F("Ped_run_"+str(Runs[run])+"_board_"+str(board)+"_ch_"+str(4*i+j)+"_logscale","PED distribution",300,1450,1750)
                #### Using log scale to enanhance peacks 
                #print(f"Run={run}, board={board}, channel={4*i+j}")
                #print(f"Shape of AllRuns[run][board]: {np.shape(AllRuns[run][board])}")

                ################## Histograms filling #####################################
                for index in range(len(AllRuns[run][board][4*i+j])):
                    histo.Fill(int(AllRuns[run][board][4*i+j][index]))

                for bin in range(histo.GetXaxis().GetNbins()):
                    if histo.GetBinContent(bin)!=0:
                        histo2.SetBinContent(bin,mt.log10(histo.GetBinContent(bin)))

                ##################### Searching peacks with TSpectrum ##################
                s = TSpectrum()
                nfoundPeacks = s.Search(histo2,0,"",0.00001)
                #histo2.Write()
                xPeacks= s.GetPositionX()
                xPositions=[]
                for x in range(nfoundPeacks):
                    xPositions.append(xPeacks[x])
                xPositions.sort()
                yPeacks = []
                ############################# Evaluate 1phe ############################
                for  h in range(nfoundPeacks):
                    yPeacks.append(histo2.GetBinContent(histo.FindBin(xPositions[h])))
                MaxIndex  = yPeacks.index(max(yPeacks))
                SecondMaxPeacks = MaxIndex+1
                try:
                    Onephe =  xPositions[SecondMaxPeacks]-xPositions[MaxIndex]
                    if Onephe <= 20 and  ( xPositions[SecondMaxPeacks+1] -  xPositions[SecondMaxPeacks]) <15 :
                        Onephe =  xPositions[SecondMaxPeacks+1]-xPositions[MaxIndex]
                except:
                    Onephe = "no 2nd peack"
                OnePhes_channel.append(Onephe)
                PedValues_channel.append(xPositions[MaxIndex])
		########################################################################
            OnePhes_singleBoard.append(OnePhes_channel)
            PedValues_singleBoard.append(PedValues_channel)
            del  OnePhes_channel
            del PedValues_channel
    OnePhes.append(OnePhes_singleBoard)
    PedValues.append(PedValues_singleBoard)

################# 1phe  writings  ##############################

for nBoard in range(16):
    file=open("/home/biolchini/Documents/muography/MURAVES/RawData/BLU/pedestal_analysed_data/pedestal_"+str(nBoard)+".cfg","w")
    file.write("ch \t ped \t 1pe \n")
    for ch in range(32):
        for run in range(len(Runs)):
            if  OnePhes[nBoard][ch][run] == "no 2nd peack":
                 file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][run]))+ "\t" + str(1000)+ "\t")
            else:
#                if int(OnePhes[nBoard][ch][run]) > 38 or int(OnePhes[nBoard][ch][run]) < 25: #nero
                if  nBoard !=5 and (int(OnePhes[nBoard][ch][run]) > 38 or int(OnePhes[nBoard][ch][run]) < 20):  

                    if ch!=0 and OnePhes[nBoard][ch-1][run] != "no 2nd peack":
                        file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][run]))+ "\t" + str(int(OnePhes[nBoard][ch-1][run]))+ "\t 1" )
                        OnePhes[nBoard][ch][run] = OnePhes[nBoard][ch-1][run]
                    else:

                        file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][run]))+ "\t" + str(28)+ "\t 0")
                        OnePhes[nBoard][ch][run] = 30
                elif nBoard==5 and (int(OnePhes[nBoard][ch][run]) > 28 or int(OnePhes[nBoard][ch][run]) < 10):
                    if ch!=0 and OnePhes[nBoard][ch-1][run] != "no 2nd peack":
                        file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][run]))+ "\t" + str(int(OnePhes[nBoard][ch-1][run]))+ "\t 1")
                        OnePhes[nBoard][ch][run] = OnePhes[nBoard][ch-1][run]
                    else:
                        file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][run]))+ "\t" + str(18)+ "\t")
                        OnePhes[nBoard][ch][run] = 18
                else:
                    file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][run]))+ "\t" + str(int(OnePhes[nBoard][ch][run]))+ "\t 0")
           
        file.write("\n")

