const sendBtn = document.getElementById("send-btn");
const userInput = document.getElementById("user-input");
const chatBox = document.getElementById("chat-box");
const uploadBtn = document.getElementById("upload-btn");
const pdfUpload = document.getElementById("pdf-upload");
const uploadStatus = document.getElementById("upload-status");
const uploadDropzone = document.getElementById("upload-dropzone");
const fileNameDisplay = document.getElementById("file-name-display");
const clearBtn = document.getElementById("clear-btn");
const newChatBtn = document.getElementById("new-chat-btn");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");
const mobileSidebarToggle = document.getElementById("mobile-sidebar-toggle");

const EMPTY_STATE_HTML = `
<div class="empty-state" id="empty-state">
    <div class="empty-icon">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
        </svg>
    </div>
    <h2>How can I help you study?</h2>
    <p>Upload your notes, then ask a question below.</p>
    <div class="suggestion-row">
        <button class="suggestion-chip" data-text="Summarize the key points of my notes">Summarize my notes</button>
        <button class="suggestion-chip" data-text="Explain the main concept in simple terms">Explain a concept</button>
        <button class="suggestion-chip" data-text="Quiz me on this topic">Quiz me</button>
    </div>
</div>`;

function attachSuggestionListeners() {
    document.querySelectorAll(".suggestion-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            userInput.value = chip.dataset.text;
            userInput.focus();
        });
    });
}

// Render any server-rendered bot messages as markdown on page load
window.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".message.bot").forEach((el) => {
        const raw = el.textContent;
        el.innerHTML = marked.parse(raw);
    });
    attachSuggestionListeners();
    chatBox.scrollTop = chatBox.scrollHeight;
});

sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
        sendMessage();
    }
});

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    const emptyState = document.getElementById("empty-state");
    if (emptyState) emptyState.remove();

    appendMessage("user", message);
    userInput.value = "";

    const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message })
    });

    const data = await response.json();
    appendMessage("bot", data.reply);
}

function appendMessage(sender, text) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", sender);
    if (sender === "bot") {
        msgDiv.innerHTML = marked.parse(text);
    } else {
        msgDiv.textContent = text;
    }
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ---------- Upload ----------

pdfUpload.addEventListener("change", () => {
    if (pdfUpload.files.length > 0) {
        fileNameDisplay.textContent = pdfUpload.files[0].name;
    } else {
        fileNameDisplay.textContent = "Choose a PDF";
    }
});

uploadDropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadDropzone.classList.add("dragover");
});

uploadDropzone.addEventListener("dragleave", () => {
    uploadDropzone.classList.remove("dragover");
});

uploadDropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadDropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
        pdfUpload.files = e.dataTransfer.files;
        pdfUpload.dispatchEvent(new Event("change"));
    }
});

uploadBtn.addEventListener("click", async () => {
    const file = pdfUpload.files[0];
    if (!file) {
        uploadStatus.textContent = "Please choose a PDF first.";
        uploadStatus.className = "upload-status-text error";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    uploadBtn.disabled = true;
    uploadStatus.textContent = "Uploading...";
    uploadStatus.className = "upload-status-text";

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        uploadStatus.textContent = data.message;
        uploadStatus.className = "upload-status-text success";
    } catch (err) {
        uploadStatus.textContent = "Upload failed. Try again.";
        uploadStatus.className = "upload-status-text error";
    }

    uploadBtn.disabled = false;
});

// ---------- Clear / New Chat ----------

async function clearChat() {
    const confirmed = confirm("Start a new chat? This clears history and uploaded notes.");
    if (!confirmed) return;

    const response = await fetch("/clear", { method: "POST" });
    if (response.ok) {
        chatBox.innerHTML = EMPTY_STATE_HTML;
        attachSuggestionListeners();
        fileNameDisplay.textContent = "Choose a PDF";
        uploadStatus.textContent = "";
    }
}

clearBtn.addEventListener("click", clearChat);
newChatBtn.addEventListener("click", clearChat);

// ---------- Sidebar toggle ----------

sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
});

mobileSidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("mobile-open");
});