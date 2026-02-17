import json
import sys
import os
import datetime as dt
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QSplitter,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QToolBar,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QGroupBox,
    QProgressDialog,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QComboBox,
    QCheckBox,
    QStackedWidget,
    QScrollArea,
    QGridLayout,
    QTabWidget,
    QMenu,
    QSizePolicy,
)

from PySide6.QtGui import QAction, QIcon, QKeySequence, QFont, QPalette, QColor
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSize

import markdown

# Import backend logic
sys.path.append(os.path.dirname(__file__))
from backend import NoteManager

# Import env manager
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
import manage_env


# ---------------------------------------------------------
# MAKISE KURISU STYLE: "Deep Logic" Theme
# ---------------------------------------------------------
COLORS = {
    "primary": "#38bdf8",        # Electric Cyan/Blue (High energy)
    "primary_dark": "#0ea5e9",   # Deep Sky Blue
    "primary_dim": "rgba(56, 189, 248, 0.1)", # Transparent accent
    "success": "#4ade80",        # Neon Green
    "warning": "#fbbf24",        # Amber
    "error": "#f87171",          # Soft Red
    "background": "#0f172a",     # Midnight Blue (The Void)
    "surface": "#1e293b",        # Slate Blue (Panels/Cards)
    "surface_bright": "#334155", # Lighter Highlight
    "text": "#f8fafc",           # Crisp White
    "text_secondary": "#94a3b8", # Muted Blue-Grey
    "text_muted": "#64748b",     # Darker Grey
    "border": "#334155",         # Subtle Separators
    "input_bg": "#020617",       # Deepest Blue for Input Fields
}

class WorkerThread(QThread):
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(str(result))
        except Exception as e:
            self.error.emit(str(e))


