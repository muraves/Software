#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>
#include "ClusterLists.h"
#include <random>
using namespace std;

///////// FUNCTION TO OBTAIN THE CLUSTER POSITION FROM A WEIGHTED MEAN ///////////
double ClusterPosition(vector <double> stripDeposits, vector <double> stripPos) {
  double clusterPositionNum = 0.;
  double clusterPositionDen = 0.;
  double clusterPosition, addFactor;
  for(int i=0; i<stripDeposits.size(); i++) {
    addFactor = stripDeposits.at(i)*stripPos.at(i);
    clusterPositionNum = clusterPositionNum + addFactor;
    clusterPositionDen = clusterPositionDen + stripDeposits.at(i);
  }
  clusterPosition = (double) (clusterPositionNum/clusterPositionDen);
  return clusterPosition;
}

//////// FUCTION TO CALCULATE THE ENERGY OF THE CLUSTER (SUM OF THE STRIP DEPOSITS) ///////
double ClusterEnergy(vector <double> stripDeposits) {
  double ClusterEnergy =0;
   for(int i=0; i<stripDeposits.size(); i++) {
     ClusterEnergy += stripDeposits.at(i);
       }
   return  ClusterEnergy;
}

vector<int> SortIndices(vector<double> ReferenceVector) {

  vector<int> indices(ReferenceVector.size());
  iota(indices.begin(), indices.end(), 0);
  sort(indices.begin(), indices.end(),
           [&](int A, int B) -> bool {
                return ReferenceVector[A] > ReferenceVector[B];
            });
  return indices;
}

///////////////////////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////////////////////

