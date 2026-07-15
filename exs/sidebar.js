const extApi = typeof browser !== "undefined" ? browser : chrome;
const BASES = [
  "http://127.0.0.1:5050",
  "http://localhost:5050",
  "http://127.0.0.1:5000",
  "http://localhost:5000",
  "https://condranew2.onrender.com"
];
let extensionApiKey = localStorage.getItem("condraExtensionApiKey") || "";
const DEFAULT_OUTLOOK_USER_EMAIL = "heparknew111@outlook.com";

let currentEmail = null;
let currentEmailKey = "";
let currentSummary = null;
let currentMatchDebug = null;
let notesCache = { userEmail: "", fetchedAt: 0, notes: [] };
let autoLoadInFlight = false;

const account = { value: localStorage.getItem("condraSidebarAccount") || "" };
const statusEl = document.getElementById("status");
const summaryView = document.getElementById("summary-view");
const notesView = document.getElementById("notes-view");
const askView = document.getElementById("ask-view");
const notesList = document.getElementById("notes-list");
const noteForm = document.getElementById("note-form");
const answerEl = document.getElementById("answer");
const serverKeyModal = document.getElementById("server-key-modal");
const serverKeyForm = document.getElementById("server-key-form");
const serverKeyInput = document.getElementById("server-key-input");
const serverKeyCancel = document.getElementById("server-key-cancel");
const serverKeyMessage = document.getElementById("server-key-message");
const serverKeyField = document.getElementById("server-key-field");
const microsoftSigninButton = document.getElementById("microsoft-signin");
let activeMode = "summary";

function isSupportedMailUrl(url) {
  const value = String(url || "");
  return value.startsWith("https://mail.google.com/")
    || value.startsWith("https://outlook.live.com/")
    || value.startsWith("https://outlook.office.com/");
}

function isMissingContentScriptError(err) {
  const message = String(err && err.message || err || "");
  return message.includes("Could not establish connection")
    || message.includes("Receiving end does not exist")
    || message.includes("The message port closed before a response was received");
}

async function sendMessageToMailTab(tabId, message) {
  try {
    return await extApi.tabs.sendMessage(tabId, message);
  } catch (err) {
    if (isMissingContentScriptError(err)) {
      throw new Error("Refresh Gmail or Outlook, then open an email again.");
    }
    throw err;
  }
}

const NOTE_LABEL_COLORS = [
  { background: "#16a766", text: "#ffffff" },
  { background: "#4a86e8", text: "#ffffff" },
  { background: "#ffad47", text: "#000000" },
  { background: "#a479e2", text: "#ffffff" },
  { background: "#f691b3", text: "#000000" },
  { background: "#43d692", text: "#000000" },
  { background: "#fad165", text: "#000000" },
  { background: "#fb4c2f", text: "#ffffff" }
];

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.className = isError ? "status error" : "status";
}

function isRealEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || "").trim());
}

function isPlaceholderUser(value) {
  return ["outlook-local", "gmail-local", "local"].includes(String(value || "").trim().toLowerCase());
}

function rememberAccount(value) {
  const clean = String(value || "").trim();
  if (!isRealEmail(clean) || isPlaceholderUser(clean)) return;
  account.value = clean;
  localStorage.setItem("condraSidebarAccount", clean);
}

function userEmailForOpenEmail(email) {
  const detected = String((email && email.userEmail) || "").trim();
  if (isRealEmail(detected) && !isPlaceholderUser(detected)) return detected;
  const saved = String(account.value || localStorage.getItem("condraSidebarAccount") || "").trim();
  if (isRealEmail(saved) && !isPlaceholderUser(saved)) return saved;
  if (String((email && email.provider) || "").trim() === "outlook") return DEFAULT_OUTLOOK_USER_EMAIL;
  return "";
}

