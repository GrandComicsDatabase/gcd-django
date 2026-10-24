/* Inline sequence edits are kept in this browser (localStorage) and sent to
   the server only by Save, Ctrl+S, an action of the page or hiding the tab. */
(() => {
  'use strict';
  const root = document.getElementById('sequence-workbench');
  if (!root) return;
  const state = JSON.parse(document.getElementById('sequence-workbench-data').textContent);
  const error = root.querySelector('[data-error]');
  const notice = root.querySelector('[data-notice]');
  const saveButton = document.querySelector('[data-save-sequences]');
  const saveStatus = document.querySelector('[data-save-status]');
  const draftKey = 'sequence-draft:' + root.dataset.saveUrl;
  // stored: whether the unsaved edits are also in localStorage; discarding:
  // leaving for the discard confirmation, which needs no save.
  let dirty = false, saving = null, stored = true, discarding = false;
  const message = text => { error.textContent = text; error.classList.toggle('hidden', !text); };
  const inform = text => { notice.textContent = text; notice.classList.toggle('hidden', !text); };
  function showStatus(text) {
    if (saveStatus) saveStatus.textContent = text ?? (!dirty ? '' : stored ? 'Unsaved edits kept in this browser' : 'Unsaved edits');
    if (saveButton) { saveButton.disabled = !dirty || !!saving; saveButton.classList.toggle('opacity-50', saveButton.disabled); }
  }
  function storeDraft() {
    try {
      localStorage.setItem(draftKey, JSON.stringify({version: state.version, issues: state.issues, saved: Date.now()}));
      stored = true;
    } catch (_) { stored = false; }  // Private mode or full storage: the page warns before closing.
  }
  function clearDraft() {
    try { localStorage.removeItem(draftKey); } catch (_) { /* Nothing could be stored either. */ }
  }
  const persist = () => { dirty = true; discarding = false; storeDraft(); showStatus(); };
  const sectionFor = issue => root.querySelector(`[data-issue="${issue.id}"]`);
  const rowFor = row => root.querySelector(`[data-row="${row.id}"]`);

  const coverType = state.coverType;
  const reprintType = Number(Array.from(root.querySelectorAll('[data-field="type"] option')).find(o => o.textContent === 'cover reprint (on interior page)')?.value);
  function calculate(issue) {
    const section = sectionFor(issue);
    const active = issue.rows.filter(row => !row.deleted);
    const cover = active.find(row => Number(row.type) === coverType);
    if (cover) issue.rows = [cover, ...issue.rows.filter(row => row !== cover)];
    let sequence = cover ? 1 : 0, total = 0, physical = 1, unknown = false;
    const wrap = cover && Number(cover.pages) >= 2;
    const body = section.querySelector('tbody');
    let previousElement = null;
    for (const row of issue.rows) {
      const element = rowFor(row);
      const expected = previousElement ? previousElement.nextElementSibling : body.firstElementChild;
      if (expected !== element) body.insertBefore(element, expected);
      previousElement = element;
      if (row.deleted) { element.querySelector('[data-range]').textContent = 'Mark to delete'; continue; }
      if (row !== cover && Number(row.type) === coverType && reprintType) row.type = reprintType;
      row.sequence = row === cover ? 0 : sequence++;
      element.querySelector('[data-sequence]').textContent = row.sequence;
      const noFeature = state.noFeatureTypes.includes(Number(row.type));
      element.querySelectorAll('[data-field="type"] option').forEach(option => {
        option.disabled = row.allowed_types ? !row.allowed_types.includes(Number(option.value)) : false;
        option.hidden = option.disabled;
      });
      const feature = element.querySelector('[data-field="feature"]');
      feature.disabled = noFeature;
      if (noFeature) { row.feature = ''; row.feature_text = ''; row.selected_features = []; }
      feature.placeholder = noFeature ? 'No feature' : 'Type to search';
      renderFeatures(row, element);
      for (const field of ['title', 'type', 'pages']) {
        const input = element.querySelector(`[data-field="${field}"]`);
        // Do not reformat the field being typed into.
        if (input !== document.activeElement) input.value = field === 'pages' && row[field] !== '' ? Number(Number(row[field]).toFixed(3)) : row[field];
      }
      if (document.activeElement !== feature) feature.value = row.feature_text ?? row.feature;
      const pages = Number(row.pages);
      let range = '—';
      if (!row.pages || !Number.isFinite(pages) || pages <= 0) { if (!unknown) range = '? pages'; unknown = true; }
      else {
        total += Math.round(pages * 1000);
        if (!unknown) {
          range = wrap && row === cover ? `[1, ${issue.declared === null ? 'last' : Math.ceil(Number(issue.declared))}] · ${pages > 2 ? 'gatefold' : 'wraparound'}` : `[${physical}..${physical + Math.ceil(pages) - 1}]`;
          physical += wrap && row === cover ? 1 : Math.ceil(pages);
        }
      }
      element.querySelector('[data-range]').textContent = range;
    }
    const next = section.querySelector('[data-next-sequence]'); if (next) next.value = active.length ? sequence : 0;
    const sum = total / 1000;
    section.querySelector('[data-total]').textContent = `${active.length} sequences · ${Number(sum.toFixed(3))} pages${unknown ? ' + unknown' : ''}`;
    const declared = issue.declared === null ? null : Number(Number(issue.declared).toFixed(3));
    const check = section.querySelector('[data-page-check]');
    const matches = !unknown && declared !== null && Math.round(Number(declared) * 1000) === total;
    check.textContent = declared === null ? 'Issue page count not declared' : unknown ? `Issue: ${declared} pages · complete missing page counts to compare` : matches ? `✓ Matches issue: ${declared} pages` : `Issue: ${declared} pages · difference ${Number((sum - Number(declared)).toFixed(3))}`;
    const anomalies = [];
    if (!cover) anomalies.push('Missing cover');
    if (!unknown && Number.isInteger(sum) && sum % 2 !== 0) anomalies.push('Odd total page count');
    if (!unknown && !Number.isInteger(sum)) anomalies.push('Fractional total page count');
    if (declared !== null && !unknown) anomalies.push(sum < Number(declared) ? 'Total < issue' : sum > Number(declared) ? 'Total > issue' : 'Total = issue');
    check.textContent += anomalies.length ? ' · ' + anomalies.join(' · ') : '';
    check.classList.toggle('text-green-700', matches && !!cover && !anomalies.some(x => x.startsWith('Odd')));
    check.classList.toggle('text-amber-700', !matches || !cover || anomalies.some(x => x.startsWith('Odd')));
  }
  // The rows of each issue, and the fields the server saves: a draft applies
  // only to the same rows, and a draft equal to the saved data is not restored.
  const rowIds = issues => JSON.stringify(issues.map(issue => [issue.id, issue.rows.map(row => row.id).sort((a, b) => a - b)]));
  const editable = issues => JSON.stringify(issues.map(issue => issue.rows.map(row => [
    row.id, row.title, Number(row.type), row.pages === '' ? '' : Number(row.pages), row.feature_text,
    (row.selected_features || []).map(item => Number(item.id))])));
  try {
    const draft = JSON.parse(localStorage.getItem(draftKey));
    if (draft?.issues) {
      if (editable(draft.issues) === editable(state.issues)) clearDraft();
      else if (draft.version === state.version && rowIds(draft.issues) === rowIds(state.issues)) {
        // Nothing changed on the server since: the edits of an earlier visit apply as they were.
        state.issues = draft.issues; dirty = true;
        inform('Unsaved edits from an earlier visit were restored from this browser.');
      } else {
        clearDraft();
        inform('Unsaved edits kept in this browser were discarded: the sequences were changed elsewhere since.');
      }
    }
    // Drafts of changesets never opened again (e.g. discarded ones) go after 30 days.
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const key = localStorage.key(i);
      if (!key?.startsWith('sequence-draft:') || key === draftKey) continue;
      let saved = 0;
      try { saved = JSON.parse(localStorage.getItem(key))?.saved || 0; } catch (_) { /* Unreadable: removed below. */ }
      if (!(Date.now() - saved < 30 * 864e5)) localStorage.removeItem(key);
    }
  } catch (_) { /* Storage unavailable or unreadable: the page works without drafts. */ }
  // Rendering computed indices does not by itself create a draft.
  state.issues.forEach(calculate);
  showStatus();
  function updateMigrationCount() {
    const count = root.querySelectorAll('[data-migration-needed]').length;
    root.querySelectorAll('[data-migration-count]').forEach(label => {
      label.textContent = `(${count})`;
      label.closest('button').disabled = count === 0;
      label.closest('button').classList.toggle('opacity-50', count === 0);
    });
  }
  updateMigrationCount();
  let migrating = false;
  root.addEventListener('submit', async event => {
    const form = event.target.closest('[data-migrate-credits]');
    if (!form) return;
    event.preventDefault();
    if (migrating) return;
    migrating = true;
    const rowId = form.dataset.migrateCredits;
    const scroll = {left: window.scrollX, top: window.scrollY};
    try {
      await flush();
      message('');
      root.inert = true;
      const response = await postJSON(form.dataset.migrateUrl || form.action, {
        version: state.version, story: rowId ? Number(rowId) : undefined,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Credit migration failed.');
      result.rows.forEach(row => {
        const fragment = document.createElement('template');
        fragment.innerHTML = row.html;
        rowFor(row).replaceWith(fragment.content);
      });
      state.issues = result.issues;
      state.version = result.version;
      state.issues.forEach(calculate);
      updateMigrationCount();
    } catch (err) {
      message(err.message === 'Failed to fetch' ? 'Connection unavailable. Reconnect before migrating.' : err.message);
    } finally {
      migrating = false;
      root.inert = false;
      const focus = rowId ? rowFor({id: rowId})?.querySelector('[data-menu-toggle]') : form.querySelector('button');
      if (focus?.disabled) { form.tabIndex = -1; form.focus({preventScroll: true}); }
      else focus?.focus({preventScroll: true});
      window.scrollTo(scroll);
    }
  });
  function postJSON(url, data, keepalive = false) {
    const body = JSON.stringify(data);
    return fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]').value,
      },
      // keepalive lets the request finish after the tab closes; browsers cap its body at 64 KiB.
      body, keepalive: keepalive && new Blob([body]).size < 65536,
    });
  }
  // The only way edits reach the server: one request with all rows, of which
  // the server writes those that changed.
  async function flush({keepalive = false} = {}) {
    if (saving) await saving.catch(() => {});
    if (!dirty) return;
    saving = (async () => {
      for (const input of root.querySelectorAll('[data-field]')) {
        if (!input.checkValidity()) { input.reportValidity(); throw new Error('Correct the highlighted field before continuing.'); }
      }
      const sent = JSON.stringify(state.issues);
      dirty = false;
      showStatus('Saving…');
      const response = await postJSON(root.dataset.saveUrl, {version: state.version, issues: state.issues}, keepalive);
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || 'Save failed. Try again.');
      const unchanged = JSON.stringify(state.issues) === sent;
      state.version = result.version;
      // The type choices of a row follow its saved type.
      for (const issue of state.issues) {
        for (const row of issue.rows) if (result.allowed?.[row.id]) row.allowed_types = result.allowed[row.id];
      }
      state.issues.forEach(calculate);
      // Edits typed while the request was running stay in the draft, on the new version.
      if (unchanged) clearDraft(); else { dirty = true; storeDraft(); }
      message(''); inform('');
    })().catch(err => {
      // The save may not have reached the server: keep the edits pending.
      dirty = true;
      message(err.message === 'Failed to fetch' ? 'Connection unavailable. The edits are kept in this browser: save again when the connection is back.' : err.message);
      throw err;
    }).finally(() => { saving = null; showStatus(dirty ? undefined : 'All edits saved'); });
    return saving;
  }
  saveButton?.addEventListener('click', () => flush().catch(() => {}));
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); flush().catch(() => {}); }
  });
  // Hidden is the last state a page can rely on before it is closed or
  // discarded (Page Lifecycle API), also on phones.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && dirty && !discarding) flush({keepalive: true}).catch(() => {});
  });
  // Back from a cancelled discard (page restored from the back/forward cache).
  window.addEventListener('pageshow', () => { discarding = false; });
  // Server forms (delete, move, submit) see the saved sequences.
  let resubmitting = false;
  document.addEventListener('submit', async event => {
    if (resubmitting || !(dirty || saving) || event.target.closest('[data-migrate-credits]')) return;
    // Discarding needs no save; if it is cancelled, the draft is still here.
    if (event.submitter?.name === 'discard') { discarding = true; return; }
    event.preventDefault();
    try { await flush(); resubmitting = true; event.target.requestSubmit(event.submitter); }
    catch (_) { /* The error is shown; stay on the page. */ } finally { resubmitting = false; }
  }, true);
  // Links of this site leave only after the pending edits are saved, so the
  // next page (Edit, Preview, Compare) shows them.
  document.addEventListener('click', async event => {
    const link = event.target.closest('a[href]');
    if (!link || !(dirty || saving) || event.defaultPrevented || event.button !== 0
        || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey
        || link.origin !== location.origin || link.hasAttribute('download')) return;
    event.preventDefault();
    if (link.target === '_blank') {
      // Open the tab within the click, so it is not blocked as a popup, and load it after the save.
      const tab = window.open('', '_blank');
      try {
        await flush();
        if (tab) { tab.opener = null; tab.location = link.href; } else location.assign(link.href);  // the tab was blocked
      } catch (_) { tab?.close(); }
      return;
    }
    try { await flush(); location.assign(link.href); }
    catch (_) { /* The error is shown; stay on the page. */ }
  });

  let adding = false;
  root.addEventListener('click', async event => {
    const button = event.target.closest('[data-add-sequence], [data-duplicate-sequence]');
    if (!button || adding) return;
    closeMenus();
    adding = true;
    try {
      await flush();
      message('');
      root.inert = true;
      const section = button.closest('[data-issue]');
      const response = await postJSON(root.dataset.addUrl, {
        issue: Number(section.dataset.issue), version: state.version,
        duplicate: button.hasAttribute('data-duplicate-sequence')
          ? Number(button.closest('[data-row]').dataset.row) : undefined,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || 'Could not add the sequence. Try again.');
      const fragment = document.createElement('template');
      fragment.innerHTML = result.row_html;
      section.querySelector('[data-empty]')?.remove();
      section.querySelector('tbody').append(fragment.content);
      updateMigrationCount();
      state.issues = result.issues;
      state.version = result.version;
      state.issues.forEach(calculate);
      root.inert = false;
      rowFor({id: result.row_id}).querySelector('[data-field="title"]').focus();
    } catch (err) {
      message(err.message === 'Failed to fetch' ? 'Reconnect to add a sequence. Existing local edits are retained.' : err.message);
    } finally {
      root.inert = false;
      adding = false;
    }
  });
  // Edits kept in localStorage survive the tab; only edits that could not be stored need a warning.
  window.addEventListener('beforeunload', event => { if (dirty && !stored) { event.preventDefault(); event.returnValue = ''; } });
  function rowContext(input) {
    const issue = state.issues.find(i => i.id === Number(input.closest('[data-issue]').dataset.issue));
    return {issue, row: issue.rows.find(r => r.id === Number(input.closest('[data-row]').dataset.row))};
  }
  function renderFeatures(row, element) {
    const selected = row.selected_features || [];
    const editor = element.querySelector('[data-feature-editor]');
    const noFeature = state.noFeatureTypes.includes(Number(row.type));
    editor.inert = noFeature || row.deleted;
    editor.classList.toggle('opacity-50', noFeature);
    if (noFeature) editor.open = false;
    const label = element.querySelector('[data-feature-label]');
    label.textContent = noFeature ? 'No feature' : selected[0]?.text || row.feature_text || 'Type to search';
    label.title = selected.length ? selected.map(item => item.text).join('; ') : label.textContent;
    const count = element.querySelector('[data-feature-count]');
    count.textContent = selected.length > 1 ? '+' + (selected.length - 1) : '';
    count.classList.toggle('hidden', selected.length < 2);
    const tokens = element.querySelector('[data-feature-tokens]');
    tokens.replaceChildren();
    for (const item of selected) {
      const button = document.createElement('button'); button.type = 'button';
      button.dataset.featureRemove = item.id; button.textContent = item.text + ' ×';
      button.setAttribute('aria-label', 'Remove feature ' + item.text);
      button.className = 'max-w-full break-words rounded bg-blue-100 px-1 text-xs'; tokens.append(button);
    }
  }
  root.addEventListener('toggle', event => {
    if (!event.target.matches('[data-feature-editor]') || !event.target.open) return;
    root.querySelectorAll('[data-feature-editor]').forEach(editor => {
      if (editor !== event.target) editor.open = false;
    });
    event.target.querySelector('[data-field="feature"]').focus();
  }, true);
  // Clicking elsewhere closes feature editors, search results and menus.
  document.addEventListener('click', event => {
    root.querySelectorAll('[data-feature-editor][open]').forEach(editor => {
      if (!event.composedPath().includes(editor)) editor.open = false;
    });
    if (!event.target.closest('[data-feature-results], [data-field="feature"], [data-feature-remove]')) hideFeatures();
    if (!event.target.closest('[data-menu], [data-menu-toggle]')) closeMenus();
  });
  function hideFeatures() {
    root.querySelectorAll('[data-feature-results]').forEach(list => list.classList.add('hidden'));
    root.querySelectorAll('[data-field="feature"]').forEach(input => input.setAttribute('aria-expanded', 'false'));
  }
  let autocompleteTimer, autocompleteController;
  root.addEventListener('input', event => {
    const input = event.target.closest('[data-field]'); if (!input) return;
    const {issue, row} = rowContext(input);
    if (input.dataset.field === 'feature') {
      if (!row.selected_features?.length) { row.feature_text = input.value; row.feature = input.value; }
    } else row[input.dataset.field] = input.dataset.field === 'type' ? Number(input.value) : input.value;
    calculate(issue);
    persist();
    if (input.dataset.field !== 'feature') { hideFeatures(); return; }
    clearTimeout(autocompleteTimer); autocompleteController?.abort();
    const list = document.getElementById(input.getAttribute('aria-controls')); list.replaceChildren();
    hideFeatures();
    if (!input.value.trim()) return;
    const query = input.value;
    autocompleteTimer = setTimeout(async () => {
      autocompleteController = new AbortController();
      const url = new URL(root.dataset.autocompleteUrl, location.origin);
      url.searchParams.set('q', query);
      url.searchParams.set('forward', JSON.stringify({language_code: sectionFor(issue).dataset.language, type: row.type}));
      try {
        const response = await fetch(url, {signal: autocompleteController.signal});
        if (!response.ok) throw new Error();
        const result = await response.json();
        if (input.value !== query || document.activeElement !== input) return;
        for (const match of result.results || []) {
          if (row.selected_features?.some(item => Number(item.id) === Number(match.id))) continue;
          const option = document.createElement('button'); option.type = 'button';
          const label = new DOMParser().parseFromString(match.text, 'text/html').body.textContent;
          option.textContent = label; option.dataset.featureChoice = match.id;
          option.setAttribute('role', 'option'); option.className = 'block w-full break-words p-2 text-left hover:bg-blue-100 focus:bg-blue-100'; list.append(option);
        }
        if (!list.childElementCount) list.textContent = row.selected_features?.length ? 'No match. Remove selected features to use free text.' : 'No match. This text will be saved as a feature.';
        list.classList.remove('hidden'); input.setAttribute('aria-expanded', 'true');
      } catch (_) { /* Local text remains available offline. */ }
    }, 200);
  });
  root.addEventListener('click', event => {
    const choice = event.target.closest('[data-feature-choice], [data-feature-remove]'); if (!choice) return;
    const {issue, row} = rowContext(choice);
    const input = choice.closest('[data-row]').querySelector('[data-field="feature"]');
    if (choice.hasAttribute('data-feature-remove')) row.selected_features = row.selected_features.filter(item => Number(item.id) !== Number(choice.dataset.featureRemove));
    else {
      row.selected_features ||= [];
      row.selected_features.push({id: Number(choice.dataset.featureChoice), text: choice.textContent});
      row.feature_text = ''; row.feature = row.selected_features.map(item => item.text).join('; '); input.value = '';
    }
    hideFeatures(); calculate(issue); persist(); input.focus();
  });
  root.addEventListener('keydown', event => {
    const input = event.target.closest('[data-field="feature"]');
    if (input && event.key === 'ArrowDown') { event.preventDefault(); document.getElementById(input.getAttribute('aria-controls')).querySelector('button')?.focus(); }
    const choice = event.target.closest('[data-feature-choice]');
    if (choice && ['ArrowDown', 'ArrowUp'].includes(event.key)) { event.preventDefault(); (event.key === 'ArrowDown' ? choice.nextElementSibling : choice.previousElementSibling)?.focus(); }
    if (event.key === 'Escape') {
      hideFeatures();
      const editor = event.target.closest('[data-feature-editor]');
      if (editor) { editor.open = false; editor.querySelector('summary').focus(); }
    }
  });
  let dragged = null;
  root.addEventListener('dragstart', event => {
    const handle = event.target.closest('[data-handle]');
    if (!handle || handle.getAttribute('draggable') !== 'true') return;
    dragged = handle.closest('[data-row]');
    event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', dragged.dataset.row);
    dragged.classList.add('opacity-50');
  });
  root.addEventListener('dragend', () => { dragged?.classList.remove('opacity-50'); dragged = null; });
  root.addEventListener('dragover', event => {
    const target = event.target.closest('[data-row]');
    if (dragged && target && dragged.closest('tbody') === target.closest('tbody')) { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; }
  });
  function move(source, target, after) {
    const issue = state.issues.find(i => i.id === Number(source.closest('[data-issue]').dataset.issue));
    const row = issue.rows.find(r => r.id === Number(source.dataset.row));
    const destination = issue.rows.find(r => r.id === Number(target.dataset.row));
    if (row === destination || row.deleted || destination.deleted) return;
    issue.rows = issue.rows.filter(r => r !== row);
    issue.rows.splice(issue.rows.indexOf(destination) + (after ? 1 : 0), 0, row);
    if (reprintType && Number(row.type) === coverType && issue.rows.find(r => !r.deleted) !== row) {
      row.type = reprintType;
    }
    calculate(issue); persist();
  }
  root.addEventListener('drop', event => {
    const target = event.target.closest('[data-row]');
    if (!dragged || !target || dragged.closest('tbody') !== target.closest('tbody')) return;
    event.preventDefault();
    move(dragged, target, event.clientY > target.getBoundingClientRect().top + target.offsetHeight / 2);
    dragged.classList.remove('opacity-50'); dragged = null;
  });
  root.addEventListener('keydown', event => {
    if (event.target.matches('[data-handle]') && event.altKey && ['ArrowUp', 'ArrowDown'].includes(event.key)) {
      event.preventDefault(); const source = event.target.closest('[data-row]');
      const target = event.key === 'ArrowUp' ? source.previousElementSibling : source.nextElementSibling;
      if (target) { move(source, target, event.key === 'ArrowDown'); event.target.focus(); }
    }
    if (event.key === 'Escape') closeMenus(true);
  });
  function closeMenus(focus = false) {
    root.querySelectorAll('[data-menu]').forEach(menu => {
      if (focus && !menu.classList.contains('hidden')) menu.parentElement.querySelector('[data-menu-toggle]').focus();

      menu.classList.add('hidden');
      menu.parentElement.querySelector('[data-menu-toggle]').setAttribute('aria-expanded', 'false');
    });
  }
  function openMenu(row) {
    const menu = row.querySelector('[data-menu]');
    const wasOpen = !menu.classList.contains('hidden'); closeMenus();
    if (!wasOpen) {
      menu.classList.remove('hidden'); row.querySelector('[data-menu-toggle]').setAttribute('aria-expanded', 'true');
      menu.querySelector('a, button')?.focus(); menu.scrollIntoView({block: 'nearest'});
    }
  }
  root.addEventListener('click', event => { const toggle = event.target.closest('[data-menu-toggle]'); if (toggle) openMenu(toggle.closest('[data-row]')); });
  root.querySelectorAll('[data-import]').forEach(form => {
    const input = form.querySelector('input[type="file"]');
    const dropzone = form.querySelector('[data-dropzone]');
    async function upload() {
      const file = input.files[0]; if (!file) return;
      const format = {csv: 'csv', tsv: 'tab', json: 'json', yaml: 'yaml', yml: 'yaml'}[file.name.split('.').pop().toLowerCase()];
      if (!format) { message('Choose a CSV, TSV, JSON or YAML file.'); input.value = ''; return; }
      try {
        await flush();
        form.querySelector('[data-format]')?.remove();
        const field = document.createElement('input'); field.type = 'hidden'; field.name = format; field.value = '1'; field.dataset.format = '';
        form.append(field); form.requestSubmit();
      } catch (_) { input.value = ''; }
    }
    input.addEventListener('change', upload);
    dropzone.addEventListener('dragover', event => { if (!dragged) { event.preventDefault(); dropzone.classList.add('border-blue-500'); } });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('border-blue-500'));
    dropzone.addEventListener('drop', event => {
      if (dragged) return;
      event.preventDefault(); dropzone.classList.remove('border-blue-500');
      if (event.dataTransfer.files.length !== 1) { message('Drop one file at a time.'); return; }
      input.files = event.dataTransfer.files; upload();
    });
  });
})();
