// static/js/accounts.js
class AccountsManager {
    constructor() {
        this.init();
        this.setupEventListeners();
        this.startHeartbeat();
    }

    init() {
        // Get CSRF token for AJAX requests
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                        document.querySelector('meta[name="csrf-token"]')?.content;
        
        // Initialize tooltips and popovers
        this.initializeBootstrapComponents();
        
        // Setup real-time features
        this.setupOnlineStatus();
        this.setupNotificationHandler();
    }

    initializeBootstrapComponents() {
        // Initialize Bootstrap tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

        // Initialize Bootstrap popovers
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
    }

    setupEventListeners() {
        // Follow/Unfollow functionality
        document.addEventListener('click', (e) => {
            if (e.target.matches('.follow-btn') || e.target.closest('.follow-btn')) {
                e.preventDefault();
                this.handleFollowToggle(e.target.closest('.follow-btn'));
            }
        });

        // Profile avatar upload preview
        const avatarInput = document.querySelector('#id_avatar');
        if (avatarInput) {
            avatarInput.addEventListener('change', this.handleAvatarPreview.bind(this));
        }

        // Auto-save notification settings
        const notificationSettings = document.querySelectorAll('.notification-setting');
        notificationSettings.forEach(setting => {
            setting.addEventListener('change', this.handleNotificationSettingChange.bind(this));
        });

        // Search functionality
        const searchInput = document.querySelector('#user-search');
        if (searchInput) {
            this.setupUserSearch(searchInput);
        }

        // Form validation enhancement
        this.enhanceFormValidation();

        // Profile completion progress
        this.updateProfileCompletion();
    }

    // Follow/Unfollow functionality
    async handleFollowToggle(button) {
        const userId = button.dataset.userId;
        const isFollowing = button.classList.contains('following');
        
        try {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

            const response = await this.makeRequest(`/accounts/api/follow/${userId}/`, {
                method: 'POST',
            });

            if (response.following) {
                button.classList.add('following');
                button.innerHTML = '<i class="fas fa-user-minus"></i> Unfollow';
                button.classList.replace('btn-primary', 'btn-outline-secondary');
            } else {
                button.classList.remove('following');
                button.innerHTML = '<i class="fas fa-user-plus"></i> Follow';
                button.classList.replace('btn-outline-secondary', 'btn-primary');
            }

            // Update followers count
            const followersCount = document.querySelector('.followers-count');
            if (followersCount) {
                followersCount.textContent = response.followers_count;
            }

            this.showToast('Success', response.following ? 'Now following user' : 'Unfollowed user', 'success');

        } catch (error) {
            this.showToast('Error', 'Failed to update follow status', 'error');
            console.error('Follow toggle error:', error);
        } finally {
            button.disabled = false;
        }
    }

    // Avatar upload preview
    handleAvatarPreview(event) {
        const file = event.target.files[0];
        const preview = document.querySelector('.avatar-preview') || this.createAvatarPreview();

        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                preview.src = e.target.result;
                preview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    }

    createAvatarPreview() {
        const preview = document.createElement('img');
        preview.className = 'avatar-preview rounded-circle mt-2';
        preview.style.width = '100px';
        preview.style.height = '100px';
        preview.style.objectFit = 'cover';
        preview.style.display = 'none';
        
        const avatarInput = document.querySelector('#id_avatar');
        avatarInput.parentNode.appendChild(preview);
        
        return preview;
    }

    // Notification settings auto-save
    async handleNotificationSettingChange(event) {
        const setting = event.target;
        const settingName = setting.name;
        const isEnabled = setting.checked;

        try {
            await this.makeRequest('/accounts/api/notification-settings/', {
                method: 'POST',
                body: JSON.stringify({
                    [settingName]: isEnabled
                })
            });

            this.showToast('Settings Updated', `${settingName.replace('_', ' ')} ${isEnabled ? 'enabled' : 'disabled'}`, 'success');
        } catch (error) {
            // Revert the change if it failed
            setting.checked = !isEnabled;
            this.showToast('Error', 'Failed to update notification settings', 'error');
        }
    }