class WelcomeDialog(QDialog):
    """Welcome dialog for creating or opening scratch notes."""

    fileSelected = Signal(Path)
    createNew = Signal(str, str)  # name, date

    def __init__(self, manager: NoteManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("📝 Daily Report Client")
        self.resize(900, 650)
        self.setup_ui()
        self.load_recent_files()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS["background"]};
            }}
            /* Main Buttons */
            QPushButton {{
                background-color: {COLORS["primary"]};
                color: #0f172a; /* Dark text on bright button for contrast */
                border: none;
                border-radius: 8px;
                padding: 14px 28px;
                font-weight: 700;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {COLORS["primary_dark"]};
            }}
            /* Outline Buttons */
            QPushButton#secondary {{
                background-color: transparent;
                color: {COLORS["primary"]};
                border: 2px solid {COLORS["primary"]};
            }}
            QPushButton#secondary:hover {{
                background-color: {COLORS["primary_dim"]};
            }}
            /* Input Fields - Deep background */
            QLineEdit {{
                background-color: {COLORS["input_bg"]};
                border: 2px solid {COLORS["border"]};
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                color: {COLORS["text"]};
                selection-background-color: {COLORS["primary"]};
                selection-color: {COLORS["input_bg"]};
            }}
            QLineEdit:focus {{
                border-color: {COLORS["primary"]};
            }}
            /* Lists - Card Style with Breathing Room */
            QListWidget {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 12px 16px;
                margin-bottom: 8px;
                color: #e2e8f0;
            }}
            QListWidget::item:hover {{
                background-color: #1e293b;
                border-color: #38bdf8;
            }}
            QListWidget::item:selected {{
                background-color: rgba(56, 189, 248, 0.15);
                border: 1px solid #38bdf8;
                color: #38bdf8;
            }}
            /* Text Labels */
            QLabel {{
                color: {COLORS["text"]};
            }}
            /* Cards/Panels */
            QFrame#card {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(24)
        layout.setContentsMargins(40, 40, 40, 40)

        # Header
        header = QLabel("🚀 Welcome to Daily Report Client")
        header.setStyleSheet("font-size: 28px; font-weight: bold; color: #1565C0;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        subtitle = QLabel("Create, manage, and generate your daily technical reports")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        # Main content area
        content = QHBoxLayout()
        content.setSpacing(24)

        # Left: Create new
        left_card = QFrame()
        left_card.setObjectName("card")
        left_layout = QVBoxLayout(left_card)
        left_layout.setSpacing(16)

        new_title = QLabel("✨ Create New Note")
        new_title.setStyleSheet("font-size: 18px; font-weight: bold; background-color: rgba(56, 189, 248, 0.1); padding: 8px; border-radius: 6px; color: #38bdf8;")
        new_title.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        left_layout.addWidget(new_title)

        # Name input
        name_label = QLabel("Note Title:")
        name_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        name_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred) 
        left_layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., LLM Research, Bug Fix Session...")
        left_layout.addWidget(self.name_input)

        # Date input
        date_label = QLabel("Date:")
        date_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        date_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        left_layout.addWidget(date_label)

        self.date_input = QLineEdit()
        self.date_input.setText(dt.date.today().isoformat())
        left_layout.addWidget(self.date_input)

        left_layout.addStretch()

        create_btn = QPushButton("📝 Create Note")
        create_btn.clicked.connect(self.on_create_new)
        left_layout.addWidget(create_btn)

        content.addWidget(left_card, 1)

        # Right: Recent files
        right_card = QFrame()
        right_card.setObjectName("card")
        right_layout = QVBoxLayout(right_card)
        right_layout.setSpacing(16)

        recent_title = QLabel("📚 Recent Notes")
        recent_title.setStyleSheet("font-size: 18px; font-weight: bold; background-color: rgba(56, 189, 248, 0.1); padding: 8px; border-radius: 6px; color: #38bdf8;")
        recent_title.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        right_layout.addWidget(recent_title)

        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self.on_file_selected)
        self.recent_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.recent_list.customContextMenuRequested.connect(self.show_context_menu)
        right_layout.addWidget(self.recent_list)

        open_btn = QPushButton("📂 Open Selected")
        open_btn.setObjectName("secondary")
        open_btn.clicked.connect(self.on_open_selected)
        right_layout.addWidget(open_btn)

        content.addWidget(right_card, 1)

        layout.addLayout(content)

        # Bottom: Quick actions
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)

        browse_scratch = QPushButton("📁 Browse Scratch")
        browse_scratch.setObjectName("secondary")
        browse_scratch.clicked.connect(self.browse_scratch)
        bottom_layout.addWidget(browse_scratch)

        browse_reports = QPushButton("📊 Browse Reports")
        browse_reports.setObjectName("secondary")
        browse_reports.clicked.connect(self.browse_reports)
        bottom_layout.addWidget(browse_reports)

        bottom_layout.addStretch()

        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setObjectName("secondary")
        settings_btn.clicked.connect(self.open_settings)
        bottom_layout.addWidget(settings_btn)

        layout.addLayout(bottom_layout)

    def load_recent_files(self):
        self.recent_list.clear()
        files = self.manager.list_scratch_files()

        for file_info in files[:20]:  # Show last 20 files
            item = QListWidgetItem()
            item.setData(Qt.UserRole, file_info["path"])

            # Format display text
            name = file_info["name"]
            modified = file_info["modified"].strftime("%Y-%m-%d %H:%M")
            size = self._format_size(file_info["size"])

            item.setText(f"{name}\n   📅 {modified}  •  📄 {size}")
            self.recent_list.addItem(item)

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f}KB"
        else:
            return f"{size/(1024*1024):.1f}MB"

    def on_create_new(self):
        name = self.name_input.text().strip()
        date_str = self.date_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Missing Title", "Please enter a note title.")
            return

        try:
            dt.date.fromisoformat(date_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Date", "Please enter a valid date (YYYY-MM-DD).")
            return

        self.createNew.emit(name, date_str)
        self.accept()

    def on_file_selected(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        self.fileSelected.emit(path)
        self.accept()

    def on_open_selected(self):
        selected = self.recent_list.selectedItems()
        if selected:
            self.on_file_selected(selected[0])
        else:
            QMessageBox.information(self, "No Selection", "Please select a file from the list.")

    def show_context_menu(self, position):
        item = self.recent_list.itemAt(position)
        if not item:
            return

        menu = QMenu(self)
        open_action = menu.addAction("📂 Open")
        delete_action = menu.addAction("🗑️ Delete")

        action = menu.exec(self.recent_list.mapToGlobal(position))
        if action == open_action:
            self.on_file_selected(item)
        elif action == delete_action:
            path = item.data(Qt.UserRole)
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Delete '{path.name}'?\n\nThis action cannot be undone.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                path.unlink()
                self.load_recent_files()

    def browse_scratch(self):
        dialog = FileBrowserDialog(self.manager, "scratch", self)
        dialog.fileSelected.connect(self.on_file_selected_from_browser)
        dialog.exec()

    def browse_reports(self):
        dialog = FileBrowserDialog(self.manager, "reports", self)
        dialog.fileSelected.connect(self.on_file_selected_from_browser)
        dialog.exec()

    def on_file_selected_from_browser(self, path: Path):
        self.fileSelected.emit(path)
        self.accept()

    def open_settings(self):
        dlg = EnvSettingsDialog(self)
        dlg.exec()


class FileBrowserDialog(QDialog):
    """Dialog for browsing scratch files or reports."""

    fileSelected = Signal(Path)
    reportDeleted = Signal()

    def __init__(self, manager: NoteManager, mode: str = "scratch", parent=None):
        super().__init__(parent)
        self.manager = manager
        self.mode = mode
        self.setWindowTitle("📁 File Browser" if mode == "scratch" else "📊 Report Browser")
        self.resize(1000, 700)
        self.setup_ui()
        self.load_files()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS["background"]};
            }}
            QPushButton {{
                background-color: {COLORS["primary"]};
                color: #000000;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton#danger {{
                background-color: rgba(248, 113, 113, 0.2);
                color: {COLORS["error"]};
                border: 1px solid {COLORS["error"]};
            }}
            QPushButton#danger:hover {{
                background-color: {COLORS["error"]};
                color: white;
            }}
            /* Table Styling */
            QTableWidget {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 8px;
                gridline-color: {COLORS["border"]};
                color: {COLORS["text"]};
                selection-background-color: {COLORS["primary_dim"]};
                selection-color: {COLORS["primary"]};
            }}
            QHeaderView::section {{
                background-color: {COLORS["background"]};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {COLORS["primary"]};
                font-weight: bold;
                color: {COLORS["primary"]};
            }}
            /* Scrollbars (Optional refinement) */
            QScrollBar:vertical {{
                background: {COLORS["background"]};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS["surface_bright"]};
                min-height: 20px;
                border-radius: 5px;
            }}
            QLineEdit {{
                background-color: {COLORS["input_bg"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
                padding: 8px;
                color: {COLORS["text"]};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel("📁 Scratch Files" if self.mode == "scratch" else "📊 Generated Reports")
        header.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(header)

        # Search/filter
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Search:")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by name, title, or tags...")
        self.search_input.textChanged.connect(self.filter_files)
        search_layout.addWidget(self.search_input)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setObjectName("secondary")
        refresh_btn.clicked.connect(self.load_files)
        search_layout.addWidget(refresh_btn)

        layout.addLayout(search_layout)

        # File table
        self.table = QTableWidget()
        self.table.setColumnCount(6 if self.mode == "reports" else 3)
        headers = ["Name", "Date Modified", "Size"]
        if self.mode == "reports":
            headers = ["Name", "Title", "Tags", "Date", "Modified", "Size"]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)  # 多选模式
        self.table.doubleClicked.connect(self.on_open)
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()

        # Delete button for both modes
        delete_btn = QPushButton("🗑️ Delete Selected")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self.on_delete_multi)
        btn_layout.addWidget(delete_btn)

        if self.mode == "reports":
            generate_weekly_btn = QPushButton("📅 Generate Weekly Summary")
            generate_weekly_btn.clicked.connect(self.on_generate_weekly)
            btn_layout.addWidget(generate_weekly_btn)

        btn_layout.addStretch()

        open_btn = QPushButton("📂 Open Selected")
        open_btn.clicked.connect(self.on_open)
        btn_layout.addWidget(open_btn)

        cancel_btn = QPushButton("Close")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        self.files_data = []

    def load_files(self):
        self.files_data = []

        if self.mode == "scratch":
            files = self.manager.list_scratch_files()
            for f in files:
                self.files_data.append({
                    "path": f["path"],
                    "name": f["name"],
                    "modified": f["modified"].strftime("%Y-%m-%d %H:%M"),
                    "size": self._format_size(f["size"]),
                })
        else:
            reports = self.manager.list_daily_reports()
            for r in reports:
                self.files_data.append({
                    "path": r["path"],
                    "name": r["name"],
                    "title": r.get("title", "N/A"),
                    "tags": ", ".join(r.get("tags", [])),
                    "date": r.get("date", ""),
                    "modified": r["modified"].strftime("%Y-%m-%d %H:%M"),
                    "size": self._format_size(r["size"]),
                })

        self.update_table()

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f}KB"
        else:
            return f"{size/(1024*1024):.1f}MB"

    def update_table(self):
        self.table.setRowCount(len(self.files_data))

        for i, data in enumerate(self.files_data):
            if self.mode == "scratch":
                self.table.setItem(i, 0, QTableWidgetItem(data["name"]))
                self.table.setItem(i, 1, QTableWidgetItem(data["modified"]))
                self.table.setItem(i, 2, QTableWidgetItem(data["size"]))
            else:
                self.table.setItem(i, 0, QTableWidgetItem(data["name"]))
                self.table.setItem(i, 1, QTableWidgetItem(data["title"]))
                self.table.setItem(i, 2, QTableWidgetItem(data["tags"]))
                self.table.setItem(i, 3, QTableWidgetItem(data["date"]))
                self.table.setItem(i, 4, QTableWidgetItem(data["modified"]))
                self.table.setItem(i, 5, QTableWidgetItem(data["size"]))

    def filter_files(self, text: str):
        text = text.lower()
        filtered = []
        for data in self.files_data:
            if any(text in str(v).lower() for v in data.values() if isinstance(v, str)):
                filtered.append(data)

        self.table.setRowCount(len(filtered))
        for i, data in enumerate(filtered):
            if self.mode == "scratch":
                self.table.setItem(i, 0, QTableWidgetItem(data["name"]))
                self.table.setItem(i, 1, QTableWidgetItem(data["modified"]))
                self.table.setItem(i, 2, QTableWidgetItem(data["size"]))
            else:
                self.table.setItem(i, 0, QTableWidgetItem(data["name"]))
                self.table.setItem(i, 1, QTableWidgetItem(data["title"]))
                self.table.setItem(i, 2, QTableWidgetItem(data["tags"]))
                self.table.setItem(i, 3, QTableWidgetItem(data["date"]))
                self.table.setItem(i, 4, QTableWidgetItem(data["modified"]))
                self.table.setItem(i, 5, QTableWidgetItem(data["size"]))

    def on_open(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select a file.")
            return

        row = selected[0].row()
        if row < len(self.files_data):
            path = self.files_data[row]["path"]
            self.fileSelected.emit(path)
            self.accept()

    def on_delete(self):
        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        if row >= len(self.files_data):
            return

        path = self.files_data[row]["path"]
        name = self.files_data[row]["name"]

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete report '{name}'?\n\nThis will also remove the hash from the index.",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            if self.manager.delete_report(path):
                QMessageBox.information(self, "Deleted", f"Report '{name}' deleted successfully.")
                self.reportDeleted.emit()
                self.load_files()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete report.")

    def on_delete_multi(self):
        """Delete multiple selected files."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select files to delete.")
            return

        # Get unique rows
        rows = set(item.row() for item in selected)
        valid_rows = [r for r in rows if r < len(self.files_data)]

        if not valid_rows:
            return

        # Prepare confirmation message
        names = [self.files_data[r]["name"] for r in valid_rows]
        if len(names) > 5:
            display_names = "\n".join(names[:5]) + f"\n... and {len(names) - 5} more"
        else:
            display_names = "\n".join(names)

        mode_text = "reports" if self.mode == "reports" else "scratch files"
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(names)} {mode_text}?\n\n{display_names}\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        # Delete files
        success_count = 0
        failed_names = []

        for row in valid_rows:
            path = self.files_data[row]["path"]
            name = self.files_data[row]["name"]

            try:
                if self.mode == "reports":
                    if self.manager.delete_report(path):
                        success_count += 1
                    else:
                        failed_names.append(name)
                else:
                    # Scratch mode - just delete the file
                    path.unlink()
                    success_count += 1
            except Exception as e:
                failed_names.append(f"{name} ({e})")

        # Show result
        if success_count > 0:
            if self.mode == "reports":
                self.reportDeleted.emit()
            self.load_files()

        if failed_names:
            QMessageBox.critical(
                self,
                "Partial Error",
                f"Deleted {success_count} files.\n\nFailed to delete:\n" + "\n".join(failed_names)
            )
        else:
            QMessageBox.information(self, "Success", f"Successfully deleted {success_count} files.")

    def on_generate_weekly(self):
        dialog = GenerateWeeklyDialog(self.manager, self)
        dialog.exec()


class GenerateWeeklyDialog(QDialog):
    """Dialog for generating weekly summary."""

    def __init__(self, manager: NoteManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("📅 Generate Weekly Summary")
        self.resize(450, 300)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS["background"]};
            }}
            QPushButton {{
                background-color: {COLORS["success"]};
                color: {COLORS["text"]};
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #1B5E20;
            }}
            QPushButton:disabled {{
                background-color: {COLORS["border"]};
                color: {COLORS["text_muted"]};
            }}
            QComboBox {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
                padding: 8px;
                color: {COLORS["text"]};
            }}
            QLabel {{
                color: {COLORS["text"]};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("📅 Generate Weekly Summary")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        info = QLabel("Generate a weekly summary from your daily reports.")
        info.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(info)

        # Year selection
        year_layout = QHBoxLayout()
        year_label = QLabel("Year:")
        year_layout.addWidget(year_label)

        self.year_combo = QComboBox()
        current_year = dt.date.today().year
        for year in range(current_year - 2, current_year + 1):
            self.year_combo.addItem(str(year), year)
        self.year_combo.setCurrentText(str(current_year))
        year_layout.addWidget(self.year_combo)
        layout.addLayout(year_layout)

        # Week selection
        week_layout = QHBoxLayout()
        week_label = QLabel("Week:")
        week_layout.addWidget(week_label)

        self.week_combo = QComboBox()
        for week in range(1, 54):
            self.week_combo.addItem(f"Week {week:02d}", week)

        # Set current week
        current_week = dt.date.today().isocalendar()[1]
        self.week_combo.setCurrentIndex(current_week - 1)
        week_layout.addWidget(self.week_combo)
        layout.addLayout(week_layout)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()

        self.generate_btn = QPushButton("🚀 Generate Summary")
        self.generate_btn.clicked.connect(self.on_generate)
        btn_layout.addWidget(self.generate_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

    def on_generate(self):
        year = self.year_combo.currentData()
        week = self.week_combo.currentData()

        self.generate_btn.setEnabled(False)
        self.status_label.setText("⏳ Generating weekly summary...")
        self.status_label.setStyleSheet(f"color: {COLORS['primary']};")

        self.worker = WorkerThread(self.manager.generate_weekly_summary, year, week)
        self.worker.finished.connect(self.on_success)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_success(self, output):
        self.status_label.setText("✅ Weekly summary generated!")
        self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        self.generate_btn.setEnabled(True)
        QMessageBox.information(self, "Success", "Weekly summary generated successfully!")
        self.accept()

    def on_error(self, error):
        self.status_label.setText("❌ Generation failed!")
        self.status_label.setStyleSheet(f"color: {COLORS['error']};")
        self.generate_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to generate weekly summary:\n\n{error}")


class MarkdownEditor(QTextEdit):
    contentChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        font = QFont("JetBrains Mono", 12)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS["background"]}; /* Deep dark */
                border: none; /* Clean look */
                padding: 16px;
                color: {COLORS["text"]};
                font-family: "JetBrains Mono", "Consolas", monospace;
                font-size: 13px;
                line-height: 1.5;
            }}
        """)
        self.textChanged.connect(self.contentChanged.emit)


class EnvSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Environment Settings")
        self.resize(650, 450)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS["background"]};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                border: 1px solid {COLORS["border"]};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                padding: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: {COLORS["primary"]};
            }}
            QPushButton {{
                background-color: {COLORS["primary"]};
                color: {COLORS["text"]};
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {COLORS["primary_dark"]};
            }}
            QPushButton:pressed {{
                background-color: {COLORS["primary"]};
            }}
            QPushButton#secondary {{
                background-color: transparent;
                color: {COLORS["primary"]};
                border: 1px solid {COLORS["primary"]};
            }}
            QPushButton#secondary:hover {{
                background-color: rgba(25, 118, 210, 0.1);
            }}
            QPushButton#danger {{
                background-color: {COLORS["error"]};
                color: {COLORS["text"]};
            }}
            QTableWidget {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
                gridline-color: {COLORS["border"]};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:selected {{
                background-color: rgba(33, 150, 243, 0.2);
                color: {COLORS["text"]};
            }}
            QHeaderView::section {{
                background-color: {COLORS["background"]};
                padding: 10px;
                border: none;
                border-bottom: 2px solid {COLORS["border"]};
                font-weight: bold;
                color: {COLORS["text_secondary"]};
            }}
            QLabel {{
                color: {COLORS["text"]};
            }}
            QLabel#help {{
                color: {COLORS["text_secondary"]};
                font-size: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("🔐 Environment Variables")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLORS['text']};")
        layout.addWidget(title)

        # Help text
        help_text = QLabel("Configure your API keys and settings. Values are stored locally in .env.secrets")
        help_text.setObjectName("help")
        layout.addWidget(help_text)

        # Settings Group
        settings_group = QGroupBox("API Configuration")
        settings_layout = QVBoxLayout(settings_group)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["🔑 Key", "📝 Value"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setColumnWidth(0, 200)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        settings_layout.addWidget(self.table)

        # Button row
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("➕ Add Variable")
        add_btn.setObjectName("secondary")
        add_btn.clicked.connect(self.add_empty_row)
        btn_layout.addWidget(add_btn)

        delete_btn = QPushButton("🗑️ Delete Selected")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self.delete_selected_row)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        reset_btn = QPushButton("🔄 Refresh")
        reset_btn.setObjectName("secondary")
        reset_btn.clicked.connect(self.load_settings)
        btn_layout.addWidget(reset_btn)

        settings_layout.addLayout(btn_layout)
        layout.addWidget(settings_group)

        # Dialog buttons
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        dialog_buttons.button(QDialogButtonBox.Save).setText("💾 Save Settings")
        dialog_buttons.button(QDialogButtonBox.Cancel).setText("Cancel")
        dialog_buttons.accepted.connect(self.save_settings)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

    def load_settings(self):
        """Load settings from .env.secrets only"""
        # Only load from .env.secrets, not system env
        envs = manage_env.load_env()

        # Pre-populate with essential keys if not exists
        default_keys = {
            "REPORT_API_KEY": "",
            "REPORT_API_URL": "",
            "REPORT_API_MODEL": "",
        }

        for key, default_val in default_keys.items():
            if key not in envs:
                envs[key] = default_val

        self.table.setRowCount(len(envs))

        for i, (k, v) in enumerate(sorted(envs.items())):
            key_item = QTableWidgetItem(k)
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            key_item.setBackground(QColor(COLORS["background"]))
            self.table.setItem(i, 0, key_item)

            # Mask sensitive values
            val_item = QTableWidgetItem(str(v))
            if "key" in k.lower() or "token" in k.lower() or "secret" in k.lower():
                val_item.setToolTip("Double-click to edit (sensitive value)")
            self.table.setItem(i, 1, val_item)

    def add_empty_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem("NEW_KEY"))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.editItem(self.table.item(row, 0))

    def delete_selected_row(self):
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            self.table.removeRow(row)

    def save_settings(self):
        current_data = {}
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            val_item = self.table.item(row, 1)

            if key_item and val_item:
                key = key_item.text().strip()
                val = val_item.text().strip()
                if key and key != "NEW_KEY":
                    current_data[key] = val

        try:
            with open(manage_env.ENV_FILE, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=2)

            # Reload to reflect changes
            self.load_settings()

            QMessageBox.information(self, "✅ Saved", "Settings saved successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "❌ Error", f"Failed to save settings:\n{str(e)}")


class SyncDialog(QDialog):
    def __init__(self, manager: NoteManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("🔄 Sync Repository")
        self.resize(500, 400)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS["background"]};
            }}
            QPushButton {{
                background-color: {COLORS["primary"]};
                color: {COLORS["text"]};
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 500;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {COLORS["primary_dark"]};
            }}
            QPushButton:disabled {{
                background-color: {COLORS["border"]};
                color: {COLORS["text_muted"]};
            }}
            QPushButton#secondary {{
                background-color: transparent;
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
            }}
            QListWidget {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 8px;
                padding: 8px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
            }}
            QListWidget::item:selected {{
                background-color: rgba(33, 150, 243, 0.1);
                color: {COLORS["text"]};
            }}
            QLabel {{
                color: {COLORS["text"]};
            }}
            QLabel#status {{
                color: {COLORS["text_secondary"]};
                font-size: 13px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("🚀 Sync to GitHub")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        # Status
        self.status_label = QLabel("Ready to sync your notes to the remote repository.")
        self.status_label.setObjectName("status")
        layout.addWidget(self.status_label)

        # Progress list
        self.progress_list = QListWidget()
        layout.addWidget(self.progress_list)

        # Button layout
        btn_layout = QHBoxLayout()

        self.sync_btn = QPushButton("🔄 Start Sync")
        self.sync_btn.clicked.connect(self.start_sync)
        btn_layout.addWidget(self.sync_btn)

        cancel_btn = QPushButton("Close")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        self.worker = None

    def add_progress(self, icon: str, message: str, status: str = "pending"):
        item = QListWidgetItem(f"{icon} {message}")
        if status == "success":
            item.setForeground(QColor(COLORS["success"]))
        elif status == "error":
            item.setForeground(QColor(COLORS["error"]))
        elif status == "running":
            item.setForeground(QColor(COLORS["primary"]))
        self.progress_list.addItem(item)
        self.progress_list.scrollToBottom()
        return item

    def start_sync(self):
        self.sync_btn.setEnabled(False)
        self.progress_list.clear()
        self.add_progress("⏳", "Initializing sync...", "running")

        self.worker = WorkerThread(self.manager.sync)
        self.worker.finished.connect(self.on_sync_success)
        self.worker.error.connect(self.on_sync_error)
        self.worker.start()

    def on_sync_success(self, message):
        self.add_progress("✅", f"Sync complete: {message}", "success")
        self.status_label.setText("🎉 All changes synced successfully!")
        self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        self.sync_btn.setEnabled(True)
        self.sync_btn.setText("🔄 Sync Again")

    def on_sync_error(self, error):
        self.add_progress("❌", f"Sync failed: {error}", "error")
        self.status_label.setText("⚠️ Sync encountered an error.")
        self.status_label.setStyleSheet(f"color: {COLORS['error']};")
        self.sync_btn.setEnabled(True)


