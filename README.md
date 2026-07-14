# OpenAI Chat Mac

A small macOS desktop chat app built with Python, PySide6, and the OpenAI API. It stores your API key locally with `keyring`, which uses macOS Keychain when available.

## Files

- `main.py` - the PySide6 user interface, chat history, loading state, and button/Enter handling.
- `openai_client.py` - the OpenAI Responses API wrapper and friendly error messages.
- `settings.py` - API-key storage and non-secret preference storage.
- `requirements.txt` - Python packages needed for development and packaging.
- `Info.plist` - macOS bundle metadata used by PyInstaller.
- `OpenAIChat.spec` - repeatable PyInstaller build configuration for a `.app`.
- `launcher.c` - small native launcher used only because this source folder is itself named `condra-local-download.app`.

## Run From Source

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python main.py
```

Paste your OpenAI API key into Settings, click **Save Settings**, then start chatting. Press Enter to send. Press Shift+Enter to add a newline.

## Double-Click This Project Folder

This repository folder is named like a macOS app: `condra-local-download.app`. Because of that, Finder treats the source folder itself as an application bundle.

After installing dependencies, you can double-click `condra-local-download.app`. The native launcher at `Contents/MacOS/condra-local-download` starts `main.py`. If dependencies are missing, it shows a dialog telling you what to install.

The launcher also starts `app.py` and `saveApp.py` in the background. It records process ids in `.app.py.pid` and `.saveApp.pid` so repeated double-clicks do not create duplicate workers, and writes output to `app.log` and `saveApp.log`.

If you edit `launcher.c`, rebuild that source-folder launcher with:

```bash
clang -arch arm64 launcher.c -o Contents/MacOS/condra-local-download
chmod +x Contents/MacOS/condra-local-download
```

## Build A macOS `.app`

From the project folder, with the virtual environment active:

```bash
pyinstaller OpenAIChat.spec
```

The built app will be here:

```text
dist/OpenAI Chat.app
```

You can double-click that app in Finder.

## Share A Downloadable App

Do not use GitHub's green **Code > Download ZIP** file as the app download.
GitHub source-code ZIPs rename the top folder with the branch name, such as
`condra-local-download.app-main`, so the folder is no longer a normal `.app`
bundle.

Build and package the real app instead:

```bash
./scripts/package-app.sh
```

That creates:

```text
release/OpenAI Chat.app.zip
```

Upload `release/OpenAI Chat.app.zip` to a GitHub Release and have people
download that file. After unzipping it, they will get `OpenAI Chat.app`.

If macOS says the downloaded app is damaged or cannot be opened, that is
Gatekeeper blocking an unsigned app from the internet. For personal testing,
Control-click the app and choose **Open**, or run:

```bash
xattr -dr com.apple.quarantine "OpenAI Chat.app"
```

For public distribution, sign and notarize the app with an Apple Developer ID.

You can also build without the spec file:

```bash
pyinstaller --windowed --name "OpenAI Chat" --osx-bundle-identifier com.example.openaichat --add-data "Info.plist:." main.py
```

The spec-file build is recommended because it includes `keyring` backend modules more reliably.

## How macOS Knows What To Run

A macOS app bundle is a folder ending in `.app`. Inside it, macOS reads:

```text
Contents/Info.plist
```

The important key is:

```xml
<key>CFBundleExecutable</key>
<string>OpenAI Chat</string>
```

That tells macOS to launch this executable inside the bundle:

```text
Contents/MacOS/OpenAI Chat
```

PyInstaller creates that executable from `main.py` and copies the Python runtime and dependencies into the `.app`.

## API Key Safety

The API key is not hard-coded in the source code. It is saved through the `keyring` package. On macOS, that normally means the key is stored in Keychain under the service name `OpenAIChatMac`.

The app stores non-secret preferences, such as the model name, here:

```text
~/Library/Application Support/OpenAI Chat Mac/settings.json
```

## Notes

The default model is `gpt-4.1-mini`. You can change it in the Settings panel without changing code.
