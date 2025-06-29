"""
Controller manager for orchestrating multiple controllers with dependency management.
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable
from collections import deque
from dataclasses import dataclass
import time
import json
from pathlib import Path
import os

from src.controllers.controller_base import (
    ControllerStage,
    ControllerInput,
    ControllerResult,
    ControllerConfig,
    ControllerStatus,
)

# Removed SensorReading import since sensors are not used
from src.utils.log_service import info, error, debug


from src.utils.config_service import (
    get_config_service,
    ConfigurationError,
)

from .controller_registry import CONTROLLER_CLASS_MAP


@dataclass
class ControllerDependency:
    """Represents a dependency between controllers"""

    source_controller_id: str
    target_controller_id: str
    data_mapping: Optional[Dict[str, str]] = None  # Map output keys to input keys


class ControllerManager:
    """Manages multiple controllers with dependency resolution and execution orchestration"""

    def __init__(
        self,
        manager_id: str = "default",
        max_concurrency: Optional[int] = None,
        enable_parallel_execution: Optional[bool] = None,
    ):
        self.manager_id = manager_id
        self._controllers: Dict[str, ControllerStage] = {}
        self._dependencies: List[ControllerDependency] = []
        self._execution_order: List[str] = []
        self._execution_stages: List[List[str]] = []
        self._running = False
        self._processing_stats: Dict[str, Any] = {}
        self._error_handlers: Dict[str, Callable[..., Any]] = {}

        # Concurrency control
        self._controller_locks: Dict[str, asyncio.Lock] = {}
        # Determine max concurrency from config, env or parameter
        limit = max_concurrency
        if limit is None:
            service = get_config_service()
            if service is not None:
                limit = service.get("controller_concurrency_limit", int, None)
        if limit is None:
            limit = int(os.getenv("CONTROLLER_MANAGER_CONCURRENCY_LIMIT", "10"))
        self._execution_semaphore = asyncio.Semaphore(limit)
        self._max_concurrency = limit

        # Determine whether parallel execution is enabled
        par = enable_parallel_execution
        if par is None:
            service = get_config_service()
            if service is not None:
                par = service.get(
                    "controller_manager.parallel_execution", bool, False
                )
        if par is None:
            env = os.getenv("CONTROLLER_MANAGER_PARALLEL_EXECUTION")
            par = str(env).lower() in {"1", "true", "yes"} if env is not None else False
        self._parallel_execution = bool(par)

    def register_controller(self, controller: ControllerStage) -> None:
        """Register a controller with the manager"""
        if controller.controller_id in self._controllers:
            raise ValueError(
                f"Controller {controller.controller_id} already registered"
            )

        self._controllers[controller.controller_id] = controller
        self._controller_locks[controller.controller_id] = asyncio.Lock()

        # Recalculate execution order
        self._calculate_execution_order()

        info(
            "Controller registered",
            controller_id=controller.controller_id,
        )

    def create_controller(self, config: Dict[str, Any]) -> Optional[ControllerStage]:
        """Create a controller instance from configuration dict."""
        if "controller_id" not in config:
            raise ConfigurationError(
                "Controller configuration must include 'controller_id'"
            )
        if "type" not in config:
            raise ConfigurationError("Controller configuration must include 'type'")
        try:
            controller_id = config["controller_id"]
            controller_type = config["type"]
            cfg = ControllerConfig(
                controller_id=controller_id,
                controller_type=controller_type,
                enabled=config.get("enabled", True),
                parameters=config.get("parameters", {}),
                input_sensors=config.get("input_sensors", []),
                input_controllers=config.get("input_controllers", []),
                output_name=config.get("output_name"),
            )

            ctrl_cls = CONTROLLER_CLASS_MAP.get(controller_type)
            if ctrl_cls is None:
                raise ValueError(f"Unknown controller type: {controller_type}")

            return ctrl_cls(controller_id, cfg)

        except Exception as exc:
            error(
                "Failed to create controller from config",
                controller_id=config.get("controller_id"),
                error=str(exc),
            )
        return None

    def add_controller_from_config(
        self, config: Dict[str, Any]
    ) -> Optional[ControllerStage]:
        """Create and register a controller from configuration."""
        try:
            controller = self.create_controller(config)
        except Exception as exc:
            error(f"Failed to create controller: {exc}")
            return None
        if controller is not None:
            self.register_controller(controller)
            return controller
        return None

    def unregister_controller(self, controller_id: str) -> bool:
        """Unregister a controller"""
        if controller_id not in self._controllers:
            return False

        # Remove dependencies
        self._dependencies = [
            dep
            for dep in self._dependencies
            if dep.source_controller_id != controller_id
            and dep.target_controller_id != controller_id
        ]

        # Remove controller
        del self._controllers[controller_id]
        del self._controller_locks[controller_id]

        # Recalculate execution order
        self._calculate_execution_order()

        info(
            "Controller unregistered",
            controller_id=controller_id,
        )
        return True

    def add_dependency(
        self,
        source_id: str,
        target_id: str,
        data_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        """Add a dependency between controllers"""
        if source_id not in self._controllers:
            raise ValueError(f"Source controller {source_id} not registered")
        if target_id not in self._controllers:
            raise ValueError(f"Target controller {target_id} not registered")

        dependency = ControllerDependency(source_id, target_id, data_mapping)
        self._dependencies.append(dependency)

        # Recalculate execution order
        self._calculate_execution_order()

        info(
            "Dependency added",
            source_controller=source_id,
            target_controller=target_id,
        )

    def _calculate_execution_order(self) -> None:
        """Calculate execution order using topological sort"""
        # Build adjacency list
        graph: Dict[str, List[str]] = {cid: [] for cid in self._controllers.keys()}
        in_degree: Dict[str, int] = {cid: 0 for cid in self._controllers.keys()}

        for dep in self._dependencies:
            graph[dep.source_controller_id].append(dep.target_controller_id)
            in_degree[dep.target_controller_id] += 1

        # Topological sort + stage building
        queue = deque(cid for cid, degree in in_degree.items() if degree == 0)
        execution_order: List[str] = []
        stages: List[List[str]] = []

        while queue:
            stage: List[str] = list(queue)
            stages.append(stage)
            next_queue: deque[str] = deque()
            while queue:
                current = queue.popleft()
                execution_order.append(current)
                for neighbor in graph[current]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue

        # Check for cycles
        if len(execution_order) != len(self._controllers):
            remaining = set(self._controllers.keys()) - set(execution_order)
            raise ValueError(
                f"Circular dependency detected involving controllers: {remaining}"
            )

        self._execution_order = execution_order
        self._execution_stages = stages
        debug(
            "Execution order updated",
            manager_id=self.manager_id,
            order=self._execution_order,
            stages=self._execution_stages,
        )

    async def start_all_controllers(self) -> bool:
        """Start all registered controllers"""
        success_count = 0

        for controller_id in self._controllers:
            controller = self._controllers[controller_id]
            if await controller.start():
                success_count += 1
            else:
                error(
                    "Failed to start controller",
                    controller_id=controller_id,
                )

        self._running = success_count > 0
        info(
            "Controllers started",
            manager_id=self.manager_id,
            started=success_count,
            total=len(self._controllers),
        )
        return success_count == len(self._controllers)

    async def stop_all_controllers(self) -> None:
        """Stop all controllers"""
        self._running = False

        tasks = []
        for controller in self._controllers.values():
            tasks.append(controller.stop())

        await asyncio.gather(*tasks, return_exceptions=True)
        info(
            "All controllers stopped",
            manager_id=self.manager_id,
        )

    async def process_data(
        self,
        sensor_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, ControllerResult]:
        """Process sensor data through all controllers in dependency order"""
        if not self._running:
            return {}

        metadata = metadata or {}
        controller_outputs: Dict[str, Any] = {}
        results: Dict[str, ControllerResult] = {}

        start_time = time.time()

        try:
            if not self._parallel_execution:
                async with self._execution_semaphore:
                    for controller_id in self._execution_order:
                        controller = self._controllers[controller_id]

                        if controller.status != ControllerStatus.RUNNING:
                            continue

                        input_data = self._prepare_controller_input(
                            controller_id, sensor_data, controller_outputs, metadata
                        )

                        async with self._controller_locks[controller_id]:
                            result = await controller.process_with_timing(input_data)
                        results[controller_id] = result

                        if result.success and result.data is not None:
                            controller_outputs[controller_id] = result.data
            else:
                for stage in self._execution_stages:
                    async with asyncio.TaskGroup() as tg:
                        for controller_id in stage:
                            controller = self._controllers[controller_id]
                            if controller.status != ControllerStatus.RUNNING:
                                continue

                            tg.create_task(
                                self._run_controller(
                                    controller_id,
                                    sensor_data,
                                    metadata,
                                    controller_outputs,
                                    results,
                                )
                            )

        except Exception as e:
            error(
                "Error in controller processing",
                manager_id=self.manager_id,
                error=str(e),
            )

        # Update statistics
        processing_time = (time.time() - start_time) * 1000
        self._update_processing_stats(processing_time, results)

        return results

    def _prepare_controller_input(
        self,
        controller_id: str,
        sensor_data: Dict[str, Any],
        controller_outputs: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> ControllerInput:
        """Prepare input data for a specific controller"""
        controller = self._controllers[controller_id]
        config = controller.config

        # Filter sensor data based on controller configuration
        filtered_sensor_data = {}
        if config.input_sensors:
            for sensor_id in config.input_sensors:
                if sensor_id in sensor_data:
                    filtered_sensor_data[sensor_id] = sensor_data[sensor_id]
        else:
            # Include all sensor data if no specific sensors configured
            filtered_sensor_data = sensor_data

        # Prepare controller data from dependencies
        controller_data = {}
        for dep in self._dependencies:
            if (
                dep.target_controller_id == controller_id
                and dep.source_controller_id in controller_outputs
            ):
                source_data = controller_outputs[dep.source_controller_id]

                if dep.data_mapping:
                    # Apply data mapping
                    mapped_data = {}
                    for source_key, target_key in dep.data_mapping.items():
                        if source_key in source_data:
                            mapped_data[target_key] = source_data[source_key]
                    controller_data[dep.source_controller_id] = mapped_data
                else:
                    # Use all data
                    controller_data[dep.source_controller_id] = source_data

        # Filter controller data by input_controllers if specified
        if config.input_controllers:
            controller_data = {
                cid: data
                for cid, data in controller_data.items()
                if cid in config.input_controllers
            }

        return ControllerInput(
            sensor_data=filtered_sensor_data,
            controller_data=controller_data,
            timestamp=time.time(),
            metadata=metadata,
        )

    async def _run_controller(
        self,
        controller_id: str,
        sensor_data: Dict[str, Any],
        metadata: Dict[str, Any],
        controller_outputs: Dict[str, Any],
        results: Dict[str, ControllerResult],
    ) -> None:
        """Execute a single controller respecting locks and concurrency limits."""
        input_data = self._prepare_controller_input(
            controller_id, sensor_data, controller_outputs, metadata
        )

        async with self._execution_semaphore:
            async with self._controller_locks[controller_id]:
                result = await self._controllers[controller_id].process_with_timing(
                    input_data
                )

        results[controller_id] = result
        if result.success and result.data is not None:
            controller_outputs[controller_id] = result.data

    def _update_processing_stats(
        self, total_time_ms: float, results: Dict[str, ControllerResult]
    ) -> None:
        """Update processing statistics"""
        self._processing_stats = {
            "total_processing_time_ms": total_time_ms,
            "controllers_processed": len(results),
            "successful_controllers": sum(1 for r in results.values() if r.success),
            "failed_controllers": sum(1 for r in results.values() if not r.success),
            "last_update": time.time(),
            "individual_stats": {
                cid: result.processing_time_ms
                for cid, result in results.items()
                if result.processing_time_ms is not None
            },
        }

    def get_controller_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all controllers"""
        controller_stats = {}
        for controller_id, controller in self._controllers.items():
            controller_stats[controller_id] = controller.get_stats()

        return {
            "manager_id": self.manager_id,
            "running": self._running,
            "total_controllers": len(self._controllers),
            "execution_order": self._execution_order,
            "dependencies": [
                {
                    "source": dep.source_controller_id,
                    "target": dep.target_controller_id,
                    "has_mapping": dep.data_mapping is not None,
                }
                for dep in self._dependencies
            ],
            "processing_stats": self._processing_stats,
            "controller_stats": controller_stats,
        }

    def get_controller_outputs(self) -> Dict[str, Any]:
        """Get latest outputs from all controllers"""
        outputs = {}
        for controller_id, controller in self._controllers.items():
            output = controller.get_output()
            if output is not None:
                outputs[controller_id] = output
        return outputs

    def get_controller(self, controller_id: str) -> Optional[ControllerStage]:
        """Get a specific controller by ID"""
        return self._controllers.get(controller_id)

    def list_controllers(self) -> List[str]:
        """Get list of all registered controller IDs"""
        return list(self._controllers.keys())

    async def reset_controller(self, controller_id: str) -> bool:
        """Reset a specific controller"""
        if controller_id not in self._controllers:
            return False

        controller = self._controllers[controller_id]

        try:
            await controller.stop()
            await asyncio.sleep(0.1)  # Brief pause
            return await controller.start()
        except Exception as e:
            error(
                "Error resetting controller",
                controller_id=controller_id,
                error=str(e),
            )
            return False

    def save_configuration(self, config_path: Path) -> bool:
        """Save controller configuration to file"""
        try:
            config_data = {
                "manager_id": self.manager_id,
                "controllers": {
                    cid: {
                        "controller_type": controller.config.controller_type,
                        "config": {
                            "controller_id": controller.config.controller_id,
                            "controller_type": controller.config.controller_type,
                            "enabled": controller.config.enabled,
                            "parameters": controller.config.parameters,
                            "input_sensors": controller.config.input_sensors,
                            "input_controllers": controller.config.input_controllers,
                            "output_name": controller.config.output_name,
                        },
                    }
                    for cid, controller in self._controllers.items()
                },
                "dependencies": [
                    {
                        "source": dep.source_controller_id,
                        "target": dep.target_controller_id,
                        "data_mapping": dep.data_mapping,
                    }
                    for dep in self._dependencies
                ],
            }

            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=2)

            info(
                "Controller configuration saved",
                manager_id=self.manager_id,
                path=str(config_path),
            )
            return True

        except Exception as e:
            error(
                "Error saving controller configuration",
                manager_id=self.manager_id,
                path=str(config_path),
                error=str(e),
            )
            return False