class GenerateReportDialog(QDialog):
    def __init__(self, manager: NoteManager, input_path: Path = None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.input_path = input_path
        self.setWindowTitle("📝 Generate Report")
        self.resize(500, 350)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS["background"]};
            }}
            QPushButton {{
                background-color: {COLORS["success"]};
                color: {COLORS["text"]};
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 500;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #1B5E20;
            }}
            QPushButton:disabled {{
                background-color: {COLORS["border"]};
                color: {COLORS["text_muted"]};
            }}
            QPushButton#secondary {{
                background-color: transparent;
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
            }}
            QCheckBox {{
                color: {COLORS["text"]};
            }}
            QLabel {{
                color: {COLORS["text"]};
            }}
            QFrame#card {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 8px;
                padding: 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("📝 Generate Daily Report")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        # Info card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)

        file_name = self.input_path.name if self.input_path else "Current note"
        info = QLabel(f"This will convert '{file_name}' into a structured daily report using AI.")
        info.setWordWrap(True)
        card_layout.addWidget(info)

        layout.addWidget(card)

        # Options
        self.force_check = QCheckBox("Force regeneration (ignore hash check)")
        layout.addWidget(self.force_check)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()

        self.generate_btn = QPushButton("🚀 Generate Report")
        self.generate_btn.clicked.connect(self.start_generation)
        btn_layout.addWidget(self.generate_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        # Status
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

    def start_generation(self):
        self.generate_btn.setEnabled(False)
        self.status_label.setText("⏳ Generating report... This may take a minute.")
        self.status_label.setStyleSheet(f"color: {COLORS['primary']};")

        force = self.force_check.isChecked()

        self.worker = WorkerThread(
            self.manager.generate_report,
            self.input_path,
            None,  # date_str
            force
        )
        self.worker.finished.connect(self.on_generation_success)
        self.worker.error.connect(self.on_generation_error)
        self.worker.start()

    def on_generation_success(self, output):
        self.status_label.setText("✅ Report generated successfully!")
        self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("🔄 Generate Another")

        QMessageBox.information(
            self,
            "✅ Success",
            "Report generated successfully!\n\nCheck the content/daily/ folder.",
        )
        self.accept()

    def on_generation_error(self, error):
        self.status_label.setText("❌ Generation failed!")
        self.status_label.setStyleSheet(f"color: {COLORS['error']};")
        self.generate_btn.setEnabled(True)

        QMessageBox.critical(self, "❌ Error", f"Report generation failed:\n\n{error}")


class MainWindow(QMainWindow):
    def __init__(self, manager: NoteManager, current_file: Path = None):
        super().__init__()
        self.manager = manager
        self.current_file = current_file
        self.setWindowTitle("📝 Daily Report Client")
        self.resize(1400, 900)

        self.setup_ui()
        self.load_note()
        self.apply_styles()

        # Autosave timer (every 30s)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.save_note)
        self.autosave_timer.start(30000)

        # Track unsaved changes
        self.has_unsaved_changes = False

    def apply_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS["background"]};
            }}
            QToolBar {{
                background-color: {COLORS["surface"]};
                border-bottom: 1px solid {COLORS["border"]};
                spacing: 10px;
                padding: 5px;
            }}
            QToolButton {{
                background-color: transparent;
                border-radius: 4px;
                color: {COLORS["text"]};
                padding: 6px;
            }}
            QToolButton:hover {{
                background-color: {COLORS["primary_dim"]};
                color: {COLORS["primary"]};
            }}
            QStatusBar {{
                background-color: {COLORS["surface"]};
                color: {COLORS["text_secondary"]};
            }}
            /* The Splitter Handle */
            QSplitter::handle {{
                background-color: {COLORS["border"]};
                width: 2px;
            }}
            QLabel {{ color: {COLORS["text"]}; }}
        """)

    def setup_ui(self):
        # Toolbar
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Home action - back to welcome screen
        home_action = QAction("🏠 Home", self)
        home_action.setShortcut("Ctrl+H")
        home_action.triggered.connect(self.go_home)
        toolbar.addAction(home_action)

        toolbar.addSeparator()

        # File actions
        new_action = QAction("🆕 New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_file)
        toolbar.addAction(new_action)

        save_action = QAction("💾 Save", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_note_silent)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        # Sync action
        sync_action = QAction("🔄 Sync", self)
        sync_action.setShortcut("Ctrl+Shift+S")
        sync_action.triggered.connect(self.open_sync_dialog)
        toolbar.addAction(sync_action)

        toolbar.addSeparator()

        # Generate action
        generate_action = QAction("📝 Generate Report", self)
        generate_action.setShortcut("Ctrl+G")
        generate_action.triggered.connect(self.open_generate_dialog)
        toolbar.addAction(generate_action)

        toolbar.addSeparator()

        # Browse actions
        browse_scratch_action = QAction("📁 Scratch", self)
        browse_scratch_action.triggered.connect(self.browse_scratch)
        toolbar.addAction(browse_scratch_action)

        browse_reports_action = QAction("📊 Reports", self)
        browse_reports_action.triggered.connect(self.browse_reports)
        toolbar.addAction(browse_reports_action)

        toolbar.addSeparator()

        # Settings action
        settings_action = QAction("⚙️ Settings", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        # Spacer
        toolbar.addSeparator()
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # File info label
        self.file_label = QLabel(self.get_file_display_name())
        self.file_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        toolbar.addWidget(self.file_label)

        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Editor panel
        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        editor_header = QLabel("✏️ Editor")
        editor_header.setStyleSheet("font-weight: bold; font-size: 14px; color: #424242;")
        editor_layout.addWidget(editor_header)

        self.editor = MarkdownEditor(self)
        self.editor.contentChanged.connect(self.on_content_changed)
        editor_layout.addWidget(self.editor)

        layout.addWidget(editor_panel, 1)

        # Preview panel
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        preview_header = QLabel("👁️ Preview")
        preview_header.setStyleSheet("font-weight: bold; font-size: 14px; color: #424242;")
        preview_layout.addWidget(preview_header)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 8px;
                padding: 16px;
                color: {COLORS["text"]};
                font-size: 14px;
                line-height: 1.6;
            }}
        """)
        preview_layout.addWidget(self.preview)

        layout.addWidget(preview_panel, 1)

        # Status Bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

    def get_file_display_name(self):
        if self.current_file:
            return f"📄 {self.current_file.name}"
        return "📄 New File"

    def on_content_changed(self):
        self.has_unsaved_changes = True
        self.update_preview()

    def load_note(self):
        if self.current_file and self.current_file.exists():
            text = self.current_file.read_text(encoding="utf-8")
            self.editor.setPlainText(text)
            self.status.showMessage(f"Loaded: {self.current_file.name}")
        else:
            self.editor.setPlainText(f"# Notes for {dt.date.today().isoformat()}\n\n")
            self.status.showMessage("New note created.")
        self.has_unsaved_changes = False
        self.file_label.setText(self.get_file_display_name())

    def save_note(self):
        if not self.current_file:
            return
        content = self.editor.toPlainText()
        self.current_file.write_text(content, encoding="utf-8")
        self.has_unsaved_changes = False
        self.status.showMessage(f"💾 Saved at {dt.datetime.now().strftime('%H:%M:%S')}")

    def save_note_silent(self):
        self.save_note()
        self.status.showMessage("✅ Saved successfully!")

    def update_preview(self):
        md_text = self.editor.toPlainText()
        html = markdown.markdown(md_text, extensions=["fenced_code", "tables", "nl2br"])

        # MAKISE KURISU NOTE: 
        # I have aligned the HTML CSS with the application's dark theme.
        css = f"""
        <style>
            body {{
                font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: {COLORS["text"]}; 
                background-color: {COLORS["surface"]}; /* Dark background for preview */
                font-size: 14px;
            }}
            /* Headers - Cyan/Blue accent */
            h1, h2, h3 {{
                color: {COLORS["primary"]};
                font-weight: 600;
                margin-top: 20px;
            }}
            h1 {{ border-bottom: 1px solid {COLORS["border"]}; padding-bottom: 10px; }}
            
            /* Code Blocks - The most important part */
            code {{
                background-color: {COLORS["primary_dim"]};
                color: {COLORS["primary"]};
                font-family: "JetBrains Mono", Consolas, monospace;
                padding: 2px 4px;
                border-radius: 4px;
            }}
            pre {{
                background-color: {COLORS["background"]}; /* Darker block */
                border: 1px solid {COLORS["border"]};
                padding: 15px;
                border-radius: 8px;
                overflow-x: auto;
            }}
            pre code {{
                background-color: transparent;
                color: {COLORS["text"]};
            }}
            
            /* Blockquotes */
            blockquote {{
                border-left: 4px solid {COLORS["primary"]};
                margin: 0;
                padding-left: 15px;
                color: {COLORS["text_secondary"]};
            }}
            
            /* Links */
            a {{ color: {COLORS["primary"]}; text-decoration: none; }}
            
            /* Tables */
            table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
            th {{ 
                background-color: {COLORS["background"]}; 
                color: {COLORS["primary"]};
                text-align: left; 
                padding: 10px;
                border-bottom: 2px solid {COLORS["border"]};
            }}
            td {{ 
                padding: 10px; 
                border-bottom: 1px solid {COLORS["border"]}; 
            }}
        </style>
        """
        self.preview.setHtml(css + html)

    def go_home(self):
        """Return to welcome screen."""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before returning to home?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                self.save_note()
            elif reply == QMessageBox.Cancel:
                return

        # Show welcome dialog
        dialog = WelcomeDialog(self.manager, self)
        dialog.fileSelected.connect(self.on_file_selected)
        dialog.createNew.connect(self.on_create_new)
        if dialog.exec() == QDialog.Accepted:
            if self.current_file:
                self.load_note()
        dialog.deleteLater()

    def new_file(self):
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before creating a new file?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                self.save_note()
            elif reply == QMessageBox.Cancel:
                return

        # Show welcome dialog to create new file
        dialog = WelcomeDialog(self.manager, self)
        dialog.fileSelected.connect(self.on_file_selected)
        dialog.createNew.connect(self.on_create_new)
        dialog.exec()

    def open_file_dialog(self):
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before opening another file?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                self.save_note()
            elif reply == QMessageBox.Cancel:
                return

        self.browse_scratch()

    def on_file_selected(self, path: Path):
        self.current_file = path
        self.load_note()

    def open_report_for_viewing(self, path: Path):
        """Open a report file for viewing in the editor."""
        self.current_file = path
        self.load_note()
        QMessageBox.information(self, "Report Opened", f"Opened report for viewing:\n{path.name}")

    def on_create_new(self, name: str, date_str: str):
        try:
            path = self.manager.create_scratch_note(name, date_str)
            self.current_file = path
            self.load_note()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create note: {e}")

    def browse_scratch(self):
        dialog = FileBrowserDialog(self.manager, "scratch", self)
        dialog.fileSelected.connect(self.on_file_selected)
        dialog.exec()

    def browse_reports(self):
        dialog = FileBrowserDialog(self.manager, "reports", self)
        dialog.fileSelected.connect(self.open_report_for_viewing)
        dialog.exec()

    def open_sync_dialog(self):
        if self.has_unsaved_changes:
            self.save_note()
        dlg = SyncDialog(self.manager, self)
        dlg.exec()

    def open_generate_dialog(self):
        if self.has_unsaved_changes:
            self.save_note()
        dlg = GenerateReportDialog(self.manager, self.current_file, self)
        dlg.exec()

    def open_settings(self):
        dlg = EnvSettingsDialog(self)
        dlg.exec()

    def closeEvent(self, event):
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Save:
                self.save_note()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)

    # Set application-wide font
    font = QFont("-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", 10)
    app.setFont(font)

    # Set application-wide palette and stylesheet for consistent theming
    app.setStyleSheet(f"""
        QApplication, QWidget {{
            background-color: {COLORS["background"]};
            color: {COLORS["text"]};
        }}
        QDialog {{
            background-color: {COLORS["background"]};
        }}
        QMainWindow {{
            background-color: {COLORS["background"]};
        }}
    """)

    # Initialize manager
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manager = NoteManager(repo_root)

    # Show welcome dialog
    welcome = WelcomeDialog(manager)

    current_file = None

    def on_file_selected(path: Path):
        nonlocal current_file
        current_file = path

    def on_create_new(name: str, date_str: str):
        nonlocal current_file
        try:
            current_file = manager.create_scratch_note(name, date_str)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to create note: {e}")

    welcome.fileSelected.connect(on_file_selected)
    welcome.createNew.connect(on_create_new)

    if welcome.exec() == QDialog.Accepted and current_file:
        window = MainWindow(manager, current_file)
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
