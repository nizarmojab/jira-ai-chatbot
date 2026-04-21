/**
 * JIRA AI CHATBOT - CLIENT APPLICATION
 * Capgemini Engineering - Infotainment & Connectivity
 */

// ============================================================================
// CONFIGURATION & STATE
// ============================================================================
const CONFIG = {
    API: {
        CHAT: '/chat',
        HEALTH: '/health',
    },
    HEALTH_CHECK_INTERVAL: 30000, // 30 seconds
    AUTO_SCROLL_THRESHOLD: 100,
};

const STATE = {
    messages: [],
    isTyping: false,
    isConnected: false,
    currentChatId: null,
    chats: [],
};

// ============================================================================
// DOM ELEMENTS
// ============================================================================
const DOM = {
    // Containers
    messagesContainer: document.getElementById('messagesContainer'),
    welcomeScreen: document.getElementById('welcomeScreen'),
    typingIndicator: document.getElementById('typingIndicator'),
    toastContainer: document.getElementById('toastContainer'),
    sidebar: document.querySelector('.sidebar'),

    // Input
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    navSearch: document.getElementById('navSearch'),

    // Buttons
    newChatBtn: document.getElementById('newChatBtn'),
    exportChatBtn: document.getElementById('exportChatBtn'),
    sidebarToggle: document.getElementById('sidebarToggle'),
    commandBtns: document.querySelectorAll('.command-btn'),
    exampleCards: document.querySelectorAll('.example-card'),
    chatHistoryList: document.getElementById('chatHistoryList'),

    // Status
    statusDot: document.getElementById('statusDot'),
    projectName: document.getElementById('projectName'),
    connectionIcon: document.getElementById('connectionIcon'),
    connectionText: document.getElementById('connectionText'),
    currentTime: document.getElementById('currentTime'),
};

// ============================================================================
// INITIALIZATION
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('🤖 Jira AI Chatbot initialized with Chat History');

    // Load chat history
    loadChatHistory();
    initializeChatHistory();

    initializeEventListeners();
    checkHealth();
    setInterval(checkHealth, CONFIG.HEALTH_CHECK_INTERVAL);

    // Update clock
    updateClock();
    setInterval(updateClock, 1000);

    // Focus input
    DOM.messageInput.focus();
});

// ============================================================================
// EVENT LISTENERS
// ============================================================================
function initializeEventListeners() {
    // Send message
    DOM.sendBtn.addEventListener('click', () => sendMessage());

    // Input handling
    DOM.messageInput.addEventListener('keydown', handleInputKeydown);
    DOM.messageInput.addEventListener('input', handleInputResize);

    // Command buttons
    DOM.commandBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const command = btn.getAttribute('data-command');
            sendMessage(command);
        });
    });

    // Example cards
    DOM.exampleCards.forEach(card => {
        card.addEventListener('click', () => {
            const query = card.getAttribute('data-query');
            sendMessage(query);
        });
    });

    // Action buttons
    DOM.newChatBtn?.addEventListener('click', createNewChat);
    DOM.exportChatBtn?.addEventListener('click', exportChat);
    DOM.sidebarToggle?.addEventListener('click', toggleSidebar);

    // Nav search
    DOM.navSearch?.addEventListener('keydown', handleNavSearch);
}

// ============================================================================
// SIDEBAR TOGGLE
// ============================================================================
function toggleSidebar() {
    if (DOM.sidebar) {
        DOM.sidebar.classList.toggle('open');
    }
}

// ============================================================================
// NAV SEARCH
// ============================================================================
function handleNavSearch(event) {
    if (event.key === 'Enter') {
        const query = DOM.navSearch.value.trim();
        if (query) {
            sendMessage(query);
            DOM.navSearch.value = '';
        }
    }
}

// ============================================================================
// CLOCK UPDATE
// ============================================================================
function updateClock() {
    if (!DOM.currentTime) return;

    const now = new Date();
    const time = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
    });
    DOM.currentTime.textContent = time;
}

