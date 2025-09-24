#include <vector>
#include <numeric>
#include <stdio.h>
#include <string>
#include <sstream>
#include <stdlib.h>
#include <iostream>
#include <fstream>
#include <math.h>
#include <time.h>
#include <ctime>
#include "TH1.h"
#include "TTree.h"
#include "TFile.h"
#include "TPad.h"
#include "TSpectrum.h"
#include "TCanvas.h"
#include "TPolyMarker.h"
#include <Python.h>
#include "pyhelper.hpp"
#include "ROOT/TDataFrame.hxx"
using namespace std;

int main( int argc,  char* argv[]) {
  
 // Measure the total time of the code 
  clock_t start = clock();
  char color[6];
  strcpy(color,argv[1]);
  cout << "Detector: "<< color;
  int run;
  stringstream run_ss(argv[2]);
  run_ss >> run;
  char run_string[10];
  sprintf(run_string, "%d", run);
  cout << "\t run: " << run_string << endl;
  
  // NAME OF THE PED FILE TO BE OPENED /////
  char PED_File_name[1000];
  strcpy(PED_File_name,"/media/muraves/DATA/");
  strncat(PED_File_name,color,6);
  strncat(PED_File_name,"/PreANALYZED/PIEDISTALLI_run",30);
  //strncat(PED_File_name,"/PreANALYZED/ADC_run",30);
  strncat(PED_File_name,run_string,10);

  // NAME OF THE FILE WHERE TO WRITE ONEPHEs
  char Pedestal_File[1000];
  strcpy(Pedestal_File,"/home/muraves/Desktop/MURAVES/ANALYSIS/ReconstructionTracks_from3to4/config/ped");
  strncat(Pedestal_File,color,6);
 strncat(Pedestal_File,"/ped_run",8);
  strncat(Pedestal_File,run_string,10);
  strncat(Pedestal_File,"/pedestal_",11);
  
  // USE PYTHON GLOB.GLOB TO FIND THE TAIL OF THE FILE NAME /////
  CPyInstance hInstance;
  CPyObject pName_searchFile = PyUnicode_FromString("SearchFileName");
  CPyObject Module_SearchAFile = PyImport_Import(pName_searchFile);
  CPyObject SearchFile_func = PyObject_GetAttrString(Module_SearchAFile, "Search_File");
  PyObject *PED_name_toPy = PyTuple_New(1);
  PyTuple_SetItem(PED_name_toPy, 0, PyUnicode_FromString(PED_File_name));
  CPyObject CompleteFileName;
  CompleteFileName =PyObject_CallObject(SearchFile_func,PED_name_toPy);
  Py_ssize_t size;
  const char *Complete_ADCfile_name = PyUnicode_AsUTF8AndSize(CompleteFileName.getObject(), &size); // ----> COMPLETE NAME 
  cout << Complete_ADCfile_name << endl;
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  TFile *fileROOT = new TFile(Complete_ADCfile_name);
  
  if(fileROOT->IsOpen() && fileROOT->GetListOfKeys()->Contains("PEDtree") ) {
  ///////////////////////////SLOW CONTROL INFORMATIONS /////////////////////////////////////
  char SlowControlFileName[100];
  strcpy(SlowControlFileName,"/media/mCdata/VESUVIO/datiVesuvio/");
  strncat(SlowControlFileName,color,5);
  strncat(SlowControlFileName,"/SLOWCONTROL_",30);
  strncat(SlowControlFileName,color,5);
  strncat(SlowControlFileName,".txt",5);
 
  ifstream SlowControl(SlowControlFileName);
  string slow_line;
  char c_slow_line[1000]; 
  char *char_run, *char_tr, *char_wp, *char_temperature;
  double SC_run,SC_tr,SC_temperature,SC_wp;
  int SC_run_int;
  char *slow_ptr;
  vector<char*>  SLOW_DATAdata_splitted;

  ////////////////////////// READ SLOW CONTROL LINE /////////////////////////////////////////
  while (getline(SlowControl, slow_line))
    {
      SLOW_DATAdata_splitted.clear();
      memset(c_slow_line, 0, sizeof slow_line);
      strcpy (c_slow_line, slow_line.c_str());
      slow_ptr = strtok(c_slow_line,"\t");
      while(slow_ptr!=NULL) {
	
	  SLOW_DATAdata_splitted.push_back(slow_ptr);
	  slow_ptr = strtok(NULL,"\t");
	}
	SC_run = strtod(SLOW_DATAdata_splitted.at(0),&char_run); 
	SC_run_int = (int) SC_run;
	//////////// WHEN THE CORRESPONDING RUN IS FOUND //////////////////////
	if(SC_run == run) {
	SC_tr = (double) strtod(SLOW_DATAdata_splitted.at(43),&char_tr); 
	SC_temperature = (double) strtod(SLOW_DATAdata_splitted.at(3),&char_temperature); 
	SC_wp = strtod(SLOW_DATAdata_splitted.at(5),&char_wp);

	  break;
	}
      }
  
  ////////////////////////////////////////////////////////////////////////////////////////////////
 
  TTree *tree = (TTree*) fileROOT->Get("PEDtree");
  
  ///////////PREPARING THE OUTPUT TREE//////////
  char OutputTreeFileName[100];
  strcpy(OutputTreeFileName,"/media/muraves2/MURAVES_DATA/");
  strncat(OutputTreeFileName,color,6);
  strncat(OutputTreeFileName,"/PEDanalysis/TREES/PEDdata_",30);
  strncat(OutputTreeFileName,color,6);
  strncat(OutputTreeFileName,"_run",5);
  strncat(OutputTreeFileName,run_string,10);
  strncat(OutputTreeFileName,".root",6);
  TFile *tree_file = new TFile(OutputTreeFileName,"recreate");

  TTree *OnePheTree = new TTree("OnePheTree","");
  OnePheTree->SetEntries(1);

  char CanvasFileName[100];
  strcpy(CanvasFileName,"/media/muraves2/MURAVES_DATA/");
  strncat(CanvasFileName,color,6);
  strncat(CanvasFileName,"/PEDanalysis/CANVAS/SpectrumANDpeaks_",50);
  strncat(CanvasFileName,color,6);
  strncat(CanvasFileName,"_run",5);
  strncat(CanvasFileName,run_string,10);
  strncat(CanvasFileName,".root",6);
  
  TFile *Canvasfile = new TFile(CanvasFileName,"recreate");
  
  ////////////// SAVE SLOW CONTROL INFO IN THE TREE ///////////////////
  TBranch *b_WP = OnePheTree->Branch("WorkingPoint",&SC_wp);
  TBranch *b_TR = OnePheTree->Branch("TriggerRate",&SC_tr);
  TBranch *b_Temp = OnePheTree->Branch("Temperature",&SC_temperature);
  TBranch *b_Run = OnePheTree->Branch("Run",&run);
  
  b_WP->Fill();
  b_TR->Fill();
  b_Temp->Fill();
  b_Run->Fill();
  /////////////////////////////////////////////////////////////////////
  int nChannels = 32;
  int nBoards = 16;
  int nbins = 150;
  Double_t xmin = 1450;
  Double_t xmax =1750;
  Int_t i,nfound,bin,onePhe,fNPeaks = 0,nPeaksReal=0;
  Double_t a;
  vector<int> indices(100);
  vector<int> indicestoberemoved;
  vector<int> OnePheVector;
  vector<double> PedestalVector;
  for(int b=0; b<nBoards; b++) {

    // OPEN FILE TO WRITE THE OnePhe
    char BoardPedFile[1000];
    char board_string[10];
    sprintf(board_string, "%d.cfg", b);
    strcpy(BoardPedFile,Pedestal_File);
    strncat(BoardPedFile,board_string,8);
    cout << "Writing file " << BoardPedFile << endl;
    ofstream fileTxt;
   
    fileTxt.open(BoardPedFile);
    fileTxt << "ch" << "\t" << "Pedestal" << "\t" << "OnePhe" << endl;      
    OnePheVector.clear();
    PedestalVector.clear();
    TCanvas *c = new TCanvas();

    c->SetWindowSize(1400,900);
    c->SetCanvasSize(1400,900);
    c->SetName(Form("Board_%d",b));
    c->Divide(4,8);
    //////////////////////////////////////////////////////////////////////////////////
    
    for(int ch=0; ch<nChannels; ch++) {

      c->cd(ch+1);
      // CREATE THE NAME OF THE BRANCH TO PLOT // 
      char ch_char[3];
      sprintf(ch_char, "%d", ch);
      char BranchName[10];
      char BranchName_noh[10];
      strcpy(BranchName,"adc");
      strncat(BranchName,ch_char,3);
      strcpy(BranchName_noh,BranchName);
      strncat(BranchName,">>h",3);
      ///////////////////////////////////////////
      // CREATE THE CONDITION (scheda == b)
      char b_char[3];
      sprintf(b_char, "%d", b); 
      char Condition[20];
      strcpy(Condition,"scheda==");
      strncat(Condition,b_char,3);
      ////////////////////////////////////////

      //// VARIABLES NEEDED TO FIND PEAKS WITH TSPECTRUM ///
      Double_t *xpeaks;
      Double_t fPositionX[100];
      Double_t fPositionY[100];

      ////////////////////////////////////////////////////
      ROOT::TDataFrame d("PEDtree", Complete_ADCfile_name);
      auto max = d.Filter(Condition).Max(BranchName_noh);
      auto min = d.Filter(Condition).Min(BranchName_noh);
      xmin = *min;
      xmax= *max;
      nbins = (Int_t) (xmax-xmin)/2;

      TH1F *h = new TH1F("h","",nbins,xmin,xmax);
      TH1F *h2 = new TH1F("h_log","",nbins,xmin,xmax);
      h2->SetName(Form("HLog10_Board_%d_Channel%d",b,ch));      
      /// DRAW THE SPECTRUM AND SET LOG SCALE///
      tree->Draw(BranchName,Condition);
      h->SetName(Form("H_Board_%d_Channel%d",b,ch));    
      //FILL LOG 10 SCALE HISTOGRAM //
      for(int bin=0; bin<h->GetXaxis()->GetNbins(); bin++) {  
	if(h->GetBinContent(bin)>10) {
	  h2->SetBinContent(bin,log10(h->GetBinContent(bin)));

	}
      }
      
      ///////////////////////////////////////
      Double_t source[nbins], dest[nbins];
      ////// SEARCH FOR PEAKS IN THE LOG10 HISTOGRAM /////
      for(i = 0; i < nbins; i++) source[i]=h2->GetBinContent(i + 1);

      TSpectrum *s = new TSpectrum();      
      nfound = s->SearchHighRes(source, dest, nbins, 1, 2, kTRUE, 3, kTRUE, 3);
      xpeaks= s->GetPositionX();
      /////////////////////////////////////////////////////////////
      ///// GET THE POSITIONS OF THE PEAKS /////
      for (i = 0; i < nfound; i++) {
	a=xpeaks[i];
	bin = 1 + Int_t(a + 0.5);
	fPositionX[i] = h2->GetBinCenter(bin);
	fPositionY[i] = h2->GetBinContent(bin);
      }
      ////////////////////////////////////////////
      
      ///// SORT PEAKS IN DECREASING ORDER /////
      indices.clear();
      if(nfound>0) {
      indices.resize(nfound);
      iota(indices.begin(), indices.end(), 0);
      sort(indices.begin(), indices.end(),
           [&](int A, int B) -> bool {
	     return fPositionY[A] > fPositionY[B];
	   });
      }
      //////////////////////////////////////////////
      /// REMOVE PEAKS BEFORE THE PEDESTAL ///////
      nPeaksReal=0;
      indicestoberemoved.clear();
      for(int k=0; k<nfound;k++) {
	if(fPositionX[indices.at(k)]< fPositionX[indices.at(0)]) {
	  indicestoberemoved.push_back(k);
	}else nPeaksReal++;
      }
      for(int j=0;j<indicestoberemoved.size();j++){
	indices.erase(indices.begin()+indicestoberemoved.at(j)-j);
      }
      ////////////////////////////////////////////////////////
      
	/// CALCULATE THE 1PHE VALUE ///////
	if(nPeaksReal>1) {
	  onePhe = fPositionX[indices.at(1)] - fPositionX[indices.at(0)];
      }
	else onePhe = 1000;

	if(onePhe<20 && nPeaksReal>2 && (color!= "ROSSO" && b!=5)) {
	//if(onePhe<20 && nPeaksReal>2) {
	  onePhe = fPositionX[indices.at(2)] - fPositionX[indices.at(0)];
	}
	
	if(onePhe> 40) {
	  if(ch>0) onePhe = OnePheVector.at(ch-1);
	  else onePhe = 40;
	}
	if(nPeaksReal>0) fileTxt << ch << "\t" << fPositionX[indices.at(0)] << "\t" << onePhe << endl;
	else  fileTxt << ch << "\t" << 0 << "\t" << onePhe << endl;
	OnePheVector.push_back(onePhe);
	if(nPeaksReal>0)  PedestalVector.push_back(fPositionX[indices.at(0)]);
	else PedestalVector.push_back(0);
	//////////////////////////////////////////////
      ////// DRAWING THE PEAKS /////////
	if(nfound==0)continue;
	TPolyMarker * pm = (TPolyMarker*)h2->GetListOfFunctions()->FindObject("TPolyMarker");
      if (pm) {
	h2->GetListOfFunctions()->Remove(pm);
	delete pm;
      }
      pm = new TPolyMarker(nfound, fPositionX, fPositionY);
      h2->GetListOfFunctions()->Add(pm);
      pm->SetMarkerStyle(23);
      pm->SetMarkerColor(kRed);
      pm->SetMarkerSize(0.8);
      h2->GetXaxis()->SetLabelSize(0.08);
      h2->GetYaxis()->SetLabelSize(0.08);
      h2->GetXaxis()->SetTitleSize(0.06);
      h2->GetYaxis()->SetTitleSize(0.06);
      h2->GetYaxis()->SetTitleOffset(0.5);
      h2->GetXaxis()->SetTitleOffset(0.3);
      h2->GetXaxis()->SetTitle("ADC counts");
      h2->GetYaxis()->SetTitle("Log10 (entries)");
      h2->Draw();
     
      //////////////////////////////////////////////
    }
    Canvasfile->cd();
    c->Write();
    TBranch *b_OnePhe = OnePheTree->Branch(Form("OnePhe_Board%d",b),&OnePheVector);
    TBranch *b_Pedestal = OnePheTree->Branch(Form("Pedestal_Board%d",b),&PedestalVector);
    b_Pedestal->Fill();
    b_OnePhe->Fill(); 
  }
  tree_file->cd();
  OnePheTree->Write();
  fileROOT->Close();
  Canvasfile->Close();
   //FINAL TIME OF EXECUTION --> PRINT
  clock_t end =clock();
  double elapsed = (double) (end - start)/CLOCKS_PER_SEC;
  printf("\nEXECUTION TIME: %.1f seconds \n", (double)elapsed);
  }else cout << "Searched file  does not exist" << endl;
}
