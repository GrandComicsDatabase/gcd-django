// Forum editor helpers: reply targets, quotes, drafts, the message box and record search.
(function () {
  'use strict';

  /** The quick reply form of a topic page, or null where the page has none. */
  function replyForm() {
    return document.getElementById('quick-reply-form');
  }

  /** Replies stay one level deep: a reply to a reply joins the list of its top-level post. */
  window.setReplyTarget = function (postId, rootId, name) {
    const form = replyForm();
    if (!form) return;
    form.querySelector('[name="parent"]').value = postId;
    form.setAttribute('hx-target', '#children-' + rootId);
    document.getElementById('reply-heading').textContent = 'Reply to ' + name;
    document.getElementById('cancel-reply').classList.remove('hidden');
    htmx.process(form);
    const textarea = form.querySelector('textarea');
    showWrite(textarea);
    textarea.focus();
  };

  /**
   * Make the reply form answer the topic again: no parent post, and the new post goes to the post list.
   * With focus set (the "Reply to the topic instead" button, which hides itself), the text gets the focus.
   */
  window.clearReplyTarget = function (focus) {
    const form = replyForm();
    if (!form) return;
    form.querySelector('[name="parent"]').value = '';
    form.setAttribute('hx-target', '#post-list');
    document.getElementById('reply-heading').textContent = 'Reply to the topic';
    document.getElementById('cancel-reply').classList.add('hidden');
    htmx.process(form);
    if (focus) form.querySelector('textarea').focus();
  };

  /**
   * Parts that work only with scripts (tabs, Quote, the record search) show once this file runs; the
   * fallbacks for pages without scripts (the records field) hide; the file input leaves the tab order to
   * its Attach label.
   */
  function enhance(root) {
    root.querySelectorAll('[data-needs-js]').forEach(element => { element.hidden = false; });
    root.querySelectorAll('[data-hide-with-js]').forEach(element => element.classList.add('hidden'));
    root.querySelectorAll('[data-file-input]').forEach(input => { input.tabIndex = -1; });
  }

  /** Quote the selected text of a post, or the whole post, into the reply box. */
  window.quotePost = function (postId, rootId, name) {
    const body = document.getElementById('post-body-' + postId);
    const selection = window.getSelection();
    let text = '';
    if (selection && selection.rangeCount && body.contains(selection.anchorNode)) {
      text = selection.toString();
    }
    text = (text || body.innerText).trim();
    const quote = name + ' wrote:\n' + text.split('\n').map(line => '> ' + line).join('\n') + '\n\n';
    window.setReplyTarget(postId, rootId, name);
    const textarea = replyForm().querySelector('textarea');
    const at = textarea.selectionStart || textarea.value.length;
    textarea.value = textarea.value.slice(0, at) + quote + textarea.value.slice(at);
    textarea.selectionStart = textarea.selectionEnd = at + quote.length;
    textarea.dispatchEvent(new Event('input'));
  };

  // The message box (_editor.html) -----------------------------------------------------------

  /** The message box ([data-editor]) an element is in, or null outside one. */
  function editorOf(element) {
    return element && element.closest ? element.closest('[data-editor]') : null;
  }

  /** Show text in the status line of an element's message box, marked as an error when isError is set. */
  function showStatus(element, text, isError) {
    const editor = editorOf(element);
    const status = editor && editor.querySelector('[data-editor-status]');
    if (!status) return;
    status.textContent = text;
    status.toggleAttribute('data-error', Boolean(text && isError));
    // Any new message replaces a failed request's message, which the next answer would clear.
    status.removeAttribute('data-request-error');
  }

  /** Write and Preview are tabs over the same box; the preview keeps the height of the text. */
  function selectTab(tab) {
    const tabs = Array.from(editorOf(tab).querySelectorAll('[role="tab"]'));
    const panels = tabs.map(other => document.getElementById(other.getAttribute('aria-controls')));
    if (tab !== tabs[0] && !panels[0].hidden) panels[1].style.minHeight = panels[0].offsetHeight + 'px';
    tabs.forEach(function (other, index) {
      other.setAttribute('aria-selected', String(other === tab));
      other.tabIndex = other === tab ? 0 : -1;
      panels[index].hidden = other !== tab;
    });
  }

  /** Switch the message box of a textarea back to the Write tab. */
  function showWrite(textarea) {
    const editor = editorOf(textarea);
    if (editor) selectTab(editor.querySelector('[role="tab"]'));
  }

  /** Show the Write tab again and empty the preview and the status line of the textarea's message box. */
  function resetEditor(textarea) {
    showWrite(textarea);
    const preview = document.getElementById('preview-' + textarea.id);
    if (preview) preview.innerHTML = '';
    showStatus(textarea, '', false);
  }

  document.addEventListener('click', function (event) {
    const tab = event.target.closest && event.target.closest('[data-editor] [role="tab"]');
    if (!tab) return;
    selectTab(tab);
    // A click on Write goes back to the text; from the keyboard the focus stays on the tab.
    const editor = editorOf(tab);
    if (tab === editor.querySelector('[role="tab"]') && event.detail > 0) editor.querySelector('textarea').focus();
  });

  document.addEventListener('keydown', function (event) {
    const tab = event.target.closest && event.target.closest('[data-editor] [role="tab"]');
    if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const tabs = Array.from(editorOf(tab).querySelectorAll('[role="tab"]'));
    const at = tabs.indexOf(tab);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
      : (at + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length;
    event.preventDefault();
    tabs[next].focus();
  });

  // The browser can only point at an empty message while the text is shown.
  document.addEventListener('invalid', function (event) {
    if (editorOf(event.target)) showWrite(event.target);
  }, true);

  // The cards of the GCD records follow the links of the text, so typing alone asks nothing.
  const LINK = /https?:\/\/[^\s<>()[\]"']+/g;

  /** The distinct http and https links of the text, one per line, in the order they first appear. */
  function linksOf(textarea) {
    return Array.from(new Set(textarea.value.match(LINK) || [])).join('\n');
  }

  /**
   * Return the links of the textarea with this id for the record cards request (the strip's hx-vals),
   * and keep them on the strip so the input handler can tell when they change.
   */
  window.forumLinks = function (id) {
    const links = linksOf(document.getElementById(id));
    document.getElementById('linked-' + id).dataset.links = links;
    return links;
  };

  /** The links of the textarea with this id, for a request that only reads them (similar topics). */
  window.forumLinkText = function (id) {
    const textarea = document.getElementById(id);
    return textarea ? linksOf(textarea) : '';
  };

  /** Have the strip fetch the record cards of the text's links again, through its forum-links trigger. */
  function refreshCards(textarea) {
    const strip = document.getElementById('linked-' + textarea.id);
    if (strip) htmx.trigger(strip, 'forum-links');
  }

  // Capturing also catches the input events of quotes, record picks and resets, which do not bubble.
  document.addEventListener('input', function (event) {
    const textarea = event.target;
    if (textarea.tagName !== 'TEXTAREA' || !editorOf(textarea)) return;
    const strip = document.getElementById('linked-' + textarea.id);
    if (strip && strip.dataset.links !== linksOf(textarea)) refreshCards(textarea);
  }, true);

  // Files go with the message: chosen with Attach, dropped on the box or pasted into the text.
  const chosenFiles = new WeakMap();
  // The description written for each file, kept while the tray is drawn again.
  const descriptions = new WeakMap();
  const MB = 1024 * 1024;

  /**
   * Why a file cannot join those already chosen (too many, too large, a type not accepted), or ''. A file
   * whose type the browser does not know (no extension) goes on: the forum judges files by their content.
   */
  function fileProblem(input, file, count) {
    if (count >= Number(input.dataset.maxFiles)) return 'Attach at most ' + input.dataset.maxFiles + ' files.';
    if (file.size > Number(input.dataset.maxBytes)) {
      return file.name + ': larger than ' + Math.floor(Number(input.dataset.maxBytes) / MB) + ' MB.';
    }
    if (file.type && file.type !== 'application/octet-stream' && !input.accept.split(',').includes(file.type)) {
      return file.name + ': not a JPEG, PNG, GIF or WebP image, or a PDF.';
    }
    return '';
  }

  /** A size in bytes as whole KB (at least 1) below one MB, else as MB with one decimal. */
  function fileSize(bytes) {
    return bytes < MB ? Math.max(1, Math.round(bytes / 1024)) + ' KB' : (bytes / MB).toFixed(1) + ' MB';
  }

  /**
   * Redraw the tray of chosen files, each with a thumbnail (or "PDF", or "File" for a file of unknown type),
   * a description field (not for a PDF), name, size and remove button, and the
   * count line; the tray hides when empty. Object URLs of the old thumbnails are released first.
   */
  function drawFiles(input) {
    const tray = editorOf(input).querySelector('[data-file-tray]');
    const list = tray.querySelector('[data-file-list]');
    const files = chosenFiles.get(input) || [];
    list.querySelectorAll('img').forEach(image => URL.revokeObjectURL(image.src));
    list.replaceChildren();
    files.forEach(function (file, index) {
      const item = tray.querySelector('template').content.firstElementChild.cloneNode(true);
      const thumb = item.querySelector('[data-file-thumb]');
      if (file.type.startsWith('image/')) {
        const image = document.createElement('img');
        image.src = URL.createObjectURL(file);
        image.alt = '';
        thumb.append(image);
      } else {
        // A file the browser gives no type is checked by the forum when sent: it may still be an image.
        thumb.textContent = file.type === 'application/pdf' ? 'PDF' : 'File';
      }
      const name = item.querySelector('[data-file-name]');
      name.textContent = name.title = file.name;
      item.querySelector('[data-file-size]').textContent = fileSize(file.size);
      const description = item.querySelector('[data-file-description]');
      if (file.type !== 'application/pdf') {
        description.value = descriptions.get(file) || '';
        description.setAttribute('aria-label', 'Description of ' + file.name + ', for readers who cannot see it');
        description.addEventListener('input', () => descriptions.set(file, description.value));
        // Enter ends the description, it does not send the message.
        description.addEventListener('keydown', event => { if (event.key === 'Enter') event.preventDefault(); });
      } else {
        // A PDF needs none, but keeps its place, so the descriptions stay in the order of the files.
        description.type = 'hidden';
        description.value = '';
      }
      const remove = item.querySelector('[data-file-remove]');
      remove.dataset.index = index;
      remove.setAttribute('aria-label', 'Remove file ' + (index + 1) + ' of ' + files.length + ': ' + file.name);
      list.append(item);
    });
    tray.querySelector('[data-file-count]').textContent = files.length + ' of ' + input.dataset.maxFiles +
      ' files · ' + Math.floor(Number(input.dataset.maxBytes) / MB) + ' MB each at most';
    tray.hidden = !files.length;
  }

  const CANNOT_SET_FILES = 'This browser cannot keep or add these files: attach them again with Attach.';

  /**
   * The input itself holds the files, so the form sends them as before. Return false when the browser
   * cannot set them (no DataTransfer constructor, as in Safari before 14.1): the input keeps what it had.
   */
  function setFiles(input, files) {
    let done = true;
    try {
      const transfer = new DataTransfer();
      files.forEach(file => transfer.items.add(file));
      input.files = transfer.files;
      chosenFiles.set(input, files);
    } catch (error) {
      chosenFiles.set(input, Array.from(input.files));
      done = files.length === input.files.length;
    }
    drawFiles(input);
    return done;
  }

  /**
   * Add files to the chosen ones, skipping repeats, and say in the status line how many were attached
   * and why any were refused.
   */
  function addFiles(input, incoming) {
    const files = (chosenFiles.get(input) || []).slice();
    const before = files.length;
    const problems = [];
    Array.from(incoming).forEach(function (file) {
      /** Whether a chosen file is this one again: same name, size and modification time. */
      const same = other => other.name === file.name && other.size === file.size && other.lastModified === file.lastModified;
      if (files.some(same)) return;
      const problem = fileProblem(input, file, files.length);
      if (problem) problems.push(problem);
      else files.push(file);
    });
    if (!setFiles(input, files)) problems.unshift(CANNOT_SET_FILES);
    const count = (chosenFiles.get(input) || []).length;
    const parts = Array.from(new Set(problems));
    if (count > before) {
      parts.unshift((count - before === 1 ? '1 file' : (count - before) + ' files') + ' attached, ' +
        count + ' of ' + input.dataset.maxFiles + '.');
    }
    showStatus(input, parts.join(' '), problems.length > 0);
  }

  /** After the file chooser closes, the focus goes back to Attach, not to the hidden input. */
  function focusAttach(input) {
    if (document.activeElement !== input) return;
    const label = editorOf(input).querySelector('label[for="' + input.id + '"]');
    if (label) label.focus();
  }

  document.addEventListener('change', function (event) {
    const input = event.target;
    if (!input.matches || !input.matches('[data-file-input]')) return;
    if (event.isTrusted) {
      addFiles(input, input.files);
      focusAttach(input);
    } else {
      // A form reset emptied the input.
      chosenFiles.set(input, Array.from(input.files));
      drawFiles(input);
      showStatus(input, '', false);
    }
  });

  document.addEventListener('cancel', function (event) {
    if (event.target.matches && event.target.matches('[data-file-input]')) focusAttach(event.target);
  }, true);

  document.addEventListener('click', function (event) {
    const remove = event.target.closest && event.target.closest('[data-file-remove]');
    if (!remove) return;
    const editor = editorOf(remove);
    const input = editor.querySelector('[data-file-input]');
    const files = (chosenFiles.get(input) || []).slice();
    const index = Number(remove.dataset.index);
    files.splice(index, 1);
    const done = setFiles(input, files);
    showStatus(input, done ? '' : CANNOT_SET_FILES, !done);
    const left = editor.querySelectorAll('[data-file-remove]');
    (left[Math.min(index, left.length - 1)] || editor.querySelector('label[for="' + input.id + '"]')).focus();
  });

  /** Whether a drag event carries files; other drags, such as selected text, are left to the browser. */
  function draggingFiles(event) {
    return event.dataTransfer && Array.from(event.dataTransfer.types).includes('Files');
  }

  // Dragging over the box shows where files go; a drop elsewhere does not open the file in place of the page.
  document.addEventListener('dragenter', function (event) {
    const editor = editorOf(event.target);
    if (!editor || !draggingFiles(event)) return;
    editor.dataset.drags = Number(editor.dataset.drags || 0) + 1;
    editor.setAttribute('data-drop', '');
  });

  document.addEventListener('dragleave', function (event) {
    const editor = editorOf(event.target);
    if (!editor || !draggingFiles(event)) return;
    editor.dataset.drags = Number(editor.dataset.drags || 1) - 1;
    if (Number(editor.dataset.drags) <= 0) {
      delete editor.dataset.drags;
      editor.removeAttribute('data-drop');
    }
  });

  document.addEventListener('dragover', function (event) {
    if (!draggingFiles(event) || !document.querySelector('[data-editor]')) return;
    event.preventDefault();
    if (!editorOf(event.target)) event.dataTransfer.dropEffect = 'none';
  });

  document.addEventListener('drop', function (event) {
    if (!draggingFiles(event) || !document.querySelector('[data-editor]')) return;
    event.preventDefault();
    const editor = editorOf(event.target);
    if (!editor) return;
    delete editor.dataset.drags;
    editor.removeAttribute('data-drop');
    const input = editor.querySelector('[data-file-input]');
    if (input) addFiles(input, event.dataTransfer.files);
    else showStatus(editor, 'Files can be added to new topics and replies.', true);
  });

  // A pasted screenshot is attached; pasted text, also from Word, stays text.
  document.addEventListener('paste', function (event) {
    const textarea = event.target;
    const data = event.clipboardData;
    if (textarea.tagName !== 'TEXTAREA' || !data || !data.files.length || Array.from(data.types).includes('text/plain')) return;
    const editor = editorOf(textarea);
    if (!editor) return;
    event.preventDefault();
    const input = editor.querySelector('[data-file-input]');
    if (input) addFiles(input, data.files);
    else showStatus(editor, 'Files can be added to new topics and replies.', true);
  });

  // Drafts live in this browser only, one per page and field ----------------------------------

  /**
   * The localStorage key of a field's draft: one per page path and field name. A new-topic form also keys
   * on its query (group, record, agenda item), so a prefilled error report and a plain topic keep apart.
   */
  function draftKey(textarea) {
    const form = textarea.form;
    const query = form && form.hasAttribute('data-fresh-form') ? location.search : '';
    return 'forum-draft:' + location.pathname + query + ':' + textarea.name;
  }

  /**
   * Get, set or remove a localStorage item. When storage is blocked or full the item stays as it was: a
   * get returns null, and a set returns false (true when it saved).
   */
  function storage(action, key, value) {
    try {
      if (action === 'get') return window.localStorage.getItem(key);
      if (action === 'set') window.localStorage.setItem(key, value);
      if (action === 'remove') window.localStorage.removeItem(key);
    } catch (error) {
      return action === 'set' ? false : null;
    }
    return action === 'set' ? true : null;
  }

  /** Save a field's draft; the first time this browser refuses, say so in the message box's status line. */
  function saveDraft(textarea) {
    if (storage('set', draftKey(textarea), textarea.value) || textarea.dataset.draftRefused) return;
    textarea.dataset.draftRefused = '1';
    showStatus(textarea, 'This browser does not let the forum keep a draft (storage blocked or full): ' +
      'copy long texts before leaving the page.', true);
  }

  /**
   * Put the saved draft back into a field that is empty or still holds only the text the page put there
   * (such as the link of the record an error report is about), say so, and ask for the record cards of
   * its links.
   */
  function restoreDraft(textarea) {
    const saved = storage('get', draftKey(textarea));
    if (saved && saved !== textarea.value && (!textarea.value || textarea.value === textarea.defaultValue)) {
      textarea.value = saved;
      showStatus(textarea, 'Your unsent draft was restored.', false);
      refreshCards(textarea);
    }
  }

  /**
   * A sent topic keeps its draft until a page the server marks as following its publication
   * (data-draft-published), so text sent into an error (a proxy refusing large files, a timeout, a session
   * that ended) or a send cut short by leaving the page is still there.
   */
  function settleSentDraft() {
    const sent = storage('get', 'forum-sent-draft');
    const alert = document.getElementById('forum-alert');
    if (!sent || !alert || alert.dataset.draftPublished !== '1') return;
    storage('remove', 'forum-sent-draft');
    storage('remove', sent);
  }

  /**
   * Set up a field's draft once: restore it, save it half a second after the last change (a blank field
   * removes it) and, in a form sent without htmx, save it at once on submit and mark it as sent.
   */
  function setUpDraft(textarea) {
    if (textarea.dataset.draftReady) return;
    textarea.dataset.draftReady = '1';
    restoreDraft(textarea);
    let timer = null;
    textarea.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        if (textarea.value.trim()) saveDraft(textarea);
        else storage('remove', draftKey(textarea));
      }, 500);
    });
    const form = textarea.form;
    if (form && !form.hasAttribute('hx-post')) {
      form.addEventListener('submit', function () {
        clearTimeout(timer);
        if (textarea.value.trim()) saveDraft(textarea);
        storage('set', 'forum-sent-draft', draftKey(textarea));
      });
    }
  }

  /** Set up the draft of each textarea[data-draft] inside root (the page, or content htmx loaded). */
  function setUpDrafts(root) {
    root.querySelectorAll('textarea[data-draft]').forEach(setUpDraft);
  }

  // The files of a reply sent back with an error (422), for the form that replaces it.
  let keptFiles = null;

  document.addEventListener('DOMContentLoaded', function () {
    enhance(document);
    settleSentDraft();
    setUpDrafts(document);
  });
  document.addEventListener('htmx:load', function (event) {
    const root = event.detail.elt;
    if (root.querySelectorAll) enhance(root);
    setUpDrafts(root);
    const input = keptFiles && root.querySelector && root.querySelector('[data-file-input]');
    if (input) {
      // A reply sent back with errors: its errors go to the status line and the focus to the first of them.
      const files = keptFiles;
      keptFiles = null;
      const errors = Array.from(root.querySelectorAll('.errorlist')).map(list => list.textContent.trim()).join(' ');
      const kept = !files.length ? '' : setFiles(input, files) ? ' Your files are still attached.' : ' ' + CANNOT_SET_FILES;
      showStatus(input, (errors || 'The reply was not sent.') + kept, true);
      const first = root.querySelector('.errorlist');
      const textarea = root.querySelector('textarea');
      if (first) {
        first.tabIndex = -1;
        first.focus();
      } else if (textarea) {
        textarea.focus();
      }
    }
  });

  // What a reply carried when it was sent: text and files changed meanwhile are kept when it succeeds.
  document.addEventListener('htmx:beforeRequest', function (event) {
    const form = event.detail.elt;
    if (form.id !== 'quick-reply-form') return;
    const input = form.querySelector('[data-file-input]');
    const textarea = form.querySelector('textarea');
    form.sentText = textarea.value;
    form.sentFiles = input ? (chosenFiles.get(input) || []).slice() : [];
    // Saved now, not half a second after the last key, so a reply sent back with an error never brings
    // back an older draft in place of what was sent.
    if (textarea.value.trim()) saveDraft(textarea);
  });

  /** Whether the reply box still holds what was sent (form.sentText and form.sentFiles). */
  function unchangedSince(form) {
    const input = form.querySelector('[data-file-input]');
    const files = input ? (chosenFiles.get(input) || []) : [];
    return form.querySelector('textarea').value === form.sentText && files.length === form.sentFiles.length &&
      files.every((file, index) => file === form.sentFiles[index]);
  }

  document.addEventListener('htmx:afterRequest', function (event) {
    const form = event.detail.elt;
    if (form.id !== 'quick-reply-form') return;
    // A reply answered with a redirect, to the page that shows it, was posted (htmx does not mark that
    // answer successful): its draft goes before that page loads, unless the box changed meanwhile.
    if (event.detail.xhr.getResponseHeader('HX-Redirect')) {
      if (unchangedSince(form)) storage('remove', draftKey(form.querySelector('textarea')));
      return;
    }
    if (!event.detail.successful || onLoginPage(event.detail.xhr)) return;
    const textarea = form.querySelector('textarea');
    const done = (event.detail.xhr.responseText || '').includes('data-held-for-review')
      ? 'Your reply was sent: a moderator reads it before it appears.' : 'Your reply was posted.';
    // The errors and record search of an earlier attempt go; the next reply starts clean.
    form.querySelectorAll('.errorlist').forEach(list => list.remove());
    form.querySelectorAll('[data-record-results]').forEach(results => { results.innerHTML = ''; });
    form.querySelectorAll('[data-record-status]').forEach(status => { status.textContent = ''; });
    if (!unchangedSince(form)) {
      showStatus(textarea, done + ' The box still holds its text and files, with what you changed while it ' +
        'was being sent: take out what was sent before sending again.', false);
      return;
    }
    storage('remove', draftKey(textarea));
    form.reset();
    textarea.value = textarea.defaultValue = '';
    form.querySelectorAll('[data-file-input]').forEach(function (input) {
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });
    // The reset put the record type back; the language list follows it, with no search for an empty box.
    form.querySelectorAll('[data-record-picker]').forEach(picker => languageFollowsType(picker.dataset.prefix));
    textarea.dispatchEvent(new Event('input'));
    window.clearReplyTarget();
    resetEditor(textarea);
    showStatus(textarea, done, false);
  });

  // The posted reply, or the notice that it waits for a moderator, comes into view with the focus, so
  // readers and screen readers find it.
  document.addEventListener('htmx:afterSwap', function (event) {
    if (event.detail.requestConfig.elt.id !== 'quick-reply-form' || event.detail.xhr.status !== 200) return;
    const posts = event.detail.target.querySelectorAll(':scope > article, :scope > [data-held-for-review]');
    const post = posts[posts.length - 1];
    if (!post) return;
    post.tabIndex = -1;
    post.focus({ preventScroll: true });
    post.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  });

  document.addEventListener('htmx:beforeSwap', function (event) {
    if (event.detail.xhr.status === 422 && event.detail.target.id === 'reply-form-container') {
      event.detail.shouldSwap = true;
      event.detail.isError = false;
      const input = event.detail.target.querySelector('[data-file-input]');
      keptFiles = input ? (chosenFiles.get(input) || Array.from(input.files)) : null;
      // The thumbnails of the form being replaced are released.
      event.detail.target.querySelectorAll('[data-file-list] img').forEach(image => URL.revokeObjectURL(image.src));
    }
  });

  // Failed requests ------------------------------------------------------------------------------

  const SIGNED_OUT = 'You are signed out: sign in again, then repeat what you were doing.';
  // Gateway answers: the forum may have done the work before the proxy gave up waiting.
  const GATEWAY = [502, 503, 504, 520, 522, 524];

  /** Whether the request ended on the sign-in page, after the server redirected it there. */
  function onLoginPage(xhr) {
    const alert = document.getElementById('forum-alert');
    const login = alert && alert.dataset.loginUrl;
    try {
      return Boolean(login && xhr.responseURL && new URL(xhr.responseURL).pathname.startsWith(login));
    } catch (error) {
      return false;
    }
  }

  /**
   * What a failed answer means for the user: the forum's own reason when it sent a short line of text
   * (such as "You cannot reply to this discussion."), else what its status says, with what to do.
   */
  function failureText(xhr) {
    const status = xhr.status;
    const text = (xhr.responseText || '').trim();
    if (onLoginPage(xhr)) return SIGNED_OUT;
    if (status >= 400 && status < 500 && text && text.length < 300 && !text.includes('<')) return text;
    if (status === 403) return 'Not allowed: you may be signed out, or the page is out of date. Sign in, or reload the page.';
    if (status === 404) return 'Not found: it was removed or moved. Reload the page.';
    if (status === 413) return 'Too large: send fewer or smaller files.';
    if (GATEWAY.includes(status)) {
      return 'The forum did not answer in time (error ' + status + '); it may have been done. Reload the page before trying again.';
    }
    return 'The forum had an error (' + status + '): try again later.';
  }

  /**
   * Show a failure in the alert bar at the bottom of the page, for controls outside a message box (vote,
   * follow, remove, the checks for new replies, similar topics); source is the element whose request failed,
   * so its next success clears the bar.
   */
  function showAlert(text, source) {
    const alert = document.getElementById('forum-alert');
    if (!alert) return;
    const line = alert.querySelector('[data-alert-text]');
    if (line.textContent !== text || alert.hidden) line.textContent = text;
    alert.hidden = false;
    alert.alertSource = source;
  }

  document.addEventListener('click', function (event) {
    const close = event.target.closest && event.target.closest('[data-alert-close]');
    if (close) close.closest('#forum-alert').hidden = true;
  });

  /**
   * Tell the user about a failed request where they are looking: the reply box for a reply (its text and
   * files are kept), the status line of a message box for its preview, record search and record cards
   * (also visible in the record picker), else the alert bar.
   */
  function requestFailed(event, text) {
    const element = event.detail.elt;
    if (element && element.id === 'quick-reply-form') {
      showStatus(element.querySelector('textarea'), text + ' Your text and files are kept.', true);
      return;
    }
    if (element && element.id && element.id.startsWith('linked-')) {
      // The record cards ask again at the next change of the text.
      delete element.dataset.links;
    }
    const picker = element && element.closest && element.closest('[data-record-picker]');
    const pickerStatus = picker && picker.querySelector('[data-record-status]');
    if (pickerStatus) {
      pickerStatus.textContent = text;
      pickerStatus.classList.remove('sr-only');
      pickerStatus.classList.add('text-red-700');
    }
    const editor = editorOf(element);
    const status = editor && editor.querySelector('[data-editor-status]');
    if (status) {
      showStatus(status, text, true);
      status.setAttribute('data-request-error', '');
    } else if (!pickerStatus) {
      showAlert(text, element);
    }
  }

  document.addEventListener('htmx:beforeSwap', function (event) {
    // A request redirected to the sign-in page must not put that page into the forum's.
    if (event.detail.xhr.status === 200 && onLoginPage(event.detail.xhr)) {
      event.detail.shouldSwap = false;
      // Here htmx names the swap's target as elt; the message goes where the request was made.
      requestFailed({ detail: { elt: event.detail.requestConfig.elt } }, SIGNED_OUT);
    }
  });

  document.addEventListener('htmx:responseError', function (event) {
    const xhr = event.detail.xhr;
    if (xhr.status === 422) return;
    const reply = event.detail.elt && event.detail.elt.id === 'quick-reply-form';
    if (reply && GATEWAY.includes(xhr.status)) {
      requestFailed(event, 'The forum did not answer in time (error ' + xhr.status + '): the reply may have ' +
        'been posted. Reload the topic in another tab before sending it again.');
      return;
    }
    requestFailed(event, (reply ? 'The reply was not sent. ' : '') + failureText(xhr));
  });

  document.addEventListener('htmx:sendError', function (event) {
    const reply = event.detail.elt && event.detail.elt.id === 'quick-reply-form';
    requestFailed(event, reply
      ? 'The connection dropped: the reply may not have been sent. Reload the topic in another tab before sending it again.'
      : 'The forum could not be reached: check the connection and try again.');
  });

  document.addEventListener('htmx:afterRequest', function (event) {
    if (!event.detail.successful || onLoginPage(event.detail.xhr)) return;
    // The element that made the request: a vote or follow form replaced by its answer is no longer in the
    // page, and htmx then names an ancestor as elt.
    const element = event.detail.requestConfig ? event.detail.requestConfig.elt : event.detail.elt;
    const editor = editorOf(element);
    const status = editor && editor.querySelector('[data-editor-status][data-request-error]');
    if (status) {
      status.removeAttribute('data-request-error');
      showStatus(status, '', false);
    }
    const picker = element && element.closest && element.closest('[data-record-picker]');
    const pickerStatus = picker && picker.querySelector('[data-record-status].text-red-700');
    if (pickerStatus) {
      pickerStatus.classList.add('sr-only');
      pickerStatus.classList.remove('text-red-700');
    }
    const alert = document.getElementById('forum-alert');
    if (alert && alert.alertSource === element) alert.hidden = true;
  });

  /** The language list of a record picker is open only for a record type that has a language; returns
   * whether it is. */
  function languageFollowsType(prefix) {
    const type = document.getElementById(prefix + '-type');
    const language = document.getElementById(prefix + '-language');
    const typeHasLanguage = type.selectedOptions[0].dataset.language === '1';
    language.disabled = !typeHasLanguage;
    return typeHasLanguage;
  }

  /** The record search sends the type, the language (where the type has one) and the query. */
  window.forumRecordQuery = function (prefix) {
    const typeHasLanguage = languageFollowsType(prefix);
    const language = document.getElementById(prefix + '-language').value;
    return {type: document.getElementById(prefix + '-type').value, lang: typeHasLanguage ? language : '',
            prefix: prefix, q: document.getElementById(prefix + '-query').value};
  };

  // Typing "Mickey Mouse #219" asks for an issue: the type follows, and the reader can still change it.
  document.addEventListener('input', function (event) {
    const query = event.target;
    if (!query.matches || !query.matches('[data-record-picker] input[type="search"]')) return;
    const type = document.getElementById(query.closest('[data-record-picker]').dataset.prefix + '-type');
    if (/#\s*\S/.test(query.value) && type.value === 'series') type.value = 'issue';
  });

  // A form sent without htmx goes once: a second click while the next page loads would post it again
  // (a second topic, or an error page). Its buttons are disabled only after the browser has read the
  // form, so the button that sent it still sends its name and value.
  document.addEventListener('submit', function (event) {
    const form = event.target;
    if (event.defaultPrevented || form.method !== 'post') return;
    if (form.dataset.sending) {
      event.preventDefault();
      return;
    }
    form.dataset.sending = '1';
    setTimeout(function () {
      form.querySelectorAll('button:not([disabled]), input[type="submit"]:not([disabled])').forEach(function (button) {
        button.disabled = true;
        button.dataset.sendingDisabled = '1';
      });
    }, 0);
  });

  /** Let a form held by the guard above be sent again, with its buttons back. */
  function rearm(form) {
    delete form.dataset.sending;
    form.querySelectorAll('[data-sending-disabled]').forEach(function (button) {
      button.disabled = false;
      delete button.dataset.sendingDisabled;
    });
  }

  // A send stopped by the user (Stop, Escape) leaves the form held: changing anything in it frees it.
  ['input', 'change'].forEach(function (type) {
    document.addEventListener(type, function (event) {
      const form = event.isTrusted && event.target.form;
      if (form && form.dataset.sending) rearm(form);
    });
  });

  // A new-topic form shown again by the Back button starts empty, so nothing left from the
  // previous topic, such as a poll, is posted unseen; an unsent draft comes back. A form sent
  // before the page was left can be sent again.
  window.addEventListener('pageshow', function (event) {
    // The browser may restore the parent field of a reply form whose heading says "the topic".
    const reply = replyForm();
    const cancel = document.getElementById('cancel-reply');
    if (reply && cancel && reply.querySelector('[name="parent"]').value && cancel.classList.contains('hidden')) {
      window.clearReplyTarget();
    }
    if (!event.persisted) return;
    document.querySelectorAll('form[data-sending]').forEach(rearm);
    document.querySelectorAll('form[data-fresh-form]').forEach(function (form) {
      form.reset();
      form.querySelectorAll('details').forEach(function (section) { section.open = false; });
      form.querySelectorAll('[data-file-input]').forEach(function (input) {
        input.dispatchEvent(new Event('change', { bubbles: true }));
      });
      form.querySelectorAll('[data-record-picker]').forEach(picker => languageFollowsType(picker.dataset.prefix));
      form.querySelectorAll('[data-editor] textarea').forEach(function (textarea) {
        resetEditor(textarea);
        restoreDraft(textarea);
        refreshCards(textarea);
      });
    });
  });

  // Menus (details[data-menu]) close on a click elsewhere, when the focus leaves them, and on Escape
  // pressed inside them, which gives the focus back to the menu's button.
  document.addEventListener('click', function (event) {
    document.querySelectorAll('details[data-menu][open]').forEach(function (menu) {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
  document.addEventListener('focusout', function (event) {
    const menu = event.target.closest && event.target.closest('details[data-menu][open]');
    if (menu && event.relatedTarget && !menu.contains(event.relatedTarget)) menu.open = false;
  });
  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    const menu = event.target.closest && event.target.closest('details[data-menu][open]');
    if (!menu) return;
    menu.open = false;
    menu.querySelector('summary').focus();
  });

  /** A picked record becomes a link line of the records field, or a Markdown link in the text. */
  window.forumAddRecord = function (button) {
    const picker = button.closest('[data-record-picker]');
    const textarea = document.getElementById(picker.dataset.target);
    const url = button.dataset.recordUrl;
    if (picker.dataset.mode === 'insert') {
      showWrite(textarea);
      const at = textarea.selectionStart || textarea.value.length;
      const before = textarea.value.slice(0, at);
      const space = before && !/\s$/.test(before) ? ' ' : '';
      const link = space + '[' + button.dataset.recordLabel.replace(/[\[\]]/g, '') + '](' + url + ')';
      textarea.value = textarea.value.slice(0, at) + link + textarea.value.slice(at);
      textarea.selectionStart = textarea.selectionEnd = at + link.length;
      textarea.dispatchEvent(new Event('input'));
    } else {
      const lines = textarea.value.split('\n').map(line => line.trim()).filter(Boolean);
      if (!lines.includes(url)) lines.push(url);
      textarea.value = lines.join('\n');
      textarea.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const query = picker.querySelector('input[type="search"]');
    // A search still running would bring its results back under the emptied box.
    htmx.trigger(query, 'htmx:abort');
    picker.querySelector('[data-record-results]').innerHTML = '';
    const status = picker.querySelector('[data-record-status]');
    if (status) {
      // For screen readers, as the search's counts: no longer the red line of an earlier failed search.
      status.textContent = 'Added ' + button.dataset.recordLabel + '.';
      status.classList.add('sr-only');
      status.classList.remove('text-red-700');
    }
    query.value = '';
    (picker.dataset.mode === 'insert' ? textarea : query).focus();
  };
})();
