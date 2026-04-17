#ifndef CLUSTERLIST_H
#define CLUSTERLIST_H

#include <cstdint>
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

struct DeterministicSmearingRNG {
  uint32_t state;
  explicit DeterministicSmearingRNG(uint32_t seed) : state(seed != 0 ? seed : 0x6D2B79F5u) {}
  uint32_t next_u32();
  int uniform_int(int low, int high);
};

ClusterCollection CreateClusterList(vector <double> Deposits, const double EnergyThreshold_clusterStrip, const double EnergyThreshold_singleStrip, double AdStripsThEnergy_singleStripCl, double Texp1,double Texp2,vector<double> TriggerMask1, vector<double> TriggerMask2, DeterministicSmearingRNG* smearing_rng = nullptr);
double ClusterPosition(vector <double> stripDeposits, vector <double> stripPos);
double ClusterEnergy(vector <double> stripDeposits);
vector<int> SortIndices(vector<double> ReferenceVector);

#endif
