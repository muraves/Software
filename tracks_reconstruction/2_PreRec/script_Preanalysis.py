import sys
import subprocess

#parseredPATH  = '/media/muraves2/CILINDRO/PARSERED/PUNTO_9/'
#parseredPATH  ='/media/muraves3/CILINDRO/IAEA/PARSERED/WP_100Hz/'
#parseredPATH  ='/media/muraves3/CILINDRO/IAEA/FREESKY_NUC/'
#parseredPATH  ='/media/muraves3/MURAY/ACQtest/PARSERED/'
parseredPATH  ='/media/muraves3/MURAY/ACQtest/PARSERED/CATFILES/'
runIn = int(sys.argv[1])
runEnd = int(sys.argv[2])
runIn = int(sys.argv[1])
runEnd = int(sys.argv[2])

for  run in range(runIn,runEnd):
    print('Preanalysis run ',run )
    subprocess.call(['python3', 'MakePedestalTree.py','-data', parseredPATH+'ADC_run'+str(run)+'.txt', '--run',str(run),'-type','ADC'])
    subprocess.call(['python3', 'MakePedestalTree.py', '-data', parseredPATH+'PIEDISTALLI_run'+str(run)+'.txt', '--run',str(run),'-type','PIEDISTALLI'])
