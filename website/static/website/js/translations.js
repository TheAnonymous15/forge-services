/**
 * ForgeForth Africa - Client-side Translation System
 * Handles dynamic content translation and language switching
 */

class TranslationManager {
    constructor() {
        this.currentLang = this.detectLanguage();
        this.cache = new Map();
        this.pendingTranslations = new Map();
        this.apiEndpoint = '/api/translate/';
        this.isTranslating = false;

        this.init();
    }

    /**
     * Initialize the translation manager
     */
    init() {
        // Set up language from cookie or default
        document.documentElement.lang = this.currentLang;

        // Update RTL direction if needed
        this.updateDirection();

        // Set up event listeners
        this.setupEventListeners();

        // Translate any dynamic content on load
        this.translateDynamicContent();
    }

    /**
     * Detect user's preferred language
     */
    detectLanguage() {
        // 1. Check URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        const urlLang = urlParams.get('lang');
        if (urlLang && this.isSupported(urlLang)) {
            this.setLanguageCookie(urlLang);
            return urlLang;
        }

        // 2. Check cookie
        const cookieLang = this.getCookie('ff_lang');
        if (cookieLang && this.isSupported(cookieLang)) {
            return cookieLang;
        }

        // 3. Check browser language
        const browserLang = navigator.language?.split('-')[0];
        if (browserLang && this.isSupported(browserLang)) {
            return browserLang;
        }

        // 4. Default to English
        return 'en';
    }

    /**
     * Check if a language is supported
     */
    isSupported(lang) {
        const supported = ['en', 'sw', 'fr', 'ar', 'pt', 'am', 'zu', 'yo', 'ha', 'ig', 'es', 'zh', 'de'];
        return supported.includes(lang.toLowerCase());
    }

    /**
     * Update text direction for RTL languages
     */
    updateDirection() {
        const rtlLanguages = ['ar', 'he', 'ur', 'fa'];
        const dir = rtlLanguages.includes(this.currentLang) ? 'rtl' : 'ltr';
        document.documentElement.dir = dir;
        document.body.classList.toggle('rtl', dir === 'rtl');
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Language switcher clicks
        document.addEventListener('click', (e) => {
            const langLink = e.target.closest('[data-lang-switch]');
            if (langLink) {
                e.preventDefault();
                const newLang = langLink.dataset.lang;
                this.switchLanguage(newLang);
            }
        });

        // Observe DOM for new content that needs translation
        this.setupMutationObserver();
    }