function describeBackendError(path, base, status, data) {
  const message = data && (data.message || data.error || data.text);
  return `${base}${path} failed (${status})${message ? `: ${message}` : ""}`;
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 35000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { credentials: "include", ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

function fetchOptionsWithAuth(options = {}) {
  const headers = new Headers(options.headers || {});
  if (extensionApiKey) {
    headers.set("X-Condra-Key", extensionApiKey);
  }
  return { ...options, headers };
}

function primaryBackendBase() {
  const remembered = String(localStorage.getItem("condraBackendBase") || "").trim().replace(/\/+$/, "");
  if (remembered && BASES.includes(remembered)) return remembered;
  return BASES[0].replace(/\/+$/, "");
}

function providerForSignIn() {
  const provider = String((currentEmail && currentEmail.provider) || "").trim().toLowerCase();
  if (provider === "gmail" || provider === "outlook") return provider;
  return "microsoft";
}

async function openProviderSignIn(provider = providerForSignIn()) {
  const normalized = String(provider || "").trim().toLowerCase();
  const path = normalized === "gmail" ? "/gmail/sign" : "/microsoft/sign";
  const signInBase = normalized === "gmail"
    ? primaryBackendBase().replace("http://127.0.0.1:", "http://localhost:")
    : primaryBackendBase();
  const url = `${signInBase}${path}`;
  if (extApi && extApi.tabs && extApi.tabs.create) {
    await extApi.tabs.create({ url });
    return;
  }
  window.open(url, "_blank", "noopener");
}

function shouldOfferProviderSignIn(data) {
  const error = String((data && data.error) || "").toLowerCase();
  const message = String((data && data.message) || (data && data.text) || "").toLowerCase();
  return error === "missing_user"
    || error === "reauth_required"
    || error === "label_create_failed"
    || message.includes("sign in")
    || message.includes("/sign")
    || message.includes("no saved microsoft account")
    || message.includes("no supabase token");
}

function isSignInBackendError(dataOrMessage) {
  const error = typeof dataOrMessage === "string" ? "" : String((dataOrMessage && dataOrMessage.error) || "").toLowerCase();
  const message = typeof dataOrMessage === "string"
    ? dataOrMessage.toLowerCase()
    : String((dataOrMessage && (dataOrMessage.message || dataOrMessage.text)) || "").toLowerCase();
  return ["missing_user", "session_required", "reauth_required", "extension_auth_required", "extension_auth_invalid", "user_mismatch", "supabase_not_configured"].includes(error)
    || message.includes("sign in")
    || message.includes("no saved")
    || message.includes("no supabase token")
    || message.includes("supabase not configured")
    || message.includes("requested mailbox does not match");
}

function askForServerKey(options = {}) {
  const needsKey = options.needsKey !== false;
  const message = String(options.message || "").trim();
  if (!serverKeyModal || !serverKeyForm || !serverKeyInput || !serverKeyCancel) {
    if (!needsKey) {
      openProviderSignIn().catch(() => {});
      return Promise.resolve("");
    }
    return Promise.resolve(window.prompt("Condra server key") || "");
  }

  return new Promise((resolve) => {
    let settled = false;

    function finish(value) {
      if (settled) return;
      settled = true;
      serverKeyModal.classList.add("hidden");
      serverKeyForm.removeEventListener("submit", onSubmit);
      serverKeyCancel.removeEventListener("click", onCancel);
      if (microsoftSigninButton) microsoftSigninButton.removeEventListener("click", onMicrosoftSignIn);
      serverKeyModal.removeEventListener("click", onBackdropClick);
      document.removeEventListener("keydown", onKeyDown);
      resolve(value);
    }

    function onSubmit(event) {
      event.preventDefault();
      finish(serverKeyInput.value.trim());
    }

    function onCancel() {
      finish("");
    }

    function onMicrosoftSignIn() {
      const provider = providerForSignIn();
      openProviderSignIn(provider)
        .then(() => setStatus(`${provider === "gmail" ? "Gmail" : "Microsoft"} sign-in opened. Finish there, then retry.`, false))
        .catch((err) => setStatus(String(err.message || err), true));
    }

    function onBackdropClick(event) {
      if (event.target === serverKeyModal) finish("");
    }

    function onKeyDown(event) {
      if (event.key === "Escape") finish("");
    }

    serverKeyInput.value = extensionApiKey || "";
    if (serverKeyMessage) {
      serverKeyMessage.textContent = message || "Sign in with Gmail or Microsoft to connect Condra. The server key is only needed as a fallback.";
    }
    if (microsoftSigninButton) {
      const provider = providerForSignIn();
      microsoftSigninButton.textContent = provider === "gmail" ? "Sign in with Gmail" : "Sign in with Microsoft";
    }
    if (serverKeyField) {
      serverKeyField.classList.toggle("hidden", !needsKey);
    }
    serverKeyModal.classList.remove("hidden");
    serverKeyForm.addEventListener("submit", onSubmit);
    serverKeyCancel.addEventListener("click", onCancel);
    if (microsoftSigninButton) microsoftSigninButton.addEventListener("click", onMicrosoftSignIn);
    serverKeyModal.addEventListener("click", onBackdropClick);
    document.addEventListener("keydown", onKeyDown);
    window.setTimeout(() => {
      if (needsKey) serverKeyInput.focus();
      else if (microsoftSigninButton) microsoftSigninButton.focus();
    }, 0);
  });
}

async function localFetch(path, options = {}, retryAuth = true) {
  const errors = [];
  for (const base of BASES) {
    try {
      const res = await fetchWithTimeout(`${base}${path}`, fetchOptionsWithAuth(options));
      const text = await res.text();
      let data = {};
      try {
        data = text ? JSON.parse(text) : {};
      } catch (err) {
        data = { text };
      }
      localStorage.setItem("condraBackendBase", base.replace(/\/+$/, ""));
      if (
        res.status === 403
        && retryAuth
        && (data.error === "extension_auth_required" || data.error === "extension_auth_invalid")
      ) {
        const entered = await askForServerKey({
          needsKey: true,
          message: data.message || "Sign in with Gmail or Microsoft to connect Condra. The server key is only needed as a fallback."
        });
        if (entered && entered.trim()) {
          extensionApiKey = entered.trim();
          localStorage.setItem("condraExtensionApiKey", extensionApiKey);
          return localFetch(path, options, false);
        }
      }
      if (!res.ok && retryAuth && shouldOfferProviderSignIn(data)) {
        await askForServerKey({
          needsKey: false,
          message: data.message || "Sign-in is needed before Condra can use this account."
        });
      }
      if (!res.ok) {
        if (isSignInBackendError(data)) {
          throw new Error("Sign in");
        }
        errors.push(describeBackendError(path, base, res.status, data));
        continue;
      }
      return data;
    } catch (err) {
      const message = err && err.name === "AbortError"
        ? "request timed out"
        : String(err && err.message || err);
      errors.push(`${base}${path}: ${message}`);
    }
  }
  if (errors.some(isSignInBackendError)) {
    throw new Error("Sign in");
  }
  throw new Error(errors.join(" | ") || "Could not reach Condra server.");
}

function parseSummary(raw) {
  const result = { subject: "", sender: "", time: "", bullets: [], objectiveId: "", objectiveInfo: "", objectiveCompletion: "" };
  const jsonStart = String(raw || "").indexOf("{");
  if (jsonStart !== -1) {
    let inString = false;
    let escape = false;
    let depth = 0;
    for (let i = jsonStart; i < raw.length; i++) {
      const ch = raw[i];
      if (ch === '"' && !escape) inString = !inString;
      if (!inString) {
        if (ch === "{") depth++;
        if (ch === "}") depth--;
        if (depth === 0) {
          try {
            const parsed = JSON.parse(raw.slice(jsonStart, i + 1).replace(/“|”/g, '"').replace(/’/g, "'"));
            result.bullets = Array.isArray(parsed.bullets) ? parsed.bullets : [];
            result.objectiveId = String(parsed["is Objective"] || "").trim();
            result.objectiveInfo = String(parsed["info about Objective"] || "").trim();
            result.objectiveCompletion = String(parsed["completion of objective"] || "").trim();
          } catch (err) {}
          break;
        }
      }
      escape = ch === "\\" && !escape;
      if (ch !== "\\") escape = false;
    }
  }

  String(raw || "").split("\n").forEach((line) => {
    const clean = line.trim();
    if (clean.startsWith("Subject:")) result.subject = clean.replace("Subject:", "").trim();
    if (clean.startsWith("From:")) result.sender = clean.replace("From:", "").trim();
    if (clean.startsWith("Time:")) result.time = clean.replace("Time:", "").trim();
  });
  return result;
}

function attachRawEmailContext(summary, rawChunk) {
  if (!summary) return null;
  summary.rawChunk = String(rawChunk || "");
  const bodyMatch = summary.rawChunk.match(/\nBody:\s*([\s\S]*?)(?:\n0\s*$|$)/i);
  summary.bodyText = bodyMatch ? bodyMatch[1].trim() : "";
  return summary;
}

async function getOpenEmailFromActiveTab() {
  const tabs = await extApi.tabs.query({ active: true, currentWindow: true });
  const tab = tabs && tabs[0];
  if (!tab || !tab.id || !isSupportedMailUrl(tab.url)) {
    throw new Error("Open Gmail or Outlook and select an email first.");
  }
  return sendMessageToMailTab(tab.id, { type: "CONDRA_GET_OPEN_EMAIL" });
}

async function sendHighlightToActiveTab(summary) {
  try {
    const tabs = await extApi.tabs.query({ active: true, currentWindow: true });
    const tab = tabs && tabs[0];
    if (!tab || !tab.id || !isSupportedMailUrl(tab.url)) return null;
    const result = await sendMessageToMailTab(tab.id, {
      type: "CONDRA_HIGHLIGHT_SUMMARY",
      summary: summary || null
    });
    if (currentMatchDebug && currentMatchDebug.response) {
      currentMatchDebug.response.highlight = result && result.highlight ? result.highlight : {};
    }
    return result;
  } catch (err) {
    // Highlighting is best-effort; the sidebar summary should still work.
    if (currentMatchDebug && currentMatchDebug.response) {
      currentMatchDebug.response.highlight_error = String(err && err.message || err);
    }
    return null;
  }
}

async function sendFocusHighlightToActiveTab(index) {
  try {
    const tabs = await extApi.tabs.query({ active: true, currentWindow: true });
    const tab = tabs && tabs[0];
    if (!tab || !tab.id || !isSupportedMailUrl(tab.url)) return;
    await sendMessageToMailTab(tab.id, {
      type: "CONDRA_FOCUS_HIGHLIGHT",
      index
    });
  } catch (err) {
    // Best-effort only.
  }
}

function previewText(value, maxChars = 260) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars).trim()}...`;
}

function normalizeMatchText(value) {
  return String(value || "")
    .replace(/[""]/g, '"')
    .replace(/['']/g, "'")
    .replace(/^((re|fw|fwd):\s*)+/i, "")
    .replace(/[^a-zA-Z0-9@._+-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function matchTokens(value) {
  const stop = new Set(["the", "and", "for", "you", "your", "that", "this", "with", "from", "have", "are", "was", "were", "will", "can", "email", "please", "thanks", "hello"]);
  return new Set((normalizeMatchText(value).match(/[a-z0-9]{4,}/g) || []).filter((token) => !stop.has(token)));
}

function tokenOverlapScore(left, right) {
  const a = matchTokens(left);
  const b = matchTokens(right);
  if (!a.size || !b.size) return 0;
  let overlap = 0;
  a.forEach((token) => {
    if (b.has(token)) overlap += 1;
  });
  return overlap;
}

function summaryMatchesOpenEmail(email, summary, response = {}) {
  if (!email || !summary) return false;
  const emailId = String(email.id || "").trim();
  const responseId = String(response.email_id || "").trim();
  if (emailId && responseId && emailId === responseId) return true;

  const emailSubject = normalizeMatchText(email.subject || "");
  const summarySubject = normalizeMatchText(summary.subject || "");
  const emailBody = String(email.snippet || "");
  const summaryBody = String(summary.bodyText || summary.rawChunk || "");
  let score = 0;

  if (emailSubject && summarySubject) {
    if (emailSubject === summarySubject) score += 30;
    else if (emailSubject.includes(summarySubject) || summarySubject.includes(emailSubject)) score += 12;
    else return false;
  }

  const bodySample = normalizeMatchText(emailBody).slice(0, 700);
  const summaryNorm = normalizeMatchText(summaryBody);
  if (bodySample && bodySample.length >= 80 && summaryNorm.includes(bodySample)) {
    score += 100;
  } else {
    score += Math.min(80, tokenOverlapScore(emailBody, summaryBody) * 4);
  }

  return score >= 45 || (emailSubject && summarySubject && score >= 30 && tokenOverlapScore(emailBody, summaryBody) >= 2);
}

function summaryFromMatchResponse(data) {
  return attachRawEmailContext(data.summary || (data.raw_chunk ? parseSummary(data.raw_chunk) : null), data.raw_chunk);
}

function buildMatchRequestPayload(email) {
  const userEmail = userEmailForOpenEmail(email);
  const snippet = String((email && email.snippet) || "").slice(0, 1600);
  return {
    user_email: userEmail,
    subject: (email && email.subject) || "",
    snippet
  };
}

async function fetchNotesForAction() {
  const userEmail = account.value || (currentEmail && currentEmail.userEmail) || "";
  const data = await localFetch(`/extension/notes?user_email=${encodeURIComponent(userEmail)}&t=${Date.now()}`);
  const notes = Array.isArray(data.notes) ? data.notes : [];
  notesCache = { userEmail, fetchedAt: Date.now(), notes };
  return notes;
}

async function refreshNotes(force = false) {
  renderNotesLoading();
  const notes = await fetchNotesForAction();
  renderNotes(notes);
}

function renderNotesLoading() {
  notesList.replaceChildren();

  const loader = document.createElement("div");
  loader.className = "notes-loading";
  loader.setAttribute("role", "status");
  loader.setAttribute("aria-live", "polite");

  const spinner = document.createElement("span");
  spinner.className = "notes-spinner";
  spinner.setAttribute("aria-hidden", "true");

  const copy = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = "Loading notes";
  const detail = document.createElement("span");
  detail.textContent = "Checking your saved Condra notes...";

  copy.append(title, detail);
  loader.append(spinner, copy);
  notesList.appendChild(loader);
}

function renderNotes(notes) {
  notesList.replaceChildren();
  if (!Array.isArray(notes) || !notes.length) {
    notesList.innerHTML = '<div class="empty-state compact"><strong>No notes yet</strong><span>Add one above and Condra will watch for matching emails.</span></div>';
    return;
  }

  notes.forEach((note, index) => {
    const color = NOTE_LABEL_COLORS[index % NOTE_LABEL_COLORS.length];
    const card = document.createElement("div");
    card.className = "note-card";
    card.style.setProperty("--note-label-bg", color.background);
    card.style.setProperty("--note-label-text", color.text);

    const header = document.createElement("div");
    header.className = "note-header";
    const badge = document.createElement("span");
    badge.className = "note-badge";
    badge.textContent = `Note ${index + 1}`;
    header.appendChild(badge);
    card.appendChild(header);

    const topic = document.createElement("div");
    topic.className = "note-title";
    topic.textContent = note.topic || note.text || "Untitled note";
    card.appendChild(topic);

    const meta = document.createElement("div");
    meta.className = "note-meta";
    meta.textContent = [
      note.expected_from ? `From: ${note.expected_from}` : "",
      note.ai_action ? note.ai_action.trim() : ""
    ].filter(Boolean).join(" | ");
    if (meta.textContent) card.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "note-actions";
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "note-delete";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", () => {
      deleteNote(index, deleteButton).catch((err) => setStatus(String(err.message || err), true));
    });
    actions.appendChild(deleteButton);
    card.appendChild(actions);

    notesList.appendChild(card);
  });
}

async function deleteNote(index, button) {
  if (button) {
    button.disabled = true;
    button.classList.add("saving");
    button.textContent = "Deleting";
  }

  setStatus("Deleting note...");
  try {
    const data = await localFetch("/extension/delete_note", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_email: account.value || (currentEmail && currentEmail.userEmail) || "",
        index
      })
    });

    const notes = Array.isArray(data.notes) ? data.notes : [];
    notesCache = {
      userEmail: data.user_email || account.value || "",
      fetchedAt: Date.now(),
      notes
    };
    renderNotes(notes);
    setStatus("Note deleted.");
  } finally {
    if (button) {
      button.disabled = false;
      button.classList.remove("saving");
      button.textContent = "Delete";
    }
  }
}

async function saveNoteFromForm(event) {
  event.preventDefault();
  const saveButton = document.getElementById("save-note");
  const topic = document.getElementById("note-topic").value.trim();
  const expectedFrom = document.getElementById("note-expected").value.trim();
  const aiActionText = document.getElementById("note-ai-action").value.trim();

  if (!topic || !expectedFrom || !aiActionText) {
    setStatus("Fill in topic, expected sender, and action.", true);
    return;
  }

  setStatus("Saving note...");
  saveButton.disabled = true;
  saveButton.classList.add("saving");
  saveButton.textContent = "Saving";
  const aiAction = aiActionText;
  try {
    await localFetch("/extension/save_note", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_email: account.value || (currentEmail && currentEmail.userEmail) || "",
        topic,
        expected_from: expectedFrom,
        ai_action: aiAction
      })
    });

    notesCache = { userEmail: "", fetchedAt: 0, notes: [] };
    noteForm.reset();
    setStatus("Note saved.");
    await refreshNotes(true);
  } finally {
    saveButton.disabled = false;
    saveButton.classList.remove("saving");
    saveButton.textContent = "Save Note";
  }
}

function appendChatBubble(role, text = "") {
  if (answerEl.querySelector(".ask-empty")) {
    answerEl.replaceChildren();
  }

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role === "user" ? "user" : "assistant"}`;
  bubble.textContent = String(text || "");
  answerEl.appendChild(bubble);
  bubble.scrollIntoView({ block: "end" });
  return bubble;
}

