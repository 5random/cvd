"""
Experiment Management Service for CVD Tracker

This module provides comprehensive experiment management functionality including:
- Experiment configuration and lifecycle management
- Data collection from sensors and controllers
- Structured data storage and archival
- Integration with all existing services (sensors, controllers, data saving, compression)
- Audit logging and state tracking
- Future support for G-Code and script execution
"""

import asyncio
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Callable
import shutil
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextlib import asynccontextmanager
import threading

from program.src.utils.config_service import (
    get_config_service,
    ConfigurationService,
    ConfigurationError,
)
from src.data_handler.sources.sensor_source_manager import SensorManager
from src.utils.data_utils.data_saver import DataSaver
from src.data_handler.interface.sensor_interface import SensorReading, SensorStatus
from src.utils.data_utils.compression_service import (
    get_compression_service,
    CompressionError,
)
from src.utils.data_utils.file_management_service import FileMaintenanceService
from program.src.utils.log_service import info, warning, error, debug
from src.controllers.controller_manager import ControllerManager
from src.utils.concurrency.async_utils import (
    AsyncTaskManager,
    install_signal_handlers,
    TaskHandle,
)
from src.utils.concurrency.thread_pool import get_thread_pool_manager, ThreadPoolType


class ExperimentState(Enum):
    """States of an experiment lifecycle"""

    IDLE = "idle"
    CONFIGURING = "configuring"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExperimentPhase(Enum):
    """Phases within a running experiment"""

    INITIALIZATION = "initialization"
    WARMUP = "warmup"
    PROCESSING = "processing"
    COOLDOWN = "cooldown"
    CLEANUP = "cleanup"


@dataclass
class ExperimentConfig:
    """Configuration for an experiment"""

    name: str
    description: str = ""
    duration_minutes: Optional[int] = None  # None = unlimited
    auto_start_sensors: bool = True
    auto_start_controllers: bool = True
    sensor_ids: List[str] = field(default_factory=list)  # Empty = all sensors
    controller_ids: List[str] = field(default_factory=list)  # Empty = all controllers
    data_collection_interval_ms: int = 1000
    auto_compress: bool = True
    custom_parameters: Dict[str, Any] = field(default_factory=dict)
    script_path: Optional[str] = None  # Future: G-Code or Python scripts
    phases: List[Dict[str, Any]] = field(
        default_factory=list
    )  # Future: phase definitions


@dataclass
class ExperimentResult:
    """Result data from a completed experiment"""

    experiment_id: str
    name: str
    state: ExperimentState
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    data_points_collected: int = 0
    sensor_readings_count: int = 0
    controller_outputs_count: int = 0
    errors_count: int = 0
    warnings_count: int = 0
    result_directory: Optional[Path] = None
    compressed_archive: Optional[Path] = None
    summary: Dict[str, Any] = field(default_factory=dict)
    raw_data_dir: Optional[Path] = None
    processed_data_dir: Optional[Path] = None


@dataclass
class ExperimentDataPoint:
    """Single data point collected during experiment"""

    timestamp: float
    experiment_id: Optional[str]
    phase: ExperimentPhase
    sensor_readings: Dict[str, SensorReading] = field(default_factory=dict)
    controller_outputs: Dict[str, Any] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)


