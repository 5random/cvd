"""
Log component for displaying and managing log files.
Displays logs created by log_service.py and allows downloading.
FIXED VERSION - All logic errors corrected
"""

from typing import Dict, Any, Optional, List, Callable
import asyncio
from dataclasses import dataclass
from nicegui import ui
from pathlib import Path
from datetime import datetime, timedelta
import io
import zipfile
import gzip
import bz2
import lzma

from src.utils.log_utils.log_service import (
    LogService,
    get_log_service,
    info,
    warning,
    error,
    debug,
)
from src.gui.gui_tab_components.gui_tab_base_component import BaseComponent, ComponentConfig


@dataclass
class LogFileInfo:
    """Information about a log file"""

    name: str
    path: Path
    size_bytes: int
    size_mb: float
    modified: datetime
    log_type: str
    is_compressed: bool = False


class LogViewerComponent(BaseComponent):
    """Log file viewer component"""

    def __init__(self, config: ComponentConfig, log_file_info: LogFileInfo):
        super().__init__(config)
        self.log_file_info = log_file_info
        self._content_area: Optional[ui.column] = None
        self._scroll_area: Optional[ui.scroll_area] = None
        self._log_column: Optional[ui.column] = None
        self._info_label: Optional[ui.label] = None
        self._scroll_pos: float = 0.0
        self._log_lines: List[str] = []
        self._filtered_lines: List[str] = []
        self._current_filter: str = ""
        self._current_level_filter: str = "ALL"
        self._auto_refresh: bool = False
        self._refresh_timer: Optional[ui.timer] = None
        self._max_lines = 1000  # Limit displayed lines for performance

    def render(self) -> ui.card:
        """Render log viewer card"""
        with ui.card().classes("w-full cvd-card") as card:
            # Header with file info and controls
            with ui.row().classes("w-full justify-between items-center p-4 border-b"):
                with ui.column().classes("flex-grow"):
                    ui.label(f"{self.log_file_info.name}").classes(
                        "text-lg font-semibold"
                    )
                    ui.label(
                        f"Size: {self.log_file_info.size_mb:.2f} MB | "
                        f'Modified: {self.log_file_info.modified.strftime("%Y-%m-%d %H:%M:%S")}'
                    ).classes("text-sm text-gray-500")

                with ui.row().classes("gap-2"):
                    # Level filter
                    ui.select(
                        ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        value=self._current_level_filter,
                        on_change=self._on_level_filter_change,
                    ).props("dense outlined").style("min-width: 100px")

                    # Search filter
                    ui.input(
                        "Search...",
                        value=self._current_filter,
                        on_change=self._on_filter_change,
                    ).props("dense outlined clearable").style("min-width: 200px")

                    # Auto-refresh toggle
                    ui.switch(
                        "Auto-refresh",
                        value=self._auto_refresh,
                        on_change=self._toggle_auto_refresh,
                    ).props("dense")

                    # Download button
                    ui.button("Download", icon="download", color="blue").props(
                        "dense"
                    ).on("click", self._download_log_file)

                    # Refresh button
                    ui.button("Refresh", icon="refresh", color="green").props(
                        "dense"
                    ).on("click", self._refresh_content)

            # Content area
            with ui.column().classes("w-full") as content_container:
                self._content_area = ui.column().classes("w-full p-4")
                with self._content_area:
                    # placeholder elements which will be updated
                    self._info_label = ui.label().classes("text-sm text-gray-500 mb-2")
                    with ui.scroll_area().style(
                        "height: 400px; background: #f5f5f5;"
                    ) as sa:
                        self._scroll_area = sa
                        self._scroll_area.on_scroll(self._on_scroll)
                        with ui.column().classes("w-full font-mono text-sm") as col:
                            self._log_column = col

            # Initial load
            self._refresh_content()

        return card

    def _on_filter_change(self, e) -> None:
        """Handle search filter change"""
        self._current_filter = e.value if e.value else ""
        self._apply_filters()
        self._update_display()

    def _on_scroll(self, e) -> None:
        """Remember current scroll position"""
        self._scroll_pos = e.vertical_position

    def _on_level_filter_change(self, e) -> None:
        """Handle log level filter change"""
        self._current_level_filter = e.value
        self._apply_filters()
        self._update_display()

    def _toggle_auto_refresh(self, e) -> None:
        """Toggle auto-refresh"""
        self._auto_refresh = e.value
        if self._auto_refresh:
            # Cancel existing timer if already running
            if self._refresh_timer:
                self._refresh_timer.cancel()
            # Create a single auto-refresh timer
            self._refresh_timer = ui.timer(2.0, self._refresh_content)
        else:
            if self._refresh_timer:
                self._refresh_timer.cancel()
                self._refresh_timer = None

    def _refresh_content(self) -> None:
        """Refresh log content"""
        try:
            self._load_log_content()
            self._apply_filters()
            self._update_display()
        except Exception as e:
            error(f"Error refreshing log content for {self.log_file_info.name}: {e}")

    def _load_log_content(self) -> None:
        """Load log file content"""
        try:
            if not self.log_file_info.path.exists():
                self._log_lines = [f"Log file not found: {self.log_file_info.path}"]
                return

            # Read log file (handle compressed files)
            if self.log_file_info.is_compressed:
                suffix = self.log_file_info.path.suffix.lower()
                if suffix == ".gz":
                    opener = gzip.open
                elif suffix == ".bz2":
                    opener = bz2.open
                elif suffix == ".xz":
                    opener = lzma.open
                else:
                    opener = open
                with opener(self.log_file_info.path, "rt", encoding="utf-8") as f:
                    lines = f.readlines()
            else:
                with open(self.log_file_info.path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            # Keep only recent lines for performance
            self._log_lines = lines[-self._max_lines :]

        except Exception as e:
            error(f"Error loading log file {self.log_file_info.path}: {e}")
            self._log_lines = [f"Error loading log file: {str(e)}"]

    def _apply_filters(self) -> None:
        """Apply current filters to log lines"""
        filtered_lines = self._log_lines.copy()

        # Apply level filter
        if self._current_level_filter != "ALL":
            filtered_lines = [
                line for line in filtered_lines if self._current_level_filter in line
            ]

        # Apply search filter
        if self._current_filter:
            filter_lower = self._current_filter.lower()
            filtered_lines = [
                line for line in filtered_lines if filter_lower in line.lower()
            ]

        self._filtered_lines = filtered_lines

    def _update_display(self) -> None:
        """Update the display with filtered content"""
        if not (
            self._content_area
            and self._log_column
            and self._info_label
            and self._scroll_area
        ):
            return
        # Save current scroll position from the last scroll event
        # NiceGUI's ScrollArea no longer exposes ``last_args``.
        # The ``_on_scroll`` handler already stores the last position in
        # ``self._scroll_pos`` whenever the user scrolls. Reuse that value
        # here to avoid attribute errors with newer NiceGUI versions.

        self._log_column.clear()

        if not self._filtered_lines:
            self._info_label.set_text("No log entries match the current filters")
            self._scroll_area.scroll_to(pixels=0)
            return

        # Update line count info
        total_lines = len(self._log_lines)
        filtered_count = len(self._filtered_lines)
        self._info_label.set_text(f"Showing {filtered_count} of {total_lines} lines")

        with self._log_column:
            for i, line in enumerate(self._filtered_lines):
                line_class = self._get_line_class(line)
                ui.label(line.rstrip()).classes(f"whitespace-pre {line_class}")
                if i >= 500:
                    ui.label(
                        f"... and {len(self._filtered_lines) - 500} more lines"
                    ).classes("text-gray-500 italic")
                    break

        # Restore previous scroll position
        self._scroll_area.scroll_to(pixels=self._scroll_pos)

    def _get_line_class(self, line: str) -> str:
        """Get CSS class for log line based on level"""
        line_lower = line.lower()
        if "error" in line_lower or "critical" in line_lower:
            return "text-red-600"
        elif "warning" in line_lower:
            return "text-yellow-600"
        elif "info" in line_lower:
            return "text-blue-600"
        elif "debug" in line_lower:
            return "text-gray-600"
        else:
            return "text-gray-800"

    def _download_log_file(self) -> None:
        """Download the log file"""
        try:
            # Create download for the file
            ui.download(self.log_file_info.path, filename=self.log_file_info.name)
            ui.notify(f"Downloading {self.log_file_info.name}", type="positive")
        except Exception as e:
            error(f"Error downloading log file {self.log_file_info.name}: {e}")
            ui.notify(f"Error downloading file: {str(e)}", type="negative")

    def _update_element(self, data: Any) -> None:
        """Update element with new data"""
        # Auto-refresh handles updates
        pass

    def cleanup(self) -> None:
        """Cleanup component"""
        if self._refresh_timer:
            self._refresh_timer.cancel()
        super().cleanup()


class LogComponent(BaseComponent):
    """Main log management component"""

    def __init__(self):
        config = ComponentConfig("logs")
        super().__init__(config)
        self.log_service = get_log_service()
        self._log_viewers: Dict[str, LogViewerComponent] = {}
        self._refresh_timer: Optional[ui.timer] = None
        self._selected_recent_tab: str = "info"
        # Task handle for updating statistics; used to cancel previous tasks
        self._stats_task: Optional[asyncio.Task] = None
        self._overview_container: Optional[Any] = None  # container for overview panel
        self._log_files_container: Optional[Any] = None  # container for log files panel

    def render(self) -> ui.column:
        """Render log component"""
        with ui.column().classes("w-full") as logs_container:
            # Header
            with ui.row().classes("w-full justify-between items-center mb-4"):
                ui.label("Log Management").classes("text-2xl font-bold")

                with ui.row().classes("gap-2"):
                    ui.button("Download All Logs", icon="archive", color="blue").on(
                        "click", self._download_all_logs
                    )
                    ui.button(
                        "Cleanup Old Logs", icon="delete_sweep", color="orange"
                    ).on("click", self._cleanup_old_logs)
                    ui.button("Compress Logs", icon="compress", color="purple").on(
                        "click", self._compress_logs
                    )
                    ui.button("Refresh", icon="refresh", color="green").on(
                        "click", self._refresh_log_info
                    )

            # Tabs for different sections
            with ui.tabs().classes("w-full") as tabs:
                overview_tab = ui.tab("overview", label="Overview", icon="dashboard")
                logs_tab = ui.tab("logs", label="Log Files", icon="description")

            with ui.tab_panels(tabs, value="overview").classes("w-full"):
                # Overview panel
                with ui.tab_panel("overview") as overview_panel:
                    self._overview_container = overview_panel
                    self._render_overview()

                # Log files panel
                with ui.tab_panel("logs") as log_files_panel:
                    self._log_files_container = log_files_panel
                    self._render_log_files()

            # Start refresh timer
            self._refresh_timer = ui.timer(10.0, self._refresh_log_info)

        return logs_container

    def _render_overview(self) -> None:
        """Render log overview section"""
        with ui.column().classes("w-full gap-4"):
            # Statistics cards
            self._render_log_statistics()

            # Recent log entries
            self._render_recent_entries()

    def _render_log_statistics(self) -> None:
        """Render log statistics"""
        # Cancel any previous stats update task and clear old stats row
        if self._stats_task:
            self._stats_task.cancel()
        if hasattr(self, "_stats_row") and self._stats_row:
            try:
                self._stats_row.clear()
            except Exception:
                pass
        # Render new stats placeholder
        with ui.card().classes("w-full p-4 cvd-card"):
            ui.label("Log Statistics").classes("text-lg font-semibold mb-3")
            self._stats_row = ui.row().classes("w-full gap-6")
        # load stats in background to avoid blocking UI and store task handle
        self._stats_task = asyncio.create_task(self._async_update_log_statistics())

    async def _async_update_log_statistics(self) -> None:
        """Background task to fetch log files and update statistics UI"""
        try:
            log_files = await asyncio.to_thread(self._get_log_files)
            # update UI
            self._stats_row.clear()
            with self._stats_row:
                # Total log files
                with ui.column().classes("text-center"):
                    ui.label(str(len(log_files))).classes(
                        "text-2xl font-bold text-blue-600"
                    )
                    ui.label("Log Files").classes("text-sm text-gray-500")
                # Total size
                total_size = sum(log_file.size_mb for log_file in log_files)
                with ui.column().classes("text-center"):
                    ui.label(f"{total_size:.1f} MB").classes(
                        "text-2xl font-bold text-green-600"
                    )
                    ui.label("Total Size").classes("text-sm text-gray-500")
                # Log level
                log_level = getattr(self.log_service, "log_level", "INFO")
                with ui.column().classes("text-center"):
                    ui.label(str(log_level)).classes(
                        "text-2xl font-bold text-purple-600"
                    )
                    ui.label("Log Level").classes("text-sm text-gray-500")
                # Retention days
                retention_days = getattr(self.log_service, "retention_days", 30)
                with ui.column().classes("text-center"):
                    ui.label(str(retention_days)).classes(
                        "text-2xl font-bold text-orange-600"
                    )
                    ui.label("Retention Days").classes("text-sm text-gray-500")
        except Exception as e:
            error(f"Error getting log statistics: {e}")
            self._stats_row.clear()
            with self._stats_row:
                ui.label(f"Error loading statistics: {str(e)}").classes("text-red-500")

    def _render_recent_entries(self) -> None:
        """Render recent log entries preview"""
        with ui.card().classes("w-full p-4 cvd-card"):
            ui.label("Recent Log Entries").classes("text-lg font-semibold mb-3")

            try:
                # Show recent entries from different log files
                log_files = self._get_log_files()

                with ui.tabs(
                    value=self._selected_recent_tab,
                    on_change=self._on_recent_tab_change,
                ).classes("w-full") as recent_tabs:
                    for log_type in [
                        "info",
                        "error",
                        "performance",
                        "audit",
                        "structured",
                    ]:
                        ui.tab(log_type, label=log_type.capitalize())

                with ui.tab_panels(recent_tabs, value=self._selected_recent_tab).classes(
                    "w-full"
                ):
                    for log_type in [
                        "info",
                        "error",
                        "performance",
                        "audit",
                        "structured",
                    ]:
                        with ui.tab_panel(log_type):
                            self._render_recent_entries_for_type(log_type, log_files)

            except Exception as e:
                error(f"Error rendering recent entries: {e}")
                ui.label(f"Error loading recent entries: {str(e)}").classes(
                    "text-red-500"
                )

    def _on_recent_tab_change(self, e) -> None:
        """Store the currently selected recent log tab"""
        self._selected_recent_tab = e.value

    def _render_recent_entries_for_type(
        self, log_type: str, log_files: List[LogFileInfo]
    ) -> None:
        """Render recent entries for a specific log type"""
        # Find the log file for this type
        log_file = next((f for f in log_files if log_type in f.name.lower()), None)

        if not log_file or not log_file.path.exists():
            ui.label(f"No {log_type} log file found").classes("text-gray-500")
            return

        try:
            # Read last few lines from the log file
            with open(log_file.path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            recent_lines = lines[-10:]  # Last 10 lines

            if not recent_lines:
                ui.label(f"No recent entries in {log_type} log").classes(
                    "text-gray-500"
                )
                return

            with ui.scroll_area().style("height: 200px; background: #f5f5f5;"):
                with ui.column().classes("w-full font-mono text-sm"):
                    for line in recent_lines:
                        ui.label(line.rstrip()).classes("whitespace-pre text-gray-800")

        except Exception as e:
            ui.label(f"Error reading {log_type} log: {str(e)}").classes("text-red-500")

    def _render_log_files(self) -> None:
        """Render log files section"""
        with ui.column().classes("w-full gap-4") as log_files_container:
            try:
                log_files = self._get_log_files()

                if not log_files:
                    ui.label("No log files found").classes("text-gray-500")
                    return

                # Clear existing viewers
                for viewer in self._log_viewers.values():
                    viewer.cleanup()
                self._log_viewers.clear()

                # Create viewer for each log file
                for log_file in log_files:
                    component_config = ComponentConfig(f"log_viewer_{log_file.name}")
                    viewer = LogViewerComponent(component_config, log_file)
                    viewer.render()
                    self._log_viewers[log_file.name] = viewer
            except Exception as e:
                error(f"Error rendering log files: {e}")
                ui.label(f"Error loading log files: {str(e)}").classes("text-red-500")

    def _get_log_files(self) -> List[LogFileInfo]:
        """Get list of available log files"""
        log_files = []

        try:
            log_dir = Path(self.log_service.log_dir)
            if not log_dir.exists():
                debug(f"Log directory does not exist: {log_dir}")
                return log_files

            # Get all log files (including compressed)
            for log_file_path in log_dir.glob("*.log*"):
                if log_file_path.is_file():
                    try:
                        stat = log_file_path.stat()
                        size_bytes = stat.st_size
                        size_mb = size_bytes / (1024 * 1024)
                        modified = datetime.fromtimestamp(stat.st_mtime)

                        # Determine log type from filename
                        log_type = "general"
                        name_lower = log_file_path.name.lower()
                        if "info" in name_lower:
                            log_type = "info"
                        elif "error" in name_lower:
                            log_type = "error"
                        elif "performance" in name_lower:
                            log_type = "performance"
                        elif "audit" in name_lower:
                            log_type = "audit"
                        elif "structured" in name_lower:
                            log_type = "structured"

                        is_compressed = log_file_path.suffix in [".gz", ".bz2", ".xz"]

                        log_files.append(
                            LogFileInfo(
                                name=log_file_path.name,
                                path=log_file_path,
                                size_bytes=size_bytes,
                                size_mb=size_mb,
                                modified=modified,
                                log_type=log_type,
                                is_compressed=is_compressed,
                            )
                        )
                    except Exception as e:
                        warning(f"Error processing log file {log_file_path}: {e}")
                        continue

            # Sort by modification time (newest first)
            log_files.sort(key=lambda x: x.modified, reverse=True)

        except Exception as e:
            error(f"Error getting log files: {e}")

        return log_files

    def _download_all_logs(self) -> None:
        """Download all log files as a zip archive"""
        try:
            log_files = self._get_log_files()

            if not log_files:
                ui.notify("No log files found to download", type="warning")
                return

            # Create zip archive in memory
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for log_file in log_files:
                    if log_file.path.exists():
                        zip_file.write(log_file.path, log_file.name)

            # Prepare download
            zip_buffer.seek(0)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cvd_tracker_logs_{timestamp}.zip"

            # Create temporary file for download
            temp_path = Path(self.log_service.log_dir) / filename
            with open(temp_path, "wb") as f:
                f.write(zip_buffer.getvalue())

            ui.download(temp_path, filename=filename)
            ui.notify(f"Downloaded all logs as {filename}", type="positive")

            # Clean up temp file after a delay
            def _cleanup_temp_file():
                try:
                    temp_path.unlink()
                except Exception as ex:
                    debug(f"Error deleting temp file {temp_path}: {ex}")

            ui.timer(5.0, _cleanup_temp_file, once=True)

        except Exception as e:
            error(f"Error downloading all logs: {e}")
            ui.notify(f"Error downloading logs: {str(e)}", type="negative")

    def _cleanup_old_logs(self) -> None:
        """Clean up old log files"""
        try:
            if hasattr(self.log_service, "cleanup_old_logs"):
                self.log_service.cleanup_old_logs()
                ui.notify("Old logs cleaned up successfully", type="positive")
                self._refresh_log_info()
            else:
                ui.notify("Log cleanup not implemented in log service", type="warning")
        except Exception as e:
            error(f"Error cleaning up old logs: {e}")
            ui.notify(f"Error cleaning up logs: {str(e)}", type="negative")

    def _compress_logs(self) -> None:
        """Compress old log files"""
        try:
            if hasattr(self.log_service, "compress_old_logs"):
                self.log_service.compress_old_logs()
                ui.notify("Log compression completed successfully", type="positive")
                self._refresh_log_info()
            else:
                ui.notify(
                    "Log compression not implemented in log service", type="warning"
                )
        except Exception as e:
            error(f"Error compressing logs: {e}")
            ui.notify(f"Error compressing logs: {str(e)}", type="negative")

    def _refresh_log_info(self) -> None:
        """Refresh log information"""
        try:
            # Re-render overview metrics
            if self._overview_container:
                self._overview_container.clear()
                with self._overview_container:
                    self._render_overview()
            # Re-render log files viewers
            if self._log_files_container:
                self._log_files_container.clear()
                with self._log_files_container:
                    self._render_log_files()
            debug("Refreshed log information and updated UI panels")
        except Exception as e:
            error(f"Error refreshing log info: {e}")

    def _update_element(self, data: Any) -> None:
        """Update element with new data"""
        # Updates are handled by refresh timer
        pass

    def cleanup(self) -> None:
        """Cleanup component"""
        if self._refresh_timer:
            self._refresh_timer.cancel()

        for viewer in self._log_viewers.values():
            viewer.cleanup()
        self._log_viewers.clear()

        super().cleanup()
