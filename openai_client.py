"""Small OpenAI API wrapper used by the desktop chat UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI


@dataclass(frozen=True)
class ChatMessage:
    """A single message in the current chat session."""

    role: str
    content: str


class OpenAIChatClient:
    """Calls the OpenAI Responses API with the active conversation history."""

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        if not api_key.strip():
            raise ValueError("Missing OpenAI API key. Paste your key in Settings first.")

        self.model = model.strip() or "gpt-4.1-mini"
        self.client = OpenAI(api_key=api_key.strip())

    def send_message(self, messages: Iterable[ChatMessage]) -> str:
        """Send the conversation to OpenAI and return the assistant text."""

        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": message.role, "content": message.content}
                for message in messages
            ],
        )

        text = getattr(response, "output_text", "") or ""
        if text.strip():
            return text.strip()

        raise RuntimeError("The API returned an empty response.")


def user_friendly_error(error: Exception) -> str:
    """Translate common API exceptions into messages suitable for the UI."""

    if isinstance(error, ValueError):
        return str(error)

    if isinstance(error, AuthenticationError):
        return "The API key was rejected. Check that it is copied correctly and active."

    if isinstance(error, APIConnectionError):
        return "Network error. Check your internet connection and try again."

    if isinstance(error, APIStatusError):
        detail = getattr(error, "message", "") or str(error)
        return f"OpenAI API error ({error.status_code}): {detail}"

    return f"Unexpected error: {error}"
