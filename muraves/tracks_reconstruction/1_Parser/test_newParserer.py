import tempfile
import logging
def parser_new_AI(fileoutp, eventsTot, run, subrun, numEVT, numSk, color):
    eventsTot = int(eventsTot)
    run = int(run) - 1
    subrun = int(subrun) - 1

    triggerTot = subrun * int(numEVT) + run * eventsTot

    with open(fileoutp, 'r') as inputF:
        lines = inputF.readlines()
        linecounter = len(lines)

    if linecounter <= 2:
        return 1, None

    rr = lines[160000].split('\t')
    if rr[0] == '15' and linecounter > 160002:
        lines = lines[:160001] + lines[linecounter - 1:]

    CK = 0
    if color == 'NERO':
        condition = True
    elif color in ['ROSSO', 'BLU']:
        condition = (linecounter - 2) % int(numSk) == 0

    if not condition:
        print("STATUS : Skip File")
        return 1, None

    with tempfile.NamedTemporaryFile(mode='w+', dir="/tmp", delete=True) as temp_file:
        temp_file.writelines(lines)
        temp_file.seek(0)
        temp_file.readline()  # skip header line

        p = [''] * (int(numSk) * 40)
        expected_triggers = (linecounter - 2) // int(numSk)

        with tempfile.NamedTemporaryFile(mode='w+', dir="/tmp", delete=False) as temp_outputfile:
            offset = 0
            trigger = 0

            for s in temp_file:
                r = s.split('\t')
                h = int('0x' + r[1][2:], 16)
                p[0 + 39 * offset] = str(h)
                p[1 + 39 * offset] = r[0]
                h = int('0x' + r[2], 16)
                p[2 + 39 * offset] = str(h)

                for i in range(3, 34):
                    h = int('0x' + r[i][1 if i <= 17 else 2:], 16)
                    p[i + 39 * offset] = str(h)

                p[34 + 39 * offset] = r[40].replace('', '')
                h = int('0x' + r[36], 16)
                p[35 + 39 * offset] = str(h)
                h = int('0x' + r[37], 16)
                p[36 + 39 * offset] = str(h)
                h = int('0x' + r[38][1:], 16)
                p[37 + 39 * offset] = str(h)

                h1 = int('0x' + r[34], 16)
                h2 = int('0x' + r[35], 16)
                w1 = '{0:b}'.format(h1)
                w2 = '{0:b}'.format(h2)
                wh1 = '0' * (16 - len(w1))
                wh2 = '0' * (16 - len(w2))
                w1 = wh1 + w1
                w2 = wh2 + w2
                tm = '_' + '_'.join([str(31 - i) for i in range(16) if w1[i] == '1']) + '_' + '_'.join([str(15 - i) for i in range(16) if w2[i] == '1'])

                p[38 + 39 * offset] = tm

                if offset < int(numSk) - 1:
                    offset += 1
                else:
                    temp_outputfile.write(str(triggerTot) + '\t' + '\t'.join(p[:int(numSk) * 39]) + '')
                    offset = 0
                    trigger += 1
                    triggerTot += 1

                if trigger >= expected_triggers:
                    break

    return CK, temp_outputfile.name