async function openAskRef(ref) {
  const webLink = String((ref && (ref.web_link || ref.url)) || "").trim();
  if (webLink) {
    await extApi.tabs.create({ url: webLink });
    return;
  }

  const id = String((ref && (ref.web_id || ref.thread_id || ref.id)) || "").trim();
  const subject = String((ref && ref.subject) || "").trim();
  const provider = String((currentEmail && currentEmail.provider) || "").toLowerCase();
  if (provider === "outlook") {
    const query = encodeURIComponent(subject || id);
    await extApi.tabs.create({ url: `https://outlook.live.com/mail/0/search?q=${query}` });
    return;
  }
  if (id) {
    await extApi.tabs.create({ url: `https://mail.google.com/mail/u/0/#all/${encodeURIComponent(id)}` });
  }
}

function appendAskRefsToBubble(bubble, refs) {
  if (!bubble || !Array.isArray(refs) || !refs.length) return;
  const list = document.createElement("div");
  list.className = "ask-ref-list";
  const label = document.createElement("div");
  label.className = "ask-ref-label";
  label.textContent = "Source emails";
  list.appendChild(label);

  refs.slice(0, 6).forEach((ref) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ask-ref-button";
    button.textContent = String((ref && ref.subject) || "(No Subject)");
    button.title = "Open source email";
    button.addEventListener("click", () => {
      openAskRef(ref).catch((err) => setStatus(String(err.message || err), true));
    });
    list.appendChild(button);
  });
  bubble.appendChild(list);
}

