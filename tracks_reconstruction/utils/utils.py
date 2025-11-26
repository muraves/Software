import json
import time
import traceback
from pathlib import Path

def run_with_status(rule_name, func, output_json, log_file=None) -> None:
    """
    Run a function and capture its status in a JSON file.

    Args:
        rule_name: str, the name of the Snakemake rule
        func: callable, the actual work to perform
        output_json: path to write status info
        log_file: optional path for logging text output
    """
    start = time.time()
    result = {
        "rule": rule_name,
        "status": "ok",
        "error": None,
        "runtime_s": None,
    }

    try:
        func()
    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"{type(e).__name__}: {e}"
        if log_file:
            Path(log_file).write_text(traceback.format_exc())
    finally:
        result["runtime_s"] = round(time.time() - start, 2)
        Path(output_json).write_text(json.dumps(result, indent=2))