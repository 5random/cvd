"""
Application container for dependency injection and service orchestration.
"""

# pylint: disable=too-many-instance-attributes,import-outside-toplevel
# pylint: disable=broad-exception-caught,protected-access,
# pylint: disable=attribute-defined-outside-init
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, TYPE_CHECKING
from concurrent.futures import Future
from src.utils.log_service import info, error
from src.utils.concurrency.thread_pool import (
    ManagedThreadPool,
    ThreadPoolType,
    get_thread_pool_manager,
)

from src.utils.config_service import (
    ConfigurationService,
    ConfigurationError,
    set_config_service,
)

from src.utils.data_utils.data_saver import DataSaver
from src.utils.data_utils.compression_service import (
    CompressionService,
    set_compression_service,
)
from src.utils.email_alert_service import EmailAlertService

if TYPE_CHECKING:
    from src.gui.alt_application import WebApplication


@dataclass
class ApplicationContainer:
    """Container for all application services with dependency injection"""

    config_service: ConfigurationService
    data_saver: DataSaver
    web_application: "WebApplication"
    compression_service: CompressionService
    email_alert_service: EmailAlertService
    _background_tasks: List[Tuple[ManagedThreadPool, Future]] = field(
        default_factory=list
    )
    _shutdown_requested: bool = field(default=False)

    @classmethod
    def create(cls, config_dir: Path) -> "ApplicationContainer":
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
                default_config_path=config_dir / "default_config.json",
            )
            # Set global config service for backward compatibility
            set_config_service(config_service)

            # Initialize compression service
            compression_service = CompressionService()
            set_compression_service(compression_service)
            info("Compression service initialized")

            # Initialize email alert service
            email_alert_service = EmailAlertService()
            info("Email alert service initialized")
            # Get thread pool configuration
            max_workers = config_service.get("thread_pool.max_workers", int, 4)
            get_thread_pool_manager(default_max_workers=max_workers)

            # Initialize unified data saver using configured storage paths
            storage_paths = (
                config_service.get("data_storage.storage_paths", dict, {}) or {}
            )
            base_dir = Path(storage_paths.get("base", "data"))
            flush_interval = config_service.get("data_storage.flush_interval", int, 10)
            try:
                flush_interval = int(flush_interval)
            except Exception:
                flush_interval = 1
            if flush_interval <= 0:
                flush_interval = 1
            data_saver = DataSaver(
                base_output_dir=base_dir,
                storage_paths=storage_paths,
                flush_interval=flush_interval,
            )

            # Initialize web application
            from src.gui.alt_application import SimpleGUIApplication as WebApplication

            web_application = WebApplication(config_service=config_service)

            container = cls(
                config_service=config_service,
                data_saver=data_saver,
                web_application=web_application,
                compression_service=compression_service,
                email_alert_service=email_alert_service,
            )

            info("Application container created successfully")
            return container

        except (ConfigurationError, OSError) as e:
            error(f"Failed to create application container: {e}")
            raise
        except Exception as e:
            error(f"Unexpected error creating application container: {e}")
            raise

    @classmethod
    def create_sync(cls, config_dir: Path) -> "ApplicationContainer":
        """Synchronous factory for NiceGUI compatibility

        Args:
            config_dir: Directory containing configuration files

        Returns:
            Initialized ApplicationContainer
        """
        container = cls.create(config_dir)
        return container


    async def startup(self) -> None:
        """Async startup for all services"""
        try:
            info("Starting CVD Tracker services...")

            # Initialize web application
            await self.web_application.startup()

            info("All services started successfully")

        except (RuntimeError, OSError) as e:
            error(f"Failed to start services: {e}")
            raise
        except Exception as e:
            error(f"Unexpected error starting services: {e}")
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

            # Start NiceGUI with lifecycle hooks to start/stop services
            from nicegui import ui, app

            @app.on_startup
            async def _startup() -> None:
                await self.web_application.startup()

            @app.on_shutdown
            async def _shutdown() -> None:
                await self.web_application.shutdown()

            ui.run(
                title=title,
                favicon="https://www.tuhh.de/favicon.ico",
                host=host,
                port=port,
            )

        except (RuntimeError, OSError) as e:
            error(f"Failed to start web interface: {e}")
            raise
        except Exception as e:
            error(f"Unexpected error starting web interface: {e}")
            raise

    async def shutdown(self) -> None:
        """Graceful shutdown of all services"""
        info("Shutting down CVD Tracker...")
        try:
            # Signal background services to stop
            self._shutdown_requested = True
            # No background service thread to wait for
            # Shutdown web application
            await self.web_application.shutdown()

            # Shutdown background tasks
            for pool, future in self._background_tasks:
                if not future.done():
                    future.cancel()
                # Skip shutting down shared GENERAL pool
                if getattr(pool, "pool_type", None) == ThreadPoolType.GENERAL:
                    continue
                pool.shutdown()

            info("Shutdown complete")

        except (RuntimeError, OSError) as e:
            error(f"Error during shutdown: {e}")
        except Exception as e:
            error(f"Unexpected error during shutdown: {e}")
            raise

    def shutdown_sync(self) -> None:
        """Synchronous shutdown for cleanup"""
        self._shutdown_requested = True
        # No background service thread to wait for
        # Shutdown background tasks
        for pool, future in self._background_tasks:
            if not future.done():
                future.cancel()
            # Skip shutting down shared GENERAL pool
            if getattr(pool, "pool_type", None) == ThreadPoolType.GENERAL:
                continue
            pool.shutdown()

        # Shutdown async services synchronously
        async def _async_shutdown() -> None:
            await self.web_application.shutdown()

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(_async_shutdown(), loop)
                future.result()
            else:
                asyncio.run(_async_shutdown())
        except Exception as e:
            error(f"Error shutting down async services: {e}")

        # Close data saver
        try:
            self.data_saver.close()
        except OSError as e:
            error(f"Error closing data saver: {e}")
        except Exception as e:
            error(f"Unexpected error closing data saver: {e}")
            raise

        # Clean up UI components to stop timers and other background tasks
        try:
            self.web_application.component_registry.cleanup_all()
        except RuntimeError as e:
            error(f"Error cleaning up components: {e}")
        except Exception as e:
            error(f"Unexpected error cleaning up components: {e}")
            raise

        info("Synchronous shutdown complete")

    def get_status(self) -> dict:
        """Get status of all services

        Returns:
            Dictionary with service status information
        """
        return {
            "config_loaded": bool(self.config_service._config_cache),
            "background_tasks": len(self._background_tasks),
            "shutdown_requested": self._shutdown_requested,
        }
