"""
CVD Tracker main application entry point.
Refactored to use the new core abstractions and application container.
"""

import sys
import os
from pathlib import Path

from src.utils.container import ApplicationContainer
from src.utils.log_service import info, error
import argparse


def main():
    """Main application entry point"""
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required to run CVD Tracker")
    parser = argparse.ArgumentParser(description="CVD Tracker")
    parser.add_argument(
        "--controller-concurrency-limit",
        type=int,
        help="Max concurrent controller executions",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        help="Directory containing configuration files",
    )
    args = parser.parse_args()

    if args.controller_concurrency_limit is not None:
        os.environ["CONTROLLER_MANAGER_CONCURRENCY_LIMIT"] = str(
            args.controller_concurrency_limit
        )

    info("Starting CVD Tracker...")

    try:
        # Initialize application container
        if args.config_dir:
            config_dir = args.config_dir
        elif (env := os.getenv("CVD_CONFIG_DIR")) is not None:
            config_dir = Path(env)
        else:
            # Determine config directory relative to project root
            base_dir = Path(__file__).parent.resolve()
            project_root = base_dir.parent  # project root
            config_dir = project_root / "config"

        container = ApplicationContainer.create_sync(config_dir)

        # Register cleanup handler
        import atexit

        atexit.register(container.shutdown_sync)

        # Start GUI (this blocks until the application is closed)
        container.start_gui()

    except KeyboardInterrupt:
        info("Shutdown requested by user")
    except Exception as e:
        error(f"Application error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        info("CVD Tracker stopped")


if __name__ in {"__main__", "__mp_main__"}:
    main()
