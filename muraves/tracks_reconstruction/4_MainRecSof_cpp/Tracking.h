#ifndef TRACKING_H
#define TRACKING_H

#include <vector>

using namespace std;

struct TracksCollection {
  vector<double> intercepts_3p;
  vector<double> slopes_3p;
  vector<double> chiSquares_3p;
  vector<int> cluster_index_1;
  vector<int> cluster_index_2;
  vector<int> cluster_index_3;
  vector <int> Ntracks_4p;
  vector<double> position_c1;
  vector<double> position_c2;
  vector<double> position_c3;
  vector<double> residue_c1;
  vector<double> residue_c2;
  vector<double> residue_c3;
  vector<double> TrackEnergy_3p; 
  vector <int> IsInTrack_clusters1;
  vector <int> IsInTrack_clusters2;
  vector <int> IsInTrack_clusters3;
  vector <int> IsInTrack_clusters1_4p;
  vector <int> IsInTrack_clusters2_4p;
  vector <int> IsInTrack_clusters3_4p;
  vector <int> Plane4th_isIntercepted ;
  vector<vector<double>> positions_c4;
  vector<vector<double>> intercept_4p;
  vector<vector<double>> slope_4p;
  vector<vector<double>> chiSquares_4p;
  vector<vector<double>> displacement_p4;
  vector<vector<double>> cluster_indices_4;
  vector<vector<double>> residue_c1_p4;
  vector<vector<double>> residue_c2_p4;
  vector<vector<double>> residue_c3_p4;
  vector<vector<double>> residue_c4_p4;
  vector<vector<double>> TrackEnergy_4p;
  vector<vector<double>> ScatteringAngles;
  vector<double> ExpectedPosition_OnPlane4th;
  vector<int> Track_3p_to_4p_index;
  vector<double> Track_3p_ExpectedRes_p2;
  double BestEnergy;
  double BestChi;
  int BestEnergy_index;
  int BestChi_index;
  
};

TracksCollection MakeTracks(vector<double> clusters_1, vector<double> clusters_2, vector<double> clusters_3, vector<double> clusters_4, vector<double> clustersEn_1, vector<double> clustersEn_2, vector<double> clustersEn_3, vector<double> clustersEn_4, vector<double> Texp_cl1, vector<double> Texp_cl2, vector<double> Texp_cl3, vector<double> Texp_cl4,double proximity_cut, double* X_pos,double* Z_add, double sigma);

#endif
