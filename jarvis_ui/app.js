// State variables
let ws;
let isRecording = false;
let chatId = localStorage.getItem('chatId') || `jarvis_${Math.random().toString(36).substr(2, 9)}`;
localStorage.setItem('chatId', chatId);

let apiUrl = localStorage.getItem('apiUrl') || 'ws://127.0.0.1:20067/ws';
let restUrl = localStorage.getItem('restUrl') || 'http://127.0.0.1:20067';
let currentTheme = localStorage.getItem('theme') || 'dark';

// DOM Elements
const sidebar = document.querySelector('.sidebar');
const openSidebarBtn = document.getElementById('open-sidebar-btn');
const closeSidebarBtn = document.getElementById('close-sidebar-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const msgArea = document.getElementById('messages-area');
const welcomeScreen = document.getElementById('welcome-screen');
const input = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const attachBtn = document.getElementById('attach-btn');
const micBtn = document.getElementById('mic-btn');
const fileInput = document.getElementById('file-input');

// Settings Elements
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const apiUrlInput = document.getElementById('api-url-input');
const restUrlInput = document.getElementById('rest-url-input');
const themeSelect = document.getElementById('theme-select');

let currentFinalMsg = null;
let currentThinkingBox = null;

// Initialize
applyTheme(currentTheme);
apiUrlInput.value = apiUrl;
restUrlInput.value = restUrl;
themeSelect.value = currentTheme;
initWS();

// --- Sidebar Toggles ---
closeSidebarBtn.addEventListener('click', () => {
    sidebar.classList.add('closed');
    openSidebarBtn.classList.remove('hidden');
});

openSidebarBtn.addEventListener('click', () => {
    sidebar.classList.remove('closed');
    openSidebarBtn.classList.add('hidden');
});

// --- Settings Modal ---
settingsBtn.addEventListener('click', () => settingsModal.classList.remove('hidden'));
closeSettingsBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));
saveSettingsBtn.addEventListener('click', () => {
    apiUrl = apiUrlInput.value.trim();
    restUrl = restUrlInput.value.trim();
    currentTheme = themeSelect.value;

    localStorage.setItem('apiUrl', apiUrl);
    localStorage.setItem('restUrl', restUrl);
    localStorage.setItem('theme', currentTheme);

    applyTheme(currentTheme);
    settingsModal.classList.add('hidden');

    if (ws) ws.close(); // will auto reconnect
});

function applyTheme(theme) {
    if (theme === 'light') {
        document.body.classList.add('light-theme');
    } else {
        document.body.classList.remove('light-theme');
    }
}

// --- WebSocket & Messaging ---
function initWS() {
    console.log("Connecting to", apiUrl);
    try {
        ws = new WebSocket(apiUrl);

        ws.onopen = () => {
            console.log("Connected to Jarvis API");
        };

        ws.onmessage = (event) => {
            const payload = JSON.parse(event.data);
            if (payload.type === 'agent_state') {
                handleAgentState(payload.data);
            } else if (payload.type === 'bot_action') {
                handleBotAction(payload);
            } else if (payload.type === 'error') {
                createMessageRow("Error: " + payload.message, "assistant");
            }
        };

        ws.onclose = () => {
            console.log("Disconnected. Reconnecting in 3s...");
            setTimeout(initWS, 3000);
        };
    } catch (e) {
        console.error("WS error:", e);
        setTimeout(initWS, 3000);
    }
}

