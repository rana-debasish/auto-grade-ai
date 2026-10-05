/* Small framework-free UI primitives shared by the legacy pages and new screens. */
(function (global) {
  const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);

  function button(label, { variant = 'primary', loading = false, disabled = false, type = 'button', className = '' } = {}) {
    return `<button type="${escapeHTML(type)}" class="ui-button ui-button-${escapeHTML(variant)} ${escapeHTML(className)}"${disabled || loading ? ' disabled' : ''}>${loading ? '<span class="ui-spinner" aria-hidden="true"></span>' : ''}${escapeHTML(label)}</button>`;
  }

  function setButtonLoading(element, loading, label = 'Working…') {
    if (!element) return;
    if (loading) {
      element.dataset.uiOriginal = element.innerHTML;
      element.innerHTML = `<span class="ui-spinner" aria-hidden="true"></span>${escapeHTML(label)}`;
      element.disabled = true;
      element.setAttribute('aria-busy', 'true');
    } else {
      element.innerHTML = element.dataset.uiOriginal || element.innerHTML;
      element.disabled = false;
      element.removeAttribute('aria-busy');
      delete element.dataset.uiOriginal;
    }
  }

  const statusMap = {
    queued: ['Queued', 'queued'], pending: ['Queued', 'queued'],
    processing: ['Processing', 'processing'], done: ['Done', 'done'], evaluated: ['Done', 'done'],
    failed: ['Failed', 'failed'], error: ['Failed', 'failed'], needs_review: ['Needs review', 'needs-review']
  };
  function statusBadge(status) {
    const [label, kind] = statusMap[String(status || '').toLowerCase()] || ['Unknown', 'queued'];
    return `<span class="status-badge status-${kind}"><span class="status-dot"></span>${label}</span>`;
  }

  function stepper(stage, status = 'processing') {
    const steps = [['uploaded', 'Uploaded'], ['ocr', 'OCR'], ['scoring', 'Scoring'], ['feedback', 'Feedback'], ['done', 'Done']];
    const current = status === 'queued' || status === 'pending' ? -1 : steps.findIndex(([key]) => key === stage);
    return `<ol class="ui-stepper" aria-label="Evaluation progress">${steps.map(([key, label], index) => {
      const state = status === 'failed' || status === 'error' ? (index === Math.max(0, current) ? 'failed' : index < current ? 'complete' : '') : index < current || status === 'done' && key === 'done' ? 'complete' : index === current ? 'current' : '';
      return `<li class="${state}"><span class="step-marker">${state === 'complete' ? '✓' : index + 1}</span><span>${label}</span></li>`;
    }).join('')}</ol>`;
  }

  function card({ title = '', actions = '', content = '', className = '' } = {}) {
    return `<section class="ui-card ${escapeHTML(className)}">${title || actions ? `<header class="ui-card-header"><h2>${escapeHTML(title)}</h2>${actions}</header>` : ''}<div class="ui-card-body">${content}</div></section>`;
  }

  function emptyState(title, detail = '', action = '') {
    return `<div class="ui-empty"><span class="ui-empty-mark" aria-hidden="true">✳</span><strong>${escapeHTML(title)}</strong>${detail ? `<span>${escapeHTML(detail)}</span>` : ''}${action}</div>`;
  }

  function skeleton({ lines = 3, className = '' } = {}) {
    return `<div class="ui-skeleton ${escapeHTML(className)}" aria-label="Loading">${Array.from({ length: lines }, (_, i) => `<i class="${i === lines - 1 ? 'short' : ''}"></i>`).join('')}</div>`;
  }

  function scoreRing(score, total, { size = 104, label = 'Score' } = {}) {
    const pct = total > 0 ? Math.max(0, Math.min(100, Number(score) / Number(total) * 100)) : 0;
    return `<div class="score-ring" role="img" aria-label="${escapeHTML(label)}: ${escapeHTML(score)}/${escapeHTML(total)}" style="--score:${pct}%;--ring-size:${size}px"><div><strong>${escapeHTML(score)}<small>/${escapeHTML(total)}</small></strong><span>${Math.round(pct)}%</span></div></div>`;
  }

  function table({ rows = [], columns = [], pageSize = 10, empty = 'Nothing to show yet.' } = {}) {
    let page = 0, sortKey = '', direction = 1;
    const root = document.createElement('div');
    root.className = 'ui-table-wrap';
    const render = () => {
      const sorted = [...rows].sort((a, b) => sortKey ? String(a[sortKey] ?? '').localeCompare(String(b[sortKey] ?? ''), undefined, { numeric: true }) * direction : 0);
      const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize)); page = Math.min(page, pageCount - 1);
      root.innerHTML = sorted.length ? `<div class="table-responsive"><table class="ui-table"><thead><tr>${columns.map(col => `<th scope="col"><button type="button" data-sort="${escapeHTML(col.key)}">${escapeHTML(col.label)}${sortKey === col.key ? (direction > 0 ? ' ↑' : ' ↓') : ''}</button></th>`).join('')}</tr></thead><tbody>${sorted.slice(page * pageSize, (page + 1) * pageSize).map(row => `<tr>${columns.map(col => `<td>${col.render ? col.render(row[col.key], row) : escapeHTML(row[col.key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div><footer class="ui-table-footer"><label>Rows <select aria-label="Rows per page"><option>10</option><option>25</option><option>50</option></select></label><span>${sorted.length ? `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, sorted.length)} of ${sorted.length}` : '0 results'}</span><button type="button" data-page="prev" aria-label="Previous page"${page === 0 ? ' disabled' : ''}>←</button><button type="button" data-page="next" aria-label="Next page"${page >= pageCount - 1 ? ' disabled' : ''}>→</button></footer>` : emptyState(empty);
      root.querySelectorAll('[data-sort]').forEach(el => el.addEventListener('click', () => { direction = sortKey === el.dataset.sort ? -direction : 1; sortKey = el.dataset.sort; render(); }));
      root.querySelector('[data-page="prev"]')?.addEventListener('click', () => { page--; render(); });
      root.querySelector('[data-page="next"]')?.addEventListener('click', () => { page++; render(); });
      const select = root.querySelector('select'); if (select) { select.value = String(pageSize); select.addEventListener('change', () => { pageSize = Number(select.value); page = 0; render(); }); }
    };
    render(); return root;
  }

  function toast(message, type = 'info', duration = 4000) {
    let stack = document.querySelector('.ui-toast-stack');
    if (!stack) { stack = document.createElement('div'); stack.className = 'ui-toast-stack'; stack.setAttribute('aria-live', 'polite'); document.body.append(stack); }
    const item = document.createElement('div'); item.className = `ui-toast ui-toast-${type}`;
    const text = document.createElement('span'); text.textContent = message;
    const close = document.createElement('button'); close.type = 'button'; close.setAttribute('aria-label', 'Dismiss notification'); close.textContent = '×'; close.onclick = () => item.remove();
    item.append(text, close); stack.append(item); setTimeout(() => item.remove(), duration); return item;
  }

  function openModal(dialog) {
    if (!dialog) return;
    dialog.hidden = false; dialog.setAttribute('aria-modal', 'true'); dialog.setAttribute('role', 'dialog');
    const focusable = () => [...dialog.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')];
    dialog._uiKeyHandler = event => {
      if (event.key === 'Escape') { closeModal(dialog); return; }
      if (event.key === 'Tab') { const items = focusable(); if (!items.length) return; const first = items[0], last = items[items.length - 1]; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); } }
    };
    document.addEventListener('keydown', dialog._uiKeyHandler); focusable()[0]?.focus();
  }
  function closeModal(dialog) { if (!dialog) return; dialog.hidden = true; if (dialog._uiKeyHandler) document.removeEventListener('keydown', dialog._uiKeyHandler); }

  function fileDropzone(input, { maxBytes = 10 * 1024 * 1024, accept = ['application/pdf', 'image/png', 'image/jpeg'], onChange = () => {} } = {}) {
    if (!input) return null;
    const zone = document.createElement('div'); zone.className = 'ui-dropzone'; zone.tabIndex = 0;
    zone.innerHTML = '<strong>Drop a script here</strong><span>or click to choose a PDF, PNG, or JPG · up to 10 MB</span><div class="ui-file-info" aria-live="polite"></div><button type="button" class="ui-button ui-button-secondary">Choose file</button>';
    const info = zone.querySelector('.ui-file-info');
    const handle = file => {
      info.className = 'ui-file-info';
      if (!file) { input.value = ''; onChange(null); return; }
      if (!accept.includes(file.type) || file.size <= 0 || file.size > maxBytes) { info.textContent = file.size > maxBytes ? 'File exceeds the 10 MB limit.' : 'Choose a non-empty PDF, PNG, or JPG file.'; info.classList.add('error'); input.value = ''; onChange(null); return; }
      info.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
      if (file.type.startsWith('image/')) { const preview = document.createElement('img'); preview.alt = 'Selected file preview'; preview.src = URL.createObjectURL(file); preview.className = 'ui-file-preview'; info.append(preview); }
      onChange(file);
    };
    zone.onclick = event => { if (event.target.tagName !== 'BUTTON') input.click(); };
    zone.querySelector('button').onclick = () => input.click();
    zone.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); input.click(); } };
    zone.ondragover = event => { event.preventDefault(); zone.classList.add('dragging'); };
    zone.ondragleave = () => zone.classList.remove('dragging');
    zone.ondrop = event => { event.preventDefault(); zone.classList.remove('dragging'); const file = event.dataTransfer.files[0]; if (file) { const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files; handle(file); } };
    input.addEventListener('change', () => handle(input.files[0]));
    input.parentNode.insertBefore(zone, input); input.classList.add('visually-hidden'); return { element: zone, clear: () => handle(null) };
  }

  global.AppUI = { escapeHTML, Button: { render: button, setLoading: setButtonLoading }, Card: { render: card }, StatusBadge: { render: statusBadge }, Stepper: { render: stepper }, Table: { create: table }, Toast: { show: toast }, Modal: { open: openModal, close: closeModal }, Skeleton: { render: skeleton }, EmptyState: { render: emptyState }, FileDropzone: { mount: fileDropzone }, ScoreRing: { render: scoreRing } };
})(window);