// ============================================================================
// INPUT HANDLING
// ============================================================================
function handleInputKeydown(event) {
    // Enter to send (Shift+Enter for new line)
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function handleInputResize() {
    const input = DOM.messageInput;
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
}

// ============================================================================
// MESSAGE SENDING
// ============================================================================
async function sendMessage(text = null) {
    const message = text || DOM.messageInput.value.trim();

    if (!message || STATE.isTyping) return;

    // Hide welcome screen
    if (DOM.welcomeScreen) {
        DOM.welcomeScreen.style.display = 'none';
    }

    // Add user message
    addMessage('user', message);

    // Clear input
    DOM.messageInput.value = '';
    DOM.messageInput.style.height = 'auto';

    // Show typing indicator
    showTyping();

    try {
        const response = await fetch(CONFIG.API.CHAT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });

        hideTyping();

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        // Add bot response
        addMessage('bot', data.response, {
            tickets: data.tickets || [],
            jql: data.jql,
            count: data.count,
        });

    } catch (error) {
        hideTyping();
        console.error('Send message error:', error);
        addMessage('bot', `❌ Connection error: ${error.message}`, { error: true });
        showToast('Failed to connect to server', 'error');
    }

    scrollToBottom();
}

// ============================================================================
// MESSAGE RENDERING
// ============================================================================
function addMessage(role, text, options = {}) {
    const message = {
        role,
        text,
        timestamp: new Date(),
        ...options,
    };

    STATE.messages.push(message);

    const messageEl = createMessageElement(message);
    DOM.messagesContainer.appendChild(messageEl);

    scrollToBottom();

    // Auto-save chat history after each message
    if (STATE.currentChatId) {
        saveCurrentChat();
        renderChatHistory();
    }
}

function createMessageElement(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${message.role}`;

    const avatar = message.role === 'bot' ? '<i class="fas fa-robot"></i>' : '<i class="fas fa-user"></i>';

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="message-text">${formatText(message.text)}</div>
            </div>
            ${message.tickets && message.tickets.length > 0 ? createTicketsHTML(message.tickets) : ''}
            ${message.jql ? createJQLInfo(message.jql, message.count) : ''}
            <div class="message-meta">
                <span>${formatTime(message.timestamp)}</span>
            </div>
            ${message.role === 'bot' ? createMessageActions() : ''}
        </div>
    `;

    // Add ticket click handlers
    if (message.tickets && message.tickets.length > 0) {
        setTimeout(() => {
            messageDiv.querySelectorAll('.ticket-card').forEach((card, index) => {
                card.addEventListener('click', () => {
                    openJiraTicket(message.tickets[index].key);
                });
            });
        }, 0);
    }

    // Add copy handler
    const copyBtn = messageDiv.querySelector('.copy-btn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => copyMessage(message.text, copyBtn));
    }

    return messageDiv;
}

function createTicketsHTML(tickets) {
    let html = '<div class="tickets-grid">';

    tickets.forEach(ticket => {
        const statusClass = ticket.status.toLowerCase().replace(/\s+/g, '');
        const priorityClass = ticket.priority ? ticket.priority.toLowerCase() : '';

        html += `
            <div class="ticket-card" data-key="${ticket.key}">
                <div class="ticket-header">
                    <span class="ticket-key">${ticket.key}</span>
                    <span class="status-badge ${statusClass}">${ticket.status}</span>
                    ${ticket.priority ? `<span class="priority-badge ${priorityClass}">⚡ ${ticket.priority}</span>` : ''}
                </div>
                <div class="ticket-summary">${ticket.summary}</div>
                <div class="ticket-meta">
                    <span><i class="fas fa-user"></i> ${ticket.assignee || 'Unassigned'}</span>
                </div>
            </div>
        `;
    });

    html += '</div>';
    return html;
}

function createJQLInfo(jql, count) {
    return `
        <div class="message-meta" style="margin-top: 12px; padding: 8px 12px; background: #F4F5F7; border-left: 3px solid var(--primary-blue); border-radius: 3px; font-family: monospace; font-size: 12px;">
            <i class="fas fa-code"></i> JQL: ${jql}${count ? ` (${count} results)` : ''}
        </div>
    `;
}

function createMessageActions() {
    return `
        <div class="message-actions">
            <button class="message-action-btn copy-btn">
                <i class="fas fa-copy"></i> Copy
            </button>
        </div>
    `;
}

function formatText(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

function formatTime(date) {
    // Convert string to Date if needed
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return dateObj.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
    });
}

// ============================================================================
// TYPING INDICATOR
// ============================================================================
function showTyping() {
    STATE.isTyping = true;
    DOM.typingIndicator.classList.add('active');
    scrollToBottom();
}

function hideTyping() {
    STATE.isTyping = false;
    DOM.typingIndicator.classList.remove('active');
}

