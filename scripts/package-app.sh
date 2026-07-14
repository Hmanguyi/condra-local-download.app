#!/usr/bin/env bash
set -euo pipefail

APP_NAME="OpenAI Chat.app"
ASSET_NAME="OpenAI.Chat.app.zip"
APP_PATH="dist/${APP_NAME}"
ZIP_DIR="release"
ZIP_PATH="${ZIP_DIR}/${ASSET_NAME}"

cd "$(dirname "$0")/.."

export PYINSTALLER_CONFIG_DIR="${PWD}/.pyinstaller-cache"

if [[ -x ".venv/bin/pyinstaller" ]]; then
  PYINSTALLER=".venv/bin/pyinstaller"
else
  PYINSTALLER="pyinstaller"
fi

echo "Building ${APP_NAME} with PyInstaller..."
"${PYINSTALLER}" --clean --noconfirm OpenAIChat.spec

if [[ ! -x "${APP_PATH}/Contents/MacOS/OpenAI Chat" ]]; then
  chmod +x "${APP_PATH}/Contents/MacOS/OpenAI Chat"
fi

mkdir -p "${ZIP_DIR}"
rm -f "${ZIP_PATH}"

ditto -c -k --keepParent "${APP_PATH}" "${ZIP_PATH}"

echo "Packaged ${ZIP_PATH}"