ClusterCollection CreateClusterList(vector <double> Deposits, const double EnergyThreshold_clusterStrip, const double EnergyThreshold_singleStrip, double AdStripsThEnergy_singleStripCl,double T_exp1,double T_exp2,vector<double>TriggerMask1, vector<double>TriggerMask2) {
  //EXTERNAL PARAMETERS  
  double MaxStripEnergy = 3000;
  double FirstStripPos = -0.528;
  double AdiacentStripsDistance = 0.0165;
  const int nStrips = 64;
  // INTERNAL OBJECTS 
  vector <double> clusterStripsDeposits;
  vector <double> clusterStripsPos;
  vector <double> clusterStripsID;
  double deposit,cluster_position,cluster_energy;
  double Texp; 
  /// OUTPUT OBJECTS
  vector <double > clusterPosition, clusterEnergy, clusterSize;
  vector <vector<double>> Clusters_StripsDeposits,Clusters_StripsPositions, Clusters_StripsID;
  //////////////////
  
  // SORTING OBJECTS ---> sort strips and clusters according to the energy (from highest to lowest) 
  vector <int> OrderedStripsIndices;
  vector <double> SortedStipsPositions;
  vector <double> SortedStipsID;
  vector <double> SortedStipsDeposits;
  vector <int> Sorted_clusterSize;
  vector <int> OrderedClustersIndices;
  vector <double> SortedClustersPositions;
  vector <double> SortedClustersEnergies;
  vector <vector<double>> Sorted_Clusters_StripsDeposits,Sorted_Clusters_StripsPositions, Sorted_Clusters_StripsID;
  vector<double> Texp_cluster;
  int minEnergyTriggerMask = 20;
  int prev_strip=-1, subs_strip;
  double strip_position, pre_strip_position, post_strip_position;
  double cluEn=0, cluPos = 0;
  int cluSize=0;
  vector <int> strip_index;
  /// LOOP OVER THE 64 SCINTILLATOR BARS ////
  bool ClusterIsOn=1; 
  for(int st=0; st<nStrips; st++) {
    deposit = Deposits.at(st);
    if(deposit < EnergyThreshold_clusterStrip)
      ClusterIsOn=0;
    else ClusterIsOn=1;
    if(deposit >MaxStripEnergy)
      ClusterIsOn=0;

    if(deposit > minEnergyTriggerMask) {
      if(st<32) {

	if(std::find(TriggerMask1.begin(),TriggerMask1.end(),st)==TriggerMask1.end()) ClusterIsOn=0 ;}
      
      else {

	if(std::find(TriggerMask2.begin(),TriggerMask2.end(),st-32)==TriggerMask2.end())
	  ClusterIsOn=0;
      }
    }
    if(st == nStrips-1)
      ClusterIsOn=0;
    //if( ((st<32 && std::find(TriggerMask1.begin(),TriggerMask1.end(),st)!=TriggerMask1.end()) || (st>31 && std::find(TriggerMask2.begin(),TriggerMask2.end(),st-32)!=TriggerMask2.end())) &&  deposit > EnergyThreshold_clusterStrip && deposit < MaxStripEnergy) {

    if(ClusterIsOn==1) { 
      strip_position = (double) (st*AdiacentStripsDistance);
      /// Strip Informations //////////////////
      clusterStripsDeposits.push_back(deposit);
      clusterStripsPos.push_back(FirstStripPos + strip_position);
      clusterStripsID.push_back(st);
      /////////////////////////////////////
      //// Cluster energy and position //// 
      cluEn=cluEn+deposit;
      cluPos = cluPos + (strip_position +FirstStripPos)*deposit;
      /////////////////////////////////////

      cluSize++;
      strip_index.push_back(st);
      
    }
    else {
      ///////////////// IF cluster size is equal to 1 --> add adjacent strips is energetic ////
	if(cluSize==1) {
	  if(cluEn>EnergyThreshold_singleStrip && cluEn < MaxStripEnergy)  {
	    if(strip_index.at(0)<nStrips-1 && Deposits.at(1+strip_index.at(0))>AdStripsThEnergy_singleStripCl && Deposits.at(1+strip_index.at(0)) < MaxStripEnergy) {
	      post_strip_position = (double) ((strip_index.at(0)+1)*AdiacentStripsDistance);
	      cluPos = cluPos+ Deposits.at(1+strip_index.at(0))*(FirstStripPos + post_strip_position);
	      cluEn+=Deposits.at(strip_index.at(0)+1);
	      cluSize++;
	      clusterStripsDeposits.push_back(Deposits.at(strip_index.at(0)+1));
	      clusterStripsPos.push_back(FirstStripPos + post_strip_position);
	      clusterStripsID.push_back(strip_index.at(0)+1);
	    }
	    
	    if(strip_index.at(0)>0 && Deposits.at(strip_index.at(0)-1)>AdStripsThEnergy_singleStripCl  && Deposits.at(strip_index.at(0)-1)< MaxStripEnergy) {
	      pre_strip_position = (double) ((strip_index.at(0)-1)*AdiacentStripsDistance);
	      cluPos = cluPos+ Deposits.at(strip_index.at(0)-1)*(FirstStripPos + pre_strip_position);
	      cluEn+=Deposits.at(strip_index.at(0)-1);
	      clusterStripsDeposits.push_back(Deposits.at(strip_index.at(0)-1));
	      clusterStripsPos.push_back(FirstStripPos + pre_strip_position);
	      clusterStripsID.push_back(strip_index.at(0)-1);
	      cluSize++;
	    }

	  }
	  else {
	    cluPos=0;
	    cluEn=0;
	    cluSize=0;
	  }

	}
	if(cluSize>0) {
	  cluster_position = (double) cluPos/cluEn;
	  /////// Generate a random position within [-Strip width, + Strip_width] for those clusters with one strip
	  if(cluSize==1) {
	    const int range_from  = - (int) 1000*AdiacentStripsDistance/2;
	    const int range_to    = (int) 1000*AdiacentStripsDistance/2;
	    random_device                  rand_dev;
	    mt19937                        generator(rand_dev());
	    uniform_int_distribution<int>  distr(range_from, range_to);	   
	    cluster_position = cluster_position + (double) (distr(generator))/1000.;
	  }
	  cluster_energy = cluEn;
	  clusterPosition.push_back(cluster_position);
	  clusterEnergy.push_back(cluster_energy);
	  clusterSize.push_back(cluSize);
	  
	  // ORDER STRIPS ACCORDING TO INCREASING DEPOSITS ////////////////////////////////
	  OrderedStripsIndices.clear();
	  OrderedStripsIndices = SortIndices(clusterStripsDeposits);
	  
	  for(int ind=0; ind<cluSize; ind++) {
	    SortedStipsID.push_back(clusterStripsID.at(OrderedStripsIndices.at(ind)));
	    SortedStipsPositions.push_back(clusterStripsPos.at(OrderedStripsIndices.at(ind)) );
	    SortedStipsDeposits.push_back(clusterStripsDeposits.at(OrderedStripsIndices.at(ind)) );
	    
	  }
	  Clusters_StripsDeposits.push_back(SortedStipsDeposits);
	  Clusters_StripsPositions.push_back(SortedStipsPositions);
	  Clusters_StripsID.push_back(SortedStipsID);
	  ////////////////////////////////////////////////////////////////////////////
	  
    ////////////////////////////////
	}
	strip_index.clear();
	clusterStripsDeposits.clear();
	clusterStripsPos.clear();
	SortedStipsDeposits.clear();
	SortedStipsPositions.clear();
	SortedStipsID.clear();
	cluEn=0;
	cluPos=0;
	cluSize=0;	
    }
    
  }
  // ORDER CLUSTERS ACCORDING TO INCREASING ENERGY
  OrderedClustersIndices.clear();
  OrderedClustersIndices = SortIndices(clusterEnergy);

  for(int ind=0; ind<clusterEnergy.size(); ind++) {

    SortedClustersPositions.push_back(clusterPosition.at(OrderedClustersIndices.at(ind)));
    SortedClustersEnergies.push_back(clusterEnergy.at(OrderedClustersIndices.at(ind)));
    Sorted_clusterSize.push_back(clusterSize.at(OrderedClustersIndices.at(ind)));
    Sorted_Clusters_StripsPositions.push_back(Clusters_StripsPositions.at(OrderedClustersIndices.at(ind)));
    Sorted_Clusters_StripsDeposits.push_back(Clusters_StripsDeposits.at(OrderedClustersIndices.at(ind)));
    Sorted_Clusters_StripsID.push_back(Clusters_StripsID.at(OrderedClustersIndices.at(ind)));
    if(clusterPosition.at(OrderedClustersIndices.at(ind)) <= FirstStripPos + 31*AdiacentStripsDistance) {
	Texp = T_exp1;
      }
      else {
	Texp = T_exp2;
      }
    if(clusterPosition.at(OrderedClustersIndices.at(ind)) > FirstStripPos + 31*AdiacentStripsDistance &&clusterPosition.at(OrderedClustersIndices.at(ind)) < FirstStripPos + 32*AdiacentStripsDistance ) {
      if(T_exp1>T_exp2) Texp = T_exp1;
      else  Texp = T_exp2;
    }
    Texp_cluster.push_back(Texp);
  }
  
  int Nclusters = clusterPosition.size();
  ClusterCollection results;
  results.ClustersEnergy = SortedClustersEnergies;
  results.ClustersPositions =  SortedClustersPositions;
  results.ClustersSize = Sorted_clusterSize;
  results.StripsEnergy = Sorted_Clusters_StripsDeposits;
  results.StripsPositions = Sorted_Clusters_StripsPositions;
  results.TimeExpansions = Texp_cluster;
  results.StripsID = Sorted_Clusters_StripsID;
  return results;
}
     	  


    

       
	