// ============================================================================
// HEALTH CHECK
// ============================================================================
async function checkHealth() {
    try {
        const response = await fetch(CONFIG.API.HEALTH);
        const data = await response.json();

        STATE.isConnected = data.jira_connected;

        updateConnectionStatus(data.jira_connected, data.project);

    } catch (error) {
        console.error('Health check failed:', error);
        updateConnectionStatus(false);
    }
}

function updateConnectionStatus(connected, projectName = null) {
    if (connected) {
        DOM.statusDot?.style.setProperty('background', '#36B37E');
        DOM.connectionIcon?.style.setProperty('color', 'var(--success)');
        if (DOM.connectionText) DOM.connectionText.textContent = 'Connected';
        if (projectName && DOM.projectName) {
            DOM.projectName.textContent = projectName;
        }
    } else {
        DOM.statusDot?.style.setProperty('background', 'var(--danger)');
        DOM.connectionIcon?.style.setProperty('color', 'var(--danger)');
        if (DOM.connectionText) DOM.connectionText.textContent = 'Disconnected';
        if (DOM.projectName) DOM.projectName.textContent = 'Disconnected';
    }
}

// ============================================================================
// ACTIONS
// ============================================================================
function clearChat() {
    if (!confirm('Clear the entire conversation?')) return;

    STATE.messages = [];
    DOM.messagesContainer.innerHTML = `
        <div class="welcome-screen" id="welcomeScreen" style="display: flex;">
            <div class="welcome-icon">
                <i class="fas fa-robot"></i>
            </div>
            <h1>Conversation cleared</h1>
            <p>Ask a new question to start</p>
        </div>
    `;
    DOM.welcomeScreen = document.getElementById('welcomeScreen');

    showToast('Conversation cleared', 'info');
}

