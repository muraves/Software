
#include "ReadEvent.h"
#include <algorithm>
#include <iostream>
#include <cstring>
#include <vector>

using namespace std;

struct_Event ReadEvent(char* ADCline, vector<int> stripIndices) {

  
  // SPLIT THE ADC LINE IN ITS ELEMENTS 
  char *ptr;
  vector<char*> ADCdata_splitted; 
  ptr = strtok(ADCline,"\t");
  while(ptr!=NULL) {

    ADCdata_splitted.push_back(ptr);
    ptr = strtok(NULL,"\t");
  }
  ///////////////////////////////////

  // PREPARE THE FUNCTION OUTPUT
  const int nInfoBoard = 39;
  const int nChannels = 32;
  const int nBoards = 16; 
  vector<vector<double>> boards;
  vector<double> allADC, all_timeExp, sorted_allADC;  

  // read trigger mask ////
  vector<double> TrMask_ch;
  vector<double> TrMask_strips;
  vector<vector<double>>Boards_triggerMasks_channels;
  vector<vector<double>>Boards_triggerMasks_strips;
  vector<int> TriggerMask_sizes;
  char* TrMask_char;
  vector<char*> TrMask_vectSplit;
  char* TrM_ptr;
  char *Tr_char;
  int TrMaskChannel;
  int TrMaskStrip;
  ////////////////////////////
  
  struct_Event single_event;
  char *char_timeExp;
  char *char_timestamp;
  char* char_ch;

  double timeStamp = strtod(ADCdata_splitted.at(35),&char_timestamp); //event_timeStamp


  // LOOP OVER THE BOARDS 
  for(int n=0; n<nBoards; n++) {
    double timeExp = strtod(ADCdata_splitted.at(n*nInfoBoard+37),&char_timeExp);
    all_timeExp.push_back(timeExp);
    TrMask_vectSplit.clear();
    TrMask_char = ADCdata_splitted.at(n*nInfoBoard+39);
    TrMask_strips.clear();
    TrMask_ch.clear();
    TrM_ptr = strtok(TrMask_char,"_");
    while(TrM_ptr!=NULL) {

      TrMask_vectSplit.push_back(TrM_ptr);
      TrM_ptr = strtok(NULL,"_");

    }
    for(int h=0; h<  TrMask_vectSplit.size(); h++) {
      TrMaskChannel = strtod( TrMask_vectSplit.at(h),&Tr_char);
      TrMask_ch.push_back(TrMaskChannel);
      auto it = find(stripIndices.begin(), stripIndices.end(), TrMaskChannel);
      if(it!=stripIndices.end())
	{	  
	  TrMaskStrip = it - stripIndices.begin();
	  TrMask_strips.push_back(TrMaskStrip);
	  }
      
    }
    Boards_triggerMasks_channels.push_back(TrMask_ch);
    Boards_triggerMasks_strips.push_back(TrMask_strips);
    TriggerMask_sizes.push_back(TrMask_strips.size());
    
    for(int nCh=0; nCh<nChannels; nCh++) {

      double ADC = strtod(ADCdata_splitted.at(3+n*nInfoBoard + nCh), &char_ch);
      allADC.push_back(ADC);

    }
    for(int ind=0; ind<stripIndices.size(); ind++)  {
      sorted_allADC.push_back(allADC.at(stripIndices.at(ind)));

  }
    boards.push_back(sorted_allADC);
    sorted_allADC.clear(); 
    allADC.clear();
  }
  
  single_event.TrMask_channels = Boards_triggerMasks_channels;
  single_event.TrMask_strips = Boards_triggerMasks_strips;
  single_event.TrMask_size = TriggerMask_sizes;
  single_event.boards = boards;
  single_event.timeStamp = timeStamp;
  single_event.timeExp = all_timeExp;

  return single_event;
}
   
