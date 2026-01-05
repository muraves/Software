__all__ = ["save_root_with_metadata", "load_root_metadata" ]

import ROOT
import json
import subprocess
from datetime import datetime
import subprocess
import re


def git(cmd):
    return subprocess.check_output(cmd).decode().strip()

def get_alghoritms_from_tag_name():

    # get all tags starting with 'algo'
    tags = subprocess.check_output(["git", "tag", "--list"]).decode().splitlines()

    # extract the string between 'algo' and the first '-'
    algorithm_ids = [re.search(r"([^-]+).", tag).group(1) for tag in tags]

    return algorithm_ids  # ['A', 'B', 'C']


def get_latest_tag_for_algorithm(algo_id):
    pattern = f"{algo_id}-*"
    try:
        return subprocess.check_output(["git", "describe", "--tags", "--match", pattern, "--abbrev=0"]).decode().strip()
    except subprocess.CalledProcessError:
        return None

def get_git_metadata():
    algorithms = get_alghoritms_from_tag_name()
    metadata = {
        "algorithms": {algo: get_latest_tag_for_algorithm(algo) for algo in algorithms},
        "generated_at": datetime.utcnow().isoformat(),
        "commit": git(["git", "rev-parse", "--short", "HEAD"])
    }
    return metadata

def save_root_with_metadata(path, *root_objects):
    metadata = get_git_metadata()
    f = ROOT.TFile(path, "RECREATE")

    # salva gli oggetti ROOT (istogrammi, tree, ecc.)
    for obj in root_objects:
        obj.Write()

    # salva i metadati come TObjString
    meta_str = ROOT.TObjString(json.dumps(metadata))
    meta_str.Write("METADATA")

    f.Close()
    return metadata

def load_root_metadata(path):
    f = ROOT.TFile(path)
    meta_obj = f.Get("METADATA")
    if not meta_obj:
        return None
    return json.loads(meta_obj.GetString().Data())


"""
# EXAMPLE: Save ROOT with metadata
import ROOT
from root_wrapper import save_root_with_metadata

# creo un istogramma dummy
h = ROOT.TH1F("h", "Example", 100, 0, 1)
h.FillRandom("gaus", 1000)

# genero sample con metadati
meta = save_root_with_metadata("sample.root", "algoCLUSRECO", h)
print("Metadati salvati:", meta)
"""

"""
# EXEMPLE: Read ROOT metadata
f = ROOT.TFile("sample.root")
meta_obj = f.Get("METADATA")
metadata = json.loads(meta_obj.GetString().Data())
print(metadata["algorithms"])
"""