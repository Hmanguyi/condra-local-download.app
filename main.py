"""PySide6 macOS desktop chat app for OpenAI."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional
from uuid import uuid4

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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
from settings import (
    DEFAULT_MODEL,
    load_api_key,
    load_chat_history,
    load_preferences,
    save_api_key,
    save_chat_history,
    save_preferences,
)


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
    @staticmethod
    def new_chat_record() -> dict:
        return {"id": uuid4().hex, "title": "New chat", "messages": []}

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OpenAI Chat")
        self.resize(1120, 760)

        preferences = load_preferences()
        self.api_key = load_api_key()
        self.starts_in_setup = not bool(self.api_key)
        self.chats = load_chat_history()
        if not self.chats:
            self.chats = [self.new_chat_record()]
        self.active_chat_id = str(self.chats[0]["id"])
        self.messages: list[ChatMessage] = []
        self.worker: Optional[ChatWorker] = None
        self.loading_step = 0
        self.loading_timer = QTimer(self)
        self.loading_timer.setInterval(350)
        self.loading_timer.timeout.connect(self.advance_loading_animation)
        self.typing_text = ""
        self.typing_index = 0
        self.typing_timer = QTimer(self)
        self.typing_timer.setInterval(16)
        self.typing_timer.timeout.connect(self.advance_typing_animation)

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setObjectName("chatArea")
        self.chat_area.document().setDefaultStyleSheet(
            """
            body {
                color: #14201b;
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
                font-size: 13px;
                line-height: 1.48;
            }
            .message-row {
                margin: 6px 0;
            }
            .bubble {
                border-radius: 8px;
                padding: 10px 11px;
            }
            .user {
                color: #ffffff;
                background: #25704a;
            }
            .assistant {
                color: #14201b;
                background: #ffffff;
                border: 1px solid #dce6e1;
            }
            .system {
                color: #66736d;
                font-size: 12px;
                margin: 10px 0;
            }
            .empty-title {
                color: #14201b;
                font-size: 21px;
                font-weight: 800;
                margin-top: 150px;
                text-align: center;
            }
            .empty-copy {
                color: #66736d;
                font-size: 13px;
                text-align: center;
            }
            """
        )

        self.input_box = EnterToSendTextEdit()
        self.input_box.setPlaceholderText("Message Condra...")
        self.input_box.setFixedHeight(58)
        self.input_box.send_requested.connect(self.send_message)

        self.send_button = QPushButton("↑")
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedSize(38, 38)
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
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.save_settings)

        clear_button = QPushButton("New Chat")
        clear_button.setObjectName("headerButton")
        clear_button.clicked.connect(self.clear_chat)
        self.new_chat_button = clear_button

        self.stack = QStackedWidget()
        self.stack.setObjectName("root")

        self.setup_page = self.build_setup_page()
        self.app_page = self.build_chat_panel(clear_button)
        self.settings_page = self.build_settings_page(save_button)

        # The settings screen replaces the old permanent sidebar. It behaves
        # like a collapsible view: open it from the header and return to chat.
        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.app_page)
        self.stack.addWidget(self.settings_page)
        self.setCentralWidget(self.stack)
        self.apply_styles()
        self.refresh_chat_list()
        self.load_active_chat()

        if self.api_key:
            self.show_chat()
        else:
            self.show_setup()

    def build_chat_panel(self, clear_button: QPushButton) -> QWidget:
        self.app_page = QWidget()
        self.app_page.setObjectName("chatPage")
        page_layout = QHBoxLayout(self.app_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("chatSidebar")
        self.sidebar.setMinimumWidth(220)
        self.sidebar.setMaximumWidth(300)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 16)
        sidebar_layout.setSpacing(10)

        brand = QLabel("●  Condra")
        brand.setObjectName("sidebarBrand")
        sidebar_layout.addWidget(brand)
        clear_button.setObjectName("newChatButton")
        sidebar_layout.addWidget(clear_button)

        chats_label = QLabel("YOUR CHATS")
        chats_label.setObjectName("sidebarSection")
        sidebar_layout.addWidget(chats_label)
        self.chat_list = QListWidget()
        self.chat_list.setObjectName("chatList")
        self.chat_list.currentItemChanged.connect(self.select_chat)
        sidebar_layout.addWidget(self.chat_list, 1)

        settings_button = QPushButton("Settings")
        settings_button.setObjectName("sidebarButton")
        settings_button.clicked.connect(self.show_settings)
        sidebar_layout.addWidget(settings_button)

        chat_panel = QWidget()
        chat_panel.setObjectName("conversationPanel")
        app_layout = QVBoxLayout(chat_panel)
        app_layout.setContentsMargins(28, 22, 28, 24)
        app_layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("chatHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 0, 4, 0)
        header_layout.setSpacing(12)

        title_block = QVBoxLayout()
        title_block.setSpacing(3)

        hour = datetime.now().hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        title = QLabel(greeting)
        title.setObjectName("appTitle")

        self.model_subtitle = QLabel(f"Model: {self.model_input.text().strip() or DEFAULT_MODEL}")
        self.model_subtitle.setObjectName("appSubtitle")

        title_block.addWidget(title)
        title_block.addWidget(self.model_subtitle)

        header_layout.addLayout(title_block)
        header_layout.addStretch(1)
        self.sidebar_toggle = QPushButton("Hide chats")
        self.sidebar_toggle.setObjectName("headerButton")
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.sidebar_toggle)
        app_layout.addWidget(header)

        app_layout.addWidget(self.chat_area, 1)

        self.loading_frame = QFrame()
        self.loading_frame.setObjectName("loadingFrame")
        self.loading_frame.setMaximumWidth(155)
        loading_layout = QHBoxLayout(self.loading_frame)
        loading_layout.setContentsMargins(14, 7, 14, 7)
        loading_layout.setSpacing(8)
        self.loading_dot = QLabel("●")
        self.loading_dot.setObjectName("loadingDot")
        self.loading_label = QLabel("Thinking")
        self.loading_label.setObjectName("loadingLabel")
        loading_layout.addWidget(self.loading_dot)
        loading_layout.addWidget(self.loading_label)
        loading_layout.addStretch(1)
        self.loading_frame.hide()
        app_layout.addWidget(self.loading_frame)

        composer = QFrame()
        composer.setObjectName("composer")
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(10, 10, 10, 10)
        composer_layout.setSpacing(7)

        self.model_context_label = QLabel(self.model_input.text().strip() or DEFAULT_MODEL)
        self.model_context_label.setObjectName("contextPill")
        composer_layout.addWidget(self.model_context_label, 0, Qt.AlignLeft)
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        input_row.addWidget(self.input_box, 1)
        input_row.addWidget(self.send_button, 0, Qt.AlignBottom)
        composer_layout.addLayout(input_row)
        app_layout.addWidget(composer)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("chatSplitter")
        splitter.addWidget(self.sidebar)
        splitter.addWidget(chat_panel)
        splitter.setSizes([260, 860])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        page_layout.addWidget(splitter)
        return self.app_page

    def build_settings_page(self, save_button: QPushButton) -> QWidget:
        page = QWidget()
        page.setObjectName("settingsPage")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(32, 24, 32, 32)
        outer.setSpacing(22)

        top = QHBoxLayout()
        back_button = QPushButton("Back to chat")
        back_button.setObjectName("headerButton")
        back_button.clicked.connect(self.show_chat)
        top.addWidget(back_button)
        top.addStretch(1)
        outer.addLayout(top)

        panel = QFrame()
        panel.setObjectName("settingsCard")
        panel.setMaximumWidth(680)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(34, 32, 34, 34)
        layout.setSpacing(12)

        title = QLabel("Settings")
        title.setObjectName("settingsTitle")
        helper = QLabel("Manage the connection used for your conversations. Your API key stays on this Mac.")
        helper.setObjectName("settingsHelper")
        helper.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(helper)
        layout.addSpacing(16)
        layout.addWidget(self.form_label("OpenAI API key"))
        layout.addWidget(self.key_input)
        key_help = QLabel("Stored securely in your local user settings and never displayed in full.")
        key_help.setObjectName("fieldHelp")
        key_help.setWordWrap(True)
        layout.addWidget(key_help)
        layout.addSpacing(8)
        layout.addWidget(self.form_label("Model"))
        layout.addWidget(self.model_input)
        model_help = QLabel("Choose the OpenAI model used for new messages.")
        model_help.setObjectName("fieldHelp")
        layout.addWidget(model_help)
        layout.addSpacing(12)
        layout.addWidget(save_button)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(panel)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        return page

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

        subtitle = QLabel("Paste your API key once. It is stored locally on this Mac.")
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
        chat = self.active_chat()
        if chat:
            chat["messages"] = self.serialized_messages()
            if str(chat.get("title") or "") == "New chat":
                chat["title"] = self.chat_title(text)
            self.persist_chats()
            self.refresh_chat_list()
        if len(self.messages) == 1:
            self.chat_area.clear()
        self.append_message("You", text)
        self.input_box.clear()
        self.set_waiting(True)

        self.worker = ChatWorker(self.api_key, self.model_input.text(), self.messages.copy())
        self.worker.succeeded.connect(self.handle_response)
        self.worker.failed.connect(self.handle_error)
        self.worker.finished.connect(self.worker_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def handle_response(self, text: str) -> None:
        self.loading_timer.stop()
        self.loading_frame.hide()
        self.typing_text = str(text or "")
        self.typing_index = 0
        self.typing_timer.start()
        self.advance_typing_animation()

    def advance_typing_animation(self) -> None:
        if not self.typing_text:
            self.finish_typing_animation()
            return

        remaining = len(self.typing_text) - self.typing_index
        chunk_size = 1 if len(self.typing_text) < 500 else 2 if len(self.typing_text) < 1200 else 4
        self.typing_index = min(len(self.typing_text), self.typing_index + min(chunk_size, remaining))
        partial = self.typing_text[:self.typing_index]
        self.render_messages(partial_assistant=partial)

        if self.typing_index >= len(self.typing_text):
            self.finish_typing_animation()

    def finish_typing_animation(self) -> None:
        self.typing_timer.stop()
        completed_text = self.typing_text
        self.typing_text = ""
        self.typing_index = 0
        if completed_text:
            self.messages.append(ChatMessage(role="assistant", content=completed_text))
        chat = self.active_chat()
        if chat:
            chat["messages"] = self.serialized_messages()
            self.persist_chats()
        self.render_active_chat()
        self.set_waiting(False)

    def handle_error(self, message: str) -> None:
        self.messages.pop()
        chat = self.active_chat()
        if chat:
            chat["messages"] = self.serialized_messages()
            self.persist_chats()
        self.append_system_message(message)
        self.set_waiting(False)

    def set_waiting(self, waiting: bool) -> None:
        self.send_button.setEnabled(not waiting)
        self.input_box.setEnabled(not waiting)
        self.chat_list.setEnabled(not waiting)
        self.new_chat_button.setEnabled(not waiting)
        self.loading_frame.setVisible(waiting)
        if waiting:
            self.loading_step = 0
            self.advance_loading_animation()
            self.loading_timer.start()
        else:
            self.loading_timer.stop()
            self.loading_label.setText("Thinking")
        if not waiting:
            self.input_box.setFocus()

    def advance_loading_animation(self) -> None:
        dots = "·" * (self.loading_step % 4)
        self.loading_label.setText(f"Thinking {dots}".rstrip())
        self.loading_dot.setStyleSheet(
            "color: #25704a;" if self.loading_step % 2 == 0 else "color: #8fc3a5;"
        )
        self.loading_step += 1

    def worker_finished(self) -> None:
        self.worker = None

    def save_settings(self) -> None:
        try:
            self.api_key = self.key_input.text().strip()
            self.setup_key_input.setText(self.api_key)
            save_preferences(self.model_input.text())
            save_api_key(self.api_key)
            self.model_subtitle.setText(f"Model: {self.model_input.text().strip() or DEFAULT_MODEL}")
            self.model_context_label.setText(self.model_input.text().strip() or DEFAULT_MODEL)
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
            self.model_context_label.setText(self.model_input.text().strip() or DEFAULT_MODEL)
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

    def show_settings(self) -> None:
        self.key_input.setText(self.api_key)
        self.stack.setCurrentWidget(self.settings_page)
        self.key_input.setFocus()

    def clear_chat(self) -> None:
        chat = self.new_chat_record()
        self.chats.insert(0, chat)
        self.active_chat_id = str(chat["id"])
        self.messages = []
        self.persist_chats()
        self.refresh_chat_list()
        self.render_active_chat()
        self.input_box.setFocus()

    def active_chat(self) -> Optional[dict]:
        return next(
            (chat for chat in self.chats if str(chat.get("id")) == self.active_chat_id),
            None,
        )

    def serialized_messages(self) -> list[dict[str, str]]:
        return [{"role": message.role, "content": message.content} for message in self.messages]

    @staticmethod
    def chat_title(text: str) -> str:
        clean = " ".join(str(text or "").split())
        return clean if len(clean) <= 38 else clean[:38].rstrip() + "…"

    def persist_chats(self) -> None:
        try:
            save_chat_history(self.chats)
        except RuntimeError as exc:
            self.append_system_message(str(exc))

    def refresh_chat_list(self) -> None:
        self.chat_list.blockSignals(True)
        self.chat_list.clear()
        active_item = None
        for chat in self.chats:
            item = QListWidgetItem(str(chat.get("title") or "New chat"))
            item.setData(Qt.UserRole, str(chat.get("id")))
            item.setToolTip(str(chat.get("title") or "New chat"))
            self.chat_list.addItem(item)
            if str(chat.get("id")) == self.active_chat_id:
                active_item = item
        if active_item:
            self.chat_list.setCurrentItem(active_item)
        self.chat_list.blockSignals(False)

    def select_chat(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        del previous
        if current is None or self.worker is not None:
            return
        chat_id = str(current.data(Qt.UserRole) or "")
        if chat_id and chat_id != self.active_chat_id:
            self.active_chat_id = chat_id
            self.load_active_chat()

    def load_active_chat(self) -> None:
        chat = self.active_chat()
        raw_messages = chat.get("messages", []) if chat else []
        self.messages = [
            ChatMessage(role=str(message.get("role") or "user"), content=str(message.get("content") or ""))
            for message in raw_messages
            if isinstance(message, dict) and message.get("content")
        ]
        self.render_active_chat()

    def render_active_chat(self) -> None:
        self.render_messages()

    def render_messages(self, partial_assistant: str = "") -> None:
        self.chat_area.clear()
        if not self.messages and not partial_assistant:
            self.chat_area.setHtml(
                "<div class='empty-title'>Ask Condra</div>"
                "<div class='empty-copy'>Start a conversation. Your chats are saved locally.</div>"
            )
            return
        for message in self.messages:
            speaker = "You" if message.role == "user" else "Assistant"
            self.append_message(speaker, message.content)
        if partial_assistant:
            self.append_message("Assistant", partial_assistant + "▍")

    def toggle_sidebar(self) -> None:
        visible = not self.sidebar.isHidden()
        self.sidebar.setVisible(not visible)
        self.sidebar_toggle.setText("Show chats" if visible else "Hide chats")

    def append_message(self, speaker: str, text: str) -> None:
        escaped_text = self.escape(text).replace(chr(10), "<br>")
        bubble_class = "user" if speaker == "You" else "assistant"
        alignment = "right" if speaker == "You" else "left"
        bubble_width = min(72, max(26, 22 + len(str(text or "")) // 2))
        self.chat_area.append(
            f"<table class='message-row' width='{bubble_width}%' align='{alignment}' cellspacing='0' cellpadding='0'>"
            f"<tr><td class='bubble {bubble_class}'>{escaped_text}</td></tr>"
            "</table><br>"
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
                background: #f4f7f6;
            }
            QWidget {
                color: #14201b;
                font-size: 14px;
            }
            QWidget#root {
                background: #f4f7f6;
            }
            QWidget#setupPage, QWidget#chatPage, QWidget#settingsPage {
                background: #f4f7f6;
            }
            QWidget#conversationPanel {
                background: #f4f7f6;
            }
            QFrame#chatSidebar {
                background: #17191d;
                border: none;
            }
            QLabel#sidebarBrand {
                color: #f5f6f7;
                font-size: 18px;
                font-weight: 800;
                padding: 4px 5px 10px 5px;
            }
            QLabel#sidebarSection {
                color: #8f96a1;
                font-size: 11px;
                font-weight: 700;
                padding: 12px 6px 2px 6px;
            }
            QListWidget#chatList {
                background: transparent;
                color: #dfe2e6;
                border: none;
                outline: none;
                padding: 0;
            }
            QListWidget#chatList::item {
                border-radius: 8px;
                padding: 10px 9px;
                margin: 1px 0;
            }
            QListWidget#chatList::item:hover {
                background: #282b31;
            }
            QListWidget#chatList::item:selected {
                background: #343840;
                color: #ffffff;
            }
            QFrame#setupPanel {
                background: #ffffff;
                border: 1px solid #e2e5e9;
                border-radius: 16px;
            }
            QLabel#setupTitle {
                color: #171a1f;
                font-size: 30px;
                font-weight: 800;
            }
            QLabel#setupSubtitle {
                color: #69717d;
                font-size: 15px;
            }
            QFrame#chatHeader {
                background: transparent;
                border: none;
            }
            QLabel#appTitle {
                color: #171a1f;
                font-size: 26px;
                font-weight: 800;
            }
            QLabel#appSubtitle {
                color: #747d89;
                font-size: 13px;
            }
            QTextEdit#chatArea {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f7faf8);
                border: 1px solid #dce6e1;
                border-radius: 10px;
                padding: 14px 12px;
            }
            QFrame#loadingFrame {
                background: #ffffff;
                border: 1px solid #dce6e1;
                border-radius: 8px;
            }
            QLabel#loadingDot {
                color: #25704a;
                font-size: 10px;
            }
            QLabel#loadingLabel {
                color: #25704a;
                font-size: 13px;
                font-weight: 700;
            }
            QFrame#composer {
                background: rgba(251, 252, 251, 0.96);
                border: 1px solid #dce6e1;
                border-radius: 10px;
            }
            QFrame#composer QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #dce6e1;
                border-radius: 8px;
                padding: 8px 9px;
            }
            QFrame#composer QPlainTextEdit:focus {
                border: 1px solid #8bbca0;
            }
            QLabel#contextPill {
                color: #25704a;
                background: #edf7f1;
                border: 1px solid #d6eade;
                border-radius: 10px;
                padding: 5px 9px;
                font-size: 11px;
                font-weight: 700;
            }
            QFrame#settingsCard {
                background: #ffffff;
                border: 1px solid #e2e5e9;
                border-radius: 16px;
            }
            QLabel#settingsTitle {
                color: #171a1f;
                font-size: 28px;
                font-weight: 800;
            }
            QLabel#settingsHelper {
                color: #69717d;
                font-size: 14px;
            }
            QLabel#fieldHelp {
                color: #89919c;
                font-size: 12px;
            }
            QLabel#formLabel {
                color: #414852;
                font-size: 12px;
                font-weight: 700;
            }
            QLineEdit, QPlainTextEdit {
                color: #20242a;
                border: 1px solid #d7dce2;
                border-radius: 10px;
                padding: 10px;
                background: #ffffff;
                selection-background-color: #d9e8ff;
            }
            QLineEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #25704a;
            }
            QPushButton {
                border: none;
                border-radius: 10px;
                padding: 10px 13px;
                background: #25704a;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1d5f3e;
            }
            QPushButton:disabled {
                background: #aeb6c2;
            }
            QPushButton#primaryButton {
                padding: 12px 16px;
            }
            QPushButton#headerButton {
                background: #ffffff;
                color: #3e4651;
                border: 1px solid #dfe3e8;
            }
            QPushButton#headerButton:hover {
                background: #edf7f1;
                border: 1px solid #bdd8c8;
            }
            QPushButton#newChatButton {
                background: #ffffff;
                color: #20242a;
                text-align: left;
                padding: 11px 12px;
            }
            QPushButton#newChatButton:hover {
                background: #e8ebef;
            }
            QPushButton#sidebarButton {
                background: transparent;
                color: #dfe2e6;
                text-align: left;
                padding: 10px 9px;
            }
            QPushButton#sidebarButton:hover {
                background: #282b31;
            }
            QSplitter#chatSplitter::handle {
                background: #e2e5e9;
                width: 1px;
            }
            QPushButton#setupButton {
                font-size: 15px;
                padding: 12px 14px;
            }
            QPushButton#sendButton {
                min-width: 38px;
                max-width: 38px;
                min-height: 38px;
                max-height: 38px;
                border-radius: 19px;
                padding: 0;
                background: #25704a;
                color: #ffffff;
                font-size: 20px;
                font-weight: 800;
            }
            QPushButton#sendButton:hover {
                background: #1d5f3e;
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
