import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from wdmtoolbox import wdmtoolbox
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton, QFileDialog, QLabel, QWidget, QLineEdit, QHBoxLayout, QScrollArea, QDialog
, QCheckBox, QGridLayout, QProgressBar, QTableWidget, QTableWidgetItem, QGroupBox, QButtonGroup, QInputDialog )
from PySide6.QtWebEngineWidgets import QWebEngineView
from typing import List
from PySide6.QtCore import Qt, QTimer
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QIntValidator

METADATA_FIELDS = [
    {"name": "RCHRES ID", "label": "RCHRES ID"},  # Field 1
    {"name": "DESCRIPTION", "label": "Description"},  # Field 2
]

class DSNWorker(QObject):
    progress = Signal(int)  # Signal to update progress
    finished = Signal(dict)  # Signal when processing is complete

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        """Process DSNs and emit progress updates."""
        try:
            dsns = list_dsns(self.file_path)
            grouped_dsns = {}
            total_dsns = len(dsns)

            for i, dsn in enumerate(dsns):
                # Process DSNs (categorize into buckets)
                group_key = f"{(dsn // 1000) * 1000}-{(dsn // 1000) * 1000 + 999}"
                if group_key not in grouped_dsns:
                    grouped_dsns[group_key] = []
                grouped_dsns[group_key].append(dsn)

                # Emit progress
                self.progress.emit(int((i + 1) / total_dsns * 100))

            # Emit completion with grouped DSNs
            self.finished.emit(grouped_dsns)
        except Exception as e:
            self.finished.emit({})  # Send an empty result in case of failure

def ensure_directory_exists(directory: str) -> None:
    """Ensure that a directory exists, creating it if necessary."""
    os.makedirs(directory, exist_ok=True)

def process_wdm(file_path: str, selected_dsns: List[int]) -> pd.DataFrame:
    """Extract data from a WDM file for the specified DSNs."""
    try:
        combined_data = pd.DataFrame()
        for dsn in selected_dsns:
            # Extract time-series data for the DSN
            data = wdmtoolbox.extract(file_path, dsn)
            if data.empty:
                raise ValueError(f"DSN {dsn} contains no data.")

            # Add DSN data as a column, ensuring 1D format
            combined_data[dsn] = data.values.ravel()  # Flatten to 1D

        if combined_data.empty:
            raise ValueError("No data extracted from the WDM file.")

        combined_data.index = data.index  # Use the time index from the last DSN
        return combined_data
    except Exception as e:
        raise ValueError(f"Error processing WDM file: {e}")

def list_dsns(file_path: str) -> List[int]:
    """List all DSNs available in a WDM file.

    Args:
        file_path (str): Path to the WDM file.

    Returns:
        List[int]: List of available DSNs.
    """
    try:
        dsns = wdmtoolbox.listdsns(file_path)
        if isinstance(dsns, dict):  # Check if it's an OrderedDict or dict
            return list(dsns.keys())  # Extract the keys as DSNs
        else:
            raise ValueError("Unexpected format of DSNs returned.")
    except Exception as e:
        raise ValueError(f"Error listing DSNs: {e}")

