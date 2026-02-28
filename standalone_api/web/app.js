
let authToken = localStorage.getItem('oldClientToken');
if (!authToken) {
    const isLogin = confirm("Jarvis API now requires authentication. Click OK to login, or Cancel to register.");
    const user = prompt("Username:");
    const pass = prompt("Password:");

    if (user && pass) {
        const endpoint = isLogin ? '/auth/login' : '/auth/register';
        fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: user, password: pass})
        }).then(r => r.json()).then(data => {
            if (data.token) {
                localStorage.setItem('oldClientToken', data.token);
                if (!data.has_access) {
                    const code = prompt("Beta access code required:");
                    fetch('/auth/link_code', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'Authorization': `Bearer ${data.token}`},
                        body: JSON.stringify({code})
                    }).then(r => r.json()).then(d => {
                         if(d.error) alert(d.error); else window.location.reload();
                    });
                } else {
                    window.location.reload();
                }
            } else {
                alert(data.error || data.message);
                if (!isLogin) window.location.reload(); // Reload to login after register
            }
        });
    }
}

let ws;
let isRecording = false;
let chatId = localStorage.getItem('chatId') || `web_${Math.random().toString(36).substr(2, 9)}`;
localStorage.setItem('chatId', chatId);

// DOM Elements
const msgArea = document.getElementById("messages-area");
const input = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const attachBtn = document.getElementById("attach-btn");
const micBtn = document.getElementById("mic-btn");
const fileInput = document.getElementById("file-input");

