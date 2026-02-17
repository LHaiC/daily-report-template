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
    QSystemTrayIcon,
    QMenu,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
)

from PySide6.QtGui import QAction, QIcon, QKeySequence, QFont
from PySide6.QtCore import Qt, QTimer, QThread, Signal

import markdown

# Import backend logic
sys.path.append(os.path.dirname(__file__))
from backend import NoteManager

# Import env manager
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
import manage_env


class WorkerThread(QThread):
    finished = Signal(str)
    error = Signal(str)

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


class MarkdownEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)


class EnvSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Environment Variables (Local Secrets)")
        self.resize(600, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Key", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # Add new row button
        add_btn = QPushButton("Add Variable")
        add_btn.clicked.connect(self.add_empty_row)
        layout.addWidget(add_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.load_settings()

    def load_settings(self):
        envs = manage_env.list_all_env()
        self.table.setRowCount(len(envs))

        for i, (k, v) in enumerate(envs.items()):
            self.table.setItem(i, 0, QTableWidgetItem(k))
            self.table.setItem(i, 1, QTableWidgetItem(str(v)))

    def add_empty_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem("NEW_KEY"))
        self.table.setItem(row, 1, QTableWidgetItem(""))

    def save_settings(self):
        # Save only what's in the table to .env.secrets
        # Note: This will overwrite the file with current table contents
        # system envs that were displayed but not in .env.secrets will be added if modified

        current_data = {}
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            val_item = self.table.item(row, 1)

            if key_item and val_item:
                key = key_item.text().strip()
                val = val_item.text().strip()
                if key:
                    current_data[key] = val

        # Write to .env.secrets using manage_env
        # But manage_env.save_env saves one by one. Let's do it manually or loop.
        # Actually, manage_env.save_env reads-modifies-writes.
        # It's better to update all at once.
        # Let's just update the file directly using json
        try:
            with open(manage_env.ENV_FILE, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=2)
            QMessageBox.information(self, "Saved", "Settings saved successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Daily Report Client")
        self.resize(1200, 800)

        # Initialize Backend
        # Assuming gui/ is inside repo root
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.manager = NoteManager(repo_root)
        self.current_note_path = self.manager.ensure_today_note()

        self.setup_ui()
        self.load_note()

        # Autosave timer (every 30s)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.save_note)
        self.autosave_timer.start(30000)

    def setup_ui(self):
        # Toolbar
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)

        save_action = QAction("Save && Sync", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.sync_repo)
        toolbar.addAction(save_action)

        generate_action = QAction("Generate Report", self)
        generate_action.setShortcut("Ctrl+G")
        generate_action.triggered.connect(self.generate_report)
        toolbar.addAction(generate_action)

        settings_action = QAction("Settings", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Editor
        self.editor = MarkdownEditor(self)
        self.editor.textChanged.connect(self.update_preview)
        splitter.addWidget(self.editor)

        # Preview
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        splitter.addWidget(self.preview)

        splitter.setSizes([600, 600])

        # Status Bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

    def load_note(self):
        if self.current_note_path.exists():
            text = self.current_note_path.read_text(encoding="utf-8")
            self.editor.setPlainText(text)
            self.status.showMessage(f"Loaded: {self.current_note_path.name}")
        else:
            self.editor.setPlainText(f"# Notes for {dt.date.today().isoformat()}\n\n")
            self.status.showMessage("New note created.")

    def save_note(self):
        content = self.editor.toPlainText()
        self.current_note_path.write_text(content, encoding="utf-8")
        self.status.showMessage(f"Saved: {dt.datetime.now().strftime('%H:%M:%S')}")

    def update_preview(self):
        md_text = self.editor.toPlainText()
        # Convert markdown to HTML with extensions
        html = markdown.markdown(md_text, extensions=["fenced_code", "tables", "nl2br"])

        # Simple CSS for better look
        css = """
        <style>
            body { font-family: sans-serif; line-height: 1.6; padding: 10px; }
            code { background-color: #f0f0f0; padding: 2px 4px; border-radius: 3px; }
            pre { background-color: #f6f8fa; padding: 10px; border-radius: 5px; overflow-x: auto; }
            h1, h2, h3 { color: #333; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
            img { max-width: 100%; }
        </style>
        """
        self.preview.setHtml(css + html)

    def sync_repo(self):
        self.save_note()
        self.status.showMessage("Syncing...")

        # Run in thread to avoid UI freeze
        self.worker = WorkerThread(self.manager.sync)
        self.worker.finished.connect(lambda s: self.status.showMessage(s))
        self.worker.error.connect(lambda e: QMessageBox.warning(self, "Sync Error", e))
        self.worker.start()

    def generate_report(self):
        self.save_note()
        self.status.showMessage("Generating report...")

        self.worker = WorkerThread(self.manager.generate_report)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.error.connect(
            lambda e: QMessageBox.critical(self, "Generation Error", e)
        )
        self.worker.start()

    def on_generation_finished(self, output):
        self.status.showMessage("Report Generated!")
        QMessageBox.information(
            self,
            "Success",
            "Report generated successfully.\nCheck content/daily/ folder.",
        )

    def open_settings(self):
        dlg = EnvSettingsDialog(self)
        dlg.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
