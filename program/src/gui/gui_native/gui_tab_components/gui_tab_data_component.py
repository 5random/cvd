"""
Data management component for displaying, filtering, and downloading data files.
Integrates with DataManager and DataSaver for comprehensive data handling.

This component provides:
- Data overview with statistics
- File filtering and search capabilities
- Paginated file listing
- Bulk file selection and download
- Real-time status updates

Fixed issues:
- Event handling using event.selection instead of event.args
- Pagination division-by-zero protection
- File ID collision prevention
- Memory leak prevention with proper timer cleanup
- Download functionality with proper file selection
"""

from datetime import datetime, timedelta, date

# Constants
TIME_FORMAT = "%H:%M:%S"
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass
from nicegui import ui
import asyncio
import time
import hashlib

from program.src.utils.log_service import info, warning, error, debug
from src.gui.gui_tab_components.gui_tab_base_component import (
    BaseComponent,
    ComponentConfig,
)
from src.utils.data_utils.data_manager import DataManager, get_data_manager
from src.utils.data_utils.indexing import DataCategory, FileStatus, FileMetadata


@dataclass
class DataComponentConfig:
    """Configuration for the data management component"""

    auto_refresh_interval: float = 5.0  # seconds
    files_per_page: int = 50
    max_download_files: int = 100
    show_compressed_files: bool = True
    enable_bulk_operations: bool = True


class DataOverviewCard(BaseComponent):
    """Card component displaying data overview statistics"""

    def __init__(self, config: ComponentConfig, data_manager: DataManager):
        super().__init__(config)
        self.data_manager = data_manager
        self._stats_container: Optional[ui.grid] = None
        self._last_update: Optional[ui.label] = None

    def render(self) -> ui.card:
        """Render overview card"""
        with ui.card().classes("cvd-card p-4") as card:
            ui.label("Data Overview").classes("text-lg font-semibold mb-3")

            self._stats_container = ui.grid(columns=4).classes("gap-4 w-full")
            self._last_update = ui.label("Last updated: --").classes(
                "text-xs text-gray-500 mt-3"
            )

            # Initial data load
            # Defer stats update to avoid expensive operations during initial render
            ui.timer(0.1, self._update_stats, once=True)

        self._rendered = True
        self._element = card
        return card

    def _update_stats(self) -> None:
        """Update statistics display"""
        try:
            overview = self.data_manager.get_data_overview()

            if self._stats_container:
                self._stats_container.clear()

                with self._stats_container:
                    self._create_stat_card(
                        "Total Files", overview.get("total_files", 0), "📄"
                    )
                    self._create_stat_card(
                        "Total Size",
                        self._format_file_size(overview.get("total_size_bytes", 0)),
                        "💾",
                    )
                    # Count active and compressed files from status summary
                    status_summary = overview.get("status_summary", {})
                    active_count = status_summary.get("active", 0)
                    compressed_count = status_summary.get("compressed", 0)
                    self._create_stat_card("Active Files", active_count, "🟢")
                    self._create_stat_card("Compressed", compressed_count, "📦")
                # update last-update timestamp after stats refresh
                if self._last_update:
                    self._last_update.text = (
                        f"Last updated: {datetime.now().strftime(TIME_FORMAT)}"
                    )

        except Exception as e:
            error(f"Error updating stats: {e}")
            if self._last_update:
                self._last_update.text = (
                    "Failed to update stats. Please try again later."
                )
            ui.notify(
                "An error occurred while updating statistics. Please refresh the page.",
                type="negative",
            )

    def _create_stat_card(self, label: str, value: Any, icon: str) -> None:
        """Create a single statistic card"""
        with ui.card().classes("p-3 text-center"):
            ui.label(icon).classes("text-2xl mb-1")
            ui.label(str(value)).classes("text-lg font-bold")
            ui.label(label).classes("text-sm text-gray-600")

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
        size_float = float(size_bytes)
        i = 0
        while size_float >= 1024 and i < len(size_names) - 1:
            size_float /= 1024.0
            i += 1

        return f"{size_float:.1f} {size_names[i]}"

    def _update_element(self, data: Any) -> None:
        """Update the overview with new data"""
        self._update_stats()


