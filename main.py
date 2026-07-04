"""PySide6 macOS desktop chat app for OpenAI."""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from openai_client import ChatMessage, OpenAIChatClient, user_friendly_error
from settings import DEFAULT_MODEL, load_api_key, load_preferences, save_api_key, save_preferences


class EnterToSendTextEdit(QPlainTextEdit):
    """Text box that sends on Enter and inserts a newline on Shift+Enter."""

    send_requested = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt method name
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            self.send_requested.emit()
            return
        super().keyPressEvent(event)


class ChatWorker(QThread):
    """Runs the API call away from the GUI thread so the app stays responsive."""

    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, api_key: str, model: str, messages: list[ChatMessage]) -> None:
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.messages = messages

    def run(self) -> None:
        try:
            client = OpenAIChatClient(self.api_key, self.model)
            self.succeeded.emit(client.send_message(self.messages))
        except Exception as exc:  # The UI should show clear errors, not crash.
            self.failed.emit(user_friendly_error(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OpenAI Chat")
        self.resize(940, 680)

        preferences = load_preferences()
        self.messages: list[ChatMessage] = []
        self.worker: Optional[ChatWorker] = None

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setObjectName("chatArea")

        self.input_box = EnterToSendTextEdit()
        self.input_box.setPlaceholderText("Message OpenAI...")
        self.input_box.setFixedHeight(86)
        self.input_box.send_requested.connect(self.send_message)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("sk-...")
        self.key_input.setText(load_api_key())

        self.model_input = QLineEdit(preferences.get("model", DEFAULT_MODEL))

        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)

        clear_button = QPushButton("New Chat")
        clear_button.clicked.connect(self.clear_chat)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.build_chat_panel())
        splitter.addWidget(self.build_settings_panel(save_button, clear_button))
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(splitter)
        self.setCentralWidget(root)
        self.apply_styles()
        self.append_system_message("Ready. Paste your API key in Settings, then start chatting.")

    def build_chat_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self.chat_area)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input_box, 1)
        input_row.addWidget(self.send_button)
        layout.addLayout(input_row)
        return panel

    def build_settings_panel(self, save_button: QPushButton, clear_button: QPushButton) -> QWidget:
        panel = QFrame()
        panel.setObjectName("settingsPanel")
        panel.setMinimumWidth(260)
        panel.setMaximumWidth(340)

        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        title = QLabel("Settings")
        title.setObjectName("settingsTitle")

        layout.addWidget(title)
        layout.addWidget(QLabel("OpenAI API key"))
        layout.addWidget(self.key_input)
        layout.addWidget(QLabel("Model"))
        layout.addWidget(self.model_input)
        layout.addWidget(save_button)
        layout.addSpacing(12)
        layout.addWidget(clear_button)
        layout.addStretch(1)

        return panel

    def send_message(self) -> None:
        text = self.input_box.toPlainText().strip()
        if not text or self.worker is not None:
            return

        api_key = self.key_input.text().strip()
        if not api_key:
            self.show_error("Missing OpenAI API key. Paste your key in Settings first.")
            return

        self.messages.append(ChatMessage(role="user", content=text))
        self.append_message("You", text)
        self.input_box.clear()
        self.set_waiting(True)
        self.append_system_message("Assistant is thinking...")

        self.worker = ChatWorker(api_key, self.model_input.text(), self.messages.copy())
        self.worker.succeeded.connect(self.handle_response)
        self.worker.failed.connect(self.handle_error)
        self.worker.finished.connect(self.worker_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def handle_response(self, text: str) -> None:
        self.messages.append(ChatMessage(role="assistant", content=text))
        self.append_message("Assistant", text)
        self.set_waiting(False)

    def handle_error(self, message: str) -> None:
        self.messages.pop()
        self.append_system_message(message)
        self.set_waiting(False)

    def set_waiting(self, waiting: bool) -> None:
        self.send_button.setEnabled(not waiting)
        self.input_box.setEnabled(not waiting)
        if not waiting:
            self.input_box.setFocus()

    def worker_finished(self) -> None:
        self.worker = None

    def save_settings(self) -> None:
        try:
            save_api_key(self.key_input.text())
            save_preferences(self.model_input.text())
            self.append_system_message("Settings saved.")
        except RuntimeError as exc:
            self.show_error(str(exc))

    def clear_chat(self) -> None:
        self.messages.clear()
        self.chat_area.clear()
        self.append_system_message("New chat started.")

    def append_message(self, speaker: str, text: str) -> None:
        escaped_text = self.escape(text).replace(chr(10), "<br>")
        self.chat_area.append(f"<p><b>{speaker}</b></p><p>{escaped_text}</p>")
        self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())

    def append_system_message(self, text: str) -> None:
        self.chat_area.append(f"<p class='system'><i>{self.escape(text)}</i></p>")
        self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self, "OpenAI Chat", message)
        self.append_system_message(message)

    @staticmethod
    def escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                font-size: 14px;
            }
            QTextEdit#chatArea {
                background: #fbfbfc;
                border: 1px solid #d7d7dc;
                border-radius: 8px;
                padding: 12px;
            }
            QFrame#settingsPanel {
                background: #f3f4f6;
                border: 1px solid #d7d7dc;
                border-radius: 8px;
                padding: 8px;
            }
            QLabel#settingsTitle {
                font-size: 18px;
                font-weight: 700;
                padding-bottom: 8px;
            }
            QLineEdit, QPlainTextEdit {
                border: 1px solid #c9c9d1;
                border-radius: 6px;
                padding: 8px;
                background: white;
            }
            QPushButton {
                border-radius: 6px;
                padding: 8px 12px;
                background: #2463eb;
                color: white;
                font-weight: 600;
            }
            QPushButton:disabled {
                background: #9aa7c4;
            }
            """
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("OpenAI Chat")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