function exportChat() {
    const chatText = STATE.messages
        .map(msg => `[${formatTime(msg.timestamp)}] ${msg.role.toUpperCase()}: ${msg.text}`)
        .join('\n\n');

    const blob = new Blob([chatText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jira-chat-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    showToast('Chat exported', 'success');
}

function copyMessage(text, button) {
    const plainText = text.replace(/<br>/g, '\n').replace(/<[^>]+>/g, '');

    navigator.clipboard.writeText(plainText).then(() => {
        button.innerHTML = '<i class="fas fa-check"></i> Copied';
        setTimeout(() => {
            button.innerHTML = '<i class="fas fa-copy"></i> Copy';
        }, 2000);
    });
}

function openJiraTicket(key) {
    // Try to get Jira URL from backend or use default
    const jiraBaseUrl = 'https://chatbotjira.atlassian.net';
    window.open(`${jiraBaseUrl}/browse/${key}`, '_blank');
}

// ============================================================================
// UTILITIES
// ============================================================================
function scrollToBottom() {
    const container = DOM.messagesContainer;
    const shouldScroll =
        container.scrollHeight - container.scrollTop - container.clientHeight < CONFIG.AUTO_SCROLL_THRESHOLD;

    if (shouldScroll) {
        container.scrollTo({
            top: container.scrollHeight,
            behavior: 'smooth',
        });
    }
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div style="flex: 1;">${message}</div>
    `;

    DOM.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================================================

// ============================================================================
// CHAT HISTORY MANAGEMENT
// ============================================================================

function initializeChatHistory() {
    // Always start with a new chat, but keep history in sidebar
    createNewChat(true); // Pass true to skip toast notification on startup
}

function loadChatHistory() {
    const saved = localStorage.getItem('jira_chat_history');
    if (saved) {
        try {
            STATE.chats = JSON.parse(saved);
            renderChatHistory();
        } catch (e) {
            console.error('Failed to load chat history:', e);
            STATE.chats = [];
        }
    }
}

function saveChatHistory() {
    localStorage.setItem('jira_chat_history', JSON.stringify(STATE.chats));
}

function createNewChat(silent = false) {
    // Save current chat if it exists
    if (STATE.currentChatId) {
        saveCurrentChat();
    }

    // Create new chat
    const newChat = {
        id: Date.now().toString(),
        title: 'New Chat',
        messages: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
    };

    STATE.chats.unshift(newChat);
    STATE.currentChatId = newChat.id;
    STATE.messages = [];

    saveChatHistory();
    renderChatHistory();
    clearChatDisplay();

    if (!silent) {
        showToast('New chat created', 'success');
    }
}

function loadChat(chatId) {
    // Save current chat first
    if (STATE.currentChatId) {
        saveCurrentChat();
    }

    const chat = STATE.chats.find(c => c.id === chatId);
    if (!chat) {
        console.error('Chat not found:', chatId);
        return;
    }

    console.log('Loading chat:', chatId, 'with', chat.messages?.length || 0, 'messages');

    STATE.currentChatId = chatId;
    STATE.messages = chat.messages || [];

    // Clear display
    DOM.messagesContainer.innerHTML = '';

    // If chat has messages, hide welcome screen and show messages
    if (STATE.messages.length > 0) {
        if (DOM.welcomeScreen) {
            DOM.welcomeScreen.style.display = 'none';
        }

        // Render all messages
        STATE.messages.forEach(msg => {
            const messageEl = createMessageElement(msg);
            DOM.messagesContainer.appendChild(messageEl);
        });

        scrollToBottom();
    } else {
        // No messages, show welcome screen
        if (DOM.welcomeScreen) {
            DOM.welcomeScreen.style.display = 'flex';
            DOM.messagesContainer.appendChild(DOM.welcomeScreen);
        }
    }

    renderChatHistory();
}

function saveCurrentChat() {
    if (!STATE.currentChatId) return;

    const chatIndex = STATE.chats.findIndex(c => c.id === STATE.currentChatId);
    if (chatIndex === -1) {
        console.error('Chat index not found for', STATE.currentChatId);
        return;
    }

    console.log('Saving chat:', STATE.currentChatId, 'with', STATE.messages.length, 'messages');

    // Update chat
    STATE.chats[chatIndex].messages = STATE.messages;
    STATE.chats[chatIndex].updatedAt = new Date().toISOString();

    // Auto-generate title from first message
    if (STATE.chats[chatIndex].title === 'New Chat' && STATE.messages.length > 0) {
        const firstUserMessage = STATE.messages.find(m => m.role === 'user');
        if (firstUserMessage) {
            STATE.chats[chatIndex].title = firstUserMessage.text.slice(0, 40) +
                (firstUserMessage.text.length > 40 ? '...' : '');
        }
    }

    saveChatHistory();
}

function deleteChat(chatId, event) {
    event.stopPropagation();

    if (!confirm('Delete this chat?')) return;

    STATE.chats = STATE.chats.filter(c => c.id !== chatId);

    // If deleting current chat, create a new one
    if (STATE.currentChatId === chatId) {
        STATE.currentChatId = null;
        STATE.messages = [];
        if (STATE.chats.length > 0) {
            loadChat(STATE.chats[0].id);
        } else {
            createNewChat();
        }
    }

    saveChatHistory();
    renderChatHistory();
    showToast('Chat deleted', 'info');
}

function clearChatDisplay() {
    DOM.messagesContainer.innerHTML = '';
    if (DOM.welcomeScreen) {
        DOM.welcomeScreen.style.display = 'flex';
        DOM.messagesContainer.appendChild(DOM.welcomeScreen);
    }
}

function renderChatHistory() {
    if (!DOM.chatHistoryList) return;

    if (STATE.chats.length === 0) {
        DOM.chatHistoryList.innerHTML = `
            <div class="empty-history">
                <i class="fas fa-comments"></i>
                <p>No chat history yet</p>
            </div>
        `;
        return;
    }

    DOM.chatHistoryList.innerHTML = STATE.chats.map(chat => {
        const date = new Date(chat.updatedAt);
        const timeAgo = getTimeAgo(date);
        const isActive = chat.id === STATE.currentChatId;

        return `
            <div class="chat-history-item ${isActive ? 'active' : ''}" data-chat-id="${chat.id}" onclick="loadChat('${chat.id}')">
                <div class="chat-history-icon">
                    <i class="fas fa-comments"></i>
                </div>
                <div class="chat-history-content">
                    <div class="chat-history-title">${chat.title}</div>
                    <div class="chat-history-meta">${chat.messages.length} messages • ${timeAgo}</div>
                </div>
                <button class="chat-history-delete" onclick="deleteChat('${chat.id}', event)" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
    }).join('');
}

function getTimeAgo(date) {
    // Convert string to Date if needed
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    const seconds = Math.floor((new Date() - dateObj) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    return dateObj.toLocaleDateString();
}

// Make functions globally accessible
window.loadChat = loadChat;
window.deleteChat = deleteChat;

// ============================================================================
// EXPORT
// ============================================================================
window.JiraChatbot = {
    sendMessage,
    exportChat,
    checkHealth,
    createNewChat,
    loadChat,
    deleteChat,
};