class DataFilterPanel(BaseComponent):
    """Filter panel for data files"""

    def __init__(
        self, config: ComponentConfig, data_manager: DataManager, on_filter_change
    ):
        super().__init__(config)
        self.data_manager = data_manager
        self.on_filter_change = on_filter_change

        # Filter state
        self.current_filters = {
            "category": None,
            "status": None,
            "sensor_id": "",
            "experiment_id": "",
            "date_range": (None, None),
        }

        # UI elements
        self._category_select = None
        self._status_select = None
        self._sensor_input = None
        self._experiment_input = None
        self._date_range_input = None
        self._date_dialog = None
        self._date_from_picker = None
        self._date_to_picker = None

    def render(self) -> ui.card:
        """Render filter panel"""
        with ui.card().classes("cvd-card p-4") as card:
            ui.label("Filters").classes("text-lg font-semibold mb-3")

            with ui.row().classes("gap-4 w-full items-end"):
                # Category filter
                with ui.column().classes("min-w-32"):
                    ui.label("Category").classes("text-sm font-medium")
                    self._category_select = ui.select(
                        options=["All"] + [cat.value for cat in DataCategory],
                        value="All",
                        on_change=self._on_category_change,
                    ).classes("w-full")

                # Status filter
                with ui.column().classes("min-w-32"):
                    ui.label("Status").classes("text-sm font-medium")
                    self._status_select = ui.select(
                        options=["All"] + [status.value for status in FileStatus],
                        value="All",
                        on_change=self._on_status_change,
                    ).classes("w-full")

                # Sensor ID filter
                with ui.column().classes("min-w-32"):
                    ui.label("Sensor ID").classes("text-sm font-medium")
                    self._sensor_input = ui.input(
                        placeholder="Enter sensor ID", on_change=self._on_sensor_change
                    ).classes("w-full")

                # Experiment ID filter
                with ui.column().classes("min-w-32"):
                    ui.label("Experiment ID").classes("text-sm font-medium")
                    self._experiment_input = ui.input(
                        placeholder="Enter experiment ID",
                        on_change=self._on_experiment_change,
                    ).classes("w-full")

                # Date range filter with dialog
                with ui.column().classes("min-w-48"):
                    ui.label("Date Range").classes("text-sm font-medium")
                    self._date_range_input = (
                        ui.input(placeholder="Select range")
                        .props("readonly")
                        .on("click", self._open_date_dialog)
                        .classes("w-full")
                    )

                # Clear filters button
                ui.button("Clear Filters", on_click=self._clear_filters).classes(
                    "bg-gray-500"
                )

        self._rendered = True
        self._element = card
        return card

    def _on_category_change(self, event) -> None:
        """Handle category filter change"""
        value = event.value if event.value != "All" else None
        self.current_filters["category"] = DataCategory(value) if value else None
        self._emit_filter_change()

    def _on_status_change(self, event) -> None:
        """Handle status filter change"""
        value = event.value if event.value != "All" else None
        self.current_filters["status"] = FileStatus(value) if value else None
        self._emit_filter_change()

    def _on_sensor_change(self, event) -> None:
        """Handle sensor ID filter change"""
        # Guard against None value
        raw_value = event.value or ""
        self.current_filters["sensor_id"] = raw_value.strip()
        self._emit_filter_change()

    def _on_experiment_change(self, event) -> None:
        """Handle experiment ID filter change"""
        # Guard against None value
        raw_value = event.value or ""
        self.current_filters["experiment_id"] = raw_value.strip()
        # Notify change
        self._emit_filter_change()

    def _open_date_dialog(self) -> None:
        """Open dialog to select date range"""
        from_date, to_date = self.current_filters["date_range"]

        with ui.dialog() as dialog:
            self._date_dialog = dialog
            with ui.card():
                ui.label("Select Date Range").classes("text-lg font-bold")

                self._date_from_picker = ui.date(
                    value=from_date.strftime("%Y-%m-%d") if from_date else ""
                )
                self._date_to_picker = ui.date(
                    value=to_date.strftime("%Y-%m-%d") if to_date else ""
                )

                with ui.row().classes("gap-2 justify-end"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def _apply() -> None:
                        self._apply_date_range()
                        dialog.close()

                    ui.button("Apply", on_click=_apply).props("color=primary")

        dialog.open()

    def _apply_date_range(self) -> None:
        """Apply selected date range from dialog"""
        raw_from = self._date_from_picker.value
        raw_to = self._date_to_picker.value

        from_date = None
        to_date = None
        if raw_from:
            try:
                from_date = datetime.strptime(raw_from, "%Y-%m-%d").date()
            except ValueError:
                ui.notify("Invalid date format", type="negative")
                return
        if raw_to:
            try:
                to_date = datetime.strptime(raw_to, "%Y-%m-%d").date()
            except ValueError:
                ui.notify("Invalid date format", type="negative")
                return

        # Validate range
        if from_date and to_date and to_date < from_date:
            ui.notify("Invalid date range", type="negative")
            return

        self.current_filters["date_range"] = (from_date, to_date)
        date_input = self._date_range_input
        if date_input is not None:
            date_input.value = self._format_date_range(from_date, to_date)
        self._emit_filter_change()

    def _clear_filters(self) -> None:
        """Clear all filters"""
        self.current_filters = {
            "category": None,
            "status": None,
            "sensor_id": "",
            "experiment_id": "",
            "date_range": (None, None),
        }

        # Reset UI elements
        if self._category_select:
            self._category_select.value = "All"
        if self._status_select:
            self._status_select.value = "All"
        if self._sensor_input:
            self._sensor_input.value = ""
        if self._experiment_input:
            self._experiment_input.value = ""
        if self._date_range_input:
            self._date_range_input.value = ""

        # Reset any existing date pickers so the dialog opens blank next time
        if self._date_from_picker:
            self._date_from_picker.value = ""
            self._date_from_picker = None
        if self._date_to_picker:
            self._date_to_picker.value = ""
            self._date_to_picker = None

        self._emit_filter_change()

    def _emit_filter_change(self) -> None:
        """Emit filter change to parent"""
        if self.on_filter_change:
            self.on_filter_change(self.current_filters.copy())

    def _format_date_range(
        self, from_date: Optional[date], to_date: Optional[date]
    ) -> str:
        """Format date range for display"""
        if not from_date and not to_date:
            return ""
        from_str = from_date.strftime("%Y-%m-%d") if from_date else ""
        to_str = to_date.strftime("%Y-%m-%d") if to_date else ""
        if from_str and to_str:
            return f"{from_str} - {to_str}"
        if from_str:
            return f"from {from_str}"
        return f"until {to_str}"

    def _update_element(self, data: Any) -> None:
        """Update filter panel - no action needed"""
        pass


class DataFilesList(BaseComponent):
    """Files list with pagination and selection"""

    def __init__(
        self,
        config: ComponentConfig,
        data_manager: DataManager,
        component_config: DataComponentConfig,
    ):
        super().__init__(config)
        self.data_manager = data_manager
        self.component_config = component_config

        # File list state
        self.all_files: List[FileMetadata] = []
        self.current_files: List[FileMetadata] = []
        self.selected_files: Set[str] = set()  # Set of file IDs
        self.selected_file_paths: Dict[str, Path] = {}  # Mapping from ID to file path
        # Pagination
        self.current_page = 1
        self.total_pages = 1
        # UI elements
        self._files_table = None
        self._pagination_info = None
        self._selection_info = None
        self._download_button = None
        self._refresh_button = None
        self._download_status = None
        self._download_progress = None
        self._download_spinner = None
        self._prev_button = None
        self._next_button = None

        # Download monitoring
        self._download_timer = None


    def render(self) -> ui.card:
        """Render files list"""
        with ui.card().classes("cvd-card p-4") as card:
            # Header with selection info and download button
            with ui.row().classes("justify-between items-center mb-3"):
                ui.label("Data Files").classes("text-lg font-semibold")

                self._refresh_button = ui.button(
                    "Refresh", on_click=self._refresh_files
                ).classes("bg-gray-300")

                with ui.row().classes("gap-2 items-center"):
                    self._selection_info = ui.label("No files selected").classes(
                        "text-sm text-gray-600"
                    )
                    self._download_button = ui.button(
                        "Download Selected", on_click=self._download_selected_files
                    ).classes("bg-blue-500")
                    # disable initially
                    self._download_button.disable()

            # Download status
            self._download_status = ui.label("").classes("text-sm text-blue-600 mb-2")
            self._download_spinner = ui.spinner(size="2em").classes("mb-2")
            self._download_spinner.set_visibility(False)
            self._download_progress = ui.linear_progress(
                value=0.0, show_value=False
            ).classes("w-full mb-2")
            self._download_progress.set_visibility(False)
            # Files table
            self._files_table = ui.table(
                columns=[
                    {
                        "name": "filename",
                        "label": "Filename",
                        "field": "filename",
                        "align": "left",
                    },
                    {
                        "name": "category",
                        "label": "Category",
                        "field": "category",
                        "align": "center",
                    },
                    {
                        "name": "status",
                        "label": "Status",
                        "field": "status",
                        "align": "center",
                    },
                    {
                        "name": "size",
                        "label": "Size",
                        "field": "size",
                        "align": "right",
                    },
                    {
                        "name": "sensor_id",
                        "label": "Sensor",
                        "field": "sensor_id",
                        "align": "center",
                    },
                    {
                        "name": "experiment_id",
                        "label": "Experiment",
                        "field": "experiment_id",
                        "align": "center",
                    },
                    {
                        "name": "created_at",
                        "label": "Created",
                        "field": "created_at",
                        "align": "center",
                    },
                ],
                rows=[],
                row_key="id",
                selection="multiple",
                on_select=self._on_table_select,
            ).classes("w-full")

            # Pagination
            with ui.row().classes("justify-between items-center mt-3"):
                self._pagination_info = ui.label("").classes("text-sm text-gray-600")

                with ui.row().classes("gap-2"):
                    self._prev_button = ui.button("Previous", on_click=self._prev_page)
                    # disable until pagination update
                    self._prev_button.disable()
                    self._next_button = ui.button("Next", on_click=self._next_page)
                    self._next_button.disable()

            # Load initial data
            self._load_files()

        self._rendered = True
        self._element = card
        return card

    def _load_files(self) -> None:
        """Load all files from data manager"""
        try:
            self.all_files = self.data_manager.list_files()
            self.current_files = self.all_files.copy()
            # Build mapping for all files once to prevent stale entries
            self.selected_file_paths = {
                self._generate_file_id(f): f.file_path for f in self.all_files
            }
            valid_ids = set(self.selected_file_paths.keys())
            self.selected_files = self.selected_files.intersection(valid_ids)
            self._update_selection_info()

            self._update_display()
        except Exception as e:
            error(f"Error loading files: {e}")

    def _refresh_files(self) -> None:
        """Refresh file list by rescanning directories"""
        try:
            self.data_manager.scan_directories()
        except Exception as e:
            error(f"Error scanning directories: {e}")
        self._load_files()

    def _update_display(self) -> None:
        """Update table and pagination display"""
        self._update_pagination_info()
        self._update_table()
        self._update_pagination_buttons()
        self._update_selection_info()

    def _update_table(self) -> None:
        """Update files table"""
        if not self._files_table:
            return

        try:
            # Calculate pagination
            start_idx = (self.current_page - 1) * self.component_config.files_per_page
            end_idx = start_idx + self.component_config.files_per_page
            page_files = self.current_files[start_idx:end_idx]

            # Create table rows
            rows = []
            for file_meta in page_files:
                # Generate unique ID for this file to prevent collisions
                file_id = self._generate_file_id(file_meta)

                row = {
                    "id": file_id,
                    "filename": file_meta.file_path.name,
                    "category": file_meta.category.value,
                    "status": self._format_status(file_meta.status),
                    "size": DataOverviewCard._format_file_size(file_meta.size_bytes),
                    "sensor_id": file_meta.sensor_id or "N/A",
                    "experiment_id": file_meta.experiment_id or "N/A",
                    "created_at": file_meta.created_at.strftime("%Y-%m-%d %H:%M"),
                }
                rows.append(row)

            self._files_table.rows = rows

        except Exception as e:
            error(f"Error updating table: {e}")

    def _generate_file_id(self, file_meta: FileMetadata) -> str:
        """Generate unique ID for file to prevent collisions"""
        # Use file path, size, and creation time to create unique ID
        unique_string = f"{file_meta.file_path}_{file_meta.size_bytes}_{file_meta.created_at.timestamp()}"
        # Use full MD5 digest to reduce collision risk
        return hashlib.md5(unique_string.encode()).hexdigest()

    def _format_status(self, status: FileStatus) -> str:
        """Format file status with icon"""
        status_icons = {
            FileStatus.ACTIVE: "🟢 Active",
            FileStatus.COMPRESSED: "📦 Compressed",
            FileStatus.ERROR: "❌ Error",
        }
        return status_icons.get(status, f"❓ {status.value}")

    def _update_pagination_info(self) -> None:
        """Update pagination information"""
        if not self._pagination_info:
            return

        try:
            # Protect against division by zero
            if self.component_config.files_per_page > 0:
                self.total_pages = max(
                    1,
                    (len(self.current_files) + self.component_config.files_per_page - 1)
                    // self.component_config.files_per_page,
                )
            else:
                self.total_pages = 1

            # Ensure current page is valid
            if self.current_page > self.total_pages:
                self.current_page = self.total_pages

            start_idx = (
                self.current_page - 1
            ) * self.component_config.files_per_page + 1
            end_idx = min(
                self.current_page * self.component_config.files_per_page,
                len(self.current_files),
            )

            if len(self.current_files) == 0:
                self._pagination_info.text = "No files found"
            else:
                self._pagination_info.text = f"Showing {start_idx}-{end_idx} of {len(self.current_files)} files (Page {self.current_page} of {self.total_pages})"

        except Exception as e:
            error(f"Error updating pagination info: {e}")
            if self._pagination_info:
                self._pagination_info.text = "Pagination error"

    def _update_pagination_buttons(self) -> None:
        """Update pagination button states"""
        if self._prev_button:
            if self.current_page <= 1:
                self._prev_button.disable()
            else:
                self._prev_button.enable()
        if self._next_button:
            if self.current_page >= self.total_pages:
                self._next_button.disable()
            else:
                self._next_button.enable()

    def _update_selection_info(self) -> None:
        """Update selection information and download button state"""
        if not self._selection_info:
            return

        selected_count = len(self.selected_files)

        if selected_count == 0:
            self._selection_info.text = "No files selected"
        elif selected_count == 1:
            self._selection_info.text = "1 file selected"
        else:
            self._selection_info.text = f"{selected_count} files selected"

        # Update download button state
        if self._download_button:
            can_download = (
                0 < selected_count <= self.component_config.max_download_files
            )
            # enable or disable using helper methods
            if can_download:
                self._download_button.enable()
            else:
                self._download_button.disable()

            if selected_count > self.component_config.max_download_files:
                self._download_button.text = (
                    f"Too many files (max {self.component_config.max_download_files})"
                )
            else:
                self._download_button.text = "Download Selected"

    def _prev_page(self) -> None:
        """Go to previous page"""
        if self.current_page > 1:
            self.current_page -= 1
            self._update_display()

    def _next_page(self) -> None:
        """Go to next page"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._update_display()

    def apply_filters(self, filters: Dict[str, Any]) -> None:
        """Apply filters to file list"""
        try:
            # Start with all files
            filtered_files = self.all_files.copy()

            # Apply category filter
            if filters.get("category"):
                filtered_files = [
                    f for f in filtered_files if f.category == filters["category"]
                ]

            # Apply status filter
            if filters.get("status"):
                filtered_files = [
                    f for f in filtered_files if f.status == filters["status"]
                ]

            # Apply sensor ID filter
            if filters.get("sensor_id"):
                sensor_filter = filters["sensor_id"].lower()
                filtered_files = [
                    f
                    for f in filtered_files
                    if f.sensor_id and sensor_filter in f.sensor_id.lower()
                ]

            # Apply experiment ID filter
            if filters.get("experiment_id"):
                exp_filter = filters["experiment_id"].lower()
                filtered_files = [
                    f
                    for f in filtered_files
                    if f.experiment_id and exp_filter in f.experiment_id.lower()
                ]

            # Apply date range filter
            from_date, to_date = filters.get("date_range", (None, None))
            if from_date or to_date:

                def in_range(f):
                    d = f.created_at.date()
                    if from_date and d < from_date:
                        return False
                    if to_date and d > to_date:
                        return False
                    return True

                filtered_files = [f for f in filtered_files if in_range(f)]

            # Update current files and reset page
            self.current_files = filtered_files
            self.current_page = 1

            # Clear selections that are no longer visible
            current_file_ids = {self._generate_file_id(f) for f in filtered_files}
            self.selected_files = self.selected_files.intersection(current_file_ids)
            # Cleanup stale file path mappings
            self.selected_file_paths = {
                fid: path
                for fid, path in self.selected_file_paths.items()
                if fid in current_file_ids
            }

            self._update_display()

        except Exception as e:
            error(f"Error applying filters: {e}")

    def _toggle_file_selection(self, file_id: str) -> None:
        """Toggle file selection"""
        if file_id in self.selected_files:
            self.selected_files.remove(file_id)
        else:
            self.selected_files.add(file_id)

        self._update_selection_info()

    def _download_selected_files(self) -> None:
        """Download selected files as a package"""
        if not self.selected_files:
            ui.notify("No files selected for download", type="warning")
            return

        if len(self.selected_files) > self.component_config.max_download_files:
            ui.notify(
                f"Too many files selected. Maximum: {self.component_config.max_download_files}",
                type="negative",
            )
            return

        try:
            # Convert selected IDs back to absolute file paths
            file_paths = []
            for file_id in self.selected_files:
                if file_id in self.selected_file_paths:
                    file_paths.append(
                        str(Path(self.selected_file_paths[file_id]).resolve())
                    )

            # Validate file existence and readability
            valid_paths = []
            invalid_count = 0
            for fp in file_paths:
                p = Path(fp)
                if p.exists() and p.is_file():
                    valid_paths.append(fp)
                else:
                    invalid_count += 1
            if invalid_count > 0:
                ui.notify(
                    f"{invalid_count} files not found or unreadable and were skipped",
                    type="warning",
                )
            file_paths = valid_paths

            if not file_paths:
                ui.notify("No valid files found for download", type="warning")
                return

            # Create download package
            request_id = self.data_manager.create_download_package(
                file_paths, format="zip"
            )

            if self._download_status:
                self._download_status.text = f"Download package created. Request ID: {request_id}"  # Start monitoring download using the dedicated method
            self._start_download_monitoring(request_id)

            ui.notify(f"Download package created: {request_id}", type="positive")

        except Exception as e:
            error(f"Error creating download package: {e}")
            ui.notify(f"Error creating download package: {e}", type="negative")

    def _start_download_monitoring(self, request_id: str) -> None:
        """Start download monitoring with proper timer management"""
        # Stop any existing download timer
        if self._download_timer:
            self._download_timer.cancel()

        if self._download_progress:
            self._download_progress.set_value(0.0)
            self._download_progress.set_visibility(False)
        if self._download_spinner:
            self._download_spinner.set_visibility(True)

        # Start new monitoring timer
        self._download_timer = ui.timer(
            1.0, lambda: self._monitor_download_sync(request_id)
        )

    def _stop_download_monitoring(self) -> None:
        """Stop download monitoring timer"""
        if self._download_timer:
            self._download_timer.cancel()
            self._download_timer = None
        if self._download_progress:
            self._download_progress.set_visibility(False)
        if self._download_spinner:
            self._download_spinner.set_visibility(False)

    def _monitor_download_sync(self, request_id: str) -> None:
        """Synchronous download monitoring using timer"""
        try:
            status = self.data_manager.get_download_status(request_id)
            if not status:
                if self._download_status:
                    self._download_status.text = "Download status unavailable"
                ui.notify("Download status unavailable", type="warning")
                self._stop_download_monitoring()
                return

            status_value = status.get("status", "unknown")

            if status_value == "ready":
                # Download is ready - stop monitoring and initiate download
                self._stop_download_monitoring()

                download_path = self.data_manager.get_download_file(request_id)
                if download_path and download_path.exists():
                    if self._download_status:
                        self._download_status.text = (
                            f"Download ready: {download_path.name}"
                        )

                    # Create download link using the mounted static route
                    ui.download(str(download_path), filename=download_path.name)
                    ui.notify(
                        "Download ready! File will be downloaded automatically.",
                        type="positive",
                    )
                else:
                    if self._download_status:
                        self._download_status.text = "Download file not found"
                    ui.notify("Download file not found", type="negative")
                return

            elif status_value == "error":
                # Download failed - stop monitoring and show error
                self._stop_download_monitoring()

                error_msg = status.get("error_message", "Unknown error")
                if self._download_status:
                    self._download_status.text = f"Download failed: {error_msg}"
                ui.notify(f"Download failed: {error_msg}", type="negative")
                return

            elif status_value == "processing":
                # Continue monitoring - update UI with progress if available
                progress = status.get("progress", {})
                if progress:
                    processed = progress.get("processed_files", 0)
                    total = progress.get("total_files", 0)
                    if self._download_status:
                        self._download_status.text = f"Processing download package... ({processed}/{total} files)"
                    if self._download_progress:
                        self._download_progress.set_visibility(True)
                        if total:
                            self._download_progress.set_value(processed / total)
                    if self._download_spinner:
                        self._download_spinner.set_visibility(False)
                else:
                    if self._download_status:
                        self._download_status.text = "Processing download package..."
                    if self._download_spinner:
                        self._download_spinner.set_visibility(True)
                    if self._download_progress:
                        self._download_progress.set_visibility(False)

                # Continue monitoring with next timer cycle
                # Note: Timer will automatically call this method again after interval
                return

            elif status_value == "pending":
                # Download is queued
                if self._download_status:
                    self._download_status.text = "Download request is queued..."
                if self._download_spinner:
                    self._download_spinner.set_visibility(True)
                if self._download_progress:
                    self._download_progress.set_visibility(False)
                return

            else:
                # Unknown status
                if self._download_status:
                    self._download_status.text = (
                        f"Unknown download status: {status_value}"
                    )
                warning(f"Unknown download status: {status_value}")
                return

        except Exception as e:
            error(f"Error monitoring download: {e}")
            # Stop any ongoing monitoring
            self._stop_download_monitoring()
            if self._download_status:
                self._download_status.text = f"Monitoring error: {str(e)}"
            ui.notify(f"Download monitoring error: {str(e)}", type="negative")

    def _update_element(self, data: Any) -> None:
        """Update files list with new data"""
        self._load_files()

    def _on_table_select(self, event) -> None:
        """Handle row selection change in table"""
        try:

            # Derive selected IDs from event.selection or event.value
            selected = getattr(event, "selection", None)
            if selected is None:
                selected = getattr(event, "value", [])
            if selected and isinstance(selected[0], dict):
                selected_ids = {row.get("id") for row in selected}
            else:
                selected_ids = set(selected or [])

            self.selected_files = selected_ids
            self._update_selection_info()
        except Exception as e:
            error(f"Error handling table selection: {e}")

    def cleanup(self) -> None:
        """Cleanup component resources including stopping download timer"""
        # stop download monitoring timer
        self._stop_download_monitoring()
        super().cleanup()


class DataComponent(BaseComponent):
    """Main data management component"""

    def __init__(
        self,
        config: ComponentConfig,
        data_component_config: Optional[DataComponentConfig] = None,
    ):
        super().__init__(config)
        self.component_config = data_component_config or DataComponentConfig()

        # Get data manager instance
        data_manager = get_data_manager()
        if not data_manager:
            error("DataManager not available")
            raise RuntimeError("DataManager not available")
        self.data_manager = data_manager

        # Child components
        self.overview_card = None
        self.filter_panel = None
        self.files_list = None

        # Auto-refresh timer
        self._refresh_timer = None

    def render(self) -> ui.column:
        """Render the complete data management interface"""
        with ui.column().classes("w-full gap-4") as container:
            # Data overview
            overview_config = ComponentConfig(
                component_id=f"{self.component_id}_overview", title="Data Overview"
            )
            self.overview_card = DataOverviewCard(overview_config, self.data_manager)
            self.overview_card.render()

            # Filter panel
            filter_config = ComponentConfig(
                component_id=f"{self.component_id}_filters", title="Filters"
            )
            self.filter_panel = DataFilterPanel(
                filter_config, self.data_manager, self._on_filter_change
            )
            self.filter_panel.render()

            # Files list
            files_config = ComponentConfig(
                component_id=f"{self.component_id}_files", title="Files"
            )
            self.files_list = DataFilesList(
                files_config, self.data_manager, self.component_config
            )
            self.files_list.render()

            # Start auto-refresh
            if self.component_config.auto_refresh_interval > 0:
                self._refresh_timer = ui.timer(
                    self.component_config.auto_refresh_interval, self._auto_refresh
                )

        self._rendered = True
        self._element = container
        return container

    def _update_element(self, data: Any) -> None:
        """Update all child components"""
        if self.overview_card:
            self.overview_card.update(data)
        if self.filter_panel:
            self.filter_panel.update(data)
        if self.files_list:
            self.files_list.update(data)

    def _on_filter_change(self, filters: Dict[str, Any]) -> None:
        """Handle filter changes from filter panel"""
        if self.files_list:
            self.files_list.apply_filters(filters)

    def _auto_refresh(self) -> None:
        """Auto-refresh all components"""
        try:
            # Trigger data refresh in data manager
            self.data_manager.scan_directories()

            # Update components
            self._update_element({})

        except Exception as e:
            error(f"Error during auto-refresh: {e}")

    def cleanup(self) -> None:
        """Cleanup component resources"""
        if self._refresh_timer:
            self._refresh_timer.cancel()
            self._refresh_timer = None

        # Cleanup child components
        if self.overview_card:
            self.overview_card.cleanup()
        if self.filter_panel:
            self.filter_panel.cleanup()
        if self.files_list:
            self.files_list.cleanup()

        super().cleanup()


# Factory function for easy instantiation
def create_data_component(component_id: str = "data_component") -> DataComponent:
    """Create a data component with default configuration"""
    config = ComponentConfig(
        component_id=component_id, title="Data Management", classes="data-component"
    )

    return DataComponent(config)