class ExperimentManager:
    """
    Central manager for experiment lifecycle and data collection.

    Integrates with all existing services:
    - SensorManager for data collection
    - ControllerManager for equipment control
    - DataSaver for structured storage
    - CompressionService for archival
    - ConfigService for settings
    - LogService for audit trails
    """

    def __init__(
        self,
        config_service: ConfigurationService,
        sensor_manager: Optional[SensorManager] = None,
        controller_manager: Optional[ControllerManager] = None,
        data_saver: Optional[DataSaver] = None,
        *,
        auto_install_signal_handlers: bool = True,
    ):
        """
        Initialize experiment manager with service dependencies.

        Args:
            config_service: Configuration service for settings
            sensor_manager: Optional sensor manager for data collection
            controller_manager: Optional controller manager for equipment control
            data_saver: Optional data saver for storage
            auto_install_signal_handlers: Install SIGINT/SIGTERM handlers if an
                event loop is running
        """
        self.config_service = config_service
        self.sensor_manager = sensor_manager
        self.controller_manager = controller_manager
        self.data_saver = data_saver
        # Initialize compression and maintenance service
        self.compression_service = get_compression_service()
        threshold = self.config_service.get(
            "data_storage.compression.threshold_bytes", int, 10 * 1024 * 1024
        )
        max_age = self.config_service.get(
            "data_storage.compression.max_file_age_seconds", int, 24 * 3600
        )
        self._maintenance_service = FileMaintenanceService(
            compression_service=self.compression_service,
            compression_threshold_bytes=threshold,
            max_file_age_seconds=max_age,
        )

        # Load experiment configuration from config.json
        self._load_experiment_config()

        # Current experiment state
        self._current_experiment: Optional[str] = None
        self._current_state = ExperimentState.IDLE
        self._current_phase = ExperimentPhase.INITIALIZATION
        self._experiment_configs: Dict[str, ExperimentConfig] = {}
        self._experiment_results: Dict[str, ExperimentResult] = {}

        # Data collection
        self._data_collection_handle: Optional[TaskHandle[Any]] = None
        self._collected_data: List[ExperimentDataPoint] = []
        self._collection_lock = threading.Lock()

        # Event callbacks
        self._state_change_callbacks: List[
            Callable[[ExperimentState, ExperimentState], None]
        ] = []
        self._data_callbacks: List[Callable[[ExperimentDataPoint], None]] = []

        # Shutdown flag and async task manager
        self._shutdown_event = asyncio.Event()
        self._task_manager = AsyncTaskManager("ExperimentManager")

        if auto_install_signal_handlers:
            try:
                install_signal_handlers(self._task_manager)
            except RuntimeError:
                # Called before an event loop exists; caller can invoke
                # ``install_signal_handlers`` later once the loop is running.
                warning("no_event_loop", msg="Signal handlers not installed yet")

        info("ExperimentManager initialized")

    def _load_experiment_config(self) -> None:
        """Load experiment configuration from config service"""
        try:
            # Load legacy experiment config (auto_zip, naming, state messages)
            exp_config = self.config_service.get("experiment", dict, {})
            self.auto_zip = exp_config.get("auto_zip", True)
            self.naming_pattern = exp_config.get("naming_pattern", "%Y-%m-%dT%H-%M-%S")
            self.state_messages = exp_config.get(
                "state_output",
                ["Experiment fehlgeschlagen", "Experiment läuft erfolgreich"],
            )
            # Load new experiments storage paths from data_storage
            storage_cfg = (
                self.config_service.get(
                    "data_storage.storage_paths.experiments", dict, {}
                )
                or {}
            )
            self.experiments_base_dir = Path(
                storage_cfg.get("base", "data/experiments")
            )
            results_cfg = storage_cfg.get("results", {}) or {}
            self.experiments_results_raw = results_cfg.get("raw", "results/raw")
            self.experiments_results_processed = results_cfg.get(
                "processed", "results/processed"
            )
            # Ensure base experiment directory exists
            self.experiments_base_dir.mkdir(parents=True, exist_ok=True)
            debug(
                f"Experiment config loaded: base_dir={self.experiments_base_dir}, raw={self.experiments_results_raw}, processed={self.experiments_results_processed}, auto_zip={self.auto_zip}"
            )
        except (ConfigurationError, json.JSONDecodeError, OSError) as e:
            error(f"Failed to load experiment configuration: {e}")
            # Fallback defaults
            self.auto_zip = True
            self.naming_pattern = "%Y-%m-%dT%H-%M-%S"
            self.state_messages = [
                "Experiment fehlgeschlagen",
                "Experiment läuft erfolgreich",
            ]
            self.experiments_base_dir = Path("data/experiments")
            self.experiments_results_raw = "results/raw"
            self.experiments_results_processed = "results/processed"
        except Exception as e:
            error(f"Unexpected error loading experiment configuration: {e}")
            raise

    def create_experiment(self, config: ExperimentConfig) -> str:
        """
        Create a new experiment with given configuration.

        Args:
            config: Experiment configuration

        Returns:
            Unique experiment ID
        """
        # Generate unique experiment ID with timestamp
        timestamp = datetime.now()
        experiment_id = f"{config.name}_{timestamp.strftime(self.naming_pattern)}"

        # Store configuration
        self._experiment_configs[experiment_id] = config

        # Create result tracking
        result = ExperimentResult(
            experiment_id=experiment_id,
            name=config.name,
            state=ExperimentState.IDLE,
            start_time=timestamp,
        )
        self._experiment_results[experiment_id] = result

        info(f"Created experiment: {experiment_id}")
        return experiment_id

    def get_experiment_config(self, experiment_id: str) -> Optional[ExperimentConfig]:
        """Get configuration for an experiment"""
        return self._experiment_configs.get(experiment_id)

    def get_experiment_result(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Get result data for an experiment"""
        return self._experiment_results.get(experiment_id)

    def list_experiments(self) -> List[str]:
        """List all experiment IDs"""
        return list(self._experiment_configs.keys())

    def get_current_experiment(self) -> Optional[str]:
        """Get currently active experiment ID"""
        return self._current_experiment

    def get_current_state(self) -> ExperimentState:
        """Get current experiment state"""
        return self._current_state

    def get_current_phase(self) -> ExperimentPhase:
        """Get current experiment phase"""
        return self._current_phase

    async def start_experiment(self, experiment_id: str) -> bool:
        """
        Start an experiment.

        Args:
            experiment_id: ID of experiment to start

        Returns:
            True if started successfully
        """
        if experiment_id not in self._experiment_configs:
            error(f"Experiment not found: {experiment_id}")
            return False

        if self._current_state != ExperimentState.IDLE:
            error(f"Cannot start experiment while in state: {self._current_state}")
            return False

        try:
            config = self._experiment_configs[experiment_id]
            result = self._experiment_results[experiment_id]

            # Update state
            await self._change_state(ExperimentState.STARTING)
            self._current_experiment = experiment_id

            # Create experiment directory structure under configured paths
            exp_base = self.experiments_base_dir / experiment_id
            # Create experiment folder structure: metadata, results/raw, results/processed
            metadata_dir = exp_base / "metadata"
            raw_dir = exp_base / self.experiments_results_raw
            processed_dir = exp_base / self.experiments_results_processed
            # Ensure directories exist
            metadata_dir.mkdir(parents=True, exist_ok=True)
            raw_dir.mkdir(parents=True, exist_ok=True)
            processed_dir.mkdir(parents=True, exist_ok=True)
            # Store base dir for metadata writes
            result.result_directory = metadata_dir
            # Also keep references to raw/processed for later use if needed
            result.raw_data_dir = raw_dir
            result.processed_data_dir = processed_dir

            # Initialize data collection
            self._collected_data.clear()

            # Start sensors if configured
            if config.auto_start_sensors and self.sensor_manager:
                await self._start_sensors(config.sensor_ids)

            # Start controllers if configured
            if config.auto_start_controllers and self.controller_manager:
                await self._start_controllers(config.controller_ids)

            # Start data collection
            # Schedule data collection loop via AsyncTaskManager
            self._data_collection_handle = self._task_manager.create_task(
                self._data_collection_loop(self._experiment_configs[experiment_id]),
                task_id="data_collect",
            )
            info(f"Data collection loop started for experiment {experiment_id}")

            # Update state to running
            await self._change_state(ExperimentState.RUNNING)
            result.start_time = datetime.now()

            info(f"Started experiment: {experiment_id}")

            # Schedule automatic stop if duration is set
            if config.duration_minutes:
                # schedule automatic stop via task manager
                self._task_manager.create_task(
                    self._auto_stop_experiment(config.duration_minutes),
                    task_id="auto_stop",
                )

            return True

        except (RuntimeError, OSError) as e:
            error(f"Failed to start experiment {experiment_id}: {e}")
            await self._change_state(ExperimentState.FAILED)
            return False
        except Exception as e:
            error(f"Unexpected error starting experiment {experiment_id}: {e}")
            await self._change_state(ExperimentState.FAILED)
            raise

    async def stop_experiment(self) -> bool:
        """
        Stop the currently running experiment.

        Returns:
            True if stopped successfully
        """
        if self._current_state not in [ExperimentState.RUNNING, ExperimentState.PAUSED]:
            warning("No experiment is currently running")
            return False

        try:
            await self._change_state(ExperimentState.STOPPING)

            # Stop data collection
            if self._data_collection_handle:
                # cancel and wait for data collection task
                self._data_collection_handle.cancel()
                await self._data_collection_handle.wait()
                self._data_collection_handle = None

            # Finalize experiment
            await self._finalize_experiment()

            info(f"Stopped experiment: {self._current_experiment}")
            return True

        except (RuntimeError, OSError) as e:
            error(f"Failed to stop experiment: {e}")
            await self._change_state(ExperimentState.FAILED)
            return False
        except Exception as e:
            error(f"Unexpected error stopping experiment: {e}")
            await self._change_state(ExperimentState.FAILED)
            raise

    async def pause_experiment(self) -> bool:
        """
        Pause the currently running experiment.

        Returns:
            True if paused successfully
        """
        if self._current_state != ExperimentState.RUNNING:
            warning("Can only pause a running experiment")
            return False

        try:
            await self._change_state(ExperimentState.PAUSED)
            info(f"Paused experiment: {self._current_experiment}")
            return True

        except RuntimeError as e:
            error(f"Failed to pause experiment: {e}")
            return False
        except Exception as e:
            error(f"Unexpected error pausing experiment: {e}")
            raise

    async def resume_experiment(self) -> bool:
        """
        Resume a paused experiment.

        Returns:
            True if resumed successfully
        """
        if self._current_state != ExperimentState.PAUSED:
            warning("Can only resume a paused experiment")
            return False

        try:
            await self._change_state(ExperimentState.RUNNING)
            info(f"Resumed experiment: {self._current_experiment}")
            return True

        except RuntimeError as e:
            error(f"Failed to resume experiment: {e}")
            return False
        except Exception as e:
            error(f"Unexpected error resuming experiment: {e}")
            raise

    async def cancel_experiment(self) -> bool:
        """
        Cancel the current experiment without saving results.

        Returns:
            True if cancelled successfully
        """
        if self._current_state == ExperimentState.IDLE:
            warning("No experiment to cancel")
            return False

        try:
            await self._change_state(ExperimentState.CANCELLED)

            # Stop data collection
            if self._data_collection_handle:
                # cancel and wait for data collection task
                self._data_collection_handle.cancel()
                await self._data_collection_handle.wait()
                self._data_collection_handle = None

            # Reset state
            self._current_experiment = None
            await self._change_state(ExperimentState.IDLE)

            info("Cancelled current experiment")
            return True

        except RuntimeError as e:
            error(f"Failed to cancel experiment: {e}")
            return False
        except Exception as e:
            error(f"Unexpected error cancelling experiment: {e}")
            raise

    async def _start_sensors(self, sensor_ids: List[str]) -> None:
        """Start specified sensors or all if empty list"""
        if not self.sensor_manager:
            warning("No sensor manager available")
            return

        if not sensor_ids:
            # Start all configured sensors
            await self.sensor_manager.start_all_configured_sensors()
        else:
            # Start specific sensors
            for sensor_id in sensor_ids:
                await self.sensor_manager.start_sensor(sensor_id)

    async def _start_controllers(self, controller_ids: List[str]) -> None:
        """Start specified controllers or all if empty list"""
        if not self.controller_manager:
            warning("No controller manager available")
            return

        try:
            if not controller_ids:
                # Start every registered controller
                success = await self.controller_manager.start_all_controllers()
                if not success:
                    warning("Some controllers failed to start")
                return

            # Start specified controllers individually
            for controller_id in controller_ids:
                controller = self.controller_manager.get_controller(controller_id)
                if not controller:
                    warning(f"Controller not found: {controller_id}")
                    continue

                try:
                    started = await controller.start()
                    if not started:
                        warning(f"Failed to start controller {controller_id}")
                except RuntimeError as exc:
                    error(f"Error starting controller {controller_id}: {exc}")
                except Exception as exc:
                    error(f"Unexpected error starting controller {controller_id}: {exc}")
                    raise

        except RuntimeError as e:
            error(f"Failed to start controllers: {e}")
        except Exception as e:
            error(f"Unexpected error starting controllers: {e}")
            raise

    async def _data_collection_loop(self, config: ExperimentConfig) -> None:
        """Main data collection loop for the experiment"""
        interval = config.data_collection_interval_ms / 1000.0

        debug(f"Starting data collection loop with interval {interval}s")

        try:
            while not self._shutdown_event.is_set():
                if self._current_state == ExperimentState.RUNNING:
                    await self._collect_data_point()

                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            debug("Data collection loop cancelled")
        except RuntimeError as e:
            error(f"Error in data collection loop: {e}")
            await self._change_state(ExperimentState.FAILED)
        except Exception as e:
            error(f"Unexpected error in data collection loop: {e}")
            await self._change_state(ExperimentState.FAILED)
            raise

    async def _collect_data_point(self) -> None:
        """Collect a single data point from all sources"""
        try:
            data_point = ExperimentDataPoint(
                timestamp=datetime.now().timestamp(),
                experiment_id=self._current_experiment,
                phase=self._current_phase,
            )

            # Collect sensor readings
            if self.sensor_manager:
                sensor_readings = self.sensor_manager.get_latest_readings()
                data_point.sensor_readings = sensor_readings

            # Collect controller outputs
            if self.controller_manager:
                try:
                    outputs = self.controller_manager.get_controller_outputs()
                    data_point.controller_outputs = outputs
                except Exception as exc:
                    warning(f"Failed to get controller outputs: {exc}")
                    data_point.controller_outputs = {}

            # Store data point
            with self._collection_lock:
                self._collected_data.append(data_point)

            # Save to file immediately if data_saver available
            if self.data_saver and self._current_experiment:
                await self._save_data_point(data_point)

            # Notify callbacks
            for callback in self._data_callbacks:
                try:
                    callback(data_point)
                except Exception as e:
                    warning(f"Error in data callback: {e}")

            # Update statistics
            if self._current_experiment in self._experiment_results:
                result = self._experiment_results[self._current_experiment]
                result.data_points_collected += 1
                result.sensor_readings_count += len(data_point.sensor_readings)
                result.controller_outputs_count += len(data_point.controller_outputs)

        except (RuntimeError, OSError) as e:
            error(f"Failed to collect data point: {e}")
            if self._current_experiment in self._experiment_results:
                self._experiment_results[self._current_experiment].errors_count += 1
        except Exception as e:
            error(f"Unexpected error collecting data point: {e}")
            if self._current_experiment in self._experiment_results:
                self._experiment_results[self._current_experiment].errors_count += 1
            raise

    async def _save_data_point(self, data_point: ExperimentDataPoint) -> None:
        """Save a data point to storage"""
        try:
            # Save sensor readings using DataSaver
            for sensor_id, reading in data_point.sensor_readings.items():
                # Create a modified reading with experiment context
                exp_reading = SensorReading(
                    sensor_id=f"{data_point.experiment_id or 'unknown'}_{sensor_id}",
                    value=reading.value,
                    timestamp=data_point.timestamp,
                    status=reading.status,
                    error_message=reading.error_message,
                    metadata={
                        **reading.metadata,
                        "experiment_id": data_point.experiment_id,
                        "experiment_phase": data_point.phase.value,
                        "original_sensor_id": sensor_id,
                    },
                )
                if self.data_saver:
                    self.data_saver.save(exp_reading, category="raw")

            # Save experiment-specific summary file
            await self._save_experiment_summary(data_point)

        except OSError as e:
            error(f"Failed to save data point: {e}")
        except Exception as e:
            error(f"Unexpected error saving data point: {e}")
            raise

    async def _save_experiment_summary(self, data_point: ExperimentDataPoint) -> None:
        """Save experiment summary data to CSV"""
        if not self._current_experiment:
            return

        result = self._experiment_results[self._current_experiment]
        if not result.result_directory:
            return

        summary_file = result.result_directory / "experiment_summary.csv"

        # Check if file exists to write header
        write_header = not summary_file.exists()

        try:
            with open(summary_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                if write_header:
                    writer.writerow(
                        [
                            "timestamp",
                            "phase",
                            "sensor_count",
                            "controller_count",
                            "valid_sensors",
                            "error_sensors",
                            "total_data_points",
                        ]
                    )

                valid_sensors = sum(
                    1
                    for r in data_point.sensor_readings.values()
                    if r.status == SensorStatus.OK
                )
                error_sensors = sum(
                    1
                    for r in data_point.sensor_readings.values()
                    if r.status != SensorStatus.OK
                )

                writer.writerow(
                    [
                        data_point.timestamp,
                        data_point.phase.value,
                        len(data_point.sensor_readings),
                        len(data_point.controller_outputs),
                        valid_sensors,
                        error_sensors,
                        result.data_points_collected,
                    ]
                )

        except (OSError, csv.Error) as e:
            error(f"Failed to save experiment summary: {e}")
        except Exception as e:
            error(f"Unexpected error saving experiment summary: {e}")
            raise

    async def _finalize_experiment(self) -> None:
        """Finalize the current experiment and save results.

        The experiment result is marked as ``COMPLETED`` while the manager
        returns to ``IDLE`` to allow starting a new experiment immediately.
        """
        if not self._current_experiment:
            return

        try:
            result = self._experiment_results[self._current_experiment]
            result.end_time = datetime.now()

            if result.start_time and result.end_time:
                result.duration_seconds = (
                    result.end_time - result.start_time
                ).total_seconds()

            # Save final experiment metadata
            await self._save_experiment_metadata(result)

            # Compress results if enabled
            if self.auto_zip and self.compression_service and result.result_directory:
                await self._compress_experiment_results(result)

            # Update state and reset manager
            await self._change_state(ExperimentState.COMPLETED)
            self._current_experiment = None
            await self._change_state(ExperimentState.IDLE)

            info(f"Finalized experiment: {result.experiment_id}")

        except (OSError, RuntimeError, CompressionError) as e:
            error(f"Failed to finalize experiment: {e}")
            await self._change_state(ExperimentState.FAILED)
        except Exception as e:
            error(f"Unexpected error finalizing experiment: {e}")
            await self._change_state(ExperimentState.FAILED)
            raise

    async def _save_experiment_metadata(self, result: ExperimentResult) -> None:
        """Save experiment metadata to JSON file"""
        if not result.result_directory:
            return

        metadata_file = result.result_directory / "experiment_metadata.json"

        try:
            # Prepare metadata
            metadata = {
                "experiment_id": result.experiment_id,
                "name": result.name,
                "state": result.state.value,
                "start_time": (
                    result.start_time.isoformat() if result.start_time else None
                ),
                "end_time": result.end_time.isoformat() if result.end_time else None,
                "duration_seconds": result.duration_seconds,
                "statistics": {
                    "data_points_collected": result.data_points_collected,
                    "sensor_readings_count": result.sensor_readings_count,
                    "controller_outputs_count": result.controller_outputs_count,
                    "errors_count": result.errors_count,
                    "warnings_count": result.warnings_count,
                },
                "configuration": (
                    asdict(self._experiment_configs[result.experiment_id])
                    if result.experiment_id in self._experiment_configs
                    else {}
                ),
                "summary": result.summary,
            }

            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            debug(f"Saved experiment metadata to {metadata_file}")

        except (OSError, TypeError, json.JSONDecodeError) as e:
            error(f"Failed to save experiment metadata: {e}")
        except Exception as e:
            error(f"Unexpected error saving experiment metadata: {e}")
            raise

    async def _compress_experiment_results(self, result: ExperimentResult) -> None:
        """Compress experiment results directory"""
        if not self.compression_service or not result.result_directory:
            return

        try:
            # Compress experiment results using maintenance service
            compressed_files = self._maintenance_service.compress_directory(
                result.result_directory,
                pattern="*",
                data_type="experiment",
                recursive=True,
            )

            if compressed_files:
                result.compressed_archive = compressed_files[0]
                info(f"Compressed experiment results: {result.compressed_archive}")

        except (CompressionError, OSError) as e:
            error(f"Failed to compress experiment results: {e}")
        except Exception as e:
            error(f"Unexpected error compressing experiment results: {e}")
            raise

    async def _auto_stop_experiment(self, duration_minutes: int) -> None:
        """Automatically stop experiment after specified duration"""
        try:
            await asyncio.sleep(duration_minutes * 60)

            if self._current_state == ExperimentState.RUNNING:
                info(f"Auto-stopping experiment after {duration_minutes} minutes")
                await self.stop_experiment()

        except asyncio.CancelledError:
            pass
        except RuntimeError as e:
            error(f"Error in auto-stop: {e}")
        except Exception as e:
            error(f"Unexpected error in auto-stop: {e}")
            raise

    async def _change_state(self, new_state: ExperimentState) -> None:
        """Change experiment state and notify callbacks"""
        old_state = self._current_state
        self._current_state = new_state

        # Keep result state in sync with manager state
        if (
            self._current_experiment
            and self._current_experiment in self._experiment_results
        ):
            self._experiment_results[self._current_experiment].state = new_state

        # Log state change
        info(f"Experiment state changed: {old_state.value} -> {new_state.value}")

        # Notify callbacks
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                warning(f"Error in state change callback: {e}")
                raise

    def add_state_change_callback(
        self, callback: Callable[[ExperimentState, ExperimentState], None]
    ) -> None:
        """Add callback for state changes"""
        self._state_change_callbacks.append(callback)

    def add_data_callback(
        self, callback: Callable[[ExperimentDataPoint], None]
    ) -> None:
        """Add callback for new data points"""
        self._data_callbacks.append(callback)

    def get_experiment_statistics(self, experiment_id: str) -> Dict[str, Any]:
        """Get statistics for an experiment"""
        if experiment_id not in self._experiment_results:
            return {}

        result = self._experiment_results[experiment_id]
        return {
            "experiment_id": experiment_id,
            "state": result.state.value,
            "duration_seconds": result.duration_seconds,
            "data_points_collected": result.data_points_collected,
            "sensor_readings_count": result.sensor_readings_count,
            "controller_outputs_count": result.controller_outputs_count,
            "errors_count": result.errors_count,
            "warnings_count": result.warnings_count,
            "result_directory": (
                str(result.result_directory) if result.result_directory else None
            ),
            "compressed_archive": (
                str(result.compressed_archive) if result.compressed_archive else None
            ),
        }

    def delete_experiment(self, experiment_id: str) -> bool:
        """Delete experiment configuration and stored results."""
        if experiment_id not in self._experiment_configs:
            return False

        if self._current_experiment == experiment_id and self._current_state not in [
            ExperimentState.COMPLETED,
            ExperimentState.FAILED,
            ExperimentState.CANCELLED,
            ExperimentState.IDLE,
        ]:
            warning("Cannot delete experiment while it is active")
            return False

        try:
            self._experiment_configs.pop(experiment_id, None)
            result = self._experiment_results.pop(experiment_id, None)

            exp_dir = self.experiments_base_dir / experiment_id
            if exp_dir.exists():
                shutil.rmtree(exp_dir, ignore_errors=True)

            info(f"Deleted experiment {experiment_id}")
            return True
        except (OSError, RuntimeError) as e:  # pragma: no cover - best effort
            error(f"Failed to delete experiment {experiment_id}: {e}")
            return False
        except Exception as e:
            error(f"Unexpected error deleting experiment {experiment_id}: {e}")
            raise

    async def cleanup(self) -> None:
        """Cleanup resources and stop any running experiments"""
        try:
            # Signal shutdown
            self._shutdown_event.set()

            # Stop current experiment if running
            if self._current_state in [ExperimentState.RUNNING, ExperimentState.PAUSED]:
                await self.stop_experiment()

            # Graceful stop of all running tasks
            await self._task_manager.stop_all_tasks()
            info("ExperimentManager cleanup complete")

        except RuntimeError as e:
            error(f"Error during ExperimentManager cleanup: {e}")
        except Exception as e:
            error(f"Unexpected error during ExperimentManager cleanup: {e}")
            raise


# Global experiment manager instance
_experiment_manager_instance: Optional[ExperimentManager] = None


def get_experiment_manager() -> Optional[ExperimentManager]:
    """Get the global experiment manager instance"""
    return _experiment_manager_instance


def set_experiment_manager(manager: ExperimentManager) -> None:
    """Set the global experiment manager instance"""
    global _experiment_manager_instance
    _experiment_manager_instance = manager


# Convenience functions for common operations
async def create_and_start_experiment(
    name: str,
    description: str = "",
    duration_minutes: Optional[int] = None,
    sensor_ids: Optional[List[str]] = None,
    controller_ids: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Convenience function to create and start an experiment.

    Args:
        name: Experiment name
        description: Optional description
        duration_minutes: Optional duration limit
        sensor_ids: Optional list of specific sensors to use
        controller_ids: Optional list of specific controllers to use

    Returns:
        Experiment ID if successful, None otherwise
    """
    manager = get_experiment_manager()
    if not manager:
        error("No experiment manager available")
        return None

    try:
        config = ExperimentConfig(
            name=name,
            description=description,
            duration_minutes=duration_minutes,
            sensor_ids=sensor_ids or [],
            controller_ids=controller_ids or [],
        )

        experiment_id = manager.create_experiment(config)
        success = await manager.start_experiment(experiment_id)

        if success:
            return experiment_id
        else:
            return None

    except (RuntimeError, OSError) as e:
        error(f"Failed to create and start experiment: {e}")
        return None
    except Exception as e:
        error(f"Unexpected error creating experiment: {e}")
        raise


async def stop_current_experiment() -> bool:
    """Convenience function to stop the current experiment"""
    manager = get_experiment_manager()
    if not manager:
        error("No experiment manager available")
        return False

    return await manager.stop_experiment()
