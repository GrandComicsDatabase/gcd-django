// Keep every search toggle in one row and show its form underneath.
(() => {
    const tools = document.querySelector('[data-select-tools]');
    if (!tools) return;
    const panels = Array.from(tools.querySelectorAll(':scope > details'));
    const toggles = document.createElement('div');
    toggles.className = 'flex flex-wrap gap-x-5 gap-y-1';
    const content = document.createElement('div');
    const entries = [];
    panels.forEach((panel, index) => {
        const summary = panel.querySelector('summary');
        const body = panel.querySelector('[data-select-panel-body]');
        if (!summary || !body) return;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = [
            'cursor-pointer border-0 bg-transparent py-1 text-sm text-link-gcd',
            "before:mr-1.5 before:content-['▸'] aria-expanded:before:content-['▾']",
            'focus-visible:outline focus-visible:outline-2',
            'focus-visible:outline-offset-2 focus-visible:outline-gcd',
        ].join(' ');
        button.textContent = summary.textContent;
        button.id = `select-search-toggle-${index}`;
        body.id = `select-search-panel-${index}`;
        button.setAttribute('aria-controls', body.id);
        button.setAttribute('aria-expanded', String(panel.open));
        body.setAttribute('aria-labelledby', button.id);
        body.hidden = !panel.open;
        entries.push({button, body});
        button.addEventListener('click', () => {
            const open = body.hidden;
            entries.forEach(entry => {
                const active = entry === entries[index] && open;
                entry.body.hidden = !active;
                entry.button.setAttribute('aria-expanded', String(active));
            });
        });
        toggles.appendChild(button);
        content.appendChild(body);
        panel.remove();
    });
    tools.append(toggles, content);
})();
