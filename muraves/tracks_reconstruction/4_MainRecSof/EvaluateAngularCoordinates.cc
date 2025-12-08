#include "EvaluateAngularCoordinates.h"
#include "TMath.h"

using namespace std; 
vector<double> TrackAngularCoordinates(double slope_xy, double slope_xz, double X0, double X2) {

  double Dz,Dx,Dy;
  double theta=0, phi=0;
  vector<double> coordinates;
  Dz = slope_xz*(X0 - X2);
  Dx = X2 - X0;
  Dy = slope_xy*Dx;
  theta = atan(abs(Dz)/(sqrt(Dx*Dx +Dy*Dy)))*(180./TMath::Pi());
  
  if(Dz > 0) {
    phi = atan(slope_xy)*(180./TMath::Pi()) +180.;
  }
  else {
    if(slope_xy>0) phi = atan(slope_xy)*180/TMath::Pi();
    else phi = 360. + 	atan(slope_xy)*180/TMath::Pi();             
    
  }
  
  coordinates.push_back(theta);
  coordinates.push_back(phi);
  return coordinates;
}

  