function renderAskEmpty() {
  answerEl.innerHTML = '<div class="ask-empty"><strong>Ask Condra</strong><span>Use the current email, all saved email, or no email context.</span></div>';
}

function typeAnswer(text, target = answerEl) {
  return new Promise((resolve) => {
    const value = String(text || "");
    target.textContent = "";
    target.classList.add("typing");

    let index = 0;
    function tick() {
      const chunkSize = value.length > 900 ? 4 : 2;
      target.textContent += value.slice(index, index + chunkSize);
      index += chunkSize;
      target.scrollIntoView({ block: "nearest" });

      if (index >= value.length) {
        target.classList.remove("typing");
        resolve();
        return;
      }

      window.setTimeout(tick, 14);
    }

    tick();
  });
}

async function askCondra() {
  const input = document.getElementById("question");
  const sendButton = document.getElementById("ask");
  const question = input.value.trim();
  const contextMode = document.getElementById("ask-context").value;
  if (!question) {
    setStatus("Type a question first.", true);
    return;
  }

  if (contextMode !== "chat") {
    try {
      currentEmail = await getOpenEmailFromActiveTab();
      currentEmailKey = getEmailKey(currentEmail);
      if (currentEmail && currentEmail.userEmail) {
        account.value = currentEmail.userEmail;
        localStorage.setItem("condraSidebarAccount", account.value);
      }
      if (contextMode === "current_email" && (!currentEmail || !currentEmail.isOpen)) {
        throw new Error("Open an email in Gmail or Outlook first, or switch context to All email.");
      }
    } catch (err) {
      if (contextMode === "current_email") {
        setStatus(String(err.message || err), true);
        appendChatBubble("assistant", String(err.message || err));
        return;
      }
    }
  }

  appendChatBubble("user", question);
  input.value = "";
  input.style.height = "";
  input.disabled = true;
  sendButton.disabled = true;
  const responseBubble = appendChatBubble("assistant");
  responseBubble.innerHTML = '<span class="thinking">Thinking<span></span></span>';
  setStatus("Asking Condra...");
  try {
    const data = await localFetch("/extension/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_email: account.value || (currentEmail && currentEmail.userEmail) || "",
        question,
        context_mode: contextMode,
        use_email_context: contextMode !== "chat",
        current_email: contextMode !== "chat" && currentEmail ? {
          id: currentEmail && currentEmail.id || "",
          user_email: currentEmail && currentEmail.userEmail || "",
          url: currentEmail && currentEmail.url || "",
          sender: currentEmail && currentEmail.sender || "",
          subject: currentEmail && currentEmail.subject || "",
          time: currentEmail && currentEmail.time || "",
          body: currentEmail && currentEmail.snippet || ""
        } : null
      })
    });
    await typeAnswer(data.answer || "(No answer)", responseBubble);
    appendAskRefsToBubble(responseBubble, data.refs);
    setStatus("Ready.");
  } finally {
    input.disabled = false;
    sendButton.disabled = false;
    input.focus();
  }
}

