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
    QStackedWidget,
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
        self.resize(1120, 760)

        preferences = load_preferences()
        self.api_key = load_api_key()
        self.starts_in_setup = not bool(self.api_key)
        self.messages: list[ChatMessage] = []
        self.worker: Optional[ChatWorker] = None

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setObjectName("chatArea")
        self.chat_area.document().setDefaultStyleSheet(
            """
            body {
                color: #25231f;
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
                font-size: 14px;
                line-height: 1.45;
            }
            .message-row {
                margin: 14px 0;
            }
            .speaker {
                color: #7b746a;
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
                background: #dcebdd;
                border: 1px solid #c1d8c4;
            }
            .assistant {
                background: #fffdf8;
                border: 1px solid #ddd6c8;
            }
            .system {
                color: #8a8175;
                font-size: 13px;
                margin: 12px 0;
            }
            """
        )

        self.input_box = EnterToSendTextEdit()
        self.input_box.setPlaceholderText("Ask anything...")
        self.input_box.setFixedHeight(96)
        self.input_box.send_requested.connect(self.send_message)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedWidth(96)
        self.send_button.clicked.connect(self.send_message)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("sk-...")
        self.key_input.setText(self.api_key)

        self.setup_key_input = QLineEdit()
        self.setup_key_input.setEchoMode(QLineEdit.Password)
        self.setup_key_input.setPlaceholderText("sk-...")
        self.setup_key_input.setText(self.api_key)
        self.setup_key_input.returnPressed.connect(self.save_setup)

        self.model_input = QLineEdit(preferences.get("model", DEFAULT_MODEL))

        save_button = QPushButton("Save Settings")
        save_button.setObjectName("secondaryButton")
        save_button.clicked.connect(self.save_settings)

        clear_button = QPushButton("New Chat")
        clear_button.setObjectName("subtleButton")
        clear_button.clicked.connect(self.clear_chat)

        self.stack = QStackedWidget()
        self.stack.setObjectName("root")

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.build_settings_panel(save_button, clear_button))
        splitter.addWidget(self.build_chat_panel())
        splitter.setSizes([260, 860])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setup_page = self.build_setup_page()
        self.app_page = QWidget()
        app_layout = QVBoxLayout(self.app_page)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.addWidget(splitter)

        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.app_page)
        self.setCentralWidget(self.stack)
        self.apply_styles()

        if self.api_key:
            self.show_chat()
        else:
            self.show_setup()

    def build_chat_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("chatHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(10)

        title_block = QVBoxLayout()
        title_block.setSpacing(3)

        title = QLabel("Chat")
        title.setObjectName("appTitle")

        self.model_subtitle = QLabel(f"Model: {self.model_input.text().strip() or DEFAULT_MODEL}")
        self.model_subtitle.setObjectName("appSubtitle")

        title_block.addWidget(title)
        title_block.addWidget(self.model_subtitle)

        header_layout.addLayout(title_block)
        header_layout.addStretch(1)
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
        panel.setMinimumWidth(240)
        panel.setMaximumWidth(300)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("OpenAI")
        title.setObjectName("sidebarTitle")

        helper = QLabel("Chat with your API key.")
        helper.setObjectName("settingsHelper")
        helper.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(helper)
        layout.addSpacing(18)
        layout.addWidget(clear_button)
        layout.addSpacing(18)
        layout.addWidget(self.form_label("Settings"))
        layout.addWidget(self.form_label("OpenAI API key"))
        layout.addWidget(self.key_input)
        layout.addWidget(self.form_label("Model"))
        layout.addWidget(self.model_input)
        layout.addSpacing(4)
        layout.addWidget(save_button)
        layout.addStretch(1)

        return panel

    def build_setup_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("setupPage")

        outer = QVBoxLayout(page)
        outer.setContentsMargins(56, 56, 56, 56)
        outer.setSpacing(0)
        outer.addStretch(1)

        panel = QFrame()
        panel.setObjectName("setupPanel")
        panel.setMaximumWidth(620)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(34, 34, 34, 34)
        layout.setSpacing(14)

        title = QLabel("Set up OpenAI Chat")
        title.setObjectName("setupTitle")

        subtitle = QLabel("Paste your API key once. It is stored locally in macOS Keychain.")
        subtitle.setObjectName("setupSubtitle")
        subtitle.setWordWrap(True)

        model_label = self.form_label("Model")
        self.setup_model_input = QLineEdit(self.model_input.text())
        self.setup_model_input.returnPressed.connect(self.save_setup)

        continue_button = QPushButton("Start Chatting")
        continue_button.setObjectName("setupButton")
        continue_button.clicked.connect(self.save_setup)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(14)
        layout.addWidget(self.form_label("OpenAI API key"))
        layout.addWidget(self.setup_key_input)
        layout.addWidget(model_label)
        layout.addWidget(self.setup_model_input)
        layout.addSpacing(8)
        layout.addWidget(continue_button)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(panel)
        row.addStretch(1)

        outer.addLayout(row)
        outer.addStretch(1)
        return page

    def form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("formLabel")
        return label

    def send_message(self) -> None:
        text = self.input_box.toPlainText().strip()
        if not text or self.worker is not None:
            return

        if not self.api_key:
            self.show_error("Missing OpenAI API key. Paste your key in Settings first.")
            self.show_setup()
            return

        self.messages.append(ChatMessage(role="user", content=text))
        self.append_message("You", text)
        self.input_box.clear()
        self.set_waiting(True)
        self.append_system_message("Assistant is thinking...")

        self.worker = ChatWorker(self.api_key, self.model_input.text(), self.messages.copy())
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
            self.api_key = self.key_input.text().strip()
            self.setup_key_input.setText(self.api_key)
            save_preferences(self.model_input.text())
            save_api_key(self.api_key)
            self.model_subtitle.setText(f"Model: {self.model_input.text().strip() or DEFAULT_MODEL}")
            self.append_system_message("Settings saved.")
            if self.api_key:
                self.show_chat()
        except RuntimeError as exc:
            self.show_error(str(exc))

    def save_setup(self) -> None:
        api_key = self.setup_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "OpenAI Chat", "Paste your OpenAI API key to continue.")
            return

        try:
            self.api_key = api_key
            self.key_input.setText(api_key)
            self.model_input.setText(self.setup_model_input.text().strip() or DEFAULT_MODEL)
            save_api_key(self.api_key)
            save_preferences(self.model_input.text())
            self.model_subtitle.setText(f"Model: {self.model_input.text().strip() or DEFAULT_MODEL}")
            self.show_chat()
        except RuntimeError as exc:
            QMessageBox.warning(self, "OpenAI Chat", str(exc))

    def show_setup(self) -> None:
        self.stack.setCurrentWidget(self.setup_page)
        self.setup_key_input.setFocus()

    def show_chat(self) -> None:
        self.stack.setCurrentWidget(self.app_page)
        if not self.chat_area.toPlainText().strip():
            self.append_system_message("Ready. Ask a question to start a new chat.")
        self.input_box.setFocus()

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
                background: #f4f0e8;
            }
            QWidget {
                color: #25231f;
                font-size: 14px;
            }
            QWidget#root {
                background: #f4f0e8;
            }
            QWidget#setupPage {
                background: #f4f0e8;
            }
            QFrame#setupPanel {
                background: #fffdf8;
                border: 1px solid #ddd6c8;
                border-radius: 8px;
            }
            QLabel#setupTitle {
                color: #1f1d19;
                font-size: 30px;
                font-weight: 800;
            }
            QLabel#setupSubtitle {
                color: #756f64;
                font-size: 15px;
            }
            QFrame#chatHeader {
                background: #fffdf8;
                border: 1px solid #ddd6c8;
                border-radius: 8px;
            }
            QLabel#appTitle {
                color: #1f1d19;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#appSubtitle {
                color: #756f64;
                font-size: 13px;
            }
            QTextEdit#chatArea {
                background: #fbf7ef;
                border: 1px solid #ddd6c8;
                border-radius: 8px;
                padding: 16px;
            }
            QFrame#composer {
                background: #fffdf8;
                border: 1px solid #ddd6c8;
                border-radius: 8px;
            }
            QFrame#settingsPanel {
                background: #292721;
                border: none;
                border-radius: 0;
            }
            QLabel#sidebarTitle {
                color: #f8f2e8;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#settingsHelper {
                color: #b8ad9d;
                font-size: 13px;
            }
            QLabel#formLabel {
                color: #c9bead;
                font-size: 12px;
                font-weight: 700;
            }
            QLineEdit, QPlainTextEdit {
                color: #25231f;
                border: 1px solid #d4cabc;
                border-radius: 8px;
                padding: 9px;
                background: #fffdf8;
                selection-background-color: #d8eadf;
            }
            QLineEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #2f7d5c;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 10px 13px;
                background: #2f7d5c;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #27694d;
            }
            QPushButton:disabled {
                background: #a8a094;
            }
            QPushButton#secondaryButton {
                background: #3b8767;
            }
            QPushButton#secondaryButton:hover {
                background: #327257;
            }
            QPushButton#subtleButton {
                background: #3a372f;
                color: #f8f2e8;
            }
            QPushButton#subtleButton:hover {
                background: #474338;
            }
            QPushButton#setupButton {
                font-size: 15px;
                padding: 12px 14px;
            }
            QSplitter::handle {
                background: transparent;
                width: 10px;
            }
            """
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("OpenAI Chat")

    window = MainWindow()
    if window.starts_in_setup:
        window.showMaximized()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