def create_plot(data: pd.DataFrame) -> str:
    """Generate an interactive plot using Plotly.

    Args:
        data (pd.DataFrame): Data to plot.

    Returns:
        str: HTML representation of the plot.
    """
    fig = go.Figure()
    for col in data.columns:
        fig.add_trace(go.Scatter(x=data.index, y=data[col], mode='lines', name=f"DSN {col}"))

    fig.update_layout(
        title="WDM Data Visualization",
        xaxis_title="Time",
        yaxis_title="Values",
        template="plotly_dark"
    )
    return fig.to_html(full_html=False)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.selected_dsns = []  # To track user-selected DSNs
        self.metadata_store = {}  # Initialize metadata store for saving DSN metadata
        # Initialize processed_data as an empty dictionary
        self.processed_data = {}
        self.river_name = ""  # Store river name for the session
        self.years_to_skip = []  # Store years to skip for the session

        self.setWindowTitle("WDM Data Extractor Tool")
        self.setGeometry(100, 100, 1200, 300)  # Set window size (width=1200, height=300)

        # Main widget
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        # Main layout
        self.main_layout = QVBoxLayout()  # Renamed to avoid conflicts
        self.main_layout.setSpacing(10)  # Add consistent spacing
        self.main_layout.setContentsMargins(15, 15, 15, 15)  # Add margins around the layout

        # File selection section
        self.file_label = QLabel("Select WDM File:")
        self.file_input = QLineEdit()
        self.file_button = QPushButton("Browse")
        self.file_button.clicked.connect(self.select_file)

        self.file_layout = QHBoxLayout()  # Correctly initialize file layout here
        self.file_layout.addWidget(self.file_label)
        self.file_layout.addWidget(self.file_input)
        self.file_layout.addWidget(self.file_button)

        # Scenario title section
        self.scenario_label = QLabel("Scenario Title:")
        self.scenario_input = QLineEdit()
        self.scenario_input.setPlaceholderText("Enter a scenario title")  # Hint text

        self.scenario_layout = QHBoxLayout()
        self.scenario_layout.addWidget(self.scenario_label)
        self.scenario_layout.addWidget(self.scenario_input)

        # DSN Section Layout
        self.dsn_section_layout = QVBoxLayout()  # Vertical layout for Select DSNs + Selected DSNs

        # Select DSNs area (bucket buttons)
        self.dsn_label = QLabel("Select DSNs:")
        self.dsn_button_layout = QVBoxLayout()  # Layout for bucket buttons
        self.dsn_button_widget = QWidget()
        self.dsn_button_widget.setLayout(self.dsn_button_layout)
        self.dsn_button_scroll = QScrollArea()
        self.dsn_button_scroll.setWidget(self.dsn_button_widget)
        self.dsn_button_scroll.setWidgetResizable(True)
        self.dsn_button_scroll.setFixedHeight(150)  # Resize to fit bucket buttons

        # Selected DSNs area
        self.selected_dsns_label = QLabel("Selected DSNs:")
        self.selected_dsns_display = QLabel("")  # Display the list of selected DSNs
        self.selected_dsns_display.setFrameStyle(QLabel.Panel | QLabel.Sunken)

        # "SELECTED DSN DETAILS" button
        self.dsn_details_button = QPushButton("SELECTED DSN DETAILS")
        self.dsn_details_button.setStyleSheet("background-color: grey; color: white;")  # Initial gray color
        self.dsn_details_button.clicked.connect(self.open_dsn_details_table)  # Connect to future table function

        # Reset Selected DSNs Button
        self.reset_dsns_button = QPushButton("Reset Selected DSNs")
        self.reset_dsns_button.clicked.connect(self.reset_selected_dsns)
        self.dsn_section_layout.addWidget(self.reset_dsns_button)

        # Create a new group box for data manipulation options
        self.data_manipulation_group = QGroupBox("Data Extraction/Manipulation")
        self.data_manipulation_layout = QVBoxLayout()

        # Add a new layout to the group box for Temporal Interval options
        self.temporal_interval_layout = QHBoxLayout()
        self.temporal_interval_layout.setSpacing(10)
        self.temporal_interval_label = QLabel("Select Temporal Interval:")
        self.temporal_interval_layout.addWidget(self.temporal_interval_label)

        # Create checkboxes for temporal intervals (Second, Minute, Hour, Day, Month, Year)
        self.second_checkbox = QCheckBox("Second")
        self.minute_checkbox = QCheckBox("Minute")
        self.hour_checkbox = QCheckBox("Hour")
        self.day_checkbox = QCheckBox("Day")
        self.month_checkbox = QCheckBox("Month")
        self.year_checkbox = QCheckBox("Year")

        # Add checkboxes to the layout
        self.temporal_interval_layout.addWidget(self.second_checkbox)
        self.temporal_interval_layout.addWidget(self.minute_checkbox)
        self.temporal_interval_layout.addWidget(self.hour_checkbox)
        self.temporal_interval_layout.addWidget(self.day_checkbox)
        self.temporal_interval_layout.addWidget(self.month_checkbox)
        self.temporal_interval_layout.addWidget(self.year_checkbox)

        # Add temporal interval layout to the group box
        self.data_manipulation_layout.addLayout(self.temporal_interval_layout)

        # Create a new layout for Operation Type options (Sum, Average, Min, Max)
        self.operation_type_layout = QHBoxLayout()
        self.operation_type_layout.setSpacing(100)
        self.operation_type_label = QLabel("Select Operation:")
        self.operation_type_layout.addWidget(self.operation_type_label)

        # Create checkboxes for operation types (Sum, Average, Min, Max)
        self.sum_checkbox = QCheckBox("Sum")
        self.average_checkbox = QCheckBox("Average")
        self.min_checkbox = QCheckBox("Min")
        self.max_checkbox = QCheckBox("Max")

        # Add checkboxes to the layout
        self.operation_type_layout.addWidget(self.sum_checkbox)
        self.operation_type_layout.addWidget(self.average_checkbox)
        self.operation_type_layout.addWidget(self.min_checkbox)
        self.operation_type_layout.addWidget(self.max_checkbox)

        # Add operation type layout to the group box
        self.data_manipulation_layout.addLayout(self.operation_type_layout)

        # Add this code after the operation type layout in the MainWindow class

        # Decimal Points Selection
        self.decimal_points_label = QLabel("Decimal Points:")
        self.decimal_points_input = QLineEdit()
        self.decimal_points_input.setPlaceholderText("Enter number of decimal points")
        self.decimal_points_input.setValidator(QIntValidator(0, 10))  # Allow only integers between 0 and 10
        # Set default value for decimal points
        self.decimal_points_input.setText("2")

        self.decimal_points_layout = QHBoxLayout()
        self.decimal_points_layout.addWidget(self.decimal_points_label)
        self.decimal_points_layout.addWidget(self.decimal_points_input)

        # Add decimal points layout to the data manipulation group
        self.data_manipulation_layout.addLayout(self.decimal_points_layout)

        # Create Native button (this will disable both checkboxes when selected)
        self.native_button = QPushButton("Native")
        self.native_button.clicked.connect(self.toggle_native_mode)
        self.data_manipulation_layout.addWidget(self.native_button)

        # Style the checkboxes to change the tick color to green
        self.second_checkbox.setStyleSheet(
            "QCheckBox::indicator:checked { background-color: green; border: 1px solid green; }")
        self.minute_checkbox.setStyleSheet(
            "QCheckBox::indicator:checked { background-color: green; border: 1px solid green; }")
        self.hour_checkbox.setStyleSheet(
            "QCheckBox::indicator:checked { background-color: green; border: 1px solid green; }")
        self.day_checkbox.setStyleSheet(
            "QCheckBox::indicator:checked { background-color: green; border: 1px solid green; }")
        self.month_checkbox.setStyleSheet(
            "QCheckBox::indicator:checked { background-color: green; border: 1px solid green; }")
        self.year_checkbox.setStyleSheet(
            "QCheckBox::indicator:checked { background-color: green; border: 1px solid green; }")
        self.sum_checkbox.setStyleSheet(
            "QCheckBox::indicator:checked { background-color: green; border: 1px solid green; }")
        self.average_checkbox.setStyleSheet(
            "QCheckBox::indicator:checked { background-color: green; border: 1px solid green; }")
        self.min_checkbox.setStyleSheet(
            "QCheckBox::indicator:checked { background-color: green; border: 1px solid green; }")
        self.max_checkbox.setStyleSheet(
            "QCheckBox::indicator:checked { background-color: green; border: 1px solid green; }")

        # Button groups to enforce single checkbox selection
        self.temporal_button_group = QButtonGroup()
        self.temporal_button_group.addButton(self.second_checkbox)
        self.temporal_button_group.addButton(self.minute_checkbox)
        self.temporal_button_group.addButton(self.hour_checkbox)
        self.temporal_button_group.addButton(self.day_checkbox)
        self.temporal_button_group.addButton(self.month_checkbox)
        self.temporal_button_group.addButton(self.year_checkbox)

        self.operation_button_group = QButtonGroup()
        self.operation_button_group.addButton(self.sum_checkbox)
        self.operation_button_group.addButton(self.average_checkbox)
        self.operation_button_group.addButton(self.min_checkbox)
        self.operation_button_group.addButton(self.max_checkbox)

        # Create Data Preview Button
        self.preview_button = QPushButton("Data Preview")
        self.preview_button.clicked.connect(self.preview_data)
        self.data_manipulation_layout.addWidget(self.preview_button)

        # Add layout to the group box
        self.data_manipulation_group.setLayout(self.data_manipulation_layout)

        # Add Select DSNs and Selected DSNs to DSN Section Layout
        self.dsn_section_layout.addWidget(self.dsn_label)
        self.dsn_section_layout.addWidget(self.dsn_button_scroll)
        self.dsn_section_layout.addWidget(self.selected_dsns_label)
        self.dsn_section_layout.addWidget(self.selected_dsns_display)
        self.dsn_section_layout.addWidget(self.dsn_details_button)  # Add the new button here

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)  # Start with 0 progress

        # Add widgets to the main layout
        self.main_layout.addLayout(self.file_layout)  # File selection
        self.main_layout.addLayout(self.scenario_layout)  # Scenario title input
        self.main_layout.addLayout(self.dsn_section_layout)  # DSN section
        self.main_layout.addWidget(self.progress_bar)  # Progress bar
        self.main_layout.addWidget(self.data_manipulation_group)  # Assuming main_layout is already defined

        # Set the main layout to the central widget
        self.main_widget.setLayout(self.main_layout)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select WDM File", "", "WDM Files (*.wdm);;All Files (*.*)")
        if file_path:
            self.file_input.setText(file_path)

            # Reset progress bar
            self.progress_bar.setValue(0)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    text-align: center;
                    color: black;
                    border: 1px solid grey;
                    background-color: white;
                }
                QProgressBar::chunk {
                    background-color: green;
                }
            """)

            # Create and start the worker thread
            self.worker_thread = QThread()
            self.worker = DSNWorker(file_path)
            self.worker.moveToThread(self.worker_thread)

            # Connect signals
            self.worker.progress.connect(self.progress_bar.setValue)  # Update progress bar
            self.worker.finished.connect(self.on_dsn_processing_finished)  # Handle completion
            self.worker_thread.started.connect(self.worker.run)
            self.worker.finished.connect(self.worker_thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)

            # Start the worker thread
            self.worker_thread.start()

    def on_dsn_processing_finished(self, grouped_dsns):
        """Handle completion of DSN processing."""
        if grouped_dsns:
            self.grouped_dsns = grouped_dsns
            self.populate_groups()
        else:
            self.show_error("Failed to process DSNs.")

    def populate_groups(self):
        """Populate groups (buckets) in the Select DSNs area."""
        # Clear existing bucket buttons
        while self.dsn_button_layout.count():
            child = self.dsn_button_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add bucket buttons dynamically
        for group, dsns in self.grouped_dsns.items():
            group_button = QPushButton(group)
            group_button.clicked.connect(lambda checked, g=group: self.open_dsn_popup(g))
            self.dsn_button_layout.addWidget(group_button)

    def open_dsn_popup(self, group):
        """Open a popup to display DSNs in the selected group with remembered selections."""
        dsns = self.grouped_dsns[group]

        # Create a popup dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select DSNs from {group}")
        dialog.resize(600, 300)  # Set an initial size
        dialog.setSizeGripEnabled(True)  # Allow resizing

        # Create a scrollable area
        scroll_area = QScrollArea(dialog)
        scroll_area.setWidgetResizable(True)

        # Create a widget and layout for the scrollable content
        scroll_widget = QWidget()
        grid_layout = QGridLayout(scroll_widget)

        # Define fixed spacing
        grid_layout.setHorizontalSpacing(20)  # Fixed horizontal spacing
        grid_layout.setVerticalSpacing(10)  # Fixed vertical spacing
        grid_layout.setAlignment(Qt.AlignTop)

        # Define the range increments for the 4 columns
        start = int(group.split("-")[0])  # Start of the bucket (e.g., 1000 for 1000-1999)
        ranges = [
            (start, start + 199),
            (start + 200, start + 399),
            (start + 400, start + 599),
            (start + 600, start + 799),
            (start + 800, start + 999),
        ]

        # Add DSNs to the grid layout in 4 columns
        checkboxes = []
        for col, (range_start, range_end) in enumerate(ranges):
            column_dsns = [dsn for dsn in dsns if range_start <= dsn <= range_end]
            for row, dsn in enumerate(column_dsns):
                checkbox = QCheckBox(str(dsn))
                # Pre-check if the DSN is already selected
                if dsn in self.selected_dsns:
                    checkbox.setChecked(True)

                # Apply a custom stylesheet for green background with white tick mark
                checkbox.setStyleSheet("""
                    QCheckBox::indicator {
                        width: 20px;
                        height: 20px;
                    }
                    QCheckBox::indicator:unchecked {
                        background-color: lightgrey;
                        border: 1px solid grey;
                    }
                    QCheckBox::indicator:checked {
                        background-color: green;
                        border: 1px solid grey;
                        image: url(none);  /* Remove default tickmark image */
                    }
                """)
                grid_layout.addWidget(checkbox, row, col)  # Add to the current column
                checkboxes.append(checkbox)

        # Add a Confirm button
        confirm_button = QPushButton("Confirm", dialog)
        confirm_button.clicked.connect(lambda: self.confirm_dsn_selection(dialog, checkboxes))

        # Add the scrollable content and confirm button to the dialog layout
        dialog_layout = QVBoxLayout(dialog)
        scroll_area.setWidget(scroll_widget)
        dialog_layout.addWidget(scroll_area)
        dialog_layout.addWidget(confirm_button)

        dialog.setLayout(dialog_layout)
        dialog.exec()

    def confirm_dsn_selection(self, dialog, checkboxes):
        """Confirm the selected DSNs from the popup."""
        for checkbox in checkboxes:
            dsn = int(checkbox.text())
            if checkbox.isChecked():
                if dsn not in self.selected_dsns:
                    self.selected_dsns.append(dsn)
            else:
                if dsn in self.selected_dsns:
                    self.selected_dsns.remove(dsn)

        # Refresh the selected DSNs display
        self.selected_dsns_display.setText(", ".join(map(str, sorted(self.selected_dsns))))  # Display sorted DSNs
        dialog.accept()

    def reset_selected_dsns(self):
        """Reset the list of selected DSNs."""
        self.selected_dsns.clear()  # Clear the list of selected DSNs
        self.selected_dsns_display.setText("")  # Clear the display of selected DSNs

        # Optionally, update any UI elements that depend on the selected DSNs
        # For example, disable buttons or clear tables if needed

    def open_dsn_details_table(self):
        """Open a dialog with a table for editing DSN metadata."""
        if not self.selected_dsns:
            self.show_error("No DSNs selected. Please select DSNs first.")
            return

        # Create a dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Selected DSN Details")
        dialog.resize(600, 400)  # Set initial size

        # Create the table widget
        table = QTableWidget(dialog)
        table.setRowCount(len(self.selected_dsns))  # One row per DSN
        table.setColumnCount(len(METADATA_FIELDS))  # Dynamically set column count
        table.setHorizontalHeaderLabels([field["label"] for field in METADATA_FIELDS])  # Dynamic column titles

        # Set row headers to selected DSNs and populate cells with saved data
        for row, dsn in enumerate(self.selected_dsns):
            table.setVerticalHeaderItem(row, QTableWidgetItem(str(dsn)))  # DSN as row header

            # Populate cells with saved metadata
            for col in range(table.columnCount()):
                field_name = METADATA_FIELDS[col]["name"]
                saved_value = self.metadata_store.get(dsn, {}).get(field_name, "")  # Retrieve saved data

                table.setItem(row, col, QTableWidgetItem(saved_value))  # Populate cell

        # Add clipboard paste functionality
        table.keyPressEvent = lambda event: self.paste_data(event, table)

        # Add buttons below the table
        reset_button = QPushButton("Reset", dialog)
        copy_button = QPushButton("Copy Data", dialog)
        save_button = QPushButton("Save", dialog)

        # Layout for buttons
        button_layout = QHBoxLayout()
        button_layout.addWidget(reset_button)
        button_layout.addWidget(copy_button)
        button_layout.addWidget(save_button)

        # Main layout for the dialog
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(table)
        dialog_layout.addLayout(button_layout)
        dialog.setLayout(dialog_layout)

        # Connect button actions
        reset_button.clicked.connect(lambda: self.reset_table(table))
        copy_button.clicked.connect(lambda: self.copy_table_data(table))
        save_button.clicked.connect(lambda: self.save_table_data(table, dialog))

        dialog.exec()

    def reset_table(self, table):
        """Reset all values in the table and update button color."""
        # Clear the table cells
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                table.setItem(row, col, QTableWidgetItem(""))  # Clear each cell

        # Clear saved metadata for the selected DSNs
        for row in range(table.rowCount()):
            dsn = int(table.verticalHeaderItem(row).text())  # Get the DSN
            if dsn in self.metadata_store:
                del self.metadata_store[dsn]  # Remove metadata for this DSN

        # Update the button color to reflect no data
        self.update_dsn_details_button_color()

    def paste_data(self, event, table):
        """Paste data from clipboard into the table."""
        if event.key() == Qt.Key_V and (event.modifiers() & Qt.ControlModifier):  # Ctrl+V
            clipboard = QApplication.clipboard()
            clipboard_text = clipboard.text()
            rows = clipboard_text.split("\n")

            for row_index, row in enumerate(rows):
                columns = row.split("\t")  # Assume tab-separated values
                for col_index, value in enumerate(columns):
                    # Only paste within the bounds of the table
                    if row_index < table.rowCount() and col_index < table.columnCount():
                        table.setItem(row_index, col_index, QTableWidgetItem(value))

    def copy_table_data(self, table):
        """Copy table data to the clipboard."""
        clipboard_data = []
        for row in range(table.rowCount()):
            row_data = [table.item(row, col).text() if table.item(row, col) else "" for col in
                        range(table.columnCount())]
            clipboard_data.append("\t".join(row_data))  # Use tabs to separate columns
        clipboard_text = "\n".join(clipboard_data)  # Newline separates rows

        QApplication.clipboard().setText(clipboard_text)  # Copy to clipboard

    def save_table_data(self, table, dialog):
        """Save table data for the current session."""
        if not hasattr(self, 'metadata_store'):
            self.metadata_store = {}  # Initialize metadata store if it doesn't exist

        for row in range(table.rowCount()):
            dsn = int(table.verticalHeaderItem(row).text())  # Get the DSN

            # Check if the row is entirely empty
            is_empty_row = all(
                not table.item(row, col) or table.item(row, col).text().strip() == ""
                for col in range(table.columnCount())
            )

            if is_empty_row:
                # Remove DSN from metadata if the row is empty
                if dsn in self.metadata_store:
                    del self.metadata_store[dsn]
            else:
                # Save values from each column
                if dsn not in self.metadata_store:
                    self.metadata_store[dsn] = {}

                for col in range(table.columnCount()):
                    field_name = METADATA_FIELDS[col]["name"]  # Use field names from the list
                    cell_value = table.item(row, col).text() if table.item(row, col) else ""
                    self.metadata_store[dsn][field_name] = cell_value

        dialog.accept()  # Close the dialog after saving
        self.update_dsn_details_button_color()  # Update the button color based on completeness

    def setup_export_button(self):
        """Setup the CFA Export-OLD button."""
        cfa_export_old_button = QPushButton("CFA Export-OLD")
        cfa_export_old_button.clicked.connect(self.handle_cfa_export_old)
        # Add the button to the appropriate layout or dialog

    def handle_cfa_export_old(self):
        """Handle the CFA Export-OLD button click."""
        self.show_export_dialog()

    def get_metadata(self):
        """Retrieve saved metadata as a structured dictionary."""
        return self.metadata_store

    def update_dsn_details_button_color(self):
        """Update the color of the SELECTED DSN DETAILS button based on metadata completeness."""
        if not hasattr(self, 'metadata_store') or not self.metadata_store:
            self.dsn_details_button.setStyleSheet("background-color: grey; color: white;")  # No data
            return

        all_filled = True
        partially_filled = False

        for dsn, fields in self.metadata_store.items():
            if any(value == "" for value in fields.values()):
                all_filled = False
                partially_filled = True
            else:
                partially_filled = True

        if all_filled:
            self.dsn_details_button.setStyleSheet("background-color: green; color: white;")  # All data provided
        elif partially_filled:
            self.dsn_details_button.setStyleSheet("background-color: orange; color: black;")  # Partial data
        else:
            self.dsn_details_button.setStyleSheet("background-color: darkgrey; color: Black;")  # No data

    def populate_dsns(self, group):
        """Display checkboxes for DSNs in the selected group."""
        dsns = self.grouped_dsns[group]

        # Clear existing layout
        while self.dsn_scroll_layout.count():
            child = self.dsn_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.checkboxes = []
        for dsn in dsns:
            checkbox = QCheckBox(str(dsn))
            checkbox.stateChanged.connect(self.update_selected_dsns)
            self.dsn_scroll_layout.addWidget(checkbox)
            self.checkboxes.append(checkbox)

    def group_dsns(self, dsns):
        """Categorize DSNs into groups."""
        groups = {}
        for dsn in dsns:
            group_key = f"{(dsn // 1000) * 1000}-{(dsn // 1000) * 1000 + 999}"
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(dsn)
        return groups

    def update_dsn_list(self):
        """Update DSN dropdown based on the selected group."""
        selected_group = self.dsn_combo.currentText()
        if selected_group in self.grouped_dsns:
            self.dsn_combo.clear()
            self.dsn_combo.addItems([str(dsn) for dsn in self.grouped_dsns[selected_group]])

    def update_selected_dsns(self):
        """Update the list of selected DSNs."""
        selected_dsns = [int(cb.text()) for cb in self.checkboxes if cb.isChecked()]
        self.selected_dsns = selected_dsns
        self.selected_dsns_display.setText(", ".join(map(str, self.selected_dsns)))

    def toggle_native_mode(self):
        """Enable/disable temporal and operation checkboxes for native mode."""
        if self.native_button.isChecked():
            # Disable all temporal and operation checkboxes
            self.second_checkbox.setEnabled(False)
            self.minute_checkbox.setEnabled(False)
            self.hour_checkbox.setEnabled(False)
            self.day_checkbox.setEnabled(False)
            self.month_checkbox.setEnabled(False)
            self.year_checkbox.setEnabled(False)
            self.sum_checkbox.setEnabled(False)
            self.average_checkbox.setEnabled(False)
            self.min_checkbox.setEnabled(False)
            self.max_checkbox.setEnabled(False)
        else:
            # Enable all checkboxes when native mode is disabled
            self.second_checkbox.setEnabled(True)
            self.minute_checkbox.setEnabled(True)
            self.hour_checkbox.setEnabled(True)
            self.day_checkbox.setEnabled(True)
            self.month_checkbox.setEnabled(True)
            self.year_checkbox.setEnabled(True)
            self.sum_checkbox.setEnabled(True)
            self.average_checkbox.setEnabled(True)
            self.min_checkbox.setEnabled(True)
            self.max_checkbox.setEnabled(True)

    def preview_data(self):
        """Handle the data preview logic, based on selected options."""
        if not self.selected_dsns:
            self.show_error("No DSNs selected. Please select DSNs first.")
            return

        file_path = self.file_input.text()
        if not file_path:
            self.show_error("Please select a WDM file.")
            return

        # Get the selected temporal interval and operation type
        temporal_interval = self.get_selected_temporal_interval()
        operation_type = self.get_selected_operation_type()

        if not temporal_interval or not operation_type:
            self.show_error("Please select both temporal interval and operation type.")
            return

        # Get the number of decimal points
        decimal_points_text = self.decimal_points_input.text()
        if not decimal_points_text:
            self.show_error("Please enter a valid number of decimal points.")
            return

        try:
            decimal_points = int(decimal_points_text)
        except ValueError:
            self.show_error("Please enter a valid number of decimal points.")
            return

        try:
            # Process data for each selected DSN
            self.processed_data = {}  # Initialize or clear the dictionary
            for dsn in self.selected_dsns:
                data = process_wdm(file_path, [dsn])
                resampled_data = data.resample(temporal_interval).agg(operation_type)
                self.processed_data[dsn] = resampled_data.round(decimal_points)

            # Show processed data preview
            self.show_data_preview(self.processed_data)

        except ValueError as e:
            self.show_error(str(e))

    def get_selected_temporal_interval(self):
        """Retrieve the selected temporal interval."""
        if self.second_checkbox.isChecked():
            return 'S'  # Second
        elif self.minute_checkbox.isChecked():
            return 'min'  # Minute
        elif self.hour_checkbox.isChecked():
            return 'h'  # Hour
        elif self.day_checkbox.isChecked():
            return 'D'  # Day
        elif self.month_checkbox.isChecked():
            return 'MS'  # Month
        elif self.year_checkbox.isChecked():
            return 'YE'  # Year (Annual)
        return None

    def get_selected_operation_type(self):
        """Retrieve the selected operation type."""
        if self.sum_checkbox.isChecked():
            return 'sum'
        elif self.average_checkbox.isChecked():
            return 'average'
        elif self.min_checkbox.isChecked():
            return 'min'
        elif self.max_checkbox.isChecked():
            return 'max'
        return None

    def show_data_preview(self, processed_data):
        """Display data preview in a table format with real-time decimal updates."""
        # Create a dialog window
        self.preview_dialog = QDialog(self)
        self.preview_dialog.setWindowTitle("Data Preview")
        self.preview_dialog.setMinimumWidth(1000)
        self.preview_dialog.setMinimumHeight(800)

        # Calculate number of data rows to display
        total_rows = max(len(data) for data in processed_data.values())
        num_rows = min(100, total_rows)  # Limit to 103 rows (60 + 5 + 35 + 3 headers)

        num_columns = 1 + len(processed_data)
        header_rows = 3  # Number of header rows
        total_table_rows = header_rows + num_rows  # total rows in the table
        self.preview_table = QTableWidget(self.preview_dialog)
        self.preview_table.setRowCount(total_table_rows)  # set the correct number of rows
        self.preview_table.setColumnCount(num_columns)

        # Set the headers (these should be set *before* populating data)
        self.preview_table.setItem(0, 0, QTableWidgetItem("DSN"))
        for col, dsn in enumerate(processed_data.keys(), start=1):
            self.preview_table.setItem(0, col, QTableWidgetItem(f"{dsn}"))

        # Determine the selected operation type
        operation_type = self.get_selected_operation_type()
        if operation_type is None:
            operation_type = "Unknown"  # Fallback if no operation is selected

        self.preview_table.setItem(1, 0, QTableWidgetItem("Attribute"))
        for col in range(1, num_columns):
            self.preview_table.setItem(1, col,
                                       QTableWidgetItem(operation_type.capitalize()))  # Use the selected operation

        self.preview_table.setItem(2, 0, QTableWidgetItem("Decimal Places"))
        decimal_inputs = []
        for col in range(1, num_columns):
            decimal_input = QLineEdit("2")  # Default to 2 decimal places
            decimal_input.setValidator(QIntValidator(0, 10))
            decimal_input.textChanged.connect(
                lambda _, c=col: self.update_decimal_places(self.preview_table, c, processed_data))
            self.preview_table.setCellWidget(2, col, decimal_input)
            decimal_inputs.append(decimal_input)

        # Determine the date format based on the temporal interval
        temporal_interval = self.get_selected_temporal_interval()
        if temporal_interval == 'min':  # Minute
            date_format = "%Y-%m-%d %H:%M"
        elif temporal_interval == 'h':  # Hourly
            date_format = "%Y-%m-%d %H"
        elif temporal_interval == 'D':  # Daily
            date_format = "%Y-%m-%d"
        elif temporal_interval == 'MS':  # Monthly
            date_format = "%Y-%m"
        elif temporal_interval == 'YE':  # Yearly
            date_format = "%Y"
        else:
            date_format = "%Y-%m-%d %H:%M:%S"  # Default format

        # Populate the table with data
        indices = processed_data[next(iter(processed_data))].index

        if total_rows > 100:
            # Show first 60 rows
            for i, index in enumerate(indices[:60]):
                formatted_date = index.strftime(date_format)
                self.preview_table.setItem(header_rows + i, 0, QTableWidgetItem(formatted_date))
                for col, (dsn, data) in enumerate(processed_data.items(), start=1):
                    value = data.loc[index].iloc[0] if index in data.index else None
                    if value is not None:
                        decimal_places = int(decimal_inputs[col - 1].text())
                        self.preview_table.setItem(header_rows + i, col,
                                                   QTableWidgetItem(f"{value:.{decimal_places}f}"))

            # Insert 5 rows of ellipses
            for i in range(5):
                for col in range(num_columns):
                    self.preview_table.setItem(header_rows + 60 + i, col, QTableWidgetItem("..."))

            # Show last 35 rows
            for i, index in enumerate(indices[-35:], start=0):  # start=0 is crucial here
                formatted_date = index.strftime(date_format)
                self.preview_table.setItem(header_rows + 65 + i, 0, QTableWidgetItem(formatted_date))
                for col, (dsn, data) in enumerate(processed_data.items(), start=1):
                    value = data.loc[index].iloc[0] if index in data.index else None
                    if value is not None:
                        decimal_places = int(decimal_inputs[col - 1].text())
                        self.preview_table.setItem(header_rows + 65 + i, col,
                                                   QTableWidgetItem(f"{value:.{decimal_places}f}"))
        else:
            # Show all rows if total is less than or equal to 100
            for i, index in enumerate(indices):
                formatted_date = index.strftime(date_format)
                self.preview_table.setItem(header_rows + i, 0, QTableWidgetItem(formatted_date))
                for col, (dsn, data) in enumerate(processed_data.items(), start=1):
                    value = data.loc[index].iloc[0] if index in data.index else None
                    if value is not None:
                        decimal_places = int(decimal_inputs[col - 1].text())
                        self.preview_table.setItem(header_rows + i, col,
                                                   QTableWidgetItem(f"{value:.{decimal_places}f}"))

        # Set column headers
        self.preview_table.setHorizontalHeaderLabels(
            ["Datetime"] + [f"Values (DSN {dsn})" for dsn in processed_data.keys()])

        # Create buttons
        copy_button = QPushButton("Copy")
        copy_button.clicked.connect(lambda: self.copy_dsn_data(self.preview_table))

        validate_button = QPushButton("Validate")
        validate_button.clicked.connect(self.enable_export_options)

        # Add the table and buttons to the dialog layout
        dialog_layout = QVBoxLayout()
        dialog_layout.addWidget(self.preview_table)  # Use self.preview_table
        dialog_layout.addWidget(copy_button)
        dialog_layout.addWidget(validate_button)
        self.preview_dialog.setLayout(dialog_layout)

        # Show the dialog window
        self.preview_dialog.exec()

    def copy_dsn_data(self, table):
        """Copy the DSN data to the clipboard, including the DSN row."""
        clipboard_data = []

        # Copy the DSN row (first row)
        dsn_row_data = []
        for col in range(table.columnCount()):
            item = table.item(0, col)
            if item:
                dsn_row_data.append(item.text())
        clipboard_data.append("\t".join(dsn_row_data))

        # Copy the values starting from the 4th row
        for row in range(3, table.rowCount()):  # Start from the 4th row to skip headers
            row_data = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    row_data.append(item.text())
            clipboard_data.append("\t".join(row_data))

        # Join all rows into a single string and set it to the clipboard
        clipboard_text = "\n".join(clipboard_data)
        QApplication.clipboard().setText(clipboard_text)

    def enable_export_options(self):
        """Enable the export options if a scenario name is provided."""
        # Check if the scenario name is entered
        scenario_title = self.scenario_input.text().strip()
        if not scenario_title:
            self.show_error("Please enter a scenario name to validate the results.")
            return

        # Create a dialog window for export options
        self.export_dialog = QDialog(self)
        self.export_dialog.setWindowTitle("Export Options")
        self.export_dialog.setMinimumWidth(500)

        # Create export buttons
        txt_export_button = QPushButton("Export to .txt")
        txt_export_button.clicked.connect(self.export_to_txt)

        cfa_export_old_button = QPushButton("CFA Export-OLD")
        cfa_export_old_button.clicked.connect(self.handle_cfa_export_old)  # Connect to the new method

        cfa_export_new_button = QPushButton("CFA Export-NEW")
        ssp_export_button = QPushButton("SSP-Export")

        # Add buttons to the dialog layout
        dialog_layout = QVBoxLayout()
        dialog_layout.addWidget(txt_export_button)
        dialog_layout.addWidget(cfa_export_old_button)
        dialog_layout.addWidget(cfa_export_new_button)
        dialog_layout.addWidget(ssp_export_button)
        self.export_dialog.setLayout(dialog_layout)

        # Show the export dialog
        self.export_dialog.exec()

    def export_to_txt(self):
        """Export data preview, DSN metadata, and scenario title to a .txt file."""
        # Get the file path to save the .txt file
        file_path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Text Files (*.txt);;All Files (*.*)")
        if not file_path:
            return  # User canceled the save dialog

        try:
            with open(file_path, 'w') as file:
                # Write scenario title
                scenario_title = self.scenario_input.text()
                file.write(f"Scenario Title: {scenario_title}\n\n")

                # Write DSN metadata
                file.write("DSN Metadata:\n")
                for dsn, metadata in self.metadata_store.items():
                    file.write(f"DSN {dsn}:\n")
                    for key, value in metadata.items():
                        file.write(f"  {key}: {value}\n")
                file.write("\n")

                # Write data preview headers
                for row in range(3):  # Include the first three header rows
                    row_data = []
                    for col in range(self.preview_table.columnCount()):
                        item = self.preview_table.item(row, col)
                        if item:
                            row_data.append(item.text())
                    file.write("\t".join(row_data) + "\n")

                # Write data preview values with correct decimal precision
                for row in range(3, self.preview_table.rowCount()):  # Start from the 4th row for data
                    row_data = []
                    for col in range(self.preview_table.columnCount()):
                        item = self.preview_table.item(row, col)
                        if item:
                            # Check if the column is a DSN column and apply decimal precision
                            if col > 0:  # Assuming first column is "Datetime"
                                decimal_input = self.preview_table.cellWidget(2, col)
                                if decimal_input:
                                    decimal_places = int(decimal_input.text())
                                    value = float(item.text())
                                    row_data.append(f"{value:.{decimal_places}f}")
                                else:
                                    row_data.append(item.text())
                            else:
                                row_data.append(item.text())
                    file.write("\t".join(row_data) + "\n")

            self.show_message("Data exported successfully to .txt file.")
        except Exception as e:
            self.show_error(f"Error exporting data: {e}")

    def export_cfa_old(self, river_name, years_to_skip):
        """Export data in CFA format for each DSN."""
        scenario_name = self.scenario_input.text().strip()
        if not scenario_name:
            self.show_error("Scenario name is required for export.")
            return

        # Create a new directory for the scenario
        export_dir = os.path.join(os.getcwd(), scenario_name)
        os.makedirs(export_dir, exist_ok=True)

        for dsn, data in self.processed_data.items():
            # Skip specified years
            data_to_export = data[~data.index.year.isin(map(int, years_to_skip))]  # Convert years to integers

            # Open file for writing
            file_path = os.path.join(export_dir, f"{dsn}.prn")
            with open(file_path, 'w') as f:
                nyears = data_to_export.index.year.nunique()
                f.write(f"  {river_name}\n")
                f.write(f"  NODE {dsn} {scenario_name}\n")
                f.write(f"   {nyears}   10101    {nyears}   {nyears}     0.000\n")
                f.write(f"   {nyears}      NUMBER OF OBSERVATIONS\n")
                f.write("     10101   AREA\n")
                f.write(f"     {nyears}      HISTORIC TIME SPAN\n")
                f.write(f"     {nyears}      NUMBER OF FLOODS ABOVE\n")

                for year, value in zip(data_to_export.index.year, data_to_export[data_to_export.columns[0]].values):
                    f.write(f"{river_name}         {year}   1      {value:.2f}\n")

        self.show_message("CFA Export-OLD completed successfully.")

    def show_export_dialog(self):
        """Show a dialog to collect export details and trigger the export."""
        dialog = QDialog(self)
        dialog.setWindowTitle("CFA Export-OLD")
        dialog.setMinimumWidth(400)

        # Create input fields
        river_name_label = QLabel("River Name:")
        river_name_input = QLineEdit(self.river_name)  # Pre-fill with stored value

        years_to_skip_label = QLabel("Years to Skip (comma-separated):")
        years_to_skip_input = QLineEdit(','.join(self.years_to_skip))  # Pre-fill with stored value

        # Create the "Ready to Export" button
        export_button = QPushButton("Ready to Export")
        export_button.clicked.connect(lambda: self.handle_export(dialog, river_name_input, years_to_skip_input))

        # Layout the dialog
        layout = QVBoxLayout()
        layout.addWidget(river_name_label)
        layout.addWidget(river_name_input)
        layout.addWidget(years_to_skip_label)
        layout.addWidget(years_to_skip_input)
        layout.addWidget(export_button)
        dialog.setLayout(layout)

        # Show the dialog
        dialog.exec()

    def handle_export(self, dialog, river_name_input, years_to_skip_input):
        """Handle the export process when the user clicks 'Ready to Export'."""
        self.river_name = river_name_input.text().strip()
        if not self.river_name:
            self.show_error("River Name is required for export.")
            return

        self.years_to_skip = [year.strip() for year in years_to_skip_input.text().split(',') if year.strip()]

        # Close the dialog
        dialog.accept()

        # Perform the export
        self.export_cfa_old(self.river_name, self.years_to_skip)

    def update_decimal_places(self, table, col, processed_data):
        """Update the decimal places for a specific DSN column in real-time."""
        decimal_input = table.cellWidget(2, col)
        if not decimal_input:
            return

        try:
            decimal_places = int(decimal_input.text())
        except ValueError:
            return

        row_offset = 3  # Start after header rows
        dsn = list(processed_data.keys())[col - 1]
        data = processed_data[dsn]

        for i, index in enumerate(data.index):
            value = data.loc[index].iloc[0]
            table.setItem(row_offset + i, col, QTableWidgetItem(f"{value:.{decimal_places}f}"))

    def prompt_user_for_export_details(self):
        """Prompt the user for River Name and Years to Skip."""
        river_name, ok1 = QInputDialog.getText(self, "River Name", "Enter River Name:")
        if not ok1 or not river_name.strip():
            self.show_error("River Name is required for export.")
            return None, None

        years_to_skip, ok2 = QInputDialog.getText(self, "Years to Skip", "Enter years to skip (comma-separated):")
        if not ok2:
            years_to_skip = ""  # Default to no years skipped

        return river_name.strip(), [year.strip() for year in years_to_skip.split(',') if year.strip()]

    def generate_plot(self):
        """Generate an interactive plot with Plotly."""
        file_path = self.file_input.text()
        if not file_path:
            self.show_error("Please select a WDM file.")
            return

        selected_dsns = [int(self.dsn_combo.currentText())]
        if not selected_dsns:
            self.show_error("Please select at least one DSN.")
            return

        try:
            # Process WDM data
            data = process_wdm(file_path, selected_dsns)

            # Generate Plot
            plot_html = create_plot(data)

            # Display Plot
            self.plot_view.setHtml(plot_html)

        except ValueError as e:
            self.show_error(str(e))

    def show_error(self, message: str):
        """Display an error message, replacing any existing message."""
        # Remove any existing error message
        if hasattr(self, 'error_dialog') and self.error_dialog is not None:
            self.main_layout.removeWidget(self.error_dialog)
            self.error_dialog.deleteLater()
            self.error_dialog = None

        # Create a QLabel for the error message
        self.error_dialog = QLabel(f"<p style='color: orange;'>{message}</p>")
        self.error_dialog.setFrameStyle(QLabel.Panel | QLabel.Sunken)
        self.error_dialog.setAlignment(Qt.AlignCenter)

        # Add the error dialog to the main layout
        self.main_layout.addWidget(self.error_dialog)

        # Schedule the error dialog to be removed after 2 seconds
        QTimer.singleShot(2000, self.remove_error)

    def show_message(self, message: str):
        """Display a success message."""
        # Remove any existing message
        if hasattr(self, 'error_dialog') and self.error_dialog is not None:
            self.main_layout.removeWidget(self.error_dialog)
            self.error_dialog.deleteLater()
            self.error_dialog = None

        # Create a QLabel for the success message
        self.error_dialog = QLabel(f"<p style='color: green;'>{message}</p>")
        self.error_dialog.setFrameStyle(QLabel.Panel | QLabel.Sunken)
        self.error_dialog.setAlignment(Qt.AlignCenter)

        # Add the message dialog to the main layout
        self.main_layout.addWidget(self.error_dialog)

        # Schedule the message dialog to be removed after 2 seconds
        QTimer.singleShot(2000, self.remove_error)

    def remove_error(self):
        """Safely remove the error widget from the main layout."""
        if hasattr(self, 'error_dialog') and self.error_dialog is not None:
            self.main_layout.removeWidget(self.error_dialog)
            self.error_dialog.deleteLater()
            self.error_dialog = None

def main():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()

if __name__ == "__main__":
    main()