function showMode(mode) {
  activeMode = mode;
  document.querySelectorAll(".mode-button").forEach((button) => {
    const selected = button.dataset.mode === mode;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
  });
  summaryView.classList.toggle("hidden", mode !== "summary");
  notesView.classList.toggle("hidden", mode !== "notes");
  askView.classList.toggle("hidden", mode !== "ask");

  if (mode === "summary") {
    sendHighlightToActiveTab(currentSummary);
  }
  if (mode === "notes") {
    refreshNotes(false).catch((err) => setStatus(String(err.message || err), true));
  }
}

function focusSummaryCard(index) {
  const card = summaryView.querySelector(`[data-summary-index="${index}"]`);
  if (!card) return;
  card.scrollIntoView({ block: "center", behavior: "smooth" });
  card.classList.add("selected");
  window.setTimeout(() => card.classList.remove("selected"), 1800);
}

function renderSummaryLoading(message = "Looking for a saved summary...") {
  summaryView.replaceChildren();

  const loader = document.createElement("div");
  loader.className = "summary-loading";
  loader.setAttribute("role", "status");
  loader.setAttribute("aria-live", "polite");

  const spinner = document.createElement("span");
  spinner.className = "notes-spinner";
  spinner.setAttribute("aria-hidden", "true");

  const copy = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = "Loading summary";
  const detail = document.createElement("span");
  detail.textContent = message;

  copy.append(title, detail);
  loader.append(spinner, copy);
  summaryView.appendChild(loader);
}

