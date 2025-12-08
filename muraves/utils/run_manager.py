__all__ = ['get_orientation']

import numpy as np
def get_orientation(run_number: int, color: str) -> str:
    
    orientation = "unknown"

    if color == "BLU":
        if run_number in np.arange(2800, 8819, 1) : #8819 is excluded
            orientation = "vesuvius"
        elif run_number >= 8819:
            orientation = "fre_sky"
    elif color == "NERO":
        if run_number in np.arange(2500, 5601, 1) or run_number >=7894: #5601 is excluded
            orientation = "vesuvius"
        elif run_number in np.arange(5636, 7894, 1): #7894 is excluded
            orientation = "fre_sky" 
    elif color == "ROSSO":
        if run_number in np.arange(4000, 10061, 1) or run_number >= 13458: #10061 is excluded
            orientation = "vesuvius"
        elif run_number in np.arange(10061, 13458, 1): #13458 is excluded
            orientation = "fre_sky"
    
    return orientation
