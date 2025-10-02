// static/js/websocket.js - WebSocket integration for real-time features
class WebSocketManager {
    constructor(userId, wsUrl = null) {
        this.userId = userId;
        this.wsUrl = wsUrl || this.getWebSocketURL();
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 5000;
        this.heartbeatInterval = 30000;
        this.heartbeatTimer = null;
        
        this.connect();
    }

    getWebSocketURL() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/ws/user/${this.userId}/`;
    }

    connect() {
        try {
            this.socket = new WebSocket(this.wsUrl);
            this.setupEventHandlers();
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.handleReconnect();
        }
    }

    setupEventHandlers() {
        this.socket.onopen = (event) => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.startHeartbeat();
            this.onConnect(event);
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        this.socket.onclose = (event) => {
            console.log('WebSocket disconnected:', event.code, event.reason);
            this.stopHeartbeat();
            this.onDisconnect(event);
            
            if (!event.wasClean) {
                this.handleReconnect();
            }
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.onError(error);
        };
    }

    handleMessage(data) {
        switch (data.type) {
            case 'user_status':
                this.handleUserStatus(data);
                break;
            case 'notification':
                this.handleNotification(data);
                break;
            case 'chat_message':
                this.handleChatMessage(data);
                break;
            case 'typing_indicator':
                this.handleTypingIndicator(data);
                break;
            case 'user_joined':
            case 'user_left':
                this.handleUserPresence(data);
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }

    handleUserStatus(data) {
        // Update user online status indicators
        const userElements = document.querySelectorAll(`[data-user-id="${data.user_id}"]`);
        userElements.forEach(element => {
            const indicator = element.querySelector('.online-indicator');
            if (indicator) {
                if (data.is_online) {
                    indicator.classList.remove('offline-indicator');
                    indicator.classList.add('online-indicator');
                } else {
                    indicator.classList.remove('online-indicator');
                    indicator.classList.add('offline-indicator');
                }
            }
        });
    }

    handleNotification(data) {
        // Show browser notification if permitted
        if (Notification.permission === 'granted') {
            new Notification(data.title, {
                body: data.message,
                icon: '/static/img/icon-192x192.png'
            });
        }

        // Show toast notification
        if (window.accountsManager) {
            window.accountsManager.showToast(data.title, data.message, data.level || 'info');
        }

        // Update notification count
        this.updateNotificationCount(data.unread_count);
    }

    handleChatMessage(data) {
        // Emit custom event for chat components
        const event = new CustomEvent('chatMessage', { detail: data });
        document.dispatchEvent(event);
    }

    handleTypingIndicator(data) {
        // Emit custom event for typing indicators
        const event = new CustomEvent('typingIndicator', { detail: data });
        document.dispatchEvent(event);
    }

    handleUserPresence(data) {
        // Update user presence in UI
        const event = new CustomEvent('userPresence', { detail: data });
        document.dispatchEvent(event);
    }

    updateNotificationCount(count) {
        const badge = document.getElementById('notification-count');
        if (badge) {
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.style.display = 'inline';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    sendMessage(type, data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: type,
                ...data
            }));
        } else {
            console.warn('WebSocket not connected, message not sent:', type, data);
        }
    }

    sendTypingIndicator(isTyping, roomId = null) {
        this.sendMessage('typing', {
            is_typing: isTyping,
            room_id: roomId
        });
    }

    sendStatusUpdate(status) {
        this.sendMessage('status_update', {
            status: status
        });
    }

    startHeartbeat() {
        this.heartbeatTimer = setInterval(() => {
            this.sendMessage('heartbeat', {
                timestamp: Date.now()
            });
        }, this.heartbeatInterval);
    }

    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectInterval * this.reconnectAttempts);
        } else {
            console.error('Max reconnection attempts reached');
            this.onMaxReconnectAttemptsReached();
        }
    }

    disconnect() {
        this.stopHeartbeat();
        if (this.socket) {
            this.socket.close();
        }
    }

    // Event handlers - can be overridden
    onConnect(event) {
        // Override in implementations
    }

    onDisconnect(event) {
        // Override in implementations
    }

    onError(error) {
        // Override in implementations
    }

    onMaxReconnectAttemptsReached() {
        if (window.accountsManager) {
            window.accountsManager.showToast(
                'Connection Lost', 
                'Unable to reconnect to server. Please refresh the page.', 
                'error'
            );
        }
    }
}

// Export WebSocketManager for global use
if (typeof window !== 'undefined') {
    window.WebSocketManager = WebSocketManager;
}

// Auto-initialize WebSocket for authenticated users
document.addEventListener('DOMContentLoaded', () => {
    const userMeta = document.querySelector('meta[name="user-id"]');
    if (userMeta) {
        const userId = userMeta.content;
        window.wsManager = new WebSocketManager(userId);
        
        // Setup typing indicators for chat inputs (only if Utils is available)
        if (window.Utils && window.Utils.debounce) {
            document.addEventListener('input', window.Utils.debounce((e) => {
                if (e.target.classList.contains('chat-input')) {
                    const roomId = e.target.dataset.roomId;
                    window.wsManager.sendTypingIndicator(true, roomId);
                    
                    // Stop typing after 3 seconds of inactivity
                    setTimeout(() => {
                        window.wsManager.sendTypingIndicator(false, roomId);
                    }, 3000);
                }
            }, 300));
        }
    }
});