function renderSummary(summary) {
  currentSummary = summary || null;
  sendHighlightToActiveTab(currentSummary);
  summaryView.replaceChildren();
  if (!summary) {
    summaryView.innerHTML = '<div class="empty-state"><strong>No summary yet</strong><span>Open an email and Condra will look for a saved summary automatically.</span></div>';
    return;
  }

  const hero = document.createElement("div");
  hero.className = "summary-hero";

  const eyebrow = document.createElement("div");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Open email";
  hero.appendChild(eyebrow);

  const title = document.createElement("h1");
  title.className = "title";
  title.textContent = summary.subject || "Summary";
  hero.appendChild(title);

  if (summary.sender) {
    const meta = document.createElement("div");
    meta.className = "small";
    meta.textContent = summary.sender;
    hero.appendChild(meta);
  }
  summaryView.appendChild(hero);

  (summary.bullets || []).slice(0, 8).forEach((bullet, index) => {
    const card = document.createElement("div");
    card.className = "card summary-card";
    card.dataset.summaryIndex = String(index);
    card.title = "Jump to matching highlighted text in Gmail";
    card.addEventListener("click", () => {
      focusSummaryCard(index);
      sendFocusHighlightToActiveTab(index);
    });
    const number = document.createElement("span");
    number.className = "card-number";
    number.textContent = String(index + 1);
    card.appendChild(number);
    const body = document.createElement("div");
    body.className = "card-body";
    const point = document.createElement("div");
    point.className = "card-point";
    point.textContent = bullet.point || "";
    body.appendChild(point);
    if (bullet.excerpt && String(bullet.excerpt).toLowerCase() !== "no exact excerpt") {
      const excerpt = document.createElement("div");
      excerpt.className = "excerpt";
      excerpt.textContent = `Exact: ${bullet.excerpt}`;
      body.appendChild(excerpt);
    }
    card.appendChild(body);
    summaryView.appendChild(card);
  });

  if (summary.objectiveCompletion && summary.objectiveCompletion.toLowerCase() !== "none") {
    const completion = document.createElement("div");
    completion.className = "objective-card";
    const label = document.createElement("div");
    label.className = "objective-label";
    label.textContent = "Objective completion";
    completion.appendChild(label);
    const text = document.createElement("div");
    text.className = "objective-text";
    text.textContent = summary.objectiveCompletion;
    completion.appendChild(text);
    summaryView.appendChild(completion);
  }

}

