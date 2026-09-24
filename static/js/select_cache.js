(() => {
    const form = document.getElementById('cache-selection');
    if (!form) return;
    const section = form.closest('section');
    const checkboxes = Array.from(section.querySelectorAll('input[name="cached_objects"]'));
    const covers = Array.from(section.querySelectorAll('input[name="selected_covers"]'));
    const toggles = Array.from(section.querySelectorAll('[data-cache-select-all]'));
    const toggleInputs = toggle => (toggle.dataset.cacheSelectAll === 'cover' ? covers : checkboxes)
        .filter(input => !input.disabled);
    const actions = document.getElementById('selection-actions');
    const remove = actions.querySelector('[data-cache-remove]');
    const copy = actions.querySelector('[data-cache-copy]');
    const count = actions.querySelector('[data-cache-count]');
    let submitting = false;
    let saving = false;
    let needsReload = false;
    const selectedStories = () => checkboxes.filter(input => input.checked).length;
    const hasCover = () => covers.some(input => input.checked && input.value);
    function update() {
        const selected = selectedStories();
        toggles.forEach(toggle => {
            const inputs = toggleInputs(toggle);
            toggle.hidden = false;
            toggle.textContent = inputs.some(input => input.checked) ? 'Clear selection' : 'Select all';
            toggle.disabled = submitting || saving || needsReload || !inputs.length;
        });
        if (remove) remove.disabled = submitting || saving || needsReload || (selected === 0 && !hasCover());
        if (copy) copy.disabled = submitting || saving || needsReload || (selected === 0 && !hasCover());
        if (count) {
            const stories = selected + (selected === 1 ? ' story selected' : ' stories selected');
            const coverCount = covers.filter(input => input.checked).length;
            const coverLabel = coverCount === 1 ? 'Cover' : coverCount + ' covers';
            count.textContent = hasCover()
                ? (selected ? coverLabel + ' + ' + stories : coverLabel + ' selected')
                : (selected ? stories : '');
        }
    }
    toggles.forEach(toggle => toggle.addEventListener('click', () => {
        const inputs = toggleInputs(toggle);
        const select = !inputs.some(input => input.checked);
        inputs.forEach(input => { input.checked = select; });
        update();
    }));
    [...checkboxes, ...covers].forEach(input => input.addEventListener('change', update));
    form.addEventListener('submit', event => {
        const submitter = event.submitter || copy || remove;
        if (submitting || saving || needsReload || (!selectedStories() && !hasCover())) {
            event.preventDefault();
            return;
        }
        submitting = true;
        const action = document.createElement('input');
        action.type = 'hidden';
        action.name = submitter.name;
        action.value = submitter.value;
        action.dataset.cacheAction = '';
        form.appendChild(action);
        update();
    });
    window.addEventListener('pageshow', () => {
        submitting = false;
        form.querySelectorAll('[data-cache-action]').forEach(input => input.remove());
        update();
    });
    let activeStatus = null;
    const groups = [];

    // Do not let a copy or removal overtake an unfinished order save.
    section.addEventListener('submit', (event) => {
        if (saving || needsReload) {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (saving) activeStatus.textContent = 'Saving order. Please wait before continuing.';
        }
    }, true);

    function updateControls() {
        update();
        groups.forEach(({list, sortable}) => {
            const rows = Array.from(list.children);
            if (sortable) sortable.option('disabled', saving || needsReload);
            rows.forEach((row, index) => {
                row.querySelector('[data-cache-position]').textContent = index + 1;
            });
        });
    }

    async function saveOrder(group) {
        const {list, form, status, kind} = group;
        const previous = group.savedRows;
        const rows = Array.from(list.children);
        if (rows.every((row, index) => row === previous[index])) return;
        saving = true;
        activeStatus = status;
        section.setAttribute('aria-busy', 'true');
        status.textContent = 'Saving order…';
        updateControls();
        const body = new URLSearchParams();
        body.set('csrfmiddlewaretoken', form.querySelector('[name="csrfmiddlewaretoken"]').value);
        body.set('reorder_cached_objects', kind);
        rows.forEach((row) => body.append('ordered_objects', row.dataset.cacheItem));
        try {
            const response = await fetch(form.action, {
                method: 'POST', body, credentials: 'same-origin',
                headers: {'Accept': 'application/json'}
            });
            const result = await response.json();
            if (!response.ok || !result.saved) {
                throw new Error(result.error || 'Could not save order. Try again.');
            }
            group.savedRows = rows;
            status.textContent = '';
        } catch (error) {
            previous.forEach((row) => list.appendChild(row));
            // A lost response may still have committed on the server. Require
            // a reload rather than letting a copy use an uncertain order.
            needsReload = true;
            status.textContent = 'Unable to confirm the saved order. Reload the cache before continuing. ';
            const reload = document.createElement('button');
            reload.type = 'button';
            reload.className = 'btn-blue-editing';
            reload.textContent = 'Reload cache';
            reload.addEventListener('click', () => window.location.reload());
            status.appendChild(reload);
        } finally {
            saving = false;
            section.removeAttribute('aria-busy');
            updateControls();
        }
    }

    section.querySelectorAll('[data-cache-list]').forEach((list) => {
        const kind = list.dataset.cacheList;
        if (!['story', 'cover'].includes(kind) || list.children.length < 2 ||
                typeof Sortable === 'undefined') return;
        const form = document.getElementById('cache-selection');
        const status = section.querySelector(`[data-cache-order-status="${kind}"]`);
        const group = {list, kind, form, status, savedRows: Array.from(list.children)};
        groups.push(group);
        section.querySelector(`[data-cache-order-help="${kind}"]`).hidden = false;
        group.sortable = Sortable.create(list, {
            animation: 150,
            filter: 'input, button, a, label', preventOnFilter: false,
            draggable: '[data-cache-item]', ghostClass: 'bg-blue-200',
            onEnd: () => saveOrder(group)
        });
    });
    updateControls();
})();
