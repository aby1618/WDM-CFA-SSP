import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from wdmtoolbox import wdmtoolbox
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton, QFileDialog, QLabel, QWidget, QLineEdit, QHBoxLayout, QScrollArea, QDialog
, QCheckBox, QGridLayout, QProgressBar, QTableWidget, QTableWidgetItem )
from PySide6.QtWebEngineWidgets import QWebEngineView
from typing import List
from PySide6.QtCore import Qt, QTimer
from PySide6.QtCore import QObject, QThread, Signal

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
        """Display an error message."""
        # Create a QLabel for the error message
        error_dialog = QLabel(f"<p style='color: red;'>{message}</p>")
        error_dialog.setFrameStyle(QLabel.Panel | QLabel.Sunken)
        error_dialog.setAlignment(Qt.AlignCenter)

        # Add the error dialog to the layout
        self.layout.addWidget(error_dialog)

        # Schedule the error dialog to be removed after 5 seconds
        QTimer.singleShot(5000, lambda: self.remove_error(error_dialog))

    def remove_error(self, widget):
        """Safely remove the error widget from the layout."""
        if widget in self.layout.children():
            self.layout.removeWidget(widget)
            widget.deleteLater()

def main():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()

if __name__ == "__main__":
    main()