// Chat Room WebSocket Manager
class ChatRoomManager {
    constructor(roomId, userId, userName) {
        this.roomId = roomId;
        this.userId = userId;
        this.userName = userName;
        this.socket = null;
        this.typingTimeout = null;
        this.isTyping = false;
        this.replyTo = null;
        
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.scrollToBottom();
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat/${this.roomId}/`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
            console.log('WebSocket connected');
        };
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.socket.onclose = () => {
            console.log('WebSocket disconnected');
            setTimeout(() => this.connectWebSocket(), 3000);
        };
        
        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'chat_message':
                this.addMessage(data.message);
                break;
            case 'typing_indicator':
                this.updateTypingIndicator(data);
                break;
            case 'user_presence':
                this.updateUserPresence(data);
                break;
            case 'message_reaction':
                this.updateReaction(data);
                break;
        }
    }
    
    setupEventListeners() {
        // Message form
        const form = document.getElementById('message-form');
        const input = document.getElementById('message-input');
        
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });
        
        // Typing indicator
        input.addEventListener('input', () => {
            this.handleTyping();
        });
        
        // Reply functionality
        document.addEventListener('click', (e) => {
            if (e.target.closest('[data-action="reply"]')) {
                this.setReplyTo(e.target.closest('.message-item'));
            }
        });
        
        document.getElementById('cancel-reply')?.addEventListener('click', () => {
            this.cancelReply();
        });
        
        // Emoji picker
        document.getElementById('emoji-btn').addEventListener('click', () => {
            document.getElementById('emoji-picker').classList.toggle('show');
        });
        
        document.querySelectorAll('.emoji-option').forEach(emoji => {
            emoji.addEventListener('click', (e) => {
                input.value += e.target.textContent;
                input.focus();
                document.getElementById('emoji-picker').classList.remove('show');
            });
        });
        
        // File upload
        document.getElementById('file-btn').addEventListener('click', () => {
            document.getElementById('file-input').click();
        });
        
        document.getElementById('file-input').addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.uploadFile(e.target.files[0]);
            }
        });
    }
    
    sendMessage() {
        const input = document.getElementById('message-input');
        const content = input.value.trim();
        
        if (!content) return;
        
        const messageData = {
            type: 'chat_message',
            content: content,
            reply_to: this.replyTo
        };
        
        this.socket.send(JSON.stringify(messageData));
        
        input.value = '';
        this.cancelReply();
        this.stopTyping();
    }
    
    addMessage(message) {
        const messagesContainer = document.getElementById('chat-messages');
        const messageElement = this.createMessageElement(message);
        messagesContainer.appendChild(messageElement);
        this.scrollToBottom();
    }
    
    createMessageElement(message) {
        const div = document.createElement('div');
        div.className = `message-item ${message.sender.id === this.userId ? 'own-message' : ''}`;
        div.dataset.messageId = message.id;
        
        const isOwn = message.sender.id === this.userId;
        
        div.innerHTML = `
            ${!isOwn ? `<img src="${message.sender.avatar || '/static/img/default-avatar.png'}" class="message-avatar" alt="${message.sender.name}">` : ''}
            <div>
                ${message.reply_to ? `
                    <div class="reply-preview">
                        <small><strong>${message.reply_to.sender}</strong></small><br>
                        <small>${message.reply_to.content}</small>
                    </div>
                ` : ''}
                <div class="message-content">
                    ${!isOwn ? `<div class="message-sender">${message.sender.name}</div>` : ''}
                    <div class="message-text">${this.formatMessageContent(message.content)}</div>
                    <div class="message-time">${this.formatTime(message.created_at)}</div>
                </div>
            </div>
        `;
        
        return div;
    }
    
    formatMessageContent(content) {
        // Auto-link URLs
        content = content.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>');
        // Format mentions
        content = content.replace(/@(\w+)/g, '<span class="text-primary">@$1</span>');
        return content;
    }
    
    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    }
    
    handleTyping() {
        if (!this.isTyping) {
            this.isTyping = true;
            this.socket.send(JSON.stringify({
                type: 'typing',
                is_typing: true
            }));
        }
        
        clearTimeout(this.typingTimeout);
        this.typingTimeout = setTimeout(() => {
            this.stopTyping();
        }, 3000);
    }
    
    stopTyping() {
        if (this.isTyping) {
            this.isTyping = false;
            this.socket.send(JSON.stringify({
                type: 'typing',
                is_typing: false
            }));
        }
    }
    
    updateTypingIndicator(data) {
        const indicator = document.getElementById('typing-indicator');
        const usersSpan = document.getElementById('typing-users');
        
        if (data.is_typing) {
            usersSpan.textContent = data.username;
            indicator.style.display = 'block';
        } else {
            indicator.style.display = 'none';
        }
    }
    
    updateUserPresence(data) {
        // Update online status in header
        console.log(`${data.username} ${data.action}`);
    }
    
    updateReaction(data) {
        const messageEl = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (messageEl) {
            // Update reaction display
            console.log('Reaction updated:', data);
        }
    }
    
    setReplyTo(messageElement) {
        const messageId = messageElement.dataset.messageId;
        const senderName = messageElement.querySelector('.message-sender')?.textContent || 'You';
        const messageText = messageElement.querySelector('.message-text').textContent;
        
        this.replyTo = messageId;
        
        document.getElementById('reply-to-id').value = messageId;
        document.getElementById('reply-to-name').textContent = senderName;
        document.getElementById('reply-to-text').textContent = messageText.substring(0, 50);
        document.getElementById('reply-preview').style.display = 'block';
        document.getElementById('message-input').focus();
    }
    
    cancelReply() {
        this.replyTo = null;
        document.getElementById('reply-to-id').value = '';
        document.getElementById('reply-preview').style.display = 'none';
    }
    
    scrollToBottom() {
        const container = document.getElementById('chat-messages');
        container.scrollTop = container.scrollHeight;
    }
    
    uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('content', `Shared ${file.name}`);
        
        fetch(`/chat/api/room/${this.roomId}/send/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        }).then(response => response.json())
          .then(data => {
              if (data.success) {
                  console.log('File uploaded');
              }
          });
    }
}

// Initialize chat room
document.addEventListener('DOMContentLoaded', () => {
    if (typeof roomId !== 'undefined') {
        window.chatRoom = new ChatRoomManager(roomId, userId, userName);
    }
});