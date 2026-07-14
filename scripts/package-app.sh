#!/usr/bin/env bash
set -euo pipefail

APP_NAME="OpenAI Chat.app"
APP_PATH="dist/${APP_NAME}"
ZIP_DIR="release"
ZIP_PATH="${ZIP_DIR}/${APP_NAME}.zip"

cd "$(dirname "$0")/.."

if [[ ! -d "${APP_PATH}" ]]; then
  echo "Building ${APP_NAME} with PyInstaller..."
  pyinstaller OpenAIChat.spec
fi

if [[ ! -x "${APP_PATH}/Contents/MacOS/OpenAI Chat" ]]; then
  chmod +x "${APP_PATH}/Contents/MacOS/OpenAI Chat"
fi

mkdir -p "${ZIP_DIR}"
rm -f "${ZIP_PATH}"

# ditto preserves the macOS bundle layout better than GitHub's source ZIP.
ditto -c -k --keepParent "${APP_PATH}" "${ZIP_PATH}"

echo "Packaged ${ZIP_PATH}"
echo "Upload that zip to a GitHub Release. Do not use GitHub's source-code zip as the app download."