# Factory functions for creating controller managers with common configurations


def create_cvd_controller_manager() -> ControllerManager:
    """Create a controller manager configured for CVD tracking.

    The manager loads all controllers from the active
    :class:`ConfigurationService` and wires the default pipeline. By
    convention ``camera_capture`` provides frames to ``motion_detection``.
    If no configuration service is available a minimal setup with these two
    controllers is created so the application remains usable.
    """

    manager = ControllerManager("cvd_tracking")
    service = get_config_service()
    if service:
        # Load all controller definitions from the configuration service
        for _, cfg in service.get_controller_configs():
            manager.add_controller_from_config(cfg)
        # Wire the standard camera -> motion detection pipeline when both
        # controllers are present in the configuration. Motion detection
        # consumes the captured frame as its ``image`` input.
        if (
            "camera_capture" in manager._controllers
            and "motion_detection" in manager._controllers
        ):
            md_ctrl = manager._controllers["motion_detection"]
            md_ctrl.config.input_controllers = ["camera_capture"]
            manager.add_dependency(
                "camera_capture",
                "motion_detection",
                data_mapping={"frame": "image"},
            )
    else:
        # No configuration service found: create a minimal pipeline with
        # ``camera_capture`` feeding ``motion_detection`` so the application
        # can still run with sensible defaults.
        cam_cfg = ControllerConfig(
            controller_id="camera_capture",
            controller_type="camera_capture",
            parameters={"device_index": 0},
        )
        motion_cfg = ControllerConfig(
            controller_id="motion_detection",
            controller_type="motion_detection",
            parameters={"device_index": 0},
        )
        cam_cls = CONTROLLER_CLASS_MAP.get("camera_capture")
        motion_cls = CONTROLLER_CLASS_MAP.get("motion_detection")
        if not cam_cls or not motion_cls:
            raise RuntimeError("Required controller classes missing in registry")
        cam_ctrl = cam_cls("camera_capture", cam_cfg)
        motion_ctrl = motion_cls("motion_detection", motion_cfg)
        manager.register_controller(cam_ctrl)
        manager.register_controller(motion_ctrl)
        motion_ctrl.config.input_controllers = ["camera_capture"]
        manager.add_dependency(
            "camera_capture",
            "motion_detection",
            data_mapping={"frame": "image"},
        )

    return manager


def create_test_controller_manager() -> ControllerManager:
    """Create a simple controller manager for testing"""
    return ControllerManager("test")
