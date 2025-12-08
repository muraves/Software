#ifndef READEVENT_H
#define READEVENT_H

#include <vector>

using namespace std;

struct struct_Event {

  vector<vector<double>> boards;
  vector<vector<double>> TrMask_channels;
  vector<vector<double>> TrMask_strips;
  vector<int> TrMask_size;
  vector<double> timeExp;
  double timeStamp;
};
  
struct_Event ReadEvent(char* ADCline, vector<int> stripIndices);

    
#endif
