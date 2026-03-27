/**
 * ForgeForth SPA Router
 * Intercepts all internal navigation links and loads content via AJAX,
 * keeping the URL as "/" at all times.
 */
(function () {
    'use strict';

    const MAIN_SELECTOR = 'main';
    const INTERNAL_ROUTES = [
        '/', '/about', '/for-talent', '/for-employers', '/platform',
        '/why-africa', '/contact', '/privacy-policy',
        '/terms-of-service', '/cookie-policy'
    ];

    let isNavigating = false;
    let currentRoute = window.location.pathname;

    /**
     * Check if a URL is an internal SPA route
     */
    function isInternalRoute(href) {
        if (!href) return false;
        try {
            const url = new URL(href, window.location.origin);
            // Must be same origin
            if (url.origin !== window.location.origin) return false;
            // Must be a known route
            return INTERNAL_ROUTES.includes(url.pathname);
        } catch (e) {
            return false;
        }
    }

    /**
     * Navigate to a route via SPA
     */
    async function navigateTo(route) {
        if (isNavigating) return;
        if (route === currentRoute && route !== '/') return;

        isNavigating = true;
        const main = document.querySelector(MAIN_SELECTOR);
        if (!main) {
            isNavigating = false;
            window.location.href = route;
            return;
        }

        // Fade out current content
        main.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
        main.style.opacity = '0';
        main.style.transform = 'translateY(10px)';

        try {
            const response = await fetch(route, {
                headers: {
                    'X-Requested-With': 'SPA'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const html = await response.text();
            const pageTitle = response.headers.get('X-Page-Title') || 'ForgeForth Africa';

            // Wait for fade out to finish
            await new Promise(resolve => setTimeout(resolve, 200));

            // Replace content
            main.innerHTML = html;

            // Update document title
            document.title = pageTitle;

            // Scroll to top smoothly
            window.scrollTo({ top: 0, behavior: 'instant' });

            // Fade in new content
            requestAnimationFrame(() => {
                main.style.opacity = '1';
                main.style.transform = 'translateY(0)';
            });

            // Update current route tracking (but don't change URL)
            currentRoute = route;

            // Re-initialize any scripts needed for the new content
            reinitializePageScripts();

            // Update active nav link
            updateActiveNavLink(route);

        } catch (error) {
            console.error('SPA navigation error:', error);
            // Fallback: do a full page load
            window.location.href = route;
        } finally {
            isNavigating = false;
        }
    }

    /**
     * Re-initialize page-specific scripts after SPA navigation
     */
    function reinitializePageScripts() {
        // Re-init AOS animations
        if (typeof AOS !== 'undefined') {
            AOS.refreshHard();
        }

        // Re-init particles.js if element exists
        if (document.getElementById('particles-js') && typeof particlesJS !== 'undefined') {
            particlesJS('particles-js', {
                particles: {
                    number: { value: 80, density: { enable: true, value_area: 800 } },
                    color: { value: '#ffffff' },
                    shape: { type: 'circle' },
                    opacity: { value: 0.5, random: true },
                    size: { value: 3, random: true },
                    line_linked: {
                        enable: true, distance: 150, color: '#ffffff',
                        opacity: 0.2, width: 1
                    },
                    move: {
                        enable: true, speed: 2, direction: 'none',
                        random: true, straight: false, out_mode: 'out', bounce: false
                    }
                },
                interactivity: {
                    detect_on: 'canvas',
                    events: {
                        onhover: { enable: true, mode: 'repulse' },
                        onclick: { enable: true, mode: 'push' },
                        resize: true
                    }
                },
                retina_detect: true
            });
        }

        // Re-observe sections for fade-in animation
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };
        const observer = new IntersectionObserver(function (entries) {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('fade-in');
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);

        document.querySelectorAll('main section').forEach(section => {
            observer.observe(section);
        });

        // Re-bind any SPA links in the new content
        bindSpaLinks(document.querySelector(MAIN_SELECTOR));
    }

    /**
     * Update the active state of nav links
     */
    function updateActiveNavLink(route) {
        // Desktop nav
        document.querySelectorAll('nav a[data-spa-link]').forEach(link => {
            const href = link.getAttribute('href');
            link.classList.remove('text-primary', 'font-semibold');
            link.classList.add('text-gray-700');
            if (href === route) {
                link.classList.add('text-primary', 'font-semibold');
                link.classList.remove('text-gray-700');
            }
        });
    }

    /**
     * Bind SPA click handlers to all internal links within a container
     */
    function bindSpaLinks(container) {
        if (!container) return;

        container.querySelectorAll('a[href]').forEach(link => {
            const href = link.getAttribute('href');

            // Skip if already bound
            if (link.hasAttribute('data-spa-bound')) return;
            link.setAttribute('data-spa-bound', '');

            // Handle waitlist links - open modal instead of navigating
            if (href === '#waitlist' || href === '/#waitlist') {
                link.addEventListener('click', function (e) {
                    e.preventDefault();
                    if (typeof window.openWaitlistModal === 'function') {
                        window.openWaitlistModal();
                    }
                });
                return;
            }

            // Skip hash-only links
            if (href.startsWith('#')) return;

            // Skip external links
            if (!isInternalRoute(href)) return;

            link.setAttribute('data-spa-link', '');

            link.addEventListener('click', function (e) {
                e.preventDefault();
                const targetRoute = this.getAttribute('href');

                // Close mobile menu if open
                const mobileMenu = document.querySelector('.mobile-menu');
                if (mobileMenu && !mobileMenu.classList.contains('hidden')) {
                    mobileMenu.classList.add('hidden');
                    const menuOpen = document.querySelector('.menu-open');
                    const menuClose = document.querySelector('.menu-close');
                    if (menuOpen) menuOpen.classList.remove('hidden');
                    if (menuClose) menuClose.classList.add('hidden');
                }

                navigateTo(targetRoute);
            });
        });
    }

    /**
     * Initialize the SPA router
     */
    function init() {
        // Replace current history state to /
        if (window.location.pathname !== '/') {
            // If someone lands on /about directly, load it properly first, then fix URL
            window.history.replaceState({ route: window.location.pathname }, '', '/');
        } else {
            window.history.replaceState({ route: '/' }, '', '/');
        }

        // Bind all links on the page
        bindSpaLinks(document);

        // Handle browser back/forward (shouldn't happen since URL stays /)
        window.addEventListener('popstate', function (e) {
            if (e.state && e.state.route) {
                navigateTo(e.state.route);
            }
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose for external use if needed
    window.spaNavigateTo = navigateTo;
})();

