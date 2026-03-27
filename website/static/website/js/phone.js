class PhoneInput {
    constructor(options) {
        this.container = document.querySelector(options.container);
        this.phoneInput = document.querySelector(options.input);
        this.countryInput = document.querySelector(options.countryInput);

        this.dropdown = this.container.querySelector('#phone-code-dropdown');
        this.list = this.container.querySelector('#country-list');
        this.search = this.container.querySelector('#country-search');
        this.btn = this.container.querySelector('#phone-code-btn');
        this.selectedFlag = this.container.querySelector('#selected-flag');
        this.selectedCode = this.container.querySelector('#selected-code');
        this.hiddenInput = this.container.querySelector('#phone_code_input');

        this.countries = [];
        this.loaded = false;

        // Cache config
        this.CACHE_KEY = 'forgeforth_country_codes';
        this.CACHE_EXPIRY_KEY = 'forgeforth_country_codes_expiry';
        this.CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours

        this.init();
    }

    async init() {
        await this.loadCountries();
        this.render(this.countries);
        this.bindEvents();
        this.setDefault();
    }

    getFromCache() {
        try {
            const expiry = localStorage.getItem(this.CACHE_EXPIRY_KEY);
            if (expiry && Date.now() < parseInt(expiry)) {
                const cached = localStorage.getItem(this.CACHE_KEY);
                if (cached) {
                    const data = JSON.parse(cached);
                    if (Array.isArray(data) && data.length > 0) return data;
                }
            }
        } catch (e) { console.warn('Cache read failed:', e); }
        return null;
    }

    saveToCache(data) {
        try {
            localStorage.setItem(this.CACHE_KEY, JSON.stringify(data));
            localStorage.setItem(this.CACHE_EXPIRY_KEY, (Date.now() + this.CACHE_DURATION).toString());
        } catch (e) { console.warn('Cache save failed:', e); }
    }

    async loadCountries() {
        // Try cache first
        const cached = this.getFromCache();
        if (cached) {
            this.countries = cached;
            this.loaded = true;
            return;
        }

        // Fetch from API
        try {
            const apiUrl = window.API_SERVICE_URL || 'http://localhost:9001';
            const res = await fetch(`${apiUrl}/api/country-codes/`);
            const data = await res.json();

            if (data.success && data.countries && data.countries.length > 0) {
                this.countries = data.countries;
                this.saveToCache(this.countries);
                this.loaded = true;
                return;
            }
        } catch (e) {
            console.warn('API fetch failed, using fallback:', e);
        }

        // Fallback
        this.countries = [
            { name: "South Africa", dial_code: "+27", flag: "🇿🇦", code: "ZA" },
            { name: "Kenya", dial_code: "+254", flag: "🇰🇪", code: "KE" },
            { name: "Nigeria", dial_code: "+234", flag: "🇳🇬", code: "NG" },
            { name: "Ghana", dial_code: "+233", flag: "🇬🇭", code: "GH" },
            { name: "Uganda", dial_code: "+256", flag: "🇺🇬", code: "UG" },
            { name: "Tanzania", dial_code: "+255", flag: "🇹🇿", code: "TZ" },
            { name: "Rwanda", dial_code: "+250", flag: "🇷🇼", code: "RW" },
            { name: "Ethiopia", dial_code: "+251", flag: "🇪🇹", code: "ET" },
            { name: "Egypt", dial_code: "+20", flag: "🇪🇬", code: "EG" },
            { name: "Morocco", dial_code: "+212", flag: "🇲🇦", code: "MA" },
            { name: "United States", dial_code: "+1", flag: "🇺🇸", code: "US" },
            { name: "United Kingdom", dial_code: "+44", flag: "🇬🇧", code: "GB" },
            { name: "Germany", dial_code: "+49", flag: "🇩🇪", code: "DE" },
            { name: "France", dial_code: "+33", flag: "🇫🇷", code: "FR" },
            { name: "India", dial_code: "+91", flag: "🇮🇳", code: "IN" },
        ];
        this.loaded = true;
    }

    render(data) {
        if (!this.list) return;

        this.list.innerHTML = data.map(c => `
            <div class="pi-item px-3 py-2 flex gap-2 cursor-pointer hover:bg-white/10 rounded-md"
                 data-code="${c.dial_code}"
                 data-name="${c.name}"
                 data-flag="${c.flag}">

                <span>${c.flag}</span>
                <span class="flex-1">${c.name}</span>
                <span class="text-slate-400">${c.dial_code}</span>
            </div>
        `).join('');
    }

    bindEvents() {
        // Toggle dropdown
        this.btn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.dropdown.classList.toggle('hidden');

            if (!this.loaded) {
                this.list.innerHTML = `<div class="p-3 text-xs">Loading...</div>`;
            }
        });

        // Select country (event delegation)
        this.list.addEventListener('click', (e) => {
            const item = e.target.closest('.pi-item');
            if (!item) return;

            this.select(item);
        });

        // Search
        this.search.addEventListener('input', (e) => {
            const q = e.target.value.toLowerCase();

            const filtered = this.countries.filter(c =>
                c.name.toLowerCase().includes(q) ||
                c.dial_code.includes(q)
            );

            this.render(filtered);
        });

        // Outside click
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this.dropdown.classList.add('hidden');
            }
        });
    }

    select(item) {
        const code = item.dataset.code;
        const name = item.dataset.name;
        const flag = item.dataset.flag;

        this.hiddenInput.value = code;
        this.selectedFlag.textContent = flag;
        this.selectedCode.textContent = code;

        if (this.countryInput) {
            this.countryInput.value = name;
        }

        this.dropdown.classList.add('hidden');
    }

    setDefault() {
        const defaultCountry = this.countries.find(c => c.code === 'ZA') || this.countries[0];

        if (!defaultCountry) return;

        this.hiddenInput.value = defaultCountry.dial_code;
        this.selectedFlag.textContent = defaultCountry.flag;
        this.selectedCode.textContent = defaultCountry.dial_code;

        if (this.countryInput) {
            this.countryInput.value = defaultCountry.name;
        }
    }

    // 🔥 Public method (useful later)
    getFullPhone() {
        return this.hiddenInput.value + this.phoneInput.value;
    }
}