function getEmailKey(email) {
  if (!email) return "";
  return [
    email.id || "",
    email.userEmail || "",
    email.sender || "",
    email.subject || "",
    String(email.snippet || "").slice(0, 500),
    email.time || ""
  ].join("|");
}

async function loadOpenEmailSummary() {
  setStatus("Reading the open email...");
  renderSummaryLoading("Reading the open email...");
  currentEmail = await getOpenEmailFromActiveTab();
  currentEmailKey = getEmailKey(currentEmail);
  rememberAccount(currentEmail.userEmail);
  if (!currentEmail.isOpen) throw new Error("Open an email in Gmail or Outlook first.");

  setStatus("Looking for saved summary...");
  renderSummaryLoading();
  const matchPayload = buildMatchRequestPayload(currentEmail);
  console.log("[Condra] sidebar match_summary request", {
    ...matchPayload,
    snippet_length: String(matchPayload.snippet || "").length
  });
  const data = await localFetch("/extension/match_summary", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(matchPayload)
  });
  currentMatchDebug = { request: matchPayload, response: data };

  const matchedSummary = summaryFromMatchResponse(data);
  if (!summaryMatchesOpenEmail(currentEmail, matchedSummary, data)) {
    currentMatchDebug.rejected = { reason: "summary_did_not_match_open_email", summary: matchedSummary };
    renderSummary(null);
    if (isSignInBackendError(data)) {
      setStatus("Sign in", true);
      return;
    }
    const detail = data && (data.message || data.error)
      ? ` Backend said: ${data.message || data.error}.`
      : "";
    setStatus(`No saved summary for this open email yet.${detail}`);
    return;
  }
  renderSummary(matchedSummary);
  await sendHighlightToActiveTab(currentSummary);
  renderSummary(currentSummary);
  setStatus("Ready.");
}

