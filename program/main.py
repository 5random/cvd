"""
CVD Tracker main application entry point.
Refactored to use the new core abstractions and application container.
"""
import sys
from pathlib import Path
from src.utils.container import ApplicationContainer
from src.utils.log_utils.log_service import info, error, warning, debug

def main():
    """Main application entry point"""
    info("Starting CVD Tracker...")
     
    try:
        # Initialize application container
        # Determine config directory relative to project root
        base_dir = Path(__file__).parent.resolve()
        project_root = base_dir.parent  # one level above cvd-tracker-Neuentwicklung
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
