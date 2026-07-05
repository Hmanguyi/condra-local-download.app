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
        self.resize(1040, 720)

        preferences = load_preferences()
        self.messages: list[ChatMessage] = []
        self.worker: Optional[ChatWorker] = None

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setObjectName("chatArea")
        self.chat_area.document().setDefaultStyleSheet(
            """
            body {
                color: #1f2937;
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
                font-size: 14px;
                line-height: 1.45;
            }
            .message-row {
                margin: 14px 0;
            }
            .speaker {
                color: #6b7280;
                font-size: 12px;
                font-weight: 700;
                margin-bottom: 5px;
                text-transform: uppercase;
            }
            .bubble {
                border-radius: 14px;
                padding: 11px 13px;
            }
            .user {
                background: #dbeafe;
                border: 1px solid #bfdbfe;
            }
            .assistant {
                background: #ffffff;
                border: 1px solid #e5e7eb;
            }
            .system {
                color: #64748b;
                font-size: 13px;
                margin: 12px 0;
            }
            """
        )

        self.input_box = EnterToSendTextEdit()
        self.input_box.setPlaceholderText("Message OpenAI...")
        self.input_box.setFixedHeight(96)
        self.input_box.send_requested.connect(self.send_message)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedWidth(96)
        self.send_button.clicked.connect(self.send_message)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("sk-...")
        self.key_input.setText(load_api_key())

        self.model_input = QLineEdit(preferences.get("model", DEFAULT_MODEL))

        save_button = QPushButton("Save Settings")
        save_button.setObjectName("secondaryButton")
        save_button.clicked.connect(self.save_settings)

        clear_button = QPushButton("New Chat")
        clear_button.setObjectName("subtleButton")
        clear_button.clicked.connect(self.clear_chat)

        root = QWidget()
        root.setObjectName("root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

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
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("chatHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(3)

        title = QLabel("OpenAI Chat")
        title.setObjectName("appTitle")

        subtitle = QLabel("A private desktop chat using your own API key")
        subtitle.setObjectName("appSubtitle")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        layout.addWidget(self.chat_area)

        composer = QFrame()
        composer.setObjectName("composer")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(10, 10, 10, 10)
        composer_layout.setSpacing(10)

        composer_layout.addWidget(self.input_box, 1)
        composer_layout.addWidget(self.send_button)
        layout.addWidget(composer)
        return panel

    def build_settings_panel(self, save_button: QPushButton, clear_button: QPushButton) -> QWidget:
        panel = QFrame()
        panel.setObjectName("settingsPanel")
        panel.setMinimumWidth(282)
        panel.setMaximumWidth(340)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Settings")
        title.setObjectName("settingsTitle")

        helper = QLabel("Your key stays local in macOS Keychain.")
        helper.setObjectName("settingsHelper")
        helper.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(helper)
        layout.addSpacing(8)
        layout.addWidget(self.form_label("OpenAI API key"))
        layout.addWidget(self.key_input)
        layout.addWidget(self.form_label("Model"))
        layout.addWidget(self.model_input)
        layout.addSpacing(4)
        layout.addWidget(save_button)
        layout.addSpacing(8)
        layout.addWidget(clear_button)
        layout.addStretch(1)

        return panel

    def form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("formLabel")
        return label

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
        bubble_class = "user" if speaker == "You" else "assistant"
        self.chat_area.append(
            "<div class='message-row'>"
            f"<div class='speaker'>{speaker}</div>"
            f"<div class='bubble {bubble_class}'>{escaped_text}</div>"
            "</div>"
        )
        self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())

    def append_system_message(self, text: str) -> None:
        self.chat_area.append(f"<div class='system'>{self.escape(text)}</div>")
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
            QMainWindow {
                background: #eef2f7;
            }
            QWidget {
                color: #1f2937;
                font-size: 14px;
            }
            QWidget#root {
                background: #eef2f7;
            }
            QFrame#chatHeader {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
            }
            QLabel#appTitle {
                color: #111827;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#appSubtitle {
                color: #6b7280;
                font-size: 13px;
            }
            QTextEdit#chatArea {
                background: #f8fafc;
                border: 1px solid #d9e1ea;
                border-radius: 8px;
                padding: 16px;
            }
            QFrame#composer {
                background: #ffffff;
                border: 1px solid #d9e1ea;
                border-radius: 8px;
            }
            QFrame#settingsPanel {
                background: #ffffff;
                border: 1px solid #d9e1ea;
                border-radius: 8px;
            }
            QLabel#settingsTitle {
                color: #111827;
                font-size: 19px;
                font-weight: 800;
            }
            QLabel#settingsHelper {
                color: #6b7280;
                font-size: 13px;
            }
            QLabel#formLabel {
                color: #374151;
                font-size: 12px;
                font-weight: 700;
            }
            QLineEdit, QPlainTextEdit {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px;
                background: white;
                selection-background-color: #bfdbfe;
            }
            QLineEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #2563eb;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 9px 13px;
                background: #2563eb;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QPushButton:disabled {
                background: #94a3b8;
            }
            QPushButton#secondaryButton {
                background: #0f766e;
            }
            QPushButton#secondaryButton:hover {
                background: #0d665f;
            }
            QPushButton#subtleButton {
                background: #e2e8f0;
                color: #334155;
            }
            QPushButton#subtleButton:hover {
                background: #cbd5e1;
            }
            QSplitter::handle {
                background: transparent;
                width: 8px;
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
