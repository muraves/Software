from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence
from pathlib import Path


@dataclass
class PedestalStruct:
    """Store pedestal and 1phe data for a board, reordered by channel mapping."""
    channel_numbers: list[int] = field(default_factory=list)
    pedestal_values: list[float] = field(default_factory=list)
    onephe_values: list[float] = field(default_factory=list)
    flags: list[int] = field(default_factory=list)


def _safe_float(value: str, default: float = 0.0) -> float:
    """Safely convert string to float, returning default on error."""
    try:
        val = float(value)
        # Check for NaN
        if math.isnan(val):
            return default
        return val
    except (TypeError, ValueError):
        return default


def read_pedestal_file(
    filepath: str | Path,
    stripIndices: Sequence[int],
    board_idx: int = 0,
) -> PedestalStruct:
    """
    Read a pedestal/1phe file and reorder channels using stripIndices mapping.
    
    Args:
        filepath: Path to the txt file with 3 columns: channel_number, pedestal, 1phe
        stripIndices: Sequence mapping from file channel position to logical channel index.
                     Used to reorder the data consistently with ReadEvent function.
        board_idx:   Board index (0-based), used to compute the per-board channel offset.
                     Input files use global channel numbering (board 0: 1-32, board 1: 33-64, ...),
                     so the offset board_idx * n_channels is subtracted before indexing.
    
    Returns:
        PedestalStruct containing reordered channel data:
        - channel_numbers: original channel IDs reordered by stripIndices
        - pedestal_values: pedestal values reordered by stripIndices
        - onephe_values: 1phe values reordered by stripIndices
        - flags: 1 if value was NaN, 0 otherwise
    
    Notes:
        - Missing or invalid values are replaced with 0.0
        - Channels not present in the file are padded with 0.0
        - The mapping maintains consistency with ReadEvent's stripIndices behavior
    """
    filepath = Path(filepath)
    
    # Initialize raw data arrays matching stripIndices length
    raw_channels = [0] * len(stripIndices)
    raw_pedestals = [0.0] * len(stripIndices)
    raw_onephes = [0.0] * len(stripIndices)
    raw_flags = [0] * len(stripIndices)
    
    # Read file and populate raw data (channels are 1-indexed in input)
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) < 3:
                continue
            
            # Input channels are globally numbered: board 0 → 1-32, board 1 → 33-64, etc.
            # Convert to local 0-based index by subtracting the board offset.
            n_channels = len(stripIndices)
            channel = int(_safe_float(parts[0], default=-1.0)) - 1 - board_idx * n_channels
            if channel < 0 or channel >= len(stripIndices):
                continue
            
            # Handle NaN values
            pedestal_str = parts[1]
            onephe_str = parts[2]
            
            is_nan = False
            if pedestal_str.lower() == 'nan' or onephe_str.lower() == 'nan':
                is_nan = True
            
            pedestal = _safe_float(pedestal_str, default=0.0)
            onephe = _safe_float(onephe_str, default=0.0)
            
            raw_channels[channel] = channel
            raw_pedestals[channel] = pedestal
            raw_onephes[channel] = onephe
            raw_flags[channel] = 1 if is_nan else 0
    
    # Reorder using stripIndices, consistent with ReadEvent
    reordered_channels = [raw_channels[idx] if 0 <= idx < len(raw_channels) else 0 for idx in stripIndices]
    reordered_pedestals = [raw_pedestals[idx] if 0 <= idx < len(raw_pedestals) else 0.0 for idx in stripIndices]
    reordered_onephes = [raw_onephes[idx] if 0 <= idx < len(raw_onephes) else 0.0 for idx in stripIndices]
    reordered_flags = [raw_flags[idx] if 0 <= idx < len(raw_flags) else 0 for idx in stripIndices]
    
    return PedestalStruct(
        channel_numbers=reordered_channels,
        pedestal_values=reordered_pedestals,
        onephe_values=reordered_onephes,
        flags=reordered_flags,
    )


def write_pedestal_file(
    output_filepath: str | Path,
    pedestal_data: PedestalStruct,
    board_idx: int = 0,
) -> None:
    """
    Write pedestal data to file in the format produced by OnePhE_evaluator.write_results.

    NaN values (flag==1) are written with 1phe=1000 and flag=1.
    All other values are written as-is with flag=0.

    Args:
        output_filepath: Path to output file
        pedestal_data:   PedestalStruct to write
        board_idx:       Board index (0-based, reserved for future use)
    """
    output_filepath = Path(output_filepath)
    output_filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(output_filepath, 'w') as f:
        f.write("ch \t ped \t 1pe \n")

        for ch_idx, (ped, onephe, flag) in enumerate(zip(
            pedestal_data.pedestal_values,
            pedestal_data.onephe_values,
            pedestal_data.flags,
        )):
            if flag == 1:  # NaN in source
                f.write(f"{ch_idx}\t{int(ped)}\t1000\t 1\n")
            else:
                f.write(f"{ch_idx}\t{int(ped)}\t{int(onephe)}\t 0\n")


