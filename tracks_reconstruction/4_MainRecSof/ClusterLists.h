#ifndef CLUSTERLIST_H
#define CLUSTERLIST_H

#include <vector>
using namespace std;

struct ClusterCollection {
  vector<double> ClustersEnergy;
  vector<double> ClustersPositions;
  vector<vector<double>> StripsEnergy;
  vector<vector<double>> StripsPositions;
  vector<vector<double>> StripsID;
  vector<double> TimeExpansions;
  vector <int> ClustersSize;
};

ClusterCollection CreateClusterList(vector <double> Deposits, const double EnergyThreshold_clusterStrip, const double EnergyThreshold_singleStrip, double AdStripsThEnergy_singleStripCl, double Texp1,double Texp2,vector<double> TriggerMask1, vector<double> TriggerMask2);
double ClusterPosition(vector <double> stripDeposits, vector <double> stripPos);
double ClusterEnergy(vector <double> stripDeposits);
vector<int> SortIndices(vector<double> ReferenceVector);

#endif
