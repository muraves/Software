import uproot
import pandas as pd
import argparse
import numpy as np
import matplotlib.pyplot as plt

def load_root_to_dataframe(file_path):
    """
    Opens a ROOT file using uproot and loads its content into a pandas DataFrame.
    
    Args:
        file_path (str): Path to the ROOT file
        
    Returns:
        pd.DataFrame: DataFrame containing the ROOT file data
    """
    with uproot.open(file_path) as file:
        # Get the first tree in the file
        tree = file[file.keys()[0]]
        
        # Convert tree to DataFrame
        df = tree.arrays(library="pd")
        
    return df


def is_scalar_series(series: pd.Series) -> bool:
    """Return True if a series appears to store scalar values per row."""
    non_null = series.dropna()
    if non_null.empty:
        return True
    return bool(np.isscalar(non_null.iloc[0]))

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Load and analyze ROOT files")
    parser.add_argument("file_path", help="Path to the ROOT file")
    args = parser.parse_args()
    
    df = load_root_to_dataframe(args.file_path)
    #print(df.head())
    FEATURES_LABEL = {
        "Nclusters_Y1": "Nclusters_Y1",
        "Nclusters_Y2": "Nclusters_Y2",
        "Nclusters_Y3": "Nclusters_Y3",
        "Nclusters_Y4": "Nclusters_Y4",
        "Nclusters_Z1": "Nclusters_Z1",
        "Nclusters_Z2": "Nclusters_Z2",
        "Nclusters_Z3": "Nclusters_Z3",
        "Nclusters_Z4": "Nclusters_Z4",
        "StripsID_Y1": "StripsID_Y1",
        "StripsID_Y2": "StripsID_Y2",
        "StripsID_Y3": "StripsID_Y3",
        "StripsID_Y4": "StripsID_Y4",
        "StripsID_Z1": "StripsID_Z1",
        "StripsID_Z2": "StripsID_Z2",
        "StripsID_Z3": "StripsID_Z3",
        "StripsID_Z4": "StripsID_Z4",
        "Ntracks_3p_xy": "Ntracks_3p_xy",
        "Ntracks_3p_xz": "Ntracks_3p_xz",
        "nStripsPosition_Y1": "nStripsPosition_Y1",
        "nStripsPosition_Y2": "nStripsPosition_Y2",
        "nStripsPosition_Y3": "nStripsPosition_Y3",
        "nStripsPosition_Y4": "nStripsPosition_Y4",
        "nStripsPosition_Z1": "nStripsPosition_Z1",
        "nStripsPosition_Z2": "nStripsPosition_Z2",
        "nStripsPosition_Z3": "nStripsPosition_Z3",
        "nStripsPosition_Z4": "nStripsPosition_Z4",
        "chiSquare_3p_xy": "chiSquare_3p_xy",
        "chiSquare_3p_xz": "chiSquare_3p_xz",
        "chiSquare_4p_xy": "chiSquare_4p_xy",
        "chiSquare_4p_xz": "chiSquare_4p_xz",
        "TriggerMaskChannels": "TriggerMaskChannels",
        "TriggerMaskSize": "TriggerMaskSize",
        "TriggerMaskStrips": "TriggerMaskStrips",
    }

    candidate_features = [col for col in df.columns if col in FEATURES_LABEL.keys()]
    FEATURES = [
        col for col in candidate_features
        if pd.api.types.is_numeric_dtype(df[col]) and is_scalar_series(df[col])
    ]

    dropped = sorted(set(candidate_features) - set(FEATURES))
    if dropped:
        print("Dropping non-scalar features for PCA:", ", ".join(dropped))

    if not FEATURES:
        raise ValueError("No scalar numeric features available for PCA")

    from pca_mapper import PCAMapper
    pca_mapper = PCAMapper(
        raw_df=df,
        features=FEATURES,
        feature_labels=FEATURES_LABEL,  
    ).fit()

    print("Explained variance ratio sum:", pca_mapper.pca.explained_variance_ratio_.sum())

    features = [
    "Nclusters_Y4",
    "Nclusters_Y1",
    "Ntracks_3p_xy", 
    "nStripsPosition_Y4",
    ]
    pca_mapper.plot_pca_density_hexbin(
        gridsize=60, show_contours=False,
        features = features,
        figname="PCA_density_hexabin_all.pdf")
    plt.savefig("PCA_density_hexabin_all.pdf")

    pca_mapper.plot_pca_component_loadings("PC1", features_label=FEATURES_LABEL, top_n=10, figname="PCA1_loadings.pdf")
    pca_mapper.plot_pca_component_loadings("PC2", features_label=FEATURES_LABEL, top_n=10, figname="PCA2_loadings.pdf")
    plt.savefig("PCA_loadings.pdf")