function handleAgentState(data) {
    const { status, message, content, tool, args, result } = data;

    if (status === 'thinking' || status === 'thinking_stream') {
        updateThinkingBox(message || content, false);
    }
    else if (status === 'tool_use') {
        updateThinkingBox(`Executing tool: ${tool}...`, false);
        currentFinalMsg = null; // reset stream target
    }
    else if (status === 'observation') {
        // We could log the observation in the tool box, but let's keep it clean
        updateThinkingBox("Analyzing results...", false);
    }
    else if (status === 'final_stream') {
        finishThinkingBox();
        if (!currentFinalMsg) {
            currentFinalMsg = createMessageRow(content, 'assistant', true);
        } else {
            const contentDiv = currentFinalMsg.querySelector('.message-content');
            // Store raw text to re-render markdown properly if needed, but for stream just append
            // However, marked doesn't do incremental well. We'll append text and parse the whole block if possible.
            // For now, let's just use raw appending. To fix markdown live rendering, we need a buffer.
            if (!currentFinalMsg.rawBuffer) currentFinalMsg.rawBuffer = "";
            currentFinalMsg.rawBuffer += content;
            contentDiv.innerHTML = marked.parse(currentFinalMsg.rawBuffer);
            scrollToBottom();
        }
    }
    else if (status === 'final') {
        finishThinkingBox();
        if (!currentFinalMsg && content) {
            const row = createMessageRow('', 'assistant', false);
            row.querySelector('.message-content').innerHTML = marked.parse(content);
        }
        currentFinalMsg = null;
    }
    else if (status === 'error') {
        finishThinkingBox();
        createMessageRow(`[Error] ${message}`, 'assistant');
    }
}

function updateThinkingBox(text, isDone) {
    welcomeScreen.classList.add('hidden');
    msgArea.classList.remove('hidden');

    if (!currentThinkingBox) {
        // Create new row
        const row = document.createElement("div");
        row.className = "message-row";

        const avatar = document.createElement("div");
        avatar.className = "message-avatar assistant";
        avatar.innerHTML = "<i class='bx bxs-sun'></i>"; // Jarvis icon

        const contentDiv = document.createElement("div");
        contentDiv.className = "message-content";

        const toolBox = document.createElement("div");
        toolBox.className = "tool-box";
        toolBox.innerHTML = `
            <div class="tool-header">
                <span class="spinner"></span>
                <span class="tool-status-text">${text}</span>
            </div>
        `;

        contentDiv.appendChild(toolBox);
        row.appendChild(avatar);
        row.appendChild(contentDiv);
        msgArea.appendChild(row);

        currentThinkingBox = { row, toolBox, textSpan: toolBox.querySelector('.tool-status-text'), spinner: toolBox.querySelector('.spinner') };
        scrollToBottom();
    } else {
        currentThinkingBox.textSpan.textContent = text;
    }
}

function finishThinkingBox() {
    if (currentThinkingBox) {
        currentThinkingBox.spinner.classList.add('hidden');
        currentThinkingBox.textSpan.textContent = "Finished reasoning";
        currentThinkingBox.toolBox.style.opacity = "0.6";
        currentThinkingBox = null;
    }
}

function handleBotAction(payload) {
    if (payload.chat_id !== chatId) return;
    welcomeScreen.classList.add('hidden');
    msgArea.classList.remove('hidden');

    if (payload.action === "clear") {
        msgArea.innerHTML = "";
        welcomeScreen.classList.remove('hidden');
        msgArea.classList.add('hidden');
    } else if (payload.action === "send_message") {
        const row = createMessageRow('', 'assistant', false);
        row.querySelector('.message-content').innerHTML = marked.parse(payload.text);
    } else if (payload.action === "send_photo") {
        createMediaRow('image', payload.filename, payload.caption);
    } else if (payload.action === "send_video") {
        createMediaRow('video', payload.filename, payload.caption);
    } else if (payload.action === "send_audio" || payload.action === "send_voice") {
        createMediaRow('audio', payload.filename, payload.caption);
    } else if (payload.action === "send_document" || payload.action === "send_file") {
        createFileRow(payload.filename, payload.caption);
    }
}