def process_pedestal_files(
    input_dir: str | Path,
    output_base: str | Path,
    stripIndices: Sequence[int],
    run_range: str,
    input_pattern: str = "ped_onephe_sk{}.txt",
    output_pattern: str = "pedestal_{}",
    num_boards: int = 16,
) -> None:
    """
    Process multiple pedestal files from input directory and write to output directory.
    Output files are placed in output_base/run_range/ to mirror OnePhE_evaluator layout.

    Args:
        input_dir:     Directory containing input files
        output_base:   Base output directory (run_range sub-folder is created inside)
        stripIndices:  Channel mapping (same for all boards)
        run_range:     String used as sub-folder name, e.g. "2500_2524"
        input_pattern: Pattern for input filenames (use {} for board number, 1-indexed)
        output_pattern:Pattern for output filenames (use {} for board number, 0-indexed)
        num_boards:    Number of boards to process (default 16)
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_base) / run_range
    output_dir.mkdir(parents=True, exist_ok=True)

    for board_idx in range(num_boards):
        # Input files are 1-indexed (sk1, sk2, ..., sk16)
        input_file = input_dir / input_pattern.format(board_idx + 1)

        # Output files are 0-indexed (pedestal_0, pedestal_1, ..., pedestal_15)
        output_file = output_dir / output_pattern.format(board_idx)

        if input_file.exists():
            print(f"Processing {input_file.name} -> {output_file}")
            ped_data = read_pedestal_file(input_file, stripIndices, board_idx=board_idx)
            write_pedestal_file(output_file, ped_data, board_idx=board_idx)
        else:
            print(f"Warning: {input_file} not found, skipping board {board_idx}")


def _load_spiroc_mapping(spiroc_cfg: Path) -> list[int]:
    """Load channel ordering from spiroc-hybrid-map.cfg."""
    strips: list[int] = []
    channels: list[int] = []

    with spiroc_cfg.open("r", encoding="utf-8", errors="ignore") as handle:
        for idx, line in enumerate(handle):
            if idx == 0:
                continue  # skip header
            fields = line.strip().split()
            if len(fields) < 2:
                continue
            try:
                strips.append(int(fields[0]))
                channels.append(int(fields[1]))
            except ValueError:
                continue

    ordered = sorted(range(len(strips)), key=lambda i: strips[i])
    return [channels[i] for i in ordered]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Read pedestal/1phe files and reorder channels using spiroc-hybrid-map.cfg"
    )
    parser.add_argument(
        "--input-dir",
        default=str(Path(__file__).parent / "NERO_PED_BASE_2500_2524"),
        help="Directory containing ped_onephe_sk*.txt files (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent),
        help="Base output directory; a sub-folder named after --run-range is created inside (default: %(default)s)",
    )
    parser.add_argument(
        "--run-range",
        default=None,
        help="Sub-folder name for the output, e.g. '2500_2524'. Defaults to the input directory name.",
    )
    parser.add_argument(
        "--spiroc-cfg",
        default=str(Path(__file__).parents[1] / "muraves_cfg_files" / "spiroc-hybrid-map.cfg"),
        help="Path to spiroc-hybrid-map.cfg (default: %(default)s)",
    )
    parser.add_argument(
        "--num-boards", type=int, default=16,
        help="Number of boards/files to process (default: %(default)s)",
    )
    args = parser.parse_args()

    spiroc_cfg = Path(args.spiroc_cfg)
    print(f"Loading channel mapping from: {spiroc_cfg}")
    strip_indices = _load_spiroc_mapping(spiroc_cfg)
    print(f"Loaded {len(strip_indices)} channel mappings: {strip_indices}")

    run_range = args.run_range if args.run_range else Path(args.input_dir).name
    print(f"Run range (output sub-folder): {run_range}")

    process_pedestal_files(
        input_dir=args.input_dir,
        output_base=args.output_dir,
        stripIndices=strip_indices,
        run_range=run_range,
        num_boards=args.num_boards,
    )
    print(f"Done. Output written to: {Path(args.output_dir) / run_range}")
