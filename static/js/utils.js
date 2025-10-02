// static/js/utils.js - Additional utility functions
class Utils {
    // Format date relative to now (e.g., "2 hours ago")
    static timeAgo(date) {
        const now = new Date();
        const diffInSeconds = Math.floor((now - new Date(date)) / 1000);
        
        const intervals = {
            year: 31536000,
            month: 2592000,
            week: 604800,
            day: 86400,
            hour: 3600,
            minute: 60
        };

        for (let [unit, seconds] of Object.entries(intervals)) {
            const interval = Math.floor(diffInSeconds / seconds);
            if (interval >= 1) {
                return `${interval} ${unit}${interval > 1 ? 's' : ''} ago`;
            }
        }
        
        return 'Just now';
    }

    // Debounce function for search
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Copy text to clipboard
    static async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            const success = document.execCommand('copy');
            document.body.removeChild(textArea);
            return success;
        }
    }

    // Format file size
    static formatFileSize(bytes) {
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 Bytes';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }

    // Validate image file
    static validateImageFile(file, maxSize = 5 * 1024 * 1024) { // 5MB default
        const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
        
        if (!validTypes.includes(file.type)) {
            return { valid: false, error: 'Invalid file type. Please select a JPEG, PNG, GIF, or WebP image.' };
        }
        
        if (file.size > maxSize) {
            return { valid: false, error: `File too large. Maximum size is ${this.formatFileSize(maxSize)}.` };
        }
        
        return { valid: true };
    }

    // Generate avatar placeholder
    static generateAvatarPlaceholder(name, size = 100) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = size;
        canvas.height = size;

        // Background color based on name hash
        const hash = name.split('').reduce((a, b) => {
            a = ((a << 5) - a) + b.charCodeAt(0);
            return a & a;
        }, 0);
        const hue = Math.abs(hash) % 360;
        
        ctx.fillStyle = `hsl(${hue}, 50%, 50%)`;
        ctx.fillRect(0, 0, size, size);
        
        // Initial letter
        ctx.fillStyle = 'white';
        ctx.font = `${size / 2}px Arial`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(name.charAt(0).toUpperCase(), size / 2, size / 2);
        
        return canvas.toDataURL();
    }

    // Lazy load images
    static setupLazyLoading() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy-load');
                        observer.unobserve(img);
                    }
                });
            });

            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
        } else {
            // Fallback for older browsers
            document.querySelectorAll('img[data-src]').forEach(img => {
                img.src = img.dataset.src;
            });
        }
    }

    // Animate number counting
    static animateNumber(element, start, end, duration = 1000) {
        const range = end - start;
        const increment = range / (duration / 16); // 60fps
        let current = start;
        
        const timer = setInterval(() => {
            current += increment;
            element.textContent = Math.floor(current);
            
            if (current >= end) {
                element.textContent = end;
                clearInterval(timer);
            }
        }, 16);
    }

    // Check if element is in viewport
    static isInViewport(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }

    // Smooth scroll to element
    static scrollToElement(element, offset = 0) {
        const elementPosition = element.offsetTop - offset;
        window.scrollTo({
            top: elementPosition,
            behavior: 'smooth'
        });
    }

    // Password strength checker
    static checkPasswordStrength(password) {
        let score = 0;
        let feedback = [];

        // Length check
        if (password.length >= 8) score += 1;
        else feedback.push('At least 8 characters');

        // Uppercase check
        if (/[A-Z]/.test(password)) score += 1;
        else feedback.push('One uppercase letter');

        // Lowercase check
        if (/[a-z]/.test(password)) score += 1;
        else feedback.push('One lowercase letter');

        // Number check
        if (/\d/.test(password)) score += 1;
        else feedback.push('One number');

        // Special character check
        if (/[^A-Za-z0-9]/.test(password)) score += 1;
        else feedback.push('One special character');

        const strength = score <= 2 ? 'weak' : score <= 3 ? 'medium' : 'strong';
        
        return {
            score,
            strength,
            feedback: feedback.length ? 'Missing: ' + feedback.join(', ') : 'Strong password!',
            percentage: (score / 5) * 100
        };
    }

    // Local storage with expiration
    static setStorageWithExpiry(key, value, ttl) {
        const now = new Date();
        const item = {
            value: value,
            expiry: now.getTime() + ttl
        };
        localStorage.setItem(key, JSON.stringify(item));
    }

    static getStorageWithExpiry(key) {
        const itemStr = localStorage.getItem(key);
        if (!itemStr) return null;

        const item = JSON.parse(itemStr);
        const now = new Date();

        if (now.getTime() > item.expiry) {
            localStorage.removeItem(key);
            return null;
        }
        
        return item.value;
    }

    // Format user mention for chat/forums
    static formatUserMention(username) {
        return `@${username}`;
    }

    // Extract mentions from text
    static extractMentions(text) {
        const mentionRegex = /@(\w+)/g;
        const mentions = [];
        let match;
        
        while ((match = mentionRegex.exec(text)) !== null) {
            mentions.push(match[1]);
        }
        
        return [...new Set(mentions)]; // Remove duplicates
    }

    // Truncate text with ellipsis
    static truncateText(text, maxLength, suffix = '...') {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength - suffix.length) + suffix;
    }

    // Convert URLs to clickable links
    static linkify(text) {
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        return text.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener">$1</a>');
    }
}

// Export Utils for global use
if (typeof window !== 'undefined') {
    window.Utils = Utils;
}

// Initialize utility features when DOM loads
document.addEventListener('DOMContentLoaded', () => {
    // Setup lazy loading for images
    Utils.setupLazyLoading();
    
    // Setup password strength indicators
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        if (input.name === 'password1' || input.name === 'new_password1') {
            const strengthIndicator = document.createElement('div');
            strengthIndicator.className = 'password-strength mt-2';
            strengthIndicator.innerHTML = '<div class="password-strength-bar"></div>';
            input.parentNode.appendChild(strengthIndicator);
            
            const feedbackDiv = document.createElement('div');
            feedbackDiv.className = 'password-feedback small text-muted mt-1';
            input.parentNode.appendChild(feedbackDiv);
            
            input.addEventListener('input', (e) => {
                const result = Utils.checkPasswordStrength(e.target.value);
                const bar = strengthIndicator.querySelector('.password-strength-bar');
                
                bar.style.width = result.percentage + '%';
                bar.className = `password-strength-bar password-strength-${result.strength}`;
                feedbackDiv.textContent = result.feedback;
            });
        }
    });
});