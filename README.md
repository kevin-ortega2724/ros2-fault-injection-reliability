# Fault-injection tests of reliability models on ROS 2 control architectures

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23857810.svg)](https://doi.org/10.5281/zenodo.23857810)

Code and raw data. Authors: Daniela Buitrago Largo, Kevin David Ortega Quiñones, Germán Andrés Holguín Londoño and
Mauricio Holguín Londoño, Universidad Tecnológica de Pereira.

Process-kill faults are injected into six ROS 2 architectures. Observed time to loss of function and cell
production are compared with exact Markov chain predictions fixed before measurement. Faults are emulated
software crashes at accelerated rates; the cell is simulated and has no contact physics or PLC.

## Contents (`ros2/`)

| Path | Content |
|---|---|
| `ros2_pilot/` | Architectures, Markov predictions, injector, pilot protocol, data (360 failures) and deviations |
| `ros2_studies/` | Frozen protocol for E1, E2 and E3, runners, analysis, raw results and deviations |
| `ros2_studies/posthoc/` | Exploratory analyses added after freezing, and the initial-state audit |
| `ros2_cell/` | Gazebo work cell: CadQuery model, kinematics and line controller |

Middleware: ROS 2 Humble, Fast DDS default configuration, localhost only, best-effort topics with depth 5. Seeds are in
`ros2/ros2_studies/PROTOCOL.md`.

`PROTOCOL.md` files were not changed after freezing. `ros2/ros2_studies/results/freeze.json` holds the
SHA-256 of the protocol and code used for the runs, so those files are kept exactly as run, including a few comments
and an output path for figures. Read `DEVIATIONS.md` next to each protocol before using the data.

## Reproduce the analysis

Python 3.10 with `pip install -r requirements.txt`. ROS 2 is not needed for this step.

```bash
pytest ros2/ros2_pilot/tests
mkdir -p papers/robotics_ros2/figures   # output folder expected by the frozen analyze.py
cd ros2/ros2_studies && python3 analyze.py
```

The analysis writes tables to `results/` and figures to that folder. Its bootstrap seed is fixed.

## Repeat the experiments

Requires Ubuntu 22.04, ROS 2 Humble, Gazebo Classic 11, `ros2_control`, `gazebo_ros2_control` and `ur_description`.
With the ROS environment sourced:

```bash
cd ros2/ros2_cell && python3 build_cell.py && cd ../ros2_studies
python3 run_signal.py   # about 3.5 h
python3 run_cell.py     # about 2.75 h, six headless cells at once
```

Close other memory-heavy programs first. Runtimes are from one 16 GB machine. Kill-based runs can block a DDS
domain; the runners abandon that domain and record an incident. Writing into `results/` overwrites the published data.

## Post-hoc analyses

From `ros2/ros2_studies`, with `PYTHONPATH=.:../ros2_pilot`: `python3 posthoc/production_sensitivity.py` and
`python3 posthoc/model_checks.py` (no ROS). `posthoc/audit_initial_state.py` needs ROS 2 and takes about 40 min.

## Licenses

Code: MIT (`LICENSE`). Data: CC BY 4.0.