function createMediaRow(type, filename, caption) {
    const row = document.createElement("div");
    row.className = "message-row";
    const srcUrl = `${restUrl}/download/${encodeURIComponent(filename)}`;

    let mediaHtml = '';
    if (type === 'image') mediaHtml = `<img src="${srcUrl}" style="max-width:100%; border-radius:8px;">`;
    if (type === 'video') mediaHtml = `<video src="${srcUrl}" controls style="max-width:100%; border-radius:8px;"></video>`;
    if (type === 'audio') mediaHtml = `<audio src="${srcUrl}" controls style="width:100%; max-width: 400px;"></audio>`;

    let captionHtml = caption ? `<div style="margin-top:8px; font-size: 0.9em; color: var(--text-secondary);">${marked.parse(caption)}</div>` : '';

    row.innerHTML = `
        <div class="message-avatar assistant"><i class='bx bxs-sun'></i></div>
        <div class="message-content">
            ${mediaHtml}
            ${captionHtml}
        </div>
    `;
    msgArea.appendChild(row);
    scrollToBottom();
}

function createFileRow(filename, caption) {
    const row = document.createElement("div");
    row.className = "message-row";
    const dlUrl = `${restUrl}/download/${encodeURIComponent(filename)}`;

    let captionHtml = caption ? `<div style="margin-top:8px; font-size: 0.9em;">${marked.parse(caption)}</div>` : '';

    row.innerHTML = `
        <div class="message-avatar assistant"><i class='bx bxs-sun'></i></div>
        <div class="message-content">
            <a href="${dlUrl}" target="_blank" class="attachment-card">
                <i class='bx bx-file'></i>
                <span>${filename}</span>
                <i class='bx bx-download' style="margin-left:auto; color:var(--text-secondary); font-size: 18px;"></i>
            </a>
            ${captionHtml}
        </div>
    `;
    msgArea.appendChild(row);
    scrollToBottom();
}

function createMessageRow(text, role, isStream = false) {
    welcomeScreen.classList.add('hidden');
    msgArea.classList.remove('hidden');

    const row = document.createElement("div");
    row.className = "message-row";

    const avatar = document.createElement("div");
    avatar.className = `message-avatar ${role}`;
    avatar.innerHTML = role === 'user' ? 'U' : "<i class='bx bxs-sun'></i>";

    const content = document.createElement("div");
    content.className = "message-content";

    if (role === 'user') {
        content.textContent = text; // Plain text for user input to avoid XSS/Markdown weirdness
    } else {
        if (!isStream) {
            content.innerHTML = marked.parse(text);
        } else {
            content.textContent = text;
            row.rawBuffer = text;
        }
    }

    row.appendChild(avatar);
    row.appendChild(content);
    msgArea.appendChild(row);
    scrollToBottom();

    return row;
}

function scrollToBottom() {
    // Small delay to let images/DOM render
    setTimeout(() => {
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }, 50);
}

// --- Input Handling ---
input.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    if (this.scrollHeight > 200) this.style.overflowY = 'auto';
    else this.style.overflowY = 'hidden';

    if (this.value.trim().length > 0) {
        sendBtn.classList.add('active');
        sendBtn.removeAttribute('disabled');
    } else {
        sendBtn.classList.remove('active');
        sendBtn.setAttribute('disabled', 'true');
    }
});

input.addEventListener('keydown', (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

sendBtn.addEventListener('click', sendMessage);

function sendMessage() {
    const text = input.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    createMessageRow(text, 'user');
    ws.send(JSON.stringify({ action: "chat", message: text, chat_id: chatId }));

    input.value = "";
    input.style.height = 'auto';
    sendBtn.classList.remove('active');
    sendBtn.setAttribute('disabled', 'true');
}

newChatBtn.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "clear", chat_id: chatId }));
    }
});

// --- Upload Handling ---
attachBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    createMessageRow(`[Uploading ${file.name}...]`, 'assistant');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${restUrl}/upload`, { method: 'POST', body: formData });
        const data = await res.json();
        if (data.filepath) {
            const fileRef = `[File: ${data.filepath}]`;
            input.value += fileRef;
            input.dispatchEvent(new Event('input')); // trigger resize and button active state
            createMessageRow(`File uploaded. You can now send your message.`, 'assistant');
        } else {
            createMessageRow(`Upload failed: ${data.error}`, 'assistant');
        }
    } catch (err) {
        createMessageRow(`Upload error: ${err.message}`, 'assistant');
    }

    fileInput.value = ""; // reset
});