# Data Handler Package

Modules here manage data acquisition and preprocessing. The `interface` subpackage defines sensor abstractions used by the rest of the system, while `sources` contains concrete sensor drivers and mock hardware. Processing utilities such as filtering and transformation are found under `processing`, and `sensor_source_manager.py` coordinates sensor lifecycles and integrates data pipelines.