function initWS() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws?token=${authToken}`);

    ws.onopen = () => {
        console.log("Connected to JarvisClaw API");
    };

    ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === 'agent_state') {
            handleAgentState(payload.data);
        } else if (payload.type === 'error') {
            addMessage(payload.message, 'tool');
        } else if (payload.type === 'bot_action') {
            handleBotAction(payload);
        }
    };

    ws.onclose = () => {
        setTimeout(initWS, 3000);
    };
}

let currentThinking = null;
let currentFinalMsg = null;

function stopThinking() {
    if (currentThinking) {
        currentThinking.remove();
        currentThinking = null;
    }
}

function startThinking(text) {
    if (!currentThinking) {
        currentThinking = document.createElement("div");
        currentThinking.className = "message assistant thinking-indicator";
        currentThinking.innerHTML = `<span class="spinner"></span> <span class="text">${text}</span>`;
        msgArea.appendChild(currentThinking);
    } else {
        currentThinking.querySelector('.text').textContent = text;
    }
    scrollToBottom();
}

function handleBotAction(payload) {
    if (payload.chat_id !== chatId) return;

    if (payload.action === "clear") {
        msgArea.innerHTML = "";
    } else if (payload.action === "send_message") {
        addMessage(payload.text, 'assistant');
    } else if (payload.action === "send_document") {
        const msg = document.createElement("div");
        msg.className = `message assistant`;
        msg.innerHTML = `📎 <a href="/download/${encodeURIComponent(payload.filename)}" target="_blank" style="color:var(--accent-blue)">${payload.filename}</a>`;
        msgArea.appendChild(msg);
        scrollToBottom();
    } else if (payload.action === "send_photo") {
        const msg = document.createElement("div");
        msg.className = `message assistant`;
        msg.innerHTML = `<img src="/download/${encodeURIComponent(payload.filename)}" style="max-width: 100%; border-radius: 8px;">`;
        if (payload.caption) {
            msg.innerHTML += `<div style="margin-top:4px">${payload.caption}</div>`;
        }
        msgArea.appendChild(msg);
        scrollToBottom();
    } else if (payload.action === "send_video") {
        const msg = document.createElement("div");
        msg.className = `message assistant`;
        msg.innerHTML = `<video controls src="/download/${encodeURIComponent(payload.filename)}" style="max-width: 100%; border-radius: 8px;"></video>`;
        if (payload.caption) {
            msg.innerHTML += `<div style="margin-top:4px">${payload.caption}</div>`;
        }
        msgArea.appendChild(msg);
        scrollToBottom();
    } else if (payload.action === "send_audio" || payload.action === "send_voice") {
        const msg = document.createElement("div");
        msg.className = `message assistant`;
        msg.innerHTML = `<audio controls src="/download/${encodeURIComponent(payload.filename)}" style="max-width: 100%;"></audio>`;
        if (payload.caption) {
            msg.innerHTML += `<div style="margin-top:4px">${payload.caption}</div>`;
        }
        msgArea.appendChild(msg);
        scrollToBottom();
    } else if (payload.action === "send_file") {
        const msg = document.createElement("div");
        msg.className = `message assistant`;
        msg.innerHTML = `📎 <a href="/download/${encodeURIComponent(payload.filename)}" target="_blank" style="color:var(--accent-blue)">${payload.filename}</a>`;
        if (payload.caption) {
            msg.innerHTML += `<div style="margin-top:4px">${payload.caption}</div>`;
        }
        msgArea.appendChild(msg);
        scrollToBottom();
    }
}

function handleAgentState(data) {
    const { status, message, content, tool, args, result } = data;

    if (status === 'thinking') {
        startThinking(message || "Анализирую...");
    }
    else if (status === 'thinking_stream') {
        startThinking(content.substring(0, 50) + "...");
    }
    else if (status === 'tool_use') {
        stopThinking();
        currentFinalMsg = null;
        addMessage(`[Tool] ${tool}(${JSON.stringify(args || {})})`, 'tool');
        startThinking(`Ожидание ответа от инструмента ${tool}...`);
    }
    else if (status === 'observation') {
        stopThinking();
    }
    else if (status === 'final_stream') {
        stopThinking();
        if (!currentFinalMsg) {
            currentFinalMsg = addMessage(content, 'assistant');
        } else {
            currentFinalMsg.textContent += content;
            scrollToBottom();
        }
    }
    else if (status === 'final') {
        stopThinking();
        if (!currentFinalMsg && content) {
            addMessage(content, 'assistant');
        }
        currentFinalMsg = null;
    }
    else if (status === 'error') {
        stopThinking();
        addMessage(`[Error] ${message}`, 'tool');
    }
}

function addMessage(text, role) {
    const msg = document.createElement("div");
    msg.className = `message ${role}`;
    msg.textContent = text;
    msgArea.appendChild(msg);
    scrollToBottom();
    return msg;
}

function scrollToBottom() {
    msgArea.scrollTop = msgArea.scrollHeight;
}

function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, 'user');
    ws.send(JSON.stringify({ action: "chat", message: text, chat_id: chatId }));
    input.value = "";
    input.style.height = 'auto'; // Reset height
}

// Events
sendBtn.addEventListener("click", sendMessage);
input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

input.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

const newChatBtn = document.getElementById("new-chat-btn");
if (newChatBtn) {
    newChatBtn.addEventListener("click", () => {
        ws.send(JSON.stringify({ action: "clear", chat_id: chatId }));
    });
}

// Initialization
fetchHistory();
initWS();

async function fetchHistory() {
    try {
        const res = await fetch(`/history?chat_id=${chatId}`);
        const data = await res.json();
        data.history.forEach(m => {
            if (m.role !== 'system') {
                addMessage(m.content, m.role);
            }
        });
    } catch (e) {
        console.error("History fetch error:", e);
    }
}

// Attachment Handling
attachBtn.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    addMessage(`[Uploading...] ${file.name}`, 'tool');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/upload', {
            method: 'POST',
            headers: {'Authorization': `Bearer ${authToken}`},
            body: formData
        });
        const data = await res.json();
        if (data.filepath) {
            const fileRef = `[File: ${data.filepath}]`;
            input.value += fileRef;
            addMessage(`File attached: ${file.name}`, 'tool');
        } else {
            addMessage(`Upload failed: ${data.error}`, 'error');
        }
    } catch (err) {
        addMessage(`Upload error: ${err.message}`, 'error');
    }
});

// Voice Recording Mock
let mediaRecorder;
let audioChunks = [];

micBtn.addEventListener('click', async () => {
    if (isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        micBtn.classList.remove('recording');
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = e => {
            audioChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            audioChunks = [];
            const formData = new FormData();
            formData.append('file', audioBlob, 'voice.wav');

            addMessage(`[Processing voice message...]`, 'tool');

            try {
                const res = await fetch('/upload', {
            method: 'POST',
            headers: {'Authorization': `Bearer ${authToken}`},
            body: formData
        });
                const data = await res.json();
                if (data.filepath) {
                    const fileRef = `[Voice: ${data.filepath}]`;
                    addMessage(`Voice recorded.`, 'tool');
                    ws.send(JSON.stringify({ action: "chat", message: fileRef, chat_id: chatId }));
                }
            } catch (err) {
                console.error(err);
            }
        };

        audioChunks = [];
        mediaRecorder.start();
        isRecording = true;
        micBtn.classList.add('recording');
    } catch (err) {
        addMessage(`Microphone error: ${err.message}`, 'error');
    }
});
