import sys
import os
import subprocess
import time

skList = []
numEVT = sys.argv[3]
numSk = sys.argv[4]

infoCounter = sys.argv[1].split('_')
eventsTot = int(infoCounter[1].replace('evts', ''))
run = int(infoCounter[2].replace('run', '')) - 1
subrun = int(infoCounter[3].replace('sr', '')) - 1
triggerTot = 0 + subrun*int(numEVT) + run*eventsTot
brokenF = open('BROKENFILELIST.txt', 'a')

for ii in range (0,1):
	fileoutp = sys.argv[1]
	inputF = open(fileoutp, 'r')
	s = inputF.readline()
	linecounter = 0
	CK = 0
	rr = []
	while s:
		s = inputF.readline()
		linecounter = linecounter + 1
	rr = s.split('\t')
	if (len(rr)>1) or (len(rr)==0) :
		CK = 1
	else :
		CK = 0
	inputF.close()
	print("\n-----" + str(linecounter) + "-----\n")
	if (CK == 0) and  ((linecounter-2)%int(numSk) == 0) :
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

		inputF = open(fileoutp, 'w')
		for i in range(0, linecounter):
			inputF.write(ss[i])
		inputF.close()

		#mod = fileoutp.replace('slave','mod')
		mod = sys.argv[2]
		inputF = open(fileoutp, 'r')
		outputF = open(mod, 'a')
		offset = 0
		trigger = 0
		s = inputF.readline()
		p=['']
		for i in range(int(numSk)*40):
			p.append('')

		while s:
			s = inputF.readline()
			r = s.split('\t')
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
				offset = offset + 1
			else :
				outputF.write(str(triggerTot) + '\t')
				for i in range(int(numSk)*39-1):
					outputF.write(p[i] + '\t')
				outputF.write(p[int(numSk)*39-1] + '\n')
				offset = 0
				trigger = trigger + 1
				triggerTot = triggerTot + 1

			if (trigger==(linecounter-2)/int(numSk)) :
				s = inputF.readline()
				s = inputF.readline()

		inputF.close()
		outputF.close()

	else :
		print("\n STATUS : Skip File\n")
		brokenF.write(fileoutp + '\n')

brokenF.close()