def parser_new(fileoutp, eventsTot, run, subrun, numEVT, numSk, color):
    eventsTot = int(eventsTot)
    run = int(run) - 1
    subrun = int(subrun) - 1
    
    
    
    #eventsTot = int(infoCounter[1].replace('evts', ''))

    #run = int(infoCounter[2].replace('run', '')) - 1

    #subrun = int(infoCounter[3].replace('sr', '')) - 1

    

    triggerTot = 0 + subrun*int(numEVT) + run*eventsTot
    #brokenF = open('BROKENFILELIST.txt', 'a')

    for ii in range (0,1):
        #fileoutp = sys.argv[1]
        inputF = open(fileoutp, 'r')
        s = inputF.readline()
        linecounter = 0
        CK = 0
        rr = []
        while s:
            s = inputF.readline()
            linecounter = linecounter + 1
        inputF.close()
        rr = s.split('\t')
        if (len(rr)>1) or (len(rr)==0) :
            CK = 1
        else :
            CK = 0
        logging.debug("\n-----" + str(linecounter) + "-----\n")
        lines = open(fileoutp, 'r').readlines()
        rr = lines[160000].split('\t')
        if (rr[0] == '15') :
            if ((linecounter-2) > 160000):
                for i in range(160001, linecounter-1):
                    del lines[160001]
                open(fileoutp, 'w').writelines(lines)
        else :
            CK = 1
        #The following line was commented in the parsing of the NERO, why?? This is the only difference between the three colors.
        #if (CK == 0) and  ((linecounter-2)%int(numSk) == 0) :
        #import pdb; pdb.set_trace()
        if color=='NERO':
            condition = (CK == 0)
        elif color == 'ROSSO' or color == 'BLU' :
            condition = (CK == 0) and  ((linecounter-2)%int(numSk) == 0)

        if condition == True:
            linecounter =160002
            inputF = open(fileoutp, 'r')
            ss = inputF.readlines()
            inputF.close()
            i = 1
            while (i < linecounter-1):
                tss_chk = 0
                rr = ss[i].split('\t')
                for j in range(1,int(numSk)) :
                    if (rr[40] in ss[i+j]) :
                        tss_chk = tss_chk + 1
                if (tss_chk == int(numSk)-1) :
                    i = i + int(numSk)
                else :
                    for j in range(i+tss_chk+1, linecounter) :
                        ss[j-tss_chk-1] = ss[j]
                    linecounter = linecounter - tss_chk - 1
                    if not('2a' in rr[0]) :
                        i = i + int(numSk)
                    else :
                        temp_even = ['','','','','','','','','','','']
                        temp_odd = ['','','','','','','','','','','']
                        for j in range(2, 2*int(numSk), 2):
                            temp_even[int((j-2)/2)] = ss[i+j-1]
                            temp_odd[int((j-2)/2)] = ss[i+j]
                        for j in range(0, int(numSk)-1):
                            ss[i+j+1] = temp_odd[j]
                        for j in range(0,int(numSk)-1):
                            ss[i+j+int(numSk)] = temp_even[j]
                        i = i + int(numSk)*2
            #import pdb; pdb.set_trace()
            with tempfile.NamedTemporaryFile(mode='w+', dir="/tmp", delete=True) as temp_file:
                temp_file.writelines(ss[:linecounter])
                temp_file.seek(0)
                temp_file.readline()  # skip header line
                #import pdb; pdb.set_trace()
            #inputF = open(fileoutp, 'w')
            #for i in range(0, linecounter):
            #    inputF.write(ss[i])
            #inputF.close()

            #mod = fileoutp.replace('slave','mod')
            #mod = sys.argv[2]
            #inputF = open(fileoutp, 'r')
                
                #print(f'Processing file: {mod}')
                offset = 0
                trigger = 0
                # s = inputF.readline()
                p=['']* (int(numSk) * 40)
                #for i in range(int(numSk)*40):
                #    p.append('')
                expected_triggers = (linecounter - 2) // int(numSk)
                #print(f'Reading timestamp to skip', temp_file.readline())
                with tempfile.NamedTemporaryFile(mode='w+', dir="/tmp", delete=False) as temp_outputfile:
                    for s in temp_file:
                        r = s.split('\t')
                        #import pdb; pdb.set_trace()
                        # --- parsing / conversion logic ---
                        h = int('0x'+r[1][2:], 16)

                        p[0+39*offset] = str(h)
                        p[1+39*offset] = r[0]                   
                        h = int('0x'+r[2], 16)
                        p[2+39*offset] = str(h)
                        for i in range (3, 34):
                            if (i <= 17):
                                h = int('0x'+r[i][1:], 16)
                                p[i+39*offset] = str(h)
                            else :
                                h = int('0x'+r[i][2:], 16)
                                p[i+39*offset] = str(h)

                        p[34+39*offset] = r[40].replace('\n', '')
                        h = int('0x'+r[36], 16)
                        p[35+39*offset] = str(h)
                        h = int('0x'+r[37], 16)
                        p[36+39*offset] = str(h)
                        h = int('0x'+r[38][1:], 16)
                        p[37+39*offset] = str(h)
                        h1 = int('0x'+r[34], 16)
                        h2 = int('0x'+r[35], 16)
                        w1 = '{0:b}'.format(h1)
                        w2 = '{0:b}'.format(h2)
                        wh1 = ''
                        wh2 = ''

                        for i in range(16-len(w1)):
                            wh1 = wh1 + '0'
                        for i in range(16-len(w2)):
                            wh2 = wh2 + '0'
                        w1 = wh1 + w1
                        w2 = wh2 + w2
                        tm = '_'
                        for i in range(len(w1)):
                            if(w1[i] == '1'):
                                tm = tm + str(31 - i) + '_'
                        for i in range(len(w2)):
                            if(w2[i] == '1'):
                                tm = tm + str(15 - i) + '_'

                        p[38+39*offset] = tm

                        if (offset < int(numSk)-1) :
                            offset += 1
                        else :
                            temp_outputfile.write(str(triggerTot) + '\t')
                            temp_outputfile.write('\t'.join(p[:int(numSk)*39]) + '\n')
                            offset = 0
                            trigger += 1
                            triggerTot += 1

                        
                        if trigger >= expected_triggers:
                            break
                    #if (trigger==(linecounter-2)/int(numSk)) :
                    #    s = inputF.readline()
                    #    s = inputF.readline()
                #import pdb; pdb.set_trace()
                #inputF.close()
                #outputF.close()

        else :
            print("\n STATUS : Skip File\n")
            
            #brokenF.write(fileoutp + '\n')
    return CK, temp_outputfile.name


import time
from pathlib import Path
import muraves_lib

# Benchmarking
fileoutp = '/data/RAW_GZ/ROSSO/slaveData_evts40000_run2546_sr1.gz'
eventsTot = 40000
run = 2546
subrun = 1
numEVT = 10000
numSk = 16
color = 'ROSSO'

decompressed_filename, error = muraves_lib.file_handler.decompress(fileoutp)
print("File decompressed successfully:", decompressed_filename, error)
# Run original function
start_time = time.time()
ctrl_original, tmp_filename_original = parser_new(decompressed_filename, eventsTot, run, subrun, numEVT, numSk, color)
original_time = time.time() - start_time

# Run optimized function
start_time = time.time()
ctrl_optimized, tmp_filename_optimized = parser_new_AI(decompressed_filename, eventsTot, run, subrun, numEVT, numSk, color)
optimized_time = time.time() - start_time

print(f"Original time: {original_time} seconds")
print(f"Optimized time: {optimized_time} seconds")

# Check for differences in the content of tmp_filename
def compare_files(file1, file2):
    with open(file1, 'r') as f1, open(file2, 'r') as f2:
        lines1 = f1.readlines()
        lines2 = f2.readlines()

    if lines1 != lines2:
        print("Files are different:")
        for i, (line1, line2) in enumerate(zip(lines1, lines2)):
            if line1 != line2:
                print(f"Line {i+1} differs:")
                print(f"Original: {line1.strip()}")
                print(f"Optimized: {line2.strip()}")
    else:
        print("Files are identical.")

#compare_files(tmp_filename_original, tmp_filename_optimized)