    // User search functionality
    setupUserSearch(searchInput) {
        let searchTimeout;
        
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const query = e.target.value.trim();
            
            if (query.length < 2) {
                this.clearSearchResults();
                return;
            }

            searchTimeout = setTimeout(() => {
                this.performUserSearch(query);
            }, 300);
        });
    }

    async performUserSearch(query) {
        try {
            const response = await this.makeRequest(`/accounts/api/search/?q=${encodeURIComponent(query)}`);
            this.displaySearchResults(response.users);
        } catch (error) {
            console.error('Search error:', error);
        }
    }

    displaySearchResults(users) {
        let resultsContainer = document.querySelector('.search-results');
        if (!resultsContainer) {
            resultsContainer = this.createSearchResultsContainer();
        }

        if (users.length === 0) {
            resultsContainer.innerHTML = '<div class="text-muted p-2">No users found</div>';
            return;
        }

        const resultsHTML = users.map(user => `
            <div class="search-result-item p-2 border-bottom">
                <div class="d-flex align-items-center">
                    <img src="${user.avatar || '/static/img/default-avatar.png'}" 
                         class="rounded-circle me-2" width="40" height="40">
                    <div class="flex-grow-1">
                        <div class="fw-bold">${user.display_name}</div>
                        <small class="text-muted">${user.role}</small>
                    </div>
                    <a href="/accounts/profile/${user.id}/" class="btn btn-sm btn-outline-primary">
                        View Profile
                    </a>
                </div>
            </div>
        `).join('');

        resultsContainer.innerHTML = resultsHTML;
        resultsContainer.style.display = 'block';
    }

    createSearchResultsContainer() {
        const container = document.createElement('div');
        container.className = 'search-results position-absolute bg-white border rounded shadow-lg';
        container.style.top = '100%';
        container.style.left = '0';
        container.style.right = '0';
        container.style.zIndex = '1000';
        container.style.maxHeight = '300px';
        container.style.overflowY = 'auto';
        container.style.display = 'none';

        const searchInput = document.querySelector('#user-search');
        searchInput.parentNode.style.position = 'relative';
        searchInput.parentNode.appendChild(container);

        // Close results when clicking outside
        document.addEventListener('click', (e) => {
            if (!searchInput.parentNode.contains(e.target)) {
                container.style.display = 'none';
            }
        });

        return container;
    }

    clearSearchResults() {
        const resultsContainer = document.querySelector('.search-results');
        if (resultsContainer) {
            resultsContainer.style.display = 'none';
        }
    }

    // Online status and heartbeat
    setupOnlineStatus() {
        if (!document.querySelector('meta[name="user-authenticated"]')) return;

        // Update online status every 30 seconds
        setInterval(() => {
            this.updateOnlineStatus();
        }, 30000);

        // Update status when page becomes visible
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.updateOnlineStatus();
            }
        });
    }

    async updateOnlineStatus() {
        try {
            await this.makeRequest('/accounts/api/online-status/', {
                method: 'POST'
            });
        } catch (error) {
            console.error('Failed to update online status:', error);
        }
    }

    startHeartbeat() {
        // Send heartbeat every 2 minutes to keep session alive
        setInterval(() => {
            this.makeRequest('/accounts/api/heartbeat/', {
                method: 'POST'
            }).catch(() => {
                // Silently fail - session might be expired
            });
        }, 120000);
    }

    // Form validation enhancement
    enhanceFormValidation() {
        const forms = document.querySelectorAll('form[data-validate="true"]');
        
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                }
            });

            // Real-time validation
            const inputs = form.querySelectorAll('input, textarea, select');
            inputs.forEach(input => {
                input.addEventListener('blur', () => {
                    this.validateField(input);
                });
            });
        });
    }

    validateForm(form) {
        let isValid = true;
        const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
        
        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });

        return isValid;
    }

    validateField(field) {
        const value = field.value.trim();
        const isRequired = field.hasAttribute('required');
        let isValid = true;

        // Clear previous validation
        this.clearFieldValidation(field);

        if (isRequired && !value) {
            this.showFieldError(field, 'This field is required');
            isValid = false;
        } else if (field.type === 'email' && value && !this.isValidEmail(value)) {
            this.showFieldError(field, 'Please enter a valid email address');
            isValid = false;
        } else if (field.name === 'password1' && value && value.length < 8) {
            this.showFieldError(field, 'Password must be at least 8 characters long');
            isValid = false;
        } else if (field.name === 'password2') {
            const password1 = document.querySelector('[name="password1"]');
            if (password1 && value !== password1.value) {
                this.showFieldError(field, 'Passwords do not match');
                isValid = false;
            }
        }

        if (isValid) {
            this.showFieldSuccess(field);
        }

        return isValid;
    }

    showFieldError(field, message) {
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
        
        let feedback = field.parentNode.querySelector('.invalid-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            field.parentNode.appendChild(feedback);
        }
        feedback.textContent = message;
    }

    showFieldSuccess(field) {
        field.classList.add('is-valid');
        field.classList.remove('is-invalid');
    }

    clearFieldValidation(field) {
        field.classList.remove('is-valid', 'is-invalid');
        const feedback = field.parentNode.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.remove();
        }
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    // Profile completion tracking
    updateProfileCompletion() {
        const fields = [
            'first_name', 'last_name', 'bio', 'location', 'avatar'
        ];
        
        const completedFields = fields.filter(fieldName => {
            const field = document.querySelector(`[name="${fieldName}"]`);
            return field && field.value && field.value.trim();
        });

        const completionPercentage = Math.round((completedFields.length / fields.length) * 100);
        
        // Update progress bar if it exists
        const progressBar = document.querySelector('.profile-completion-progress');
        if (progressBar) {
            progressBar.style.width = `${completionPercentage}%`;
            progressBar.setAttribute('aria-valuenow', completionPercentage);
            progressBar.textContent = `${completionPercentage}%`;
        }

        // Show completion message
        const completionText = document.querySelector('.profile-completion-text');
        if (completionText) {
            if (completionPercentage === 100) {
                completionText.innerHTML = '<i class="fas fa-check-circle text-success"></i> Profile Complete!';
            } else {
                completionText.innerHTML = `Profile ${completionPercentage}% complete`;
            }
        }
    }

    // Notification system
    setupNotificationHandler() {
        // Check for browser notification permission
        if ('Notification' in window && Notification.permission === 'default') {
            this.requestNotificationPermission();
        }

        // Setup service worker for push notifications (if available)
        if ('serviceWorker' in navigator && 'PushManager' in window) {
            this.setupServiceWorker();
        }
    }

    async requestNotificationPermission() {
        try {
            const permission = await Notification.requestPermission();
            if (permission === 'granted') {
                this.showToast('Notifications Enabled', 'You will receive browser notifications', 'success');
            }
        } catch (error) {
            console.error('Notification permission error:', error);
        }
    }

    async setupServiceWorker() {
        try {
            const registration = await navigator.serviceWorker.register('/static/sw.js');
            console.log('Service Worker registered:', registration);
        } catch (error) {
            console.error('Service Worker registration failed:', error);
        }
    }

    // Utility methods
    async makeRequest(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        };

        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    showToast(title, message, type = 'info') {
        // Create toast container if it doesn't exist
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '9999';
            document.body.appendChild(toastContainer);
        }

        // Create toast element
        const toastId = 'toast-' + Date.now();
        const iconClass = {
            'success': 'fa-check-circle text-success',
            'error': 'fa-exclamation-circle text-danger',
            'warning': 'fa-exclamation-triangle text-warning',
            'info': 'fa-info-circle text-info'
        }[type] || 'fa-info-circle text-info';

        const toastHTML = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <i class="fas ${iconClass} me-2"></i>
                    <strong class="me-auto">${title}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHTML);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
        toast.show();

        // Remove toast element after it's hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

    // Theme management
    setupThemeToggle() {
        const themeToggle = document.querySelector('.theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', this.toggleTheme.bind(this));
        }

        // Load saved theme
        const savedTheme = localStorage.getItem('theme') || 'light';
        this.setTheme(savedTheme);
    }

    toggleTheme() {
        const currentTheme = document.body.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
    }

    setTheme(theme) {
        document.body.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        const themeIcon = document.querySelector('.theme-toggle i');
        if (themeIcon) {
            themeIcon.className = theme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.accountsManager = new AccountsManager();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AccountsManager;
}
//     constructor() {
//         this.init();
//         this.setupEventListeners();
//         this.startHeartbeat();
//     }

//     init() {
//         // Get CSRF token for AJAX requests
//         this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
//                         document.querySelector('meta[name="csrf-token"]')?.content;
        
//         // Initialize tooltips and popovers
//         this.initializeBootstrapComponents();
        
//         // Setup real-time features
//         this.setupOnlineStatus();
//         this.setupNotificationHandler();
//     }

//     initializeBootstrapComponents() {
//         // Initialize Bootstrap tooltips
//         const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
//         tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

//         // Initialize Bootstrap popovers
//         const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
//         popoverTriggerList.map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
//     }

//     setupEventListeners() {
//         // Follow/Unfollow functionality
//         document.addEventListener('click', (e) => {
//             if (e.target.matches('.follow-btn') || e.target.closest('.follow-btn')) {
//                 e.preventDefault();
//                 this.handleFollowToggle(e.target.closest('.follow-btn'));
//             }
//         });

//         // Profile avatar upload preview
//         const avatarInput = document.querySelector('#id_avatar');
//         if (avatarInput) {
//             avatarInput.addEventListener('change', this.handleAvatarPreview.bind(this));
//         }

//         // Auto-save notification settings
//         const notificationSettings = document.querySelectorAll('.notification-setting');
//         notificationSettings.forEach(setting => {
//             setting.addEventListener('change', this.handleNotificationSettingChange.bind(this));
//         });

//         // Search functionality
//         const searchInput = document.querySelector('#user-search');
//         if (searchInput) {
//             this.setupUserSearch(searchInput);
//         }

//         // Form validation enhancement
//         this.enhanceFormValidation();

//         // Profile completion progress
//         this.updateProfileCompletion();
//     }

//     // Follow/Unfollow functionality
//     async handleFollowToggle(button) {
//         const userId = button.dataset.userId;
//         const isFollowing = button.classList.contains('following');
        
//         try {
//             button.disabled = true;
//             button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

//             const response = await this.makeRequest(`/accounts/api/follow/${userId}/`, {
//                 method: 'POST',
//             });

//             if (response.following) {
//                 button.classList.add('following');
//                 button.innerHTML = '<i class="fas fa-user-minus"></i> Unfollow';
//                 button.classList.replace('btn-primary', 'btn-outline-secondary');
//             } else {
//                 button.classList.remove('following');
//                 button.innerHTML = '<i class="fas fa-user-plus"></i> Follow';
//                 button.classList.replace('btn-outline-secondary', 'btn-primary');
//             }

//             // Update followers count
//             const followersCount = document.querySelector('.followers-count');
//             if (followersCount) {
//                 followersCount.textContent = response.followers_count;
//             }

//             this.showToast('Success', response.following ? 'Now following user' : 'Unfollowed user', 'success');

//         } catch (error) {
//             this.showToast('Error', 'Failed to update follow status', 'error');
//             console.error('Follow toggle error:', error);
//         } finally {
//             button.disabled = false;
//         }
//     }

//     // Avatar upload preview
//     handleAvatarPreview(event) {
//         const file = event.target.files[0];
//         const preview = document.querySelector('.avatar-preview') || this.createAvatarPreview();

//         if (file) {
//             const reader = new FileReader();
//             reader.onload = (e) => {
//                 preview.src = e.target.result;
//                 preview.style.display = 'block';
//             };
//             reader.readAsDataURL(file);
//         }
//     }

//     createAvatarPreview() {
//         const preview = document.createElement('img');
//         preview.className = 'avatar-preview rounded-circle mt-2';
//         preview.style.width = '100px';
//         preview.style.height = '100px';
//         preview.style.objectFit = 'cover';
//         preview.style.display = 'none';
        
//         const avatarInput = document.querySelector('#id_avatar');
//         avatarInput.parentNode.appendChild(preview);
        
//         return preview;
//     }

//     // Notification settings auto-save
//     async handleNotificationSettingChange(event) {
//         const setting = event.target;
//         const settingName = setting.name;
//         const isEnabled = setting.checked;

//         try {
//             await this.makeRequest('/accounts/api/notification-settings/', {
//                 method: 'POST',
//                 body: JSON.stringify({
//                     [settingName]: isEnabled
//                 })
//             });

//             this.showToast('Settings Updated', `${settingName.replace('_', ' ')} ${isEnabled ? 'enabled' : 'disabled'}`, 'success');
//         } catch (error) {
//             // Revert the change if it failed
//             setting.checked = !isEnabled;
//             this.showToast('Error', 'Failed to update notification settings', 'error');
//         }
//     }

//     // User search functionality
//     setupUserSearch(searchInput) {
//         let searchTimeout;
        
//         searchInput.addEventListener('input', (e) => {
//             clearTimeout(searchTimeout);
//             const query = e.target.value.trim();
            
//             if (query.length < 2) {
//                 this.clearSearchResults();
//                 return;
//             }

//             searchTimeout = setTimeout(() => {
//                 this.performUserSearch(query);
//             }, 300);
//         });
//     }

//     async performUserSearch(query) {
//         try {
//             const response = await this.makeRequest(`/accounts/api/search/?q=${encodeURIComponent(query)}`);
//             this.displaySearchResults(response.users);
//         } catch (error) {
//             console.error('Search error:', error);
//         }
//     }

//     displaySearchResults(users) {
//         let resultsContainer = document.querySelector('.search-results');
//         if (!resultsContainer) {
//             resultsContainer = this.createSearchResultsContainer();
//         }

//         if (users.length === 0) {
//             resultsContainer.innerHTML = '<div class="text-muted p-2">No users found</div>';
//             return;
//         }

//         const resultsHTML = users.map(user => `
//             <div class="search-result-item p-2 border-bottom">
//                 <div class="d-flex align-items-center">
//                     <img src="${user.avatar || '/static/img/default-avatar.png'}" 
//                          class="rounded-circle me-2" width="40" height="40">
//                     <div class="flex-grow-1">
//                         <div class="fw-bold">${user.display_name}</div>
//                         <small class="text-muted">${user.role}</small>
//                     </div>
//                     <a href="/accounts/profile/${user.id}/" class="btn btn-sm btn-outline-primary">
//                         View Profile
//                     </a>
//                 </div>
//             </div>
//         `).join('');

//         resultsContainer.innerHTML = resultsHTML;
//         resultsContainer.style.display = 'block';
//     }

//     createSearchResultsContainer() {
//         const container = document.createElement('div');
//         container.className = 'search-results position-absolute bg-white border rounded shadow-lg';
//         container.style.top = '100%';
//         container.style.left = '0';
//         container.style.right = '0';
//         container.style.zIndex = '1000';
//         container.style.maxHeight = '300px';
//         container.style.overflowY = 'auto';
//         container.style.display = 'none';

//         const searchInput = document.querySelector('#user-search');
//         searchInput.parentNode.style.position = 'relative';
//         searchInput.parentNode.appendChild(container);

//         // Close results when clicking outside
//         document.addEventListener('click', (e) => {
//             if (!searchInput.parentNode.contains(e.target)) {
//                 container.style.display = 'none';
//             }
//         });

//         return container;
//     }

//     clearSearchResults() {
//         const resultsContainer = document.querySelector('.search-results');
//         if (resultsContainer) {
//             resultsContainer.style.display = 'none';
//         }
//     }

//     // Online status and heartbeat
//     setupOnlineStatus() {
//         if (!document.querySelector('meta[name="user-authenticated"]')) return;

//         // Update online status every 30 seconds
//         setInterval(() => {
//             this.updateOnlineStatus();
//         }, 30000);

//         // Update status when page becomes visible
//         document.addEventListener('visibilitychange', () => {
//             if (!document.hidden) {
//                 this.updateOnlineStatus();
//             }
//         });
//     }

//     async updateOnlineStatus() {
//         try {
//             await this.makeRequest('/accounts/api/online-status/', {
//                 method: 'POST'
//             });
//         } catch (error) {
//             console.error('Failed to update online status:', error);
//         }
//     }

//     startHeartbeat() {
//         // Send heartbeat every 2 minutes to keep session alive
//         setInterval(() => {
//             this.makeRequest('/accounts/api/heartbeat/', {
//                 method: 'POST'
//             }).catch(() => {
//                 // Silently fail - session might be expired
//             });
//         }, 120000);
//     }

//     // Form validation enhancement
//     enhanceFormValidation() {
//         const forms = document.querySelectorAll('form[data-validate="true"]');
        
//         forms.forEach(form => {
//             form.addEventListener('submit', (e) => {
//                 if (!this.validateForm(form)) {
//                     e.preventDefault();
//                 }
//             });

//             // Real-time validation
//             const inputs = form.querySelectorAll('input, textarea, select');
//             inputs.forEach(input => {
//                 input.addEventListener('blur', () => {
//                     this.validateField(input);
//                 });
//             });
//         });
//     }

//     validateForm(form) {
//         let isValid = true;
//         const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
        
//         inputs.forEach(input => {
//             if (!this.validateField(input)) {
//                 isValid = false;
//             }
//         });

//         return isValid;
//     }

//     validateField(field) {
//         const value = field.value.trim();
//         const isRequired = field.hasAttribute('required');
//         let isValid = true;

//         // Clear previous validation
//         this.clearFieldValidation(field);

//         if (isRequired && !value) {
//             this.showFieldError(field, 'This field is required');
//             isValid = false;
//         } else if (field.type === 'email' && value && !this.isValidEmail(value)) {
//             this.showFieldError(field, 'Please enter a valid email address');
//             isValid = false;
//         } else if (field.name === 'password1' && value && value.length < 8) {
//             this.showFieldError(field, 'Password must be at least 8 characters long');
//             isValid = false;
//         } else if (field.name === 'password2') {
//             const password1 = document.querySelector('[name="password1"]');
//             if (password1 && value !== password1.value) {
//                 this.showFieldError(field, 'Passwords do not match');
//                 isValid = false;
//             }
//         }

//         if (isValid) {
//             this.showFieldSuccess(field);
//         }

//         return isValid;
//     }

//     showFieldError(field, message) {
//         field.classList.add('is-invalid');
//         field.classList.remove('is-valid');
        
//         let feedback = field.parentNode.querySelector('.invalid-feedback');
//         if (!feedback) {
//             feedback = document.createElement('div');
//             feedback.className = 'invalid-feedback';
//             field.parentNode.appendChild(feedback);
//         }
//         feedback.textContent = message;
//     }

//     showFieldSuccess(field) {
//         field.classList.add('is-valid');
//         field.classList.remove('is-invalid');
//     }

//     clearFieldValidation(field) {
//         field.classList.remove('is-valid', 'is-invalid');
//         const feedback = field.parentNode.querySelector('.invalid-feedback');
//         if (feedback) {
//             feedback.remove();
//         }
//     }

//     isValidEmail(email) {
//         const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
//         return emailRegex.test(email);
//     }

//     // Profile completion tracking
//     updateProfileCompletion() {
//         const fields = [
//             'first_name', 'last_name', 'bio', 'location', 'avatar'
//         ];
        
//         const completedFields = fields.filter(fieldName => {
//             const field = document.querySelector(`[name="${fieldName}"]`);
//             return field && field.value && field.value.trim();
//         });

//         const completionPercentage = Math.round((completedFields.length / fields.length) * 100);
        
//         // Update progress bar if it exists
//         const progressBar = document.querySelector('.profile-completion-progress');
//         if (progressBar) {
//             progressBar.style.width = `${completionPercentage}%`;
//             progressBar.setAttribute('aria-valuenow', completionPercentage);
//             progressBar.textContent = `${completionPercentage}%`;
//         }

//         // Show completion message
//         const completionText = document.querySelector('.profile-completion-text');
//         if (completionText) {
//             if (completionPercentage === 100) {
//                 completionText.innerHTML = '<i class="fas fa-check-circle text-success"></i> Profile Complete!';
//             } else {
//                 completionText.innerHTML = `Profile ${completionPercentage}% complete`;
//             }
//         }
//     }

//     // Notification system
//     setupNotificationHandler() {
//         // Check for browser notification permission
//         if ('Notification' in window && Notification.permission === 'default') {
//             this.requestNotificationPermission();
//         }

//         // Setup service worker for push notifications (if available)
//         if ('serviceWorker' in navigator && 'PushManager' in window) {
//             this.setupServiceWorker();
//         }
//     }

//     async requestNotificationPermission() {
//         try {
//             const permission = await Notification.requestPermission();
//             if (permission === 'granted') {
//                 this.showToast('Notifications Enabled', 'You will receive browser notifications', 'success');
//             }
//         } catch (error) {
//             console.error('Notification permission error:', error);
//         }
//     }

//     async setupServiceWorker() {
//         try {
//             const registration = await navigator.serviceWorker.register('/sw.js');
//             console.log('Service Worker registered:', registration);
//         } catch (error) {
//             console.error('Service Worker registration failed:', error);
//         }
//     }

//     // Utility methods
//     async makeRequest(url, options = {}) {
//         const defaultOptions = {
//             headers: {
//                 'Content-Type': 'application/json',
//                 'X-CSRFToken': this.csrfToken,
//                 'X-Requested-With': 'XMLHttpRequest'
//             },
//             credentials: 'same-origin'
//         };

//         const response = await fetch(url, { ...defaultOptions, ...options });
        
//         if (!response.ok) {
//             throw new Error(`HTTP error! status: ${response.status}`);
//         }

//         return await response.json();
//     }

//     showToast(title, message, type = 'info') {
//         // Create toast container if it doesn't exist
//         let toastContainer = document.querySelector('.toast-container');
//         if (!toastContainer) {
//             toastContainer = document.createElement('div');
//             toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
//             toastContainer.style.zIndex = '9999';
//             document.body.appendChild(toastContainer);
//         }

//         // Create toast element
//         const toastId = 'toast-' + Date.now();
//         const iconClass = {
//             'success': 'fa-check-circle text-success',
//             'error': 'fa-exclamation-circle text-danger',
//             'warning': 'fa-exclamation-triangle text-warning',
//             'info': 'fa-info-circle text-info'
//         }[type] || 'fa-info-circle text-info';

//         const toastHTML = `
//             <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
//                 <div class="toast-header">
//                     <i class="fas ${iconClass} me-2"></i>
//                     <strong class="me-auto">${title}</strong>
//                     <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
//                 </div>
//                 <div class="toast-body">
//                     ${message}
//                 </div>
//             </div>
//         `;

//         toastContainer.insertAdjacentHTML('beforeend', toastHTML);
        
//         const toastElement = document.getElementById(toastId);
//         const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
//         toast.show();

//         // Remove toast element after it's hidden
//         toastElement.addEventListener('hidden.bs.toast', () => {
//             toastElement.remove();
//         });
//     }

//     // Theme management
//     setupThemeToggle() {
//         const themeToggle = document.querySelector('.theme-toggle');
//         if (themeToggle) {
//             themeToggle.addEventListener('click', this.toggleTheme.bind(this));
//         }

//         // Load saved theme
//         const savedTheme = localStorage.getItem('theme') || 'light';
//         this.setTheme(savedTheme);
//     }

//     toggleTheme() {
//         const currentTheme = document.body.getAttribute('data-theme') || 'light';
//         const newTheme = currentTheme === 'light' ? 'dark' : 'light';
//         this.setTheme(newTheme);
//     }

//     setTheme(theme) {
//         document.body.setAttribute('data-theme', theme);
//         localStorage.setItem('theme', theme);
        
//         const themeIcon = document.querySelector('.theme-toggle i');
//         if (themeIcon) {
//             themeIcon.className = theme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
//         }
//     }
// }

// // Initialize when DOM is loaded
// document.addEventListener('DOMContentLoaded', () => {
//     window.accountsManager = new AccountsManager();
// });

// // Export for use in other modules
// if (typeof module !== 'undefined' && module.exports) {
//     module.exports = AccountsManager;
// }