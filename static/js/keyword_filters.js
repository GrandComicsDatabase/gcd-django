(() => {
    if (!window.htmx) return;
    let detailOpener = null;
    let resultScroll = 0;

    function closeDetail(restoreFocus = false) {
        const panel = document.getElementById('keyword-detail');
        if (!panel) return;
        window.htmx.trigger(panel, 'htmx:abort');
        panel.hidden = true;
        panel.replaceChildren();
        panel.removeAttribute('aria-busy');
        const opener = document.getElementById(detailOpener);
        if (opener) {
            opener.setAttribute('aria-expanded', 'false');
            if (restoreFocus) {
                opener.focus({preventScroll: true});
                window.scrollTo(0, resultScroll);
            }
        }
        detailOpener = null;
    }

    function syncFilters() {
        const form = document.getElementById('keyword-filters');
        if (!form) return;
        const params = new URLSearchParams(window.location.search);
        for (const name of ['q', 'usage', 'sort']) {
            form.elements.namedItem(name).value = params.get(name) ||
                (name === 'sort' ? 'name' : '');
        }
    }

    function isResults(event) {
        return event.detail.target?.id === 'keyword-results';
    }

    function isDetail(event) {
        return event.detail.target?.id === 'keyword-detail';
    }

    document.addEventListener('click', event => {
        if (event.target.closest('[data-keyword-close]')) closeDetail(true);
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && event.target.closest('#keyword-detail')) {
            closeDetail(true);
        }
    });
    document.addEventListener('htmx:beforeHistorySave', () => closeDetail());
    document.addEventListener('htmx:historyRestore', () => {
        closeDetail();
        syncFilters();
    });

    // Follow a session-expiry redirect as a full page, not inside a fragment.
    document.addEventListener('htmx:beforeSwap', event => {
        if ((!isResults(event) && !isDetail(event)) ||
                !event.detail.xhr.responseURL) return;
        const response = new URL(event.detail.xhr.responseURL);
        const requested = new URL(event.detail.requestConfig.path, window.location.href);
        if (response.pathname !== requested.pathname) {
            event.detail.shouldSwap = false;
            window.location.assign(response.href);
        }
    });

    document.addEventListener('htmx:beforeRequest', event => {
        if (isDetail(event)) {
            const opener = event.detail.requestConfig.elt;
            if (opener.hasAttribute('aria-controls')) {
                const previous = document.getElementById(detailOpener);
                if (previous) previous.setAttribute('aria-expanded', 'false');
                detailOpener = opener.id;
                resultScroll = window.scrollY;
                opener.setAttribute('aria-expanded', 'true');
            }
            event.detail.target.hidden = false;
            event.detail.target.setAttribute('aria-busy', 'true');
        }
        if (!isResults(event)) return;
        closeDetail();
        event.detail.target.setAttribute('aria-busy', 'true');
        document.getElementById('keyword-request-status').textContent = 'Loading keywords…';
    });

    document.addEventListener('htmx:afterRequest', event => {
        if (!isResults(event) && !isDetail(event)) return;
        event.detail.target.removeAttribute('aria-busy');
        document.getElementById('keyword-request-status').textContent = event.detail.failed
            ? 'Unable to load keywords. Use Search or select the keyword to retry.' : '';
    });

    document.addEventListener('htmx:afterSettle', event => {
        if (isDetail(event) && !event.detail.target.hidden) {
            const title = document.getElementById('keyword-detail-title');
            if (title) {
                title.focus({preventScroll: true});
                title.scrollIntoView({block: 'start'});
            }
        }
        if (isResults(event) && event.detail.requestConfig?.elt?.id === 'keyword-reset') {
            syncFilters();
        }
    });
})();
