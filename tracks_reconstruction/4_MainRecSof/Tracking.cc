#include <numeric>
#include <algorithm>
#include "TGraphErrors.h"
#include "TF1.h"
#include "TFitResultPtr.h"
#include <vector>
#include "Tracking.h"
using namespace std; 

TracksCollection MakeTracks(vector<double> clusters_1, vector<double> clusters_2, vector<double> clusters_3, vector<double> clusters_4, vector<double> clustersEn_1, vector<double> clustersEn_2, vector<double> clustersEn_3, vector<double> clustersEn_4, vector<double> Texp_cl1, vector<double> Texp_cl2, vector<double> Texp_cl3, vector<double> Texp_cl4, double proximity_cut, double* X_pos,double* Z_add, double sigma) {

  /////////////////// MAKE A LOOP OVER THE CLUSTER COLLECTIONS OF EACH PLANE ////////////////////////
  // INDICES (i,j,k,h)
 
  //// variables declaration
  double p1,p2,p3,p4,x1,x2,x3,x4;
  double exp_p2,exp_m,exp_q,exp_res_2;
  //// fit 3p //////
  double fit3p_intercept, fit3p_slope,fit3p_chiSquare,intercept_error,slope_error;
  Double_t p_3p[3], x_3p[3],sigma_p3p[3],sigma_x3p[3];

  // 4th plane -> variables
  double FirstStripPos = -0.528;
  double AdiacentStripsDistance = 0.0165;
  double min_p4=FirstStripPos, max_p4=FirstStripPos + 63*AdiacentStripsDistance, res_p4_exp_p4, exp_p4,exp_p4_err;
  vector <double> res_p4_allowed, sorted_res_p4_allowed,indices_clu4 ;
  Double_t p_4p[4], x_4p[4],sigma_p4p[4],sigma_x4p[4];
  double fit4p_intercept, fit4p_slope,fit4p_chiSquare;

  // Evaluation of scattering angles
  double side_a, side_b, cos_scatt, theta_scatt;
  vector<double> theta_scatter;
  vector<vector<double>> ScatteringAngles;

  //////////////////////////////////////////// RESULTS ///////////////////////////////////////////////
  vector<double>  intercept_3ptracks, slope_3ptracks, chiSquare_3ptracks, TrackEnergy_3p;
  TracksCollection tracks_3p;
  vector<int> indices_clu1, indices_clu2,indices_clu3,Ntracks_4p;
  vector<vector<double>> multiple_indices_clu4, TrackEnergies_4p;
  vector<vector<double>> position_c4, intercept_4ptracks,slope_4ptracks,chiSquare_4ptracks, displacement_p4;
  vector<double> single_position_c4, single_intercept_4ptracks, single_slope_4ptracks, single_chiSquare_4ptracks, single_displacement_p4, TrackEnergy_4p;
  vector<double> single_residue_c1_p4, single_residue_c2_p4, single_residue_c3_p4,single_residue_c4_p4;
  vector<vector<double>> residue_c1_p4, residue_c2_p4, residue_c3_p4,residue_c4_p4;
  vector<double> position_c1,position_c2,position_c3, residue_c1, residue_c2,residue_c3,ExpectedPosition_OnPlane4th;
  vector<int> Plane4th_isIntercepted,tracks_3p_index;
  vector<double> ExpectedPosition_Res_p2;
  int track2pInd;
  /// Clusters : is in Track arrays
  vector<int> IsInTrack_clusters1, IsInTrack_clusters2,IsInTrack_clusters3,n_track_cl3_vector,n_track_cl2_vector;
  vector<int> IsInTrack_clusters1_4p, IsInTrack_clusters2_4p,IsInTrack_clusters3_4p,n_track_cl3_vector_4p,n_track_cl2_vector_4p;
  vector<vector<int>> vect_of_vect_cl1, vect_of_vect_cl2,vect_of_vect_cl3;
  vector<vector<int>> vect_of_vect_cl1_4p, vect_of_vect_cl2_4p,vect_of_vect_cl3_4p;
  int ntrack_cl1, ntrack_cl2,ntrack_cl3,ntrack_cl4, nT_cl;
  int ntrack_cl1_4p, ntrack_cl2_4p,ntrack_cl3_4p, ntracks=0;
  int BestChi_index=-1, BestEnergy_index=-1;
  double BestChi=10000, BestEnergy=0, TrackEnergy3p;
  /////// cluster of plane 1 
  for(int i=0; i<clusters_1.size();i++) {
    ntrack_cl1=0;
    ntrack_cl1_4p=0;
    p1 = clusters_1.at(i) + Z_add[0];
    x1 = X_pos[0];
    //////// clusters of plane 3
    n_track_cl3_vector.clear();
    n_track_cl3_vector_4p.clear();
    for(int k=0; k<clusters_3.size();k++)  {
      ntrack_cl3=0;
      ntrack_cl3_4p=0;
      p3 =clusters_3.at(k) + Z_add[2];
      x3 = X_pos[2];
      /////// clusters of plane 2
      n_track_cl2_vector.clear();
      n_track_cl2_vector_4p.clear();
      for(int j=0; j<clusters_2.size();j++) {
	ntrack_cl2=0;
	ntrack_cl2_4p=0;
	//Calculate the expected position from p1 - p3 line
	x2 = X_pos[1];
	exp_m = (p1-p3)/(x1-x3);
	exp_q = p1 - (p1-p3)/(x1-x3)*x1;
	exp_p2 = exp_m*x2 + exp_q; 
	p2 = clusters_2.at(j) + Z_add[1];
	exp_res_2 = p2 - exp_p2;

	// IF THE CLUSTER IS ENOUGH CLOSE TO THE EXPECTED POINT -----> TRACKING /////////
	if(abs(exp_res_2) < proximity_cut) {
	  ExpectedPosition_Res_p2.push_back(exp_res_2);
	  ntracks++;
	  ntrack_cl3++;
	  ntrack_cl1++;


	  n_track_cl2_vector.push_back(1);
	  indices_clu1.push_back(i);
	  indices_clu2.push_back(j);
	  indices_clu3.push_back(k);
	  
	  p_3p[0]=p1;
	  p_3p[1]=p2;
	  p_3p[2]=p3;
	  x_3p[0]=x1;
	  x_3p[1]=x2;
	  x_3p[2]=x3;

	  sigma_p3p[0]=sigma;
	  sigma_p3p[1]=sigma;
	  sigma_p3p[2]=sigma;
	  sigma_x3p[0]=0;
	  sigma_x3p[1]=0;
	  sigma_x3p[2]=0;

	  ///////////////////////////////////////////////////////////////////////////
	  ///////////////////////// LINEAR FIT - 3 PLANES //////////////////////////
	  //////////////////////////////////////////////////////////////////////////
	  
	  TF1* func = new TF1("pol1","pol1",-1,2);
          TGraphErrors *graph = new TGraphErrors(3,x_3p,p_3p,sigma_x3p,sigma_p3p);
	  TFitResultPtr fitResults = graph->Fit(func,"RQS");
	  fit3p_intercept = func->GetParameter(0);
	  fit3p_slope = func->GetParameter(1);
	  fit3p_chiSquare = func->GetChisquare();
	  intercept_3ptracks.push_back(fit3p_intercept);
	  slope_3ptracks.push_back(fit3p_slope);
	  chiSquare_3ptracks.push_back(fit3p_chiSquare);
	  ////////////////////////////////////////////////////////////////////////
	  // Clusters track number increment
	  
	  //////// RESULTS STORAGE 
	  position_c1.push_back(p1);
	  position_c2.push_back(p2);
	  position_c3.push_back(p3);
	  residue_c1.push_back(p1 - fit3p_intercept - fit3p_slope*x1);
	  residue_c2.push_back(p2 - fit3p_intercept - fit3p_slope*x2);
	  residue_c3.push_back(p3 - fit3p_intercept - fit3p_slope*x3);
	  TrackEnergy3p = clustersEn_1.at(i) + clustersEn_2.at(j) + clustersEn_3.at(k);
	  TrackEnergy_3p.push_back(clustersEn_1.at(i) + clustersEn_2.at(j) + clustersEn_3.at(k));
	  ////////////////////////////////////////////////////////////////////////

	  //////////////// BEST TRACK EVALUATON /////////////////////////
	  if(Texp_cl1.at(i)>0 && Texp_cl2.at(j) && Texp_cl3.at(k)) {
	    if(BestChi > fit3p_chiSquare) {
	      BestChi = fit3p_chiSquare;
	      BestChi_index = ntracks-1;
	    }
	    if(BestEnergy < TrackEnergy3p) {
	      BestEnergy = TrackEnergy3p;
	      BestEnergy_index = ntracks-1;
	    }
	  }

	  ///////////////////////////////////////////////////////////

	  // Parameters errors
	  slope_error = func->GetParError(1);
	  intercept_error = func->GetParError(0);
	  //////////////// ADD 4TH PLANE ///////////////////
	  res_p4_allowed.clear();
	  sorted_res_p4_allowed.clear();
	  indices_clu4.clear();
	  displacement_p4.clear();
	  single_position_c4.clear();
	  single_intercept_4ptracks.clear();
	  single_slope_4ptracks.clear();
	  single_chiSquare_4ptracks.clear();
	  single_residue_c1_p4.clear();
	  single_residue_c2_p4.clear();
	  single_residue_c3_p4.clear();
	  single_residue_c4_p4.clear();
	  single_displacement_p4.clear();
	  theta_scatter.clear();
	  x4 = X_pos[3];
	  // expected position of the track at x = x4;
	  exp_p4 = fit3p_intercept + x4*fit3p_slope;
	  exp_p4_err = sqrt(intercept_error*intercept_error + x4*x4*slope_error*slope_error);
	  /////////////////// IF THE TRACK INTERCEPT THE 4th PLANE //////////////
	  if(exp_p4 > min_p4 -sigma  && exp_p4 < max_p4 +sigma) {
	    ExpectedPosition_OnPlane4th.push_back(exp_p4);
	    Plane4th_isIntercepted.push_back(1);
	    // IF THE CLUSTER IS PART OF A 4PLANES TRCK ------>
	    if(clusters_4.size()>0) {
	      ntrack_cl3_4p++;
	      ntrack_cl1_4p++;
	      n_track_cl2_vector_4p.push_back(1);
	      tracks_3p_index.push_back(ntracks-1);
	      
	    }else n_track_cl2_vector_4p.push_back(0);
	    //////////////////////////////////////////////////////
	    
	    for(int h=0; h<clusters_4.size(); h++) {
	      x4 = X_pos[3];
	      p4 = clusters_4.at(h);
	      res_p4_exp_p4 = p4 -exp_p4;
	      res_p4_allowed.push_back(res_p4_exp_p4);
	    }
	    Ntracks_4p.push_back(res_p4_allowed.size());
	    // Sort p4_clusters respect to the increasing res_p4 (displacement of the cluster respect to the 3p track) 
	    vector<int> indices(res_p4_allowed.size());
	    iota(indices.begin(), indices.end(), 0);
	    sort(indices.begin(), indices.end(),
		 [&](int A, int B) -> bool {
		   return abs(res_p4_allowed[A]) < abs(res_p4_allowed[B]);
            });
	  
	      
	      for(int ind=0; ind<indices.size();ind++) {
	      sorted_res_p4_allowed.push_back(clusters_4.at(indices.at(ind)));
	      indices_clu4.push_back(indices.at(ind));
	      single_displacement_p4.push_back(res_p4_allowed.at(indices.at(ind)));
	 
	    }

	    for(int cl4=0;cl4<sorted_res_p4_allowed.size(); cl4++) {
	      p4 = sorted_res_p4_allowed.at(cl4);
	      p_4p[0]=p1;
	      p_4p[1]=p2;
	      p_4p[2]=p3;
	      p_4p[3]=p4;
	      x_4p[0]=x1;
	      x_4p[1]=x2;
	      x_4p[2]=x3;
	      x_4p[3]=x4;
	      
	      sigma_p4p[0]=sigma;
	      sigma_p4p[1]=sigma;
	      sigma_p4p[2]=sigma;
	      sigma_p4p[3]=sigma;
	      sigma_x4p[0]=0;
	      sigma_x4p[1]=0;
	      sigma_x4p[2]=0;
	      sigma_x4p[3]=0;
	      
	      ///////////////////////////////////////////////////////////////////////////
	      ///////////////////////// LINEAR FIT - 4 PLANES //////////////////////////
	      //////////////////////////////////////////////////////////////////////////

	      TF1* func4p = new TF1("pol1","pol1",-1,2);
	      TGraphErrors *graph_4p = new TGraphErrors(4,x_4p,p_4p,sigma_x4p,sigma_p4p);
	      TFitResultPtr fitResults_4p = graph_4p->Fit(func4p,"RQS");

	      fit4p_intercept = func4p->GetParameter(0);
	      fit4p_slope = func4p->GetParameter(1);
	      fit4p_chiSquare = func4p->GetChisquare();

	      /// 4 PLANES TRACK INFORMATIONS ----> STORAGE (single vector) ///////////
	      single_position_c4.push_back(p4);
	      single_intercept_4ptracks.push_back(fit4p_intercept);
	      single_slope_4ptracks.push_back(fit4p_slope);
	      single_chiSquare_4ptracks.push_back(fit4p_chiSquare);
	      single_residue_c1_p4.push_back(p1 - fit4p_intercept - fit4p_slope*x1);
	      single_residue_c2_p4.push_back(p2 - fit4p_intercept - fit4p_slope*x2);
	      single_residue_c3_p4.push_back(p3 - fit4p_intercept - fit4p_slope*x3);
	      single_residue_c4_p4.push_back(p4 - fit4p_intercept - fit4p_slope*x4);
	      TrackEnergy_4p.push_back(clustersEn_1.at(i) + clustersEn_2.at(j) + clustersEn_3.at(k) + clustersEn_4.at(indices.at(cl4)));

	      //// SCATTERING ANGLE
	      side_a = sqrt(((fit3p_intercept + x3*fit3p_slope - fit3p_intercept - x4*fit3p_slope)*(fit3p_intercept + x3*fit3p_slope - fit3p_intercept - x4*fit3p_slope)) + ((x3-x4)*(x3-x4)));
	      side_b = sqrt(((fit3p_intercept + x3*fit3p_slope - p4)*(fit3p_intercept + x3*fit3p_slope - p4)) +((x3-x4)*(x3-x4)));
	      cos_scatt =((side_a*side_a) + (side_b*side_b) - ((fit3p_intercept + x4*fit3p_slope-p4)*(fit3p_intercept + x4*fit3p_slope-p4)))/(2*side_a*side_b);
	      theta_scatt = (single_displacement_p4.at(cl4)/abs(single_displacement_p4.at(cl4)))*acos(cos_scatt)*(180./3.14159);
	      theta_scatter.push_back(theta_scatt);	      
	    }
	    /// 4 PLANES TRACK INFORMATIONS ----> STORAGE (all vectors) ///////////
	    ScatteringAngles.push_back(theta_scatter);
	    position_c4.push_back(single_position_c4);
	    intercept_4ptracks.push_back(single_intercept_4ptracks);
	    slope_4ptracks.push_back(single_slope_4ptracks);
	    chiSquare_4ptracks.push_back(single_chiSquare_4ptracks);
	    displacement_p4.push_back(single_displacement_p4);
	    multiple_indices_clu4.push_back(indices_clu4);
	    residue_c1_p4.push_back(single_residue_c1_p4);
	    residue_c2_p4.push_back(single_residue_c2_p4);
	    residue_c3_p4.push_back(single_residue_c3_p4);
	    residue_c4_p4.push_back(single_residue_c4_p4);
	    TrackEnergies_4p.push_back(TrackEnergy_4p);
	  }else {
	    Plane4th_isIntercepted.push_back(0);
	    Ntracks_4p.push_back(0);
	    n_track_cl2_vector_4p.push_back(0);
	  }
	}else {
	  n_track_cl2_vector.push_back(0);
	  n_track_cl2_vector_4p.push_back(0);
	}
      }
      if(ntrack_cl3>0) n_track_cl3_vector.push_back(1);
      else n_track_cl3_vector.push_back(0);
      if(ntrack_cl3_4p>0)n_track_cl3_vector_4p.push_back(1);
      else n_track_cl3_vector_4p.push_back(0);
      vect_of_vect_cl2.push_back(n_track_cl2_vector);
      vect_of_vect_cl2_4p.push_back(n_track_cl2_vector_4p);
    }
    vect_of_vect_cl3.push_back(n_track_cl3_vector);
    vect_of_vect_cl3_4p.push_back(n_track_cl3_vector_4p);
    IsInTrack_clusters1_4p.push_back(ntrack_cl1_4p);
    IsInTrack_clusters1.push_back(ntrack_cl1);
  }


  ////////////////////////// CLUSTERS NUMBER OF ASSOCIATED TRACKS ////////////////////
  //////////////////////////////// TRACKS 3P -----> 
  //// CLUSTERS OF 3rd PLANE 
  if(vect_of_vect_cl3.size() >0) {
  for(int j=0; j<vect_of_vect_cl3.at(0).size(); j++) {
      nT_cl=0;
      for(int i=0;i<vect_of_vect_cl3.size(); i++) {
	nT_cl += vect_of_vect_cl3.at(i).at(j);

      }	IsInTrack_clusters3.push_back(nT_cl);
    }
  }
   //// CLUSTERS OF 2nd PLANE 
  if(vect_of_vect_cl2.size()>0) {
  for(int j=0; j<vect_of_vect_cl2.at(0).size(); j++) {
      nT_cl=0;
      for(int i=0;i<vect_of_vect_cl2.size(); i++) {
	nT_cl += vect_of_vect_cl2.at(i).at(j);

      }	IsInTrack_clusters2.push_back(nT_cl);
    }
  }

  //////////////////////////////// TRACKS 4P -----> 
  //// CLUSTERS OF 3rd PLANE 
  if(vect_of_vect_cl3_4p.size() >0) {
  for(int j=0; j<vect_of_vect_cl3_4p.at(0).size(); j++) {
      nT_cl=0;
      for(int i=0;i<vect_of_vect_cl3_4p.size(); i++) {
	nT_cl += vect_of_vect_cl3_4p.at(i).at(j);

      }	IsInTrack_clusters3_4p.push_back(nT_cl);
    }
  }
   //// CLUSTERS OF 2nd PLANE 
  if(vect_of_vect_cl2_4p.size()>0) {
  for(int j=0; j<vect_of_vect_cl2_4p.at(0).size(); j++) {
      nT_cl=0;
      for(int i=0;i<vect_of_vect_cl2_4p.size(); i++) {
	nT_cl += vect_of_vect_cl2_4p.at(i).at(j);

      }	IsInTrack_clusters2_4p.push_back(nT_cl);
    }
  }

  ///////////////////////////// SAVING RASULTS ///////////////////////////
  /// 3 PLANES TRACKS
  tracks_3p.intercepts_3p = intercept_3ptracks;
  tracks_3p.slopes_3p = slope_3ptracks;
  tracks_3p.chiSquares_3p = chiSquare_3ptracks;
  tracks_3p.cluster_index_1 =  indices_clu1;
  tracks_3p.cluster_index_2 =  indices_clu2;
  tracks_3p.cluster_index_3 =  indices_clu3;
  tracks_3p.position_c1 = position_c1;
  tracks_3p.position_c2 = position_c2;
  tracks_3p.position_c3 = position_c3;
  tracks_3p.residue_c1 = residue_c1;
  tracks_3p.residue_c2 = residue_c2;
  tracks_3p.residue_c3 = residue_c3;
  tracks_3p.Ntracks_4p =  Ntracks_4p;
  tracks_3p.TrackEnergy_3p  = TrackEnergy_3p;
  tracks_3p.IsInTrack_clusters1 = IsInTrack_clusters1;
  tracks_3p.IsInTrack_clusters2 = IsInTrack_clusters2;
  tracks_3p.IsInTrack_clusters3 = IsInTrack_clusters3;
  tracks_3p.IsInTrack_clusters1_4p = IsInTrack_clusters1_4p;
  tracks_3p.IsInTrack_clusters2_4p = IsInTrack_clusters2_4p;
  tracks_3p.IsInTrack_clusters3_4p = IsInTrack_clusters3_4p;
  tracks_3p.Plane4th_isIntercepted = Plane4th_isIntercepted;
  tracks_3p.BestChi = BestChi;
  tracks_3p.BestEnergy = BestEnergy;
  tracks_3p.BestChi_index = BestChi_index;
  tracks_3p.BestEnergy_index = BestEnergy_index;
  tracks_3p.ExpectedPosition_OnPlane4th = ExpectedPosition_OnPlane4th;
  tracks_3p.Track_3p_to_4p_index = tracks_3p_index;
  tracks_3p.Track_3p_ExpectedRes_p2 = ExpectedPosition_Res_p2;
  ///// 4 PLANES TRACKS
  tracks_3p.positions_c4 = position_c4;
  tracks_3p.intercept_4p = intercept_4ptracks;
  tracks_3p.slope_4p = slope_4ptracks;
  tracks_3p.chiSquares_4p =chiSquare_4ptracks;
  tracks_3p.displacement_p4 = displacement_p4;
  tracks_3p.cluster_indices_4 = multiple_indices_clu4;
  tracks_3p.residue_c1_p4 = residue_c1_p4;
  tracks_3p.residue_c2_p4 = residue_c2_p4;
  tracks_3p.residue_c3_p4 = residue_c3_p4;
  tracks_3p.residue_c4_p4 = residue_c4_p4;
  tracks_3p.TrackEnergy_4p = TrackEnergies_4p;
  tracks_3p.ScatteringAngles = ScatteringAngles;
  //////////////////////////////////////////////////////////////////////////
  return tracks_3p;
}

	    
  
  