    /**
     * Set up mutation observer to translate dynamically added content
     */
    setupMutationObserver() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Check for elements with data-translate attribute
                        const translatables = node.querySelectorAll('[data-translate]');
                        if (translatables.length > 0) {
                            this.translateElements(translatables);
                        }
                        if (node.hasAttribute && node.hasAttribute('data-translate')) {
                            this.translateElement(node);
                        }
                    }
                });
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    /**
     * Switch to a new language
     */
    async switchLanguage(newLang) {
        if (!this.isSupported(newLang) || newLang === this.currentLang) {
            return;
        }

        // Show loading indicator
        this.showLoadingIndicator();

        // Update language
        this.currentLang = newLang;
        this.setLanguageCookie(newLang);
        document.documentElement.lang = newLang;
        this.updateDirection();

        // Reload page to get server-side translated content
        // This ensures all content is properly translated
        window.location.href = this.updateUrlLanguage(newLang);
    }

    /**
     * Update URL with language parameter
     */
    updateUrlLanguage(lang) {
        const url = new URL(window.location.href);
        url.searchParams.set('lang', lang);
        return url.toString();
    }

    /**
     * Translate dynamic content that wasn't rendered server-side
     */
    async translateDynamicContent() {
        if (this.currentLang === 'en') return;

        const elements = document.querySelectorAll('[data-translate]');
        if (elements.length > 0) {
            await this.translateElements(elements);
        }
    }

    /**
     * Translate multiple elements
     */
    async translateElements(elements) {
        const texts = [];
        const elementsArray = Array.from(elements);

        elementsArray.forEach((el) => {
            const text = el.dataset.translateOriginal || el.textContent.trim();
            if (text && !el.dataset.translated) {
                // Store original text
                if (!el.dataset.translateOriginal) {
                    el.dataset.translateOriginal = text;
                }
                texts.push({ element: el, text });
            }
        });

        if (texts.length === 0) return;

        // Check cache first
        const uncached = [];
        texts.forEach(({ element, text }) => {
            const cached = this.getFromCache(text, this.currentLang);
            if (cached) {
                element.textContent = cached;
                element.dataset.translated = 'true';
            } else {
                uncached.push({ element, text });
            }
        });

        // Translate uncached texts via API
        if (uncached.length > 0) {
            await this.batchTranslate(uncached);
        }
    }

    /**
     * Translate a single element
     */
    async translateElement(element) {
        const text = element.dataset.translateOriginal || element.textContent.trim();
        if (!text || element.dataset.translated) return;

        // Store original
        if (!element.dataset.translateOriginal) {
            element.dataset.translateOriginal = text;
        }

        // Check cache
        const cached = this.getFromCache(text, this.currentLang);
        if (cached) {
            element.textContent = cached;
            element.dataset.translated = 'true';
            return;
        }

        // Translate via API
        const translated = await this.translate(text, this.currentLang);
        if (translated) {
            element.textContent = translated;
            element.dataset.translated = 'true';
        }
    }

    /**
     * Batch translate texts via API
     */
    async batchTranslate(items) {
        if (items.length === 0) return;

        try {
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken(),
                },
                body: JSON.stringify({
                    texts: items.map(i => i.text),
                    target_lang: this.currentLang,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                if (data.translations) {
                    items.forEach((item, index) => {
                        const translated = data.translations[index];
                        if (translated) {
                            item.element.textContent = translated;
                            item.element.dataset.translated = 'true';
                            this.addToCache(item.text, this.currentLang, translated);
                        }
                    });
                }
            }
        } catch (error) {
            console.error('Batch translation failed:', error);
        }
    }

    /**
     * Translate a single text string
     */
    async translate(text, targetLang) {
        // Check cache
        const cached = this.getFromCache(text, targetLang);
        if (cached) return cached;

        try {
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken(),
                },
                body: JSON.stringify({
                    text: text,
                    target_lang: targetLang,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                if (data.translation) {
                    this.addToCache(text, targetLang, data.translation);
                    return data.translation;
                }
            }
        } catch (error) {
            console.error('Translation failed:', error);
        }

        return null;
    }

    /**
     * Get translation from cache
     */
    getFromCache(text, lang) {
        const key = `${lang}:${text}`;
        return this.cache.get(key);
    }

    /**
     * Add translation to cache
     */
    addToCache(text, lang, translation) {
        const key = `${lang}:${text}`;
        this.cache.set(key, translation);

        // Also store in localStorage for persistence
        try {
            const storageKey = 'ff_translation_cache';
            const stored = JSON.parse(localStorage.getItem(storageKey) || '{}');
            stored[key] = translation;
            // Limit cache size
            const keys = Object.keys(stored);
            if (keys.length > 1000) {
                // Remove oldest entries
                keys.slice(0, 100).forEach(k => delete stored[k]);
            }
            localStorage.setItem(storageKey, JSON.stringify(stored));
        } catch (e) {
            // localStorage might be full or disabled
        }
    }

    /**
     * Load cache from localStorage
     */
    loadCacheFromStorage() {
        try {
            const stored = JSON.parse(localStorage.getItem('ff_translation_cache') || '{}');
            Object.entries(stored).forEach(([key, value]) => {
                this.cache.set(key, value);
            });
        } catch (e) {
            // Ignore errors
        }
    }

    /**
     * Show loading indicator during language switch
     */
    showLoadingIndicator() {
        // Create overlay
        const overlay = document.createElement('div');
        overlay.id = 'translation-loading';
        overlay.innerHTML = `
            <div class="fixed inset-0 bg-gray-900/80 backdrop-blur-sm z-[9999] flex items-center justify-center">
                <div class="bg-gray-800/90 rounded-2xl p-8 flex flex-col items-center gap-4">
                    <div class="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
                    <p class="text-white text-lg">Translating...</p>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    /**
     * Hide loading indicator
     */
    hideLoadingIndicator() {
        const overlay = document.getElementById('translation-loading');
        if (overlay) {
            overlay.remove();
        }
    }

    /**
     * Get CSRF token from cookie
     */
    getCsrfToken() {
        return this.getCookie('csrftoken') || '';
    }

    /**
     * Get cookie value
     */
    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(';').shift();
        }
        return null;
    }

    /**
     * Set language cookie
     */
    setLanguageCookie(lang) {
        const expires = new Date();
        expires.setFullYear(expires.getFullYear() + 1);
        document.cookie = `ff_lang=${lang}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.TranslationManager = new TranslationManager();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TranslationManager;
}

