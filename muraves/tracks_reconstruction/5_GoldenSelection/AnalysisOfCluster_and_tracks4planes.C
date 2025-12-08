#define AnalysiOfCluster_and_tracks4planes_cxx
#include "AnalysisOfCluster_and_tracks4planes.h"
#include <TH2.h>
#include <TStyle.h>
#include <TCanvas.h>

void AnalysisOfCluster_and_tracks4planes::Loop(string detector,int run)
{
  
  TFile *FileOut = new TFile(Form("/media/muraves2/MURAVES_DATA/%s/GOLDEN_SELECTION/Track4p_%s_run%d.root",detector.c_str(),detector.c_str(),run),"recreate");
  TTree *Tracks4ptree = new TTree("Tracks4ptree",""); 
  double TrackClusterEnergy_Z1, TrackClusterEnergy_Z2, TrackClusterEnergy_Z3, TrackClusterEnergy_Z4;
  double TrackClusterEnergy_Y1, TrackClusterEnergy_Y2, TrackClusterEnergy_Y3, TrackClusterEnergy_Y4;
  int TrackClusterSize_Z1, TrackClusterSize_Z2, TrackClusterSize_Z3, TrackClusterSize_Z4;
  int TrackClusterSize_Y1, TrackClusterSize_Y2, TrackClusterSize_Y3, TrackClusterSize_Y4;
  double TrackClusterPosition_Z1, TrackClusterPosition_Z2, TrackClusterPosition_Z3, TrackClusterPosition_Z4;
  double TrackClusterPosition_Y1, TrackClusterPosition_Y2, TrackClusterPosition_Y3, TrackClusterPosition_Y4;
  int ClusterMultriplicity_Z1, ClusterMultriplicity_Z2, ClusterMultriplicity_Z3, ClusterMultriplicity_Z4;
  int ClusterMultriplicity_Y1, ClusterMultriplicity_Y2, ClusterMultriplicity_Y3, ClusterMultriplicity_Y4;
  double TrackClusterZ1_Texp, TrackClusterZ2_Texp, TrackClusterZ3_Texp, TrackClusterZ4_Texp;
  double TrackClusterY1_Texp, TrackClusterY2_Texp, TrackClusterY3_Texp, TrackClusterY4_Texp; 
  vector<double> NonTrackClusterEnergy_Z1, NonTrackClusterEnergy_Z2, NonTrackClusterEnergy_Z3,NonTrackClusterEnergy_Z4;
  vector<double> NonTrackClusterEnergy_Y1, NonTrackClusterEnergy_Y2, NonTrackClusterEnergy_Y3,NonTrackClusterEnergy_Y4;
  vector<double> NonTrackClusterSize_Z1, NonTrackClusterSize_Z2, NonTrackClusterSize_Z3,NonTrackClusterSize_Z4;
  vector<double> NonTrackClusterSize_Y1, NonTrackClusterSize_Y2, NonTrackClusterSize_Y3,NonTrackClusterSize_Y4;

  vector<double> NonTrackClusterPosition_Z1, NonTrackClusterPosition_Z2, NonTrackClusterPosition_Z3,NonTrackClusterPosition_Z4;
  vector<double> NonTrackClusterPosition_Y1, NonTrackClusterPosition_Y2, NonTrackClusterPosition_Y3,NonTrackClusterPosition_Y4;

  double Phi, Theta, Scattering_xy, ChiSquare_xy, Scattering_xz, ChiSquare_xz, ChiSquare_3p_xy, ChiSquare_3p_xz;
  double TrackClusterMaxStripEnergy_Z1, TrackClusterMinStripEnergy_Z1;
  double TrackClusterMaxStripEnergy_Z2, TrackClusterMinStripEnergy_Z2;
  double TrackClusterMaxStripEnergy_Z3, TrackClusterMinStripEnergy_Z3;
  double TrackClusterMaxStripEnergy_Z4, TrackClusterMinStripEnergy_Z4;

  double TrackClusterMaxStripEnergy_Y1, TrackClusterMinStripEnergy_Y1;
  double TrackClusterMaxStripEnergy_Y2, TrackClusterMinStripEnergy_Y2;
  double TrackClusterMaxStripEnergy_Y3, TrackClusterMinStripEnergy_Y3;
  double TrackClusterMaxStripEnergy_Y4, TrackClusterMinStripEnergy_Y4;

  int Nrun, workingP;
  double time, tr; 
  TDatime date;
  Tracks4ptree->Branch("Phi",&Phi);
  Tracks4ptree->Branch("Theta",&Theta);
  Tracks4ptree->Branch("Scattering_xy",&Scattering_xy);
  Tracks4ptree->Branch("Scattering_xz",&Scattering_xz);
  Tracks4ptree->Branch("ChiSquare_xz",&ChiSquare_xz);
  Tracks4ptree->Branch("ChiSquare_xy",&ChiSquare_xy);
  Tracks4ptree->Branch("ChiSquare_3p_xz",&ChiSquare_3p_xz);
  Tracks4ptree->Branch("ChiSquare_3p_xy",&ChiSquare_3p_xy);
  
  Tracks4ptree->Branch("TrackClusterMaxStripEnergy_Z1", &TrackClusterMaxStripEnergy_Z1);
  Tracks4ptree->Branch("TrackClusterMinStripEnergy_Z1", &TrackClusterMinStripEnergy_Z1);
  Tracks4ptree->Branch("TrackClusterMaxStripEnergy_Z2", &TrackClusterMaxStripEnergy_Z2);
  Tracks4ptree->Branch("TrackClusterMinStripEnergy_Z2", &TrackClusterMinStripEnergy_Z2);
  Tracks4ptree->Branch("TrackClusterMaxStripEnergy_Z3", &TrackClusterMaxStripEnergy_Z3);
  Tracks4ptree->Branch("TrackClusterMinStripEnergy_Z3", &TrackClusterMinStripEnergy_Z3);
  Tracks4ptree->Branch("TrackClusterMaxStripEnergy_Z4", &TrackClusterMaxStripEnergy_Z4);
  Tracks4ptree->Branch("TrackClusterMinStripEnergy_Z4", &TrackClusterMinStripEnergy_Z4);

  Tracks4ptree->Branch("TrackClusterMaxStripEnergy_Y1", &TrackClusterMaxStripEnergy_Y1);
  Tracks4ptree->Branch("TrackClusterMinStripEnergy_Y1", &TrackClusterMinStripEnergy_Y1);
  Tracks4ptree->Branch("TrackClusterMaxStripEnergy_Y2", &TrackClusterMaxStripEnergy_Y2);
  Tracks4ptree->Branch("TrackClusterMinStripEnergy_Y2", &TrackClusterMinStripEnergy_Y2);
  Tracks4ptree->Branch("TrackClusterMaxStripEnergy_Y3", &TrackClusterMaxStripEnergy_Y3);
  Tracks4ptree->Branch("TrackClusterMinStripEnergy_Y3", &TrackClusterMinStripEnergy_Y3);
  Tracks4ptree->Branch("TrackClusterMaxStripEnergy_Y4", &TrackClusterMaxStripEnergy_Y4);
  Tracks4ptree->Branch("TrackClusterMinStripEnergy_Y4", &TrackClusterMinStripEnergy_Y4);

  Tracks4ptree->Branch("TrackClusterEnergy_Z1", &TrackClusterEnergy_Z1);
  Tracks4ptree->Branch("TrackClusterEnergy_Z2", &TrackClusterEnergy_Z2);
  Tracks4ptree->Branch("TrackClusterEnergy_Z3", &TrackClusterEnergy_Z3);
  Tracks4ptree->Branch("TrackClusterEnergy_Z4", &TrackClusterEnergy_Z4);

  Tracks4ptree->Branch("TrackClusterPosition_Z1", &TrackClusterPosition_Z1);
  Tracks4ptree->Branch("TrackClusterPosition_Z2", &TrackClusterPosition_Z2);
  Tracks4ptree->Branch("TrackClusterPosition_Z3", &TrackClusterPosition_Z3);
  Tracks4ptree->Branch("TrackClusterPosition_Z4", &TrackClusterPosition_Z4);

  Tracks4ptree->Branch("TrackClusterSize_Z1", &TrackClusterSize_Z1);
  Tracks4ptree->Branch("TrackClusterSize_Z2", &TrackClusterSize_Z2);
  Tracks4ptree->Branch("TrackClusterSize_Z3", &TrackClusterSize_Z3);
  Tracks4ptree->Branch("TrackClusterSize_Z4", &TrackClusterSize_Z4);

  Tracks4ptree->Branch("TrackClusterEnergy_Y1", &TrackClusterEnergy_Y1);
  Tracks4ptree->Branch("TrackClusterEnergy_Y2", &TrackClusterEnergy_Y2);
  Tracks4ptree->Branch("TrackClusterEnergy_Y3", &TrackClusterEnergy_Y3);
  Tracks4ptree->Branch("TrackClusterEnergy_Y4", &TrackClusterEnergy_Y4);

  Tracks4ptree->Branch("TrackClusterExp_Z1", &TrackClusterZ1_Texp);
  Tracks4ptree->Branch("TrackClusterExp_Z2", &TrackClusterZ2_Texp);
  Tracks4ptree->Branch("TrackClusterExp_Z3", &TrackClusterZ3_Texp);
  Tracks4ptree->Branch("TrackClusterExp_Z4", &TrackClusterZ4_Texp);

  Tracks4ptree->Branch("TrackClusterExp_Y1", &TrackClusterY1_Texp);
  Tracks4ptree->Branch("TrackClusterExp_Y2", &TrackClusterY2_Texp);
  Tracks4ptree->Branch("TrackClusterExp_Y3", &TrackClusterY3_Texp);
  Tracks4ptree->Branch("TrackClusterExp_Y4", &TrackClusterY4_Texp);
  
  Tracks4ptree->Branch("TrackClusterPosition_Y1", &TrackClusterPosition_Y1);
  Tracks4ptree->Branch("TrackClusterPosition_Y2", &TrackClusterPosition_Y2);
  Tracks4ptree->Branch("TrackClusterPosition_Y3", &TrackClusterPosition_Y3);
  Tracks4ptree->Branch("TrackClusterPosition_Y4", &TrackClusterPosition_Y4);

  Tracks4ptree->Branch("TrackClusterSize_Y1", &TrackClusterSize_Y1);
  Tracks4ptree->Branch("TrackClusterSize_Y2", &TrackClusterSize_Y2);
  Tracks4ptree->Branch("TrackClusterSize_Y3", &TrackClusterSize_Y3);
  Tracks4ptree->Branch("TrackClusterSize_Y4", &TrackClusterSize_Y4);

  Tracks4ptree->Branch("ClusterMultriplicity_Z1", &ClusterMultriplicity_Z1);
  Tracks4ptree->Branch("ClusterMultriplicity_Z2", &ClusterMultriplicity_Z2);
  Tracks4ptree->Branch("ClusterMultriplicity_Z3", &ClusterMultriplicity_Z3);
  Tracks4ptree->Branch("ClusterMultriplicity_Z4", &ClusterMultriplicity_Z4);

  Tracks4ptree->Branch("ClusterMultriplicity_Y1", &ClusterMultriplicity_Y1);
  Tracks4ptree->Branch("ClusterMultriplicity_Y2", &ClusterMultriplicity_Y2);
  Tracks4ptree->Branch("ClusterMultriplicity_Y3", &ClusterMultriplicity_Y3);
  Tracks4ptree->Branch("ClusterMultriplicity_Y4", &ClusterMultriplicity_Y4);

  Tracks4ptree->Branch("NonTrackClusterEnergy_Z1", &NonTrackClusterEnergy_Z1);
  Tracks4ptree->Branch("NonTrackClusterEnergy_Z2", &NonTrackClusterEnergy_Z2);
  Tracks4ptree->Branch("NonTrackClusterEnergy_Z3", &NonTrackClusterEnergy_Z3);
  Tracks4ptree->Branch("NonTrackClusterEnergy_Z4", &NonTrackClusterEnergy_Z4);

  Tracks4ptree->Branch("NonTrackClusterEnergy_Y1", &NonTrackClusterEnergy_Y1);
  Tracks4ptree->Branch("NonTrackClusterEnergy_Y2", &NonTrackClusterEnergy_Y2);
  Tracks4ptree->Branch("NonTrackClusterEnergy_Y3", &NonTrackClusterEnergy_Y3);
  Tracks4ptree->Branch("NonTrackClusterEnergy_Y4", &NonTrackClusterEnergy_Y4);

  Tracks4ptree->Branch("NonTrackClusterSize_Z1", &NonTrackClusterSize_Z1);
  Tracks4ptree->Branch("NonTrackClusterSize_Z2", &NonTrackClusterSize_Z2);
  Tracks4ptree->Branch("NonTrackClusterSize_Z3", &NonTrackClusterSize_Z3);
  Tracks4ptree->Branch("NonTrackClusterSize_Z4", &NonTrackClusterSize_Z4);

  Tracks4ptree->Branch("NonTrackClusterSize_Y1", &NonTrackClusterSize_Y1);
  Tracks4ptree->Branch("NonTrackClusterSize_Y2", &NonTrackClusterSize_Y2);
  Tracks4ptree->Branch("NonTrackClusterSize_Y3", &NonTrackClusterSize_Y3);
  Tracks4ptree->Branch("NonTrackClusterSize_Y4", &NonTrackClusterSize_Y4);

  Tracks4ptree->Branch("NonTrackClusterPosition_Z1", &NonTrackClusterPosition_Z1);
  Tracks4ptree->Branch("NonTrackClusterPosition_Z2", &NonTrackClusterPosition_Z2);
  Tracks4ptree->Branch("NonTrackClusterPosition_Z3", &NonTrackClusterPosition_Z3);
  Tracks4ptree->Branch("NonTrackClusterPosition_Z4", &NonTrackClusterPosition_Z4);

  Tracks4ptree->Branch("NonTrackClusterPosition_Y1", &NonTrackClusterPosition_Y1);
  Tracks4ptree->Branch("NonTrackClusterPosition_Y2", &NonTrackClusterPosition_Y2);
  Tracks4ptree->Branch("NonTrackClusterPosition_Y3", &NonTrackClusterPosition_Y3);
  Tracks4ptree->Branch("NonTrackClusterPosition_Y4", &NonTrackClusterPosition_Y4);

  
  Tracks4ptree->Branch("Run",&Nrun);
  Tracks4ptree->Branch("TriggerRate",&tr);
  Tracks4ptree->Branch("RunDuration", &time);
  Tracks4ptree->Branch("WorkingPoint",&workingP);
  Tracks4ptree->Branch("Datetime",&date);
  
  if (fChain == 0) return;

   Long64_t nentries = fChain->GetEntriesFast();

   Long64_t nbytes = 0, nb = 0;
   for (Long64_t jentry=0; jentry<nentries;jentry++) {
      Long64_t ientry = LoadTree(jentry);
      if (ientry < 0) break;
      nb = fChain->GetEntry(jentry);   nbytes += nb;
      
     ////////////// CLUSTER POSITION VS CLUSTER SIZE IN TRACKS 3P //////////////
     if(BestTrack_3p_ChiSquare_xz!=-1) {

       if(BestTrack_4p_ChiSquare_xz!=-1) {
	 Nrun = Run;
	 time = RunDuration;
	 tr= TriggerRate;
	 workingP = WorkingPoint;
	 
	 //////////////////////////////// TREE VARIABLES /////////////////////////////////////////////////////////////////
	 Phi = Phi_4p;
	 Theta = Theta_4p;
	 date.Set(datime->GetDate(),datime->GetTime());

	 ChiSquare_3p_xz = chiSquare_3p_xz->at(BestTrack_3p_xz_index);
	 ChiSquare_3p_xy = chiSquare_3p_xy->at(BestTrack_3p_xy_index);
	 ChiSquare_xz = chiSquare_4p_xz->at(Track_3p_of_4p_index_xz).at(Track_4p_index_xz);
	 Scattering_xz = ScatteringAngle_xz->at(Track_3p_of_4p_index_xz).at(Track_4p_index_xz);
	 Scattering_xy = ScatteringAngle_xy->at(Track_3p_of_4p_index_xy).at(Track_4p_index_xy);
	 ChiSquare_xy = chiSquare_4p_xy->at(Track_3p_of_4p_index_xy).at(Track_4p_index_xy);

	 TrackClusterMaxStripEnergy_Z1 = StripsEnergy_Z1->at(TrackCluster_z1_index->at(BestTrack_3p_xz_index)).at(0);
	 TrackClusterMaxStripEnergy_Z2 = StripsEnergy_Z2->at(TrackCluster_z2_index->at(BestTrack_3p_xz_index)).at(0);
	 TrackClusterMaxStripEnergy_Z3 = StripsEnergy_Z3->at(TrackCluster_z3_index->at(BestTrack_3p_xz_index)).at(0);
	 TrackClusterMaxStripEnergy_Z4 =  StripsEnergy_Z4->at(cluster_c4_index_xz->at(Track_3p_of_4p_index_xz).at(Track_4p_index_xz)).at(0);

	 TrackClusterMaxStripEnergy_Y1 = StripsEnergy_Y1->at(TrackCluster_y1_index->at(BestTrack_3p_xy_index)).at(0);
	 TrackClusterMaxStripEnergy_Y2 = StripsEnergy_Y2->at(TrackCluster_y2_index->at(BestTrack_3p_xy_index)).at(0);
	 TrackClusterMaxStripEnergy_Y3 = StripsEnergy_Y3->at(TrackCluster_y3_index->at(BestTrack_3p_xy_index)).at(0);
	 TrackClusterMaxStripEnergy_Y4 =  StripsEnergy_Y4->at(cluster_c4_index_xy->at(Track_3p_of_4p_index_xy).at(Track_4p_index_xy)).at(0);

	 TrackClusterMinStripEnergy_Z1 = StripsEnergy_Z1->at(TrackCluster_z1_index->at(BestTrack_3p_xz_index)).at(ClusterSize_Z1->at(TrackCluster_z1_index->at(BestTrack_3p_xz_index))-1);
	 TrackClusterMinStripEnergy_Z2 = StripsEnergy_Z2->at(TrackCluster_z2_index->at(BestTrack_3p_xz_index)).at(ClusterSize_Z2->at(TrackCluster_z2_index->at(BestTrack_3p_xz_index))-1);
	 TrackClusterMinStripEnergy_Z3 = StripsEnergy_Z3->at(TrackCluster_z3_index->at(BestTrack_3p_xz_index)).at(ClusterSize_Z3->at(TrackCluster_z3_index->at(BestTrack_3p_xz_index))-1);
	 TrackClusterMinStripEnergy_Z4 =  StripsEnergy_Z4->at(cluster_c4_index_xz->at(Track_3p_of_4p_index_xz).at(Track_4p_index_xz)).at(ClusterSize_Z4->at(cluster_c4_index_xz->at(Track_3p_of_4p_index_xz).at(Track_4p_index_xz))-1);



	 TrackClusterMinStripEnergy_Y1 = StripsEnergy_Y1->at(TrackCluster_y1_index->at(BestTrack_3p_xy_index)).at(ClusterSize_Y1->at(TrackCluster_y1_index->at(BestTrack_3p_xy_index))-1);
	 TrackClusterMinStripEnergy_Y2 = StripsEnergy_Y2->at(TrackCluster_y2_index->at(BestTrack_3p_xy_index)).at(ClusterSize_Y2->at(TrackCluster_y2_index->at(BestTrack_3p_xy_index))-1);
	 TrackClusterMinStripEnergy_Y3 = StripsEnergy_Y3->at(TrackCluster_y3_index->at(BestTrack_3p_xy_index)).at(ClusterSize_Y3->at(TrackCluster_y3_index->at(BestTrack_3p_xy_index))-1);
	 TrackClusterMinStripEnergy_Y4 = StripsEnergy_Y4->at(cluster_c4_index_xy->at(Track_3p_of_4p_index_xy).at(Track_4p_index_xy)).at(ClusterSize_Y4->at(cluster_c4_index_xy->at(Track_3p_of_4p_index_xy).at(Track_4p_index_xy))-1);


	 TrackClusterEnergy_Z1=ClusterEnergy_Z1->at(TrackCluster_z1_index->at(BestTrack_3p_xz_index));
	 TrackClusterEnergy_Z2=ClusterEnergy_Z2->at(TrackCluster_z2_index->at(BestTrack_3p_xz_index));
	 TrackClusterEnergy_Z3=ClusterEnergy_Z3->at(TrackCluster_z3_index->at(BestTrack_3p_xz_index));
	 TrackClusterEnergy_Z4=ClusterEnergy_Z4->at(cluster_c4_index_xz->at(Track_3p_of_4p_index_xz).at(Track_4p_index_xz));
	 TrackClusterEnergy_Y1=ClusterEnergy_Y1->at(TrackCluster_y1_index->at(BestTrack_3p_xy_index));
	 TrackClusterEnergy_Y2=ClusterEnergy_Y2->at(TrackCluster_y2_index->at(BestTrack_3p_xy_index));
	 TrackClusterEnergy_Y3=ClusterEnergy_Y3->at(TrackCluster_y3_index->at(BestTrack_3p_xy_index));
	 TrackClusterEnergy_Y4=ClusterEnergy_Y4->at(cluster_c4_index_xy->at(Track_3p_of_4p_index_xy).at(Track_4p_index_xy));

	 TrackClusterSize_Z1=ClusterSize_Z1->at(TrackCluster_z1_index->at(BestTrack_3p_xz_index));
	 TrackClusterSize_Z2=ClusterSize_Z2->at(TrackCluster_z2_index->at(BestTrack_3p_xz_index));
	 TrackClusterSize_Z3=ClusterSize_Z3->at(TrackCluster_z3_index->at(BestTrack_3p_xz_index));
	 TrackClusterSize_Z4=ClusterSize_Z4->at(cluster_c4_index_xz->at(Track_3p_of_4p_index_xz).at(Track_4p_index_xz));
	 TrackClusterSize_Y1=ClusterSize_Y1->at(TrackCluster_y1_index->at(BestTrack_3p_xy_index));
	 TrackClusterSize_Y2=ClusterSize_Y2->at(TrackCluster_y2_index->at(BestTrack_3p_xy_index));
	 TrackClusterSize_Y3=ClusterSize_Y3->at(TrackCluster_y3_index->at(BestTrack_3p_xy_index));
	 TrackClusterSize_Y4=ClusterSize_Y4->at(cluster_c4_index_xy->at(Track_3p_of_4p_index_xy).at(Track_4p_index_xy));

	 TrackClusterPosition_Z1=ClusterPosition_Z1->at(TrackCluster_z1_index->at(BestTrack_3p_xz_index));
	 TrackClusterPosition_Z2=ClusterPosition_Z2->at(TrackCluster_z2_index->at(BestTrack_3p_xz_index));
	 TrackClusterPosition_Z3=ClusterPosition_Z3->at(TrackCluster_z3_index->at(BestTrack_3p_xz_index));
	 TrackClusterPosition_Z4=ClusterPosition_Z4->at(cluster_c4_index_xz->at(Track_3p_of_4p_index_xz).at(Track_4p_index_xz));
	 TrackClusterPosition_Y1=ClusterPosition_Y1->at(TrackCluster_y1_index->at(BestTrack_3p_xy_index));
	 TrackClusterPosition_Y2=ClusterPosition_Y2->at(TrackCluster_y2_index->at(BestTrack_3p_xy_index));
	 TrackClusterPosition_Y3=ClusterPosition_Y3->at(TrackCluster_y3_index->at(BestTrack_3p_xy_index));
	 TrackClusterPosition_Y4=ClusterPosition_Y4->at(cluster_c4_index_xy->at(Track_3p_of_4p_index_xy).at(Track_4p_index_xy));

	 TrackClusterZ1_Texp = ClusterZ1_Texp->at(TrackCluster_z1_index->at(BestTrack_3p_xz_index));
	 TrackClusterZ2_Texp = ClusterZ2_Texp->at(TrackCluster_z2_index->at(BestTrack_3p_xz_index));
	 TrackClusterZ3_Texp = ClusterZ3_Texp->at(TrackCluster_z3_index->at(BestTrack_3p_xz_index));
	 TrackClusterZ4_Texp = ClusterZ4_Texp->at(cluster_c4_index_xz->at(Track_3p_of_4p_index_xz).at(Track_4p_index_xz));

	 TrackClusterY1_Texp = ClusterY1_Texp->at(TrackCluster_y1_index->at(BestTrack_3p_xy_index));
	 TrackClusterY2_Texp = ClusterY2_Texp->at(TrackCluster_y2_index->at(BestTrack_3p_xy_index));
	 TrackClusterY3_Texp = ClusterY3_Texp->at(TrackCluster_y3_index->at(BestTrack_3p_xy_index));
	 TrackClusterY4_Texp = ClusterY4_Texp->at(cluster_c4_index_xy->at(Track_3p_of_4p_index_xy).at(Track_4p_index_xy));


	 ClusterMultriplicity_Z1 = Nclusters_Z1;
	 ClusterMultriplicity_Z2 = Nclusters_Z2;
	 ClusterMultriplicity_Z3 = Nclusters_Z3;
	 ClusterMultriplicity_Z4 = Nclusters_Z4;
	 ClusterMultriplicity_Y1 = Nclusters_Y1;
	 ClusterMultriplicity_Y2 = Nclusters_Y2;
	 ClusterMultriplicity_Y3 = Nclusters_Y3;
	 ClusterMultriplicity_Y4 = Nclusters_Y4;
	 


	 for(int i=0; i< Nclusters_Z1; i++ ) {
	   if(i!=TrackCluster_z1_index->at(BestTrack_3p_xz_index)) {
	     NonTrackClusterEnergy_Z1.push_back(ClusterEnergy_Z1->at(i));
	     NonTrackClusterPosition_Z1.push_back(ClusterPosition_Z1->at(i));
	     NonTrackClusterSize_Z1.push_back(ClusterSize_Z1->at(i));

	   }
	 }
	 for(int i=0; i< Nclusters_Z2; i++ ) {
	   if(i!=TrackCluster_z2_index->at(BestTrack_3p_xz_index)){
	     NonTrackClusterEnergy_Z2.push_back(ClusterEnergy_Z2->at(i));
	     NonTrackClusterSize_Z2.push_back(ClusterSize_Z2->at(i));
	     NonTrackClusterPosition_Z2.push_back(ClusterPosition_Z2->at(i));

	   }
	 }
	 for(int i=0; i< Nclusters_Z4; i++ ) {

	   if(i!=cluster_c4_index_xz->at(Track_3p_of_4p_index_xz).at(Track_4p_index_xz)) {
	     NonTrackClusterEnergy_Z4.push_back(ClusterEnergy_Z4->at(i));
	     NonTrackClusterPosition_Z4.push_back(ClusterPosition_Z4->at(i));
	     NonTrackClusterSize_Z4.push_back(ClusterSize_Z4->at(i));
	   }
	 }
	 
	 for(int i=0; i< Nclusters_Z3; i++ ) {

	   if(i!=TrackCluster_z3_index->at(BestTrack_3p_xz_index)) {
	     NonTrackClusterEnergy_Z3.push_back(ClusterEnergy_Z3->at(i));
	     NonTrackClusterPosition_Z3.push_back(ClusterPosition_Z3->at(i));
	     NonTrackClusterSize_Z3.push_back(ClusterSize_Z3->at(i));
	   }
	 }

	 for(int i=0; i< Nclusters_Y1; i++ ) {
	   if(i!=TrackCluster_y1_index->at(BestTrack_3p_xy_index)) {
	     NonTrackClusterPosition_Y1.push_back(ClusterPosition_Y1->at(i));
	     NonTrackClusterEnergy_Y1.push_back(ClusterEnergy_Y1->at(i));
	     NonTrackClusterSize_Y1.push_back(ClusterSize_Y1->at(i));
	   }
	 }
	 for(int i=0; i< Nclusters_Y2; i++ ) {
	   if(i!=TrackCluster_y2_index->at(BestTrack_3p_xy_index)) {
	     NonTrackClusterEnergy_Y2.push_back(ClusterEnergy_Y2->at(i));
	     NonTrackClusterPosition_Y2.push_back(ClusterPosition_Y2->at(i));
	     NonTrackClusterSize_Y2.push_back(ClusterSize_Y2->at(i));
	   }
	 }
	 	 
	 for(int i=0; i< Nclusters_Y3; i++ ) {

	   if(i!=TrackCluster_y3_index->at(BestTrack_3p_xy_index)) {
	     NonTrackClusterPosition_Y3.push_back(ClusterPosition_Y3->at(i));
	     NonTrackClusterEnergy_Y3.push_back(ClusterEnergy_Y3->at(i));
	     NonTrackClusterSize_Y3.push_back(ClusterSize_Y3->at(i));
	   }
	 }

	 for(int i=0; i< Nclusters_Y4; i++ ) {
	   if(i!=cluster_c4_index_xy->at(Track_3p_of_4p_index_xy).at(Track_4p_index_xy)) {
	     NonTrackClusterEnergy_Y4.push_back(ClusterEnergy_Y4->at(i));
	     NonTrackClusterPosition_Y4.push_back(ClusterPosition_Y4->at(i));
	     NonTrackClusterSize_Y4.push_back(ClusterSize_Y4->at(i));
	   }
	 }

	 Tracks4ptree->Fill();      
       }
     }
   
     /////////////////////////////////////////////////////

     NonTrackClusterEnergy_Z1.clear();
     NonTrackClusterEnergy_Z2.clear();
     NonTrackClusterEnergy_Z3.clear();
     NonTrackClusterEnergy_Z4.clear();

     NonTrackClusterEnergy_Y1.clear();
     NonTrackClusterEnergy_Y2.clear();
     NonTrackClusterEnergy_Y3.clear();
     NonTrackClusterEnergy_Y4.clear();

     NonTrackClusterSize_Y1.clear();
     NonTrackClusterSize_Y2.clear();
     NonTrackClusterSize_Y3.clear();
     NonTrackClusterSize_Y4.clear();

     NonTrackClusterSize_Z1.clear();
     NonTrackClusterSize_Z2.clear();
     NonTrackClusterSize_Z3.clear();
     NonTrackClusterSize_Z4.clear();

     NonTrackClusterPosition_Z1.clear();
     NonTrackClusterPosition_Z2.clear();
     NonTrackClusterPosition_Z3.clear();
     NonTrackClusterPosition_Z4.clear();

     NonTrackClusterPosition_Y1.clear();
     NonTrackClusterPosition_Y2.clear();
     NonTrackClusterPosition_Y3.clear();
     NonTrackClusterPosition_Y4.clear();
      // if (Cut(ientry) < 0) continue;
   }

   Tracks4ptree->Write();
}
