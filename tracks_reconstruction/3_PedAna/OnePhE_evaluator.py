from ROOT import TH1F
from ROOT import TFile
from ROOT import TSpectrum
from ROOT import TCanvas
#import sys
import matplotlib.pyplot as plt
import glob
import numpy as  np
import math as mt
#import subprocess
import argparse as argp
import logging
import uproot 
import pandas as pd
import time

Description = ' This code takes as input the pedestal run and computes the pedestal position and 1phe conversion.'
parser = argp.ArgumentParser(description = Description)
parser.add_argument('-data', '--ped_file', dest = "ped_file", required = True, help = 'This file cointains pedestal data')
parser.add_argument('-r','--run', dest = "run", required=True, help = 'run number')
#parser.add_argument("-info", "--info", dest = "info", nargs="+", required=True,
#                    help="Input number of runs and delta around the central run")
parser.add_argument("-o", "--output_list", dest="output_list", nargs = '+', required=True,
                    help="List of outputs")
args = parser.parse_args()

##################################

run = args.run
inputfile = args.ped_file
output_list = args.output_list
nBoards = len(output_list)
nChannels = 32
print("Started the script.")

def FillVector(input_file, nBoards):

    print("Reading the input tree...")
    start_time = time.time()
    with uproot.open(input_file) as f:
        tree = f[f.keys()[0]]
    
    df = tree.arrays(library="pd")

    # Prepare output structure
    boardALL = [[] for _ in range(nBoards)]

    # For each board index
    for i in range(nBoards):

        # Select rows where scheda == i
        df_i = df[df["scheda"] == i]

        # Extract the 32 ADC columns
        adc_cols = [f"adc_{k}" for k in range(32)]

        # Convert each row to a list of 32 values
        boardALL[i] = df_i[adc_cols].values.tolist()

    print("End.")
    print("Run Time: ", time.time() - start_time )
    return boardALL

              
############### Fill Histograms for visualization function #############
#def FillVector(input_file, nBoards):
#    print("Reading the input tree...")
#    start_time = time.time()
#
#
#
#    boardALL = []
#    for j in range(nBoards):
#        boardALL.append([])
#    try:
#        fileADC = TFile(input_file)
#        ttree = fileADC.Get("Tree")
#        for event in ttree:
#            board=[]
#            for i in range(nBoards):
#                board.append([])
#                if  ttree.scheda == i:
#                    board[i].append(ttree.adc_0)
#                    board[i].append(ttree.adc_1)
#                    board[i].append(ttree.adc_2)
#                    board[i].append(ttree.adc_3)
#                    board[i].append(ttree.adc_4)
#                    board[i].append(ttree.adc_5)
#                    board[i].append(ttree.adc_6)
#                    board[i].append(ttree.adc_7)
#                    board[i].append(ttree.adc_8)
#                    board[i].append(ttree.adc_9)
#                    board[i].append(ttree.adc_10)
#                    board[i].append(ttree.adc_11)
#                    board[i].append(ttree.adc_12)
#                    board[i].append(ttree.adc_13)
#                    board[i].append(ttree.adc_14)
#                    board[i].append(ttree.adc_15)
#                    board[i].append(ttree.adc_16)
#                    board[i].append(ttree.adc_17)
#                    board[i].append(ttree.adc_18)
#                    board[i].append(ttree.adc_19)
#                    board[i].append(ttree.adc_20)
#                    board[i].append(ttree.adc_21)
#                    board[i].append(ttree.adc_22)
#                    board[i].append(ttree.adc_23)
#                    board[i].append(ttree.adc_24)
#                    board[i].append(ttree.adc_25)
#                    board[i].append(ttree.adc_26)
#                    board[i].append(ttree.adc_27)
#                    board[i].append(ttree.adc_28)
#                    board[i].append(ttree.adc_29)
#                    board[i].append(ttree.adc_30)
#                    board[i].append(ttree.adc_31)
#                    boardALL[i].append(board[i])
#        print("End.")
#        print("Run Time: ", start_time - time.time())
#        return boardALL
#    except ValueError:
#        logging.error(f"File {input_file} could not be found or read.")
#        return None
   
###########################################################################################

AllRuns = []

################################### Fill Arrays  ###########################################

boardALL = FillVector(inputfile, nBoards)
boardT = []
for nBoard in range(nBoards):
    boardT.append(np.array(boardALL[nBoard]).transpose())
AllRuns.append(boardT)
print("LEN(boardALL):", len(boardALL))

for b in range(nBoards):
    print(f"Board {b}: entries = {len(boardALL[b])}")
del boardALL
del boardT



OnePhes = []
PedValues = []




for board in range(nBoards):
    print('Board: ',board)
    OnePhes_singleBoard = []
    PedValues_singleBoard = []
    for i in range(0,8):
        for j in range(0,4):

            OnePhes_channel = []
            PedValues_channel = []
            for r in  range(len(AllRuns)):
                ################### Peacks searching ###########################
                histo = TH1F("Ped_run_"+run+"_board_"+str(board)+"_ch_"+str(4*i+j),"PED distribution",300,1450,1750)
                histo2 = TH1F("Ped_run_"+run+"_board_"+str(board)+"_ch_"+str(4*i+j)+"_logscale","PED distribution",300,1450,1750)
                #### Using log scale to enanhance peacks 
                #print(f"Run={run}, board={board}, channel={4*i+j}")
                #print(f"Shape of AllRuns[run][board]: {np.shape(AllRuns[run][board])}")

                ################## Histograms filling #####################################
                for index in range(len(AllRuns[r][board][4*i+j])):
                    histo.Fill(int(AllRuns[r][board][4*i+j][index]))

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

for nBoard, filename in enumerate(output_list):
    file=open(filename,"w")
    file.write("ch \t ped \t 1pe \n")
    for ch in range(nChannels):
        for r in range(len(AllRuns)):
            if  OnePhes[nBoard][ch][r] == "no 2nd peack":
                 file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][r]))+ "\t" + str(1000)+ "\t")
            else:
#                if int(OnePhes[nBoard][ch][r]) > 38 or int(OnePhes[nBoard][ch][r]) < 25: #nero
                if  nBoard !=5 and (int(OnePhes[nBoard][ch][r]) > 38 or int(OnePhes[nBoard][ch][r]) < 20):  

                    if ch!=0 and OnePhes[nBoard][ch-1][r] != "no 2nd peack":
                        file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][r]))+ "\t" + str(int(OnePhes[nBoard][ch-1][r]))+ "\t 1" )
                        OnePhes[nBoard][ch][r] = OnePhes[nBoard][ch-1][r]
                    else:

                        file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][r]))+ "\t" + str(28)+ "\t 0")
                        OnePhes[nBoard][ch][r] = 30
                elif nBoard==5 and (int(OnePhes[nBoard][ch][r]) > 28 or int(OnePhes[nBoard][ch][r]) < 10):
                    if ch!=0 and OnePhes[nBoard][ch-1][r] != "no 2nd peack":
                        file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][r]))+ "\t" + str(int(OnePhes[nBoard][ch-1][r]))+ "\t 1")
                        OnePhes[nBoard][ch][r] = OnePhes[nBoard][ch-1][r]
                    else:
                        file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][r]))+ "\t" + str(18)+ "\t")
                        OnePhes[nBoard][ch][r] = 18
                else:
                    file.write(str(ch)+"\t"+str(int(PedValues[nBoard][ch][r]))+ "\t" + str(int(OnePhes[nBoard][ch][r]))+ "\t 0")
           
        file.write("\n")

