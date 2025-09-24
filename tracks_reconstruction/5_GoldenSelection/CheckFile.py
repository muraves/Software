from ROOT import TFile
from ROOT import TTree
import sys
import subprocess
nomefile = '/media/muraves2/MURAVES_DATA/'+sys.argv[1]+'/GOLDEN_SELECTION/Track4p_'+sys.argv[1]+'_run'+sys.argv[2]+'.root'
nometree = "Tracks4ptree"
fileROOT  = TFile(nomefile)
if fileROOT.IsOpen()==False or  fileROOT.GetListOfKeys().Contains(nometree)==False:
    subprocess.run(["rm",nomefile])
    print("File ",nomefile," corrupted --> removed")
    
else:
    tree = fileROOT.Get(nometree)
    entries = tree.GetEntries() 
    if entries == 0:
        subprocess.run(["rm",nomefile])
        print("File ",nomefile," corrupted --> removed")
