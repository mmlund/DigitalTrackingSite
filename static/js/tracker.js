/**
 * DNS Marketing Tracker
 * Handles client-side tracking of page views, clicks, and user pathways.
 */

(function (window, document) {
    'use strict';

    const CONFIG = {
        endpoint: 'https://digitaltrackingsite.onrender.com/track',
        sessionTimeout: 30 * 60 * 1000, // 30 minutes
    };

    // Helper to generate UUID
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // Helper to get cookie
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    // Helper to set cookie
    function setCookie(name, value, days) {
        let expires = "";
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "") + expires + "; path=/";
    }

    // Session Management
    function getSessionId() {
        let sessionId = getCookie('dns_session_id');
        if (!sessionId) {
            sessionId = generateUUID();
            setCookie('dns_session_id', sessionId, 1); // 1 day expiry for session cookie? Maybe less.
        }
        return sessionId;
    }

    // Pathway Tracking
    function getPathwayData() {
        const currentPath = window.location.pathname;
        const referrer = document.referrer;
        let sequenceStep = parseInt(sessionStorage.getItem('dns_sequence_step') || '0');

        // If referrer is external or empty, reset sequence (new session start effectively)
        // But we rely on session_id for session grouping. 
        // Sequence step should increment on every page view within the session.

        sequenceStep += 1;
        sessionStorage.setItem('dns_sequence_step', sequenceStep.toString());

        return {
            current_page: currentPath,
            previous_page: referrer, // Note: this might be external
            sequence_step: sequenceStep
        };
    }

    // Collect Data
    function collectData(eventType, eventData = {}) {
        const pathway = getPathwayData();
        const sessionId = getSessionId();

        // Parse URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const utmParams = {};
        for (const [key, value] of urlParams) {
            if (key.startsWith('utm_') || ['gclid', 'fbclid', 'ttclid'].includes(key)) {
                utmParams[key] = value;
            }
        }

        return {
            event_type: eventType,
            timestamp: new Date().toISOString(),
            session_id: sessionId,
            url: window.location.href,
            ...pathway,
            ...utmParams,
            ...eventData,
            user_agent: navigator.userAgent,
            screen_resolution: `${window.screen.width}x${window.screen.height}`,
            language: navigator.language
        };
    }

    // Send Data
    function sendData(data) {
        // Use sendBeacon if available for reliability during unload
        if (navigator.sendBeacon) {
            const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
            navigator.sendBeacon(CONFIG.endpoint, blob);
        } else {
            fetch(CONFIG.endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data),
                keepalive: true
            }).catch(console.error);
        }
    }

    // Track Page View
    function trackPageView() {
        const data = collectData('page_view', {
            title: document.title
        });
        sendData(data);
    }

    // Track Clicks (CTA)
    function trackClick(e) {
        const target = e.target.closest('a, button, .cta');
        if (target) {
            const data = collectData('click', {
                element_tag: target.tagName,
                element_id: target.id,
                element_class: target.className,
                element_text: target.innerText ? target.innerText.substring(0, 50) : '',
                target_url: target.href || ''
            });
            sendData(data);
        }
    }

    // Initialize
    function init() {
        trackPageView();
        document.addEventListener('click', trackClick);
    }

    // Start tracking when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})(window, document);