async function autoLoadOpenEmailSummary(force = false) {
  if (autoLoadInFlight) return;
  autoLoadInFlight = true;
  try {
    const email = await getOpenEmailFromActiveTab();
    const nextKey = getEmailKey(email);
    if (!force && nextKey && nextKey === currentEmailKey) {
      sendHighlightToActiveTab(currentSummary);
      return;
    }

    currentEmail = email;
    currentEmailKey = nextKey;
    rememberAccount(currentEmail.userEmail);
    if (!currentEmail.isOpen) {
      renderSummary(null);
      setStatus("Open an email.");
      return;
    }

    setStatus("Looking for saved summary...");
    renderSummaryLoading();
    const matchPayload = buildMatchRequestPayload(currentEmail);
    console.log("[Condra] sidebar match_summary request", {
      ...matchPayload,
      snippet_length: String(matchPayload.snippet || "").length
    });
    const data = await localFetch("/extension/match_summary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(matchPayload)
    });
    currentMatchDebug = { request: matchPayload, response: data };
    const matchedSummary = summaryFromMatchResponse(data);
    if (!summaryMatchesOpenEmail(currentEmail, matchedSummary, data)) {
      currentMatchDebug.rejected = { reason: "summary_did_not_match_open_email", summary: matchedSummary };
      renderSummary(null);
      if (isSignInBackendError(data)) {
        setStatus("Sign in", true);
        return;
      }
      const detail = data && (data.message || data.error)
        ? ` Backend said: ${data.message || data.error}.`
        : "";
      setStatus(`No saved summary for this open email yet.${detail}`);
      return;
    }
    renderSummary(matchedSummary);
    await sendHighlightToActiveTab(currentSummary);
    renderSummary(currentSummary);
    setStatus("Ready.");
  } catch (err) {
    renderSummary(null);
    setStatus(String(err.message || err), true);
    console.error("[Condra] auto summary load failed", err);
  } finally {
    autoLoadInFlight = false;
  }
}

document.getElementById("refresh").addEventListener("click", () => {
  if (activeMode === "notes") {
    refreshNotes(true).catch((err) => setStatus(String(err.message || err), true));
    return;
  }
  autoLoadOpenEmailSummary(true);
});

document.getElementById("signin").addEventListener("click", () => {
  askForServerKey({
    needsKey: false,
    message: "Sign in with Gmail or Microsoft on the Condra server, then return here and retry."
  }).catch((err) => setStatus(String(err.message || err), true));
});

summaryView.innerHTML = '<div class="empty-state"><strong>Waiting for email</strong><span>Open an email and Condra will load the summary automatically.</span></div>';
renderAskEmpty();
autoLoadOpenEmailSummary(true);
window.addEventListener("focus", () => autoLoadOpenEmailSummary(false));
window.setInterval(() => autoLoadOpenEmailSummary(false), 2500);

document.querySelectorAll(".mode-button").forEach((button) => {
  button.addEventListener("click", () => showMode(button.dataset.mode));
});

noteForm.addEventListener("submit", (event) => {
  saveNoteFromForm(event).catch((err) => setStatus(String(err.message || err), true));
});

document.getElementById("ask").addEventListener("click", () => {
  askCondra().catch((err) => {
    appendChatBubble("assistant", String(err.message || err));
    setStatus(String(err.message || err), true);
  });
});

document.getElementById("question").addEventListener("input", (event) => {
  const input = event.currentTarget;
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 118)}px`;
});

document.getElementById("question").addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.metaKey || event.ctrlKey) return;
  event.preventDefault();
  askCondra().catch((err) => {
    appendChatBubble("assistant", String(err.message || err));
    setStatus(String(err.message || err), true);
  });
});

if (extApi && extApi.runtime && extApi.runtime.onMessage) {
  extApi.runtime.onMessage.addListener((message) => {
    if (!message || message.type !== "CONDRA_SELECT_SUMMARY_INDEX") return false;
    focusSummaryCard(Number(message.index || 0));
    return false;
  });
}
