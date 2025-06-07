"""
Application container for dependency injection and service orchestration.
"""
# pylint: disable=too-many-instance-attributes,import-outside-toplevel
# pylint: disable=broad-exception-caught,protected-access,
# pylint: disable=attribute-defined-outside-init
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import Future
from src.utils.log_utils.log_service import info, error
from src.utils.concurrency.thread_pool import (
    ManagedThreadPool,
    ThreadPoolType,
)

from src.utils.config_utils.config_service import (
    ConfigurationService,
    set_config_service,
)
from src.data_handler.sources.sensor_source_manager import SensorManager
from src.utils.data_utils.data_saver import DataSaver
from src.data_handler.processing.pipeline.pipeline import (
    create_temperature_pipeline,
)
from src.gui.application import WebApplication
from src.utils.data_utils.compression_service import (
    CompressionService,
    set_compression_service,
)
from src.utils.alert_system_utils.email_alert_service import (
    EmailAlertService,
    set_email_alert_service,
)

@dataclass
class ApplicationContainer:
    """Container for all application services with dependency injection"""
    config_service: ConfigurationService
    sensor_manager: SensorManager
    data_saver: DataSaver
    web_application: 'WebApplication'
    compression_service: CompressionService
    email_alert_service: EmailAlertService
    _background_tasks: List[Tuple[ManagedThreadPool, Future]] = field(
        default_factory=list
    )
    _shutdown_requested: bool = field(default=False)

    @classmethod
    def create(cls, config_dir: Path) -> 'ApplicationContainer':
        """Create application container with all services

        Args:
            config_dir: Directory containing configuration files

        Returns:
            Initialized ApplicationContainer
        """
        try:
            # Initialize configuration service
            config_service = ConfigurationService(
                config_path=config_dir / "config.json",
                default_config_path=config_dir / "default_config.json"
            )
            # Set global config service for backward compatibility
            set_config_service(config_service)

            # Initialize compression service
            compression_service = CompressionService()
            set_compression_service(compression_service)
            info("Compression service initialized")

            # Initialize email alert service
            email_alert_service = EmailAlertService()
            set_email_alert_service(email_alert_service)
            info("Email alert service initialized")
            # Get thread pool configuration
            max_workers = config_service.get('thread_pool.max_workers', int, 4)

            # Initialize unified data saver using configured storage paths
            storage_paths = config_service.get(
                'data_storage.storage_paths', dict, {}
            ) or {}
            base_dir = Path(storage_paths.get('base', 'data'))
            data_saver = DataSaver(
                base_output_dir=base_dir, storage_paths=storage_paths
            )
            # Create a default temperature processing pipeline
            pipeline = create_temperature_pipeline("temperature_pipeline")
            # Initialize sensor manager with data_saver and pipeline
            sensor_manager = SensorManager(
                config_service=config_service,
                max_workers=max_workers,
                data_saver=data_saver,
                data_pipeline=pipeline
            )
            # Initialize web application
            from src.gui.application import WebApplication

            web_application = WebApplication(
                config_service=config_service,
                sensor_manager=sensor_manager
            )

            container = cls(
                config_service=config_service,
                sensor_manager=sensor_manager,
                data_saver=data_saver,
                web_application=web_application,
                compression_service=compression_service,
                email_alert_service=email_alert_service
            )

            info("Application container created successfully")
            return container

        except Exception as e:
            error(f"Failed to create application container: {e}")
            raise

    @classmethod
    def create_sync(cls, config_dir: Path) -> 'ApplicationContainer':
        """Synchronous factory for NiceGUI compatibility

        Args:
            config_dir: Directory containing configuration files

        Returns:
            ApplicationContainer with background services started
        """
        container = cls.create(config_dir)
        container._start_background_services()
        return container

    def _start_background_services(self) -> None:
        """Start async services via ManagedThreadPool"""
        import threading
        # Spawn a daemon thread for async startup
        # and keep a reference for shutdown
        self._bg_thread = threading.Thread(
            target=lambda: asyncio.run(self._async_startup()),
            name="bg_services",
            daemon=True,
        )
        self._bg_thread.start()
        info("Background services started on dedicated daemon thread")

    async def _async_startup(self) -> None:
        """Async startup for background services"""
        try:
            # Start sensor polling
            sensor_count = (
                await self.sensor_manager.start_all_configured_sensors()
            )
            info(f"Started {sensor_count} sensors")
            # Keep background services running
            while not self._shutdown_requested:
                await asyncio.sleep(1)
        except Exception as e:
            error(f"Error in background services: {e}")

    async def startup(self) -> None:
        """Async startup for all services"""
        try:
            info("Starting CVD Tracker services...")

            # Start sensor manager
            sensor_count = (
                await self.sensor_manager.start_all_configured_sensors()
            )
            info(f"Started {sensor_count} sensors")

            # Initialize web application
            await self.web_application.startup()

            info("All services started successfully")

        except Exception as e:
            error(f"Failed to start services: {e}")
            raise

    def start_gui(self) -> None:
        """Start NiceGUI application (synchronous)"""
        try:
            # Register UI components
            self.web_application.register_components()

            # Get network configuration
            title = self.config_service.get("ui.title", str, "CVD Tracker")
            host = self.config_service.get("network.host", str, "localhost")
            port = self.config_service.get("network.port", int, 8080)

            info(f"Starting web interface: {title} at {host}:{port}")

            # Start NiceGUI
            from nicegui import ui
            ui.run(title=title, host=host, port=port)

        except Exception as e:
            error(f"Failed to start web interface: {e}")
            raise

    async def shutdown(self) -> None:
        """Graceful shutdown of all services"""
        info("Shutting down CVD Tracker...")
        try:
            # Signal background services to stop
            self._shutdown_requested = True
            # Wait for background startup thread to finish
            if hasattr(self, '_bg_thread'):
                await asyncio.to_thread(self._bg_thread.join, 5)
            # Shutdown web application
            await self.web_application.shutdown()
            # Shutdown sensor manager
            await self.sensor_manager.shutdown()

            # Shutdown background tasks
            for pool, future in self._background_tasks:
                if not future.done():
                    future.cancel()
                # Skip shutting down shared GENERAL pool
                if getattr(pool, 'pool_type', None) == ThreadPoolType.GENERAL:
                    continue
                pool.shutdown()

            info("Shutdown complete")

        except Exception as e:
            error(f"Error during shutdown: {e}")

    def shutdown_sync(self) -> None:
        """Synchronous shutdown for cleanup"""
        self._shutdown_requested = True
        # Wait for background startup thread to finish
        if hasattr(self, '_bg_thread'):
            self._bg_thread.join(timeout=5)
        # Shutdown background tasks
        for pool, future in self._background_tasks:
            if not future.done():
                future.cancel()
            # Skip shutting down shared GENERAL pool
            if getattr(pool, 'pool_type', None) == ThreadPoolType.GENERAL:
                continue
            pool.shutdown()

        info("Synchronous shutdown complete")

    def get_status(self) -> dict:
        """Get status of all services

        Returns:
            Dictionary with service status information
        """
        return {
            'sensors': self.sensor_manager.get_sensor_status(),
            'config_loaded': bool(self.config_service._config_cache),
            'background_tasks': len(self._background_tasks),
            'shutdown_requested': self._shutdown_requested
        }
