// Chat Home Page Manager
class ChatHomeManager {
    constructor() {
        this.selectedMembers = [];
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.setupSearch();
    }
    
    setupEventListeners() {
        // Create chat button
        const createBtn = document.getElementById('create-chat-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => this.handleCreateChat());
        }
        
        // Room search
        const searchInput = document.getElementById('search-rooms');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.filterRooms(e.target.value));
        }
    }
    
    setupSearch() {
        // Direct message user search
        const dmSearch = document.getElementById('user-search-dm');
        if (dmSearch) {
            dmSearch.addEventListener('input', (e) => {
                this.searchUsers(e.target.value, 'dm');
            });
        }
        
        // Group chat user search
        const groupSearch = document.getElementById('user-search-group');
        if (groupSearch) {
            groupSearch.addEventListener('input', (e) => {
                this.searchUsers(e.target.value, 'group');
            });
        }
    }
    
    async searchUsers(query, type) {
        if (query.length < 2) {
            this.clearSearchResults(type);
            return;
        }
        
        try {
            const response = await fetch(`/chat/api/users/search/?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            this.displaySearchResults(data.users, type);
        } catch (error) {
            console.error('User search error:', error);
        }
    }
    
    displaySearchResults(users, type) {
        const containerId = type === 'dm' ? 'user-search-results-dm' : 'user-search-results-group';
        const container = document.getElementById(containerId);
        
        if (!container) return;
        
        if (users.length === 0) {
            container.innerHTML = '<div class="text-muted p-2">No users found</div>';
            return;
        }
        
        const html = users.map(user => `
            <div class="border rounded p-2 mb-2 user-result" data-user-id="${user.id}" 
                 style="cursor: pointer;">
                <div class="d-flex align-items-center">
                    <img src="${user.avatar || '/static/img/default-avatar.png'}" 
                         class="rounded-circle me-2" width="40" height="40" alt="${user.display_name}">
                    <div>
                        <strong>${user.display_name}</strong>
                        <br><small class="text-muted">@${user.username}</small>
                    </div>
                    ${user.is_online ? '<span class="badge bg-success ms-auto">Online</span>' : ''}
                </div>
            </div>
        `).join('');
        
        container.innerHTML = html;
        
        // Add click handlers
        container.querySelectorAll('.user-result').forEach(el => {
            el.addEventListener('click', () => {
                if (type === 'dm') {
                    this.selectUserForDM(el.dataset.userId);
                } else {
                    this.addMemberToGroup(el.dataset.userId, el.textContent.trim());
                }
            });
        });
    }
    
    selectUserForDM(userId) {
        document.getElementById('selected-user-dm').value = userId;
        document.getElementById('user-search-results-dm').innerHTML = 
            '<div class="alert alert-success">User selected! Click Create to start chatting.</div>';
    }
    
    addMemberToGroup(userId, userName) {
        if (this.selectedMembers.includes(userId)) return;
        
        this.selectedMembers.push(userId);
        this.updateSelectedMembers();
    }
    
    updateSelectedMembers() {
        const container = document.getElementById('selected-members');
        const html = this.selectedMembers.map((id, index) => `
            <span class="badge bg-primary me-2 mb-2">
                Member ${index + 1}
                <i class="fas fa-times ms-1" style="cursor: pointer;" 
                   onclick="window.chatHome.removeMember('${id}')"></i>
            </span>
        `).join('');
        
        container.innerHTML = html || '<small class="text-muted">No members selected</small>';
    }
    
    removeMember(userId) {
        this.selectedMembers = this.selectedMembers.filter(id => id !== userId);
        this.updateSelectedMembers();
    }
    
    clearSearchResults(type) {
        const containerId = type === 'dm' ? 'user-search-results-dm' : 'user-search-results-group';
        const container = document.getElementById(containerId);
        if (container) container.innerHTML = '';
    }
    
    async handleCreateChat() {
        const activeTab = document.querySelector('.tab-pane.active').id;
        
        if (activeTab === 'direct-tab') {
            await this.createDirectMessage();
        } else {
            await this.createGroupChat();
        }
    }
    
    async createDirectMessage() {
        const userId = document.getElementById('selected-user-dm').value;
        
        if (!userId) {
            alert('Please select a user');
            return;
        }
        
        const formData = new FormData();
        formData.append('room_type', 'direct');
        formData.append('members[]', userId);
        
        await this.createRoom(formData);
    }
    
    async createGroupChat() {
        const form = document.getElementById('create-group-form');
        const formData = new FormData(form);
        
        if (!formData.get('name')) {
            alert('Please enter a group name');
            return;
        }
        
        if (this.selectedMembers.length === 0) {
            alert('Please add at least one member');
            return;
        }
        
        this.selectedMembers.forEach(id => formData.append('members[]', id));
        
        await this.createRoom(formData);
    }
    
    async createRoom(formData) {
        try {
            const response = await fetch('/chat/api/room/create/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                window.location.href = data.redirect;
            } else {
                alert(data.error || 'Failed to create chat');
            }
        } catch (error) {
            console.error('Create chat error:', error);
            alert('Failed to create chat');
        }
    }
    
    filterRooms(query) {
        query = query.toLowerCase();
        const rooms = document.querySelectorAll('.chat-room-item');
        
        rooms.forEach(room => {
            const text = room.textContent.toLowerCase();
            room.style.display = text.includes(query) ? 'block' : 'none';
        });
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    window.chatHome = new ChatHomeManager();
});