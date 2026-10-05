/* ================================================================
   Student Module — Dashboard, Submit, Results
   ================================================================ */

// ---- Skeleton Loaders ----

function showStatSkeletons() {
    ['stat-assignments', 'stat-submitted', 'stat-avg-score'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<div class="skeleton skeleton-stat"></div>';
    });
}

function showTableSkeleton(tbody, cols = 5, rows = 3) {
    if (!tbody) return;
    let html = '';
    for (let i = 0; i < rows; i++) {
        html += '<tr>';
        for (let j = 0; j < cols; j++) {
            const width = j === 0 ? 'long' : (j === cols - 1 ? 'short' : 'medium');
            html += `<td><div class="skeleton skeleton-text ${width}"></div></td>`;
        }
        html += '</tr>';
    }
    tbody.innerHTML = html;
}

function showResultsSkeletons(container) {
    if (!container) return;
    let html = '';
    for (let i = 0; i < 2; i++) {
        html += `
        <div class="content-card">
            <div class="skeleton-row">
                <div class="skeleton skeleton-text long" style="flex: 1"></div>
                <div class="skeleton skeleton-text short" style="width: 80px"></div>
            </div>
            <div class="row g-3 mt-2">
                <div class="col-md-2"><div class="skeleton skeleton-circle mx-auto"></div></div>
                <div class="col-md-3"><div class="skeleton skeleton-stat"></div></div>
                <div class="col-md-3"><div class="skeleton skeleton-stat"></div></div>
                <div class="col-md-4"><div class="skeleton skeleton-stat"></div></div>
            </div>
        </div>`;
    }
    container.innerHTML = html;
}

// ---- Dashboard ----

async function loadDashboard() {
    // Show skeletons while loading
    showStatSkeletons();
    showTableSkeleton(document.getElementById('assignments-body'), 5, 3);
    
    try {
        const [assignData, resultData] = await Promise.all([
            apiRequest('/student/assignments'),
            apiRequest('/student/results'),
        ]);

        const assignments = assignData.assignments || [];
        const results = resultData.results || [];

        // Stats with animation
        const pendingAssignments = assignments.filter(a => !results.some(r => r.assignment_id === a.id)).length;
        animateValue('stat-assignments', pendingAssignments);
        animateValue('stat-submitted', results.length);

        const evaluated = results.filter(r => ['done', 'needs_review', 'evaluated'].includes(r.status));
        if (evaluated.length > 0) {
            const avg = evaluated.reduce((sum, r) => sum + r.marks_obtained, 0) / evaluated.length;
            animateValue('stat-avg-score', avg.toFixed(1));
        } else {
            document.getElementById('stat-avg-score').textContent = 'N/A';
        }

        // Assignments table
        const tbody = document.getElementById('assignments-body');
        if (assignments.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5">
                        <div class="empty-state">
                            <div class="empty-state-icon" aria-hidden="true"><svg class="theme-empty-icon" viewBox="0 0 48 48"><path d="M8 10.5A4.5 4.5 0 0 1 12.5 6H40v30H12.5A4.5 4.5 0 0 0 8 40.5v-30Z"/><path d="M8 34.5a4.5 4.5 0 0 1 4.5-4.5H40M17 14h15M17 20h15"/></svg></div>
                            <div class="empty-state-title">No assignments yet</div>
                            <div class="empty-state-text">Check back later for new assignments from your facultys.</div>
                        </div>
                    </td>
                </tr>`;
        } else {
            tbody.innerHTML = assignments.map((a, idx) => `
                <tr style="animation: cardSlideUp 0.3s ease-out ${idx * 0.1}s both">
                    <td><strong>${escapeHtml(a.title)}</strong></td>
                    <td>${escapeHtml(a.subject)}</td>
                    <td>${a.total_marks}</td>
                    <td>${formatDueDate(a.due_date)}</td>
                    <td><a href="/student/submit.html?assignment=${encodeURIComponent(a.id)}" class="btn btn-primary btn-sm">Submit</a></td>
                </tr>`).join('');
        }
        const recent = document.getElementById('recent-results');
        if (recent) recent.innerHTML = results.length ? results.slice(0, 4).map(item => {
            const scored = ['done', 'needs_review', 'evaluated'].includes(item.status);
            return `<a class="recent-result" href="/student/submission.html?id=${encodeURIComponent(item.id)}"><span><strong>${escapeHtml(item.assignment_title || 'Assignment')}</strong><small>${escapeHtml(item.assignment_subject || '')} · ${formatDate(item.submitted_at)}</small></span><span>${scored ? AppUI.ScoreRing.render(item.marks_obtained, item.total_marks || 0, { size: 68 }) : AppUI.StatusBadge.render(item.status)}</span></a>`;
        }).join('') : AppUI.EmptyState.render('No results yet', 'Submit an answer script to see evaluation progress here.', '<a href="/student/submit.html" class="btn btn-primary student-submit-cta">Submit Answer</a>');

    } catch (err) {
        console.error('Dashboard load error:', err);
        showToast('Failed to load dashboard data', 'error');
    }
}

// ---- Animate Number Value ----

function animateValue(elementId, endValue, duration = 500) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    const isNumber = !isNaN(parseFloat(endValue));
    if (!isNumber) {
        el.textContent = endValue;
        return;
    }
    
    const start = 0;
    const end = parseFloat(endValue);
    const startTime = performance.now();
    const isDecimal = endValue.toString().includes('.');
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = start + (end - start) * easeOut;
        el.textContent = isDecimal ? current.toFixed(1) : Math.round(current);
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

// ---- Load Assignments (for submit page) ----

async function loadAssignments() {
    try {
        const data = await apiRequest('/student/assignments');
        const select = document.getElementById('assignment-select');
        if (!select) return;

        const assignments = data.assignments || [];
        if (assignments.length === 0) {
            select.innerHTML = '<option value="">No assignments available</option>';
            return;
        }

        select.innerHTML = '<option value="">-- Select Assignment --</option>' +
            assignments.map(a =>
                `<option value="${a.id}">${escapeHtml(a.title)} (${escapeHtml(a.subject)}) — ${a.total_marks} marks</option>`
            ).join('');

        // Auto-select if assignment ID in URL
        const params = new URLSearchParams(window.location.search);
        const preselect = params.get('assignment');
        if (preselect) {
            select.value = preselect;
        }
    } catch (err) {
        console.error('Load assignments error:', err);
        showToast('Failed to load assignments', 'error');
    }
}

// ---- Drag & Drop Upload Zone ----

let selectedFile = null;

function setupDragDropUpload() {
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const previewContainer = document.getElementById('upload-preview-container');
    
    if (!uploadZone || !fileInput) return;

    if (window.AppUI?.FileDropzone) {
        uploadZone.hidden = true;
        AppUI.FileDropzone.mount(fileInput, { maxBytes: 10 * 1024 * 1024, onChange: file => { selectedFile = file; } });
        return;
    }
    
    // Click to upload
    uploadZone.addEventListener('click', () => fileInput.click());
    
    // Drag events
    ['dragenter', 'dragover'].forEach(event => {
        uploadZone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadZone.classList.add('drag-over');
        });
    });
    
    ['dragleave', 'drop'].forEach(event => {
        uploadZone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadZone.classList.remove('drag-over');
        });
    });
    
    // Drop handler
    uploadZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });
    
    // File input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileSelect(fileInput.files[0]);
        }
    });
}

function handleFileSelect(file) {
    const validTypes = ['application/pdf', 'image/png', 'image/jpeg'];
    const maxSize = 10 * 1024 * 1024;
    
    if (!validTypes.includes(file.type)) {
        showToast('Choose a PDF, PNG, or JPG file.', 'error');
        return;
    }
    
    if (file.size > maxSize) {
        showToast('File is too large. Maximum size is 10 MB.', 'error');
        return;
    }
    
    selectedFile = file;
    showFilePreview(file);
}

function showFilePreview(file) {
    const previewContainer = document.getElementById('upload-preview-container');
    const uploadZone = document.getElementById('upload-zone');
    
    if (!previewContainer) return;
    
    const fileIcons = {
        'application/pdf': '📄',
        'image/png': '🖼️',
        'image/jpeg': '🖼️',
        'text/plain': '📝'
    };
    
    const formatFileSize = (bytes) => {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };
    
    previewContainer.innerHTML = `
        <div class="upload-preview">
            <span class="upload-preview-icon">${fileIcons[file.type] || '📁'}</span>
            <div class="upload-preview-info">
                <div class="upload-preview-name">${escapeHtml(file.name)}</div>
                <div class="upload-preview-size">${formatFileSize(file.size)}</div>
            </div>
            <button type="button" class="upload-preview-remove" onclick="removeSelectedFile()">✕</button>
        </div>
    `;
    
    if (uploadZone) uploadZone.style.display = 'none';
}

function removeSelectedFile() {
    selectedFile = null;
    const previewContainer = document.getElementById('upload-preview-container');
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    
    if (previewContainer) previewContainer.innerHTML = '';
    if (uploadZone) uploadZone.style.display = 'block';
    if (fileInput) fileInput.value = '';
}

// ---- Submit Form ----

function setupSubmitForm() {
    const form = document.getElementById('submit-form');
    if (!form) return;
    
    // Setup drag & drop
    setupDragDropUpload();

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('submit-btn');
        const overlay = document.getElementById('loading-overlay');

        const assignmentId = document.getElementById('assignment-select').value;
        const fileInput = document.getElementById('file-input');
        const file = selectedFile || (fileInput.files ? fileInput.files[0] : null);

        if (!assignmentId) {
            showToast('Please select an assignment', 'warning');
            return;
        }

        if (!file) {
            showToast('Please select a file to upload', 'warning');
            return;
        }

        const formData = new FormData();
        formData.append('assignment_id', assignmentId);
        formData.append('file', file);

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...';
        overlay.classList.remove('d-none');

        try {
            const data = await apiRequest('/student/submit', {
                method: 'POST',
                body: formData,
            });

            overlay.classList.add('d-none');
            showToast('Answer submitted! Evaluation in progress...', 'success');
            window.location.href = `/student/submission.html?id=${encodeURIComponent(data.submission.id)}`;

        } catch (err) {
            overlay.classList.add('d-none');
            showToast(err.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Submit for Evaluation';
        }
    });
}

// ---- Display Single Result ----

function displayResult(submission) {
    const card = document.getElementById('result-card');
    const content = document.getElementById('result-content');
    if (!card || !content) return;

    card.classList.remove('d-none');
    const fb = submission.feedback || {};
    const ka = fb.keyword_analysis || {};

    content.innerHTML = `
        <div class="row g-3 mb-3">
            <div class="col-md-3 text-center">
                <div class="grade-display ${getGradeClass(fb.grade)}">${fb.grade || 'N/A'}</div>
                <div class="mt-1 small text-muted">Grade</div>
            </div>
            <div class="col-md-3 text-center">
                <div class="stat-value">${fb.marks_obtained || submission.marks_obtained}/${fb.total_marks || '-'}</div>
                <div class="small text-muted">Marks</div>
            </div>
            <div class="col-md-3 text-center">
                <div class="stat-value">${fb.similarity_percentage || (submission.similarity_score * 100).toFixed(1)}%</div>
                <div class="small text-muted">Similarity</div>
            </div>
            <div class="col-md-3 text-center">
                <div class="stat-value">${ka.keyword_overlap || 0}%</div>
                <div class="small text-muted">Keyword Match</div>
            </div>
        </div>

        ${fb.strengths ? `
        <div class="feedback-section">
            <h6 class="text-success">Strengths</h6>
            <ul>${fb.strengths.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
        </div>` : ''}

        ${fb.weaknesses && fb.weaknesses.length ? `
        <div class="feedback-section mt-2">
            <h6 class="text-danger">Areas for Improvement</h6>
            <ul>${fb.weaknesses.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul>
        </div>` : ''}

        ${fb.suggestions && fb.suggestions.length ? `
        <div class="feedback-section mt-2">
            <h6 class="text-info">Suggestions</h6>
            <ul>${fb.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
        </div>` : ''}

        ${ka.matched_keywords ? `
        <div class="feedback-section mt-2">
            <h6>Keywords Analysis</h6>
            <div>
                <span class="small fw-bold text-success">Matched:</span>
                ${ka.matched_keywords.map(k => `<span class="keyword-tag keyword-matched">${escapeHtml(k)}</span>`).join('')}
            </div>
            ${ka.missing_keywords && ka.missing_keywords.length ? `
            <div class="mt-1">
                <span class="small fw-bold text-danger">Missing:</span>
                ${ka.missing_keywords.map(k => `<span class="keyword-tag keyword-missing">${escapeHtml(k)}</span>`).join('')}
            </div>` : ''}
        </div>` : ''}
    `;
}

// ---- Load All Results (with auto-refresh) ----

let _resultsRefreshTimer = null;
let _resultsFirstLoad = true;

async function loadResults() {
    const container = document.getElementById('results-container');
    if (!container) return;
    
    // Show skeleton on first load
    if (_resultsFirstLoad) {
        showResultsSkeletons(container);
        _resultsFirstLoad = false;
    }

    try {
        const data = await apiRequest('/student/results');
        const results = data.results || [];

        if (results.length === 0) {
            container.innerHTML = `
                <div class="content-card">
                    <div class="empty-state">
                        <div class="empty-state-icon" aria-hidden="true"><svg class="theme-empty-icon" viewBox="0 0 48 48"><path d="M12 7h17l8 8v26H12z"/><path d="M29 7v9h8M18 24h13M18 30h13M18 36h8"/></svg></div>
                        <div class="empty-state-title">No submissions yet</div>
                        <div class="empty-state-text">Submit an answer to see your results here.</div>
                        <a href="/student/submit.html" class="btn btn-primary student-submit-cta">Submit Answer</a>
                    </div>
                </div>`;
            return;
        }

        // Auto-refresh if any submissions are still processing
        const hasPending = results.some(r => ['queued', 'processing', 'pending'].includes(r.status));
        if (hasPending && !_resultsRefreshTimer) {
            _resultsRefreshTimer = setInterval(() => loadResults(), 3000);
        } else if (!hasPending && _resultsRefreshTimer) {
            clearInterval(_resultsRefreshTimer);
            _resultsRefreshTimer = null;
        }

        container.innerHTML = results.map(r => {
            const fb = r.feedback || {};
            const ka = fb.keyword_analysis || {};
            const isEvaluated = ['done', 'needs_review', 'evaluated'].includes(r.status);

            return `
            <div class="content-card">
                <div class="d-flex justify-content-between align-items-start mb-3">
                    <div>
                        <h5 class="mb-1">${escapeHtml(r.assignment_title || 'Assignment')}</h5>
                        <span class="text-muted small">${escapeHtml(r.assignment_subject || '')} | Submitted ${formatDate(r.submitted_at)}</span>
                    </div>
                    ${AppUI.StatusBadge.render(r.status)}
                </div>

                ${isEvaluated ? `
                <div class="row g-3 mb-3">
                    <div class="col-md-2 text-center">
                        <div class="grade-display ${getGradeClass(fb.grade)}">${fb.grade || 'N/A'}</div>
                    </div>
                    <div class="col-md-3">
                        <div class="fw-bold">${r.marks_obtained}/${r.total_marks || '-'}</div>
                        <div class="small text-muted">Marks Obtained</div>
                    </div>
                    <div class="col-md-3">
                        <div class="fw-bold">${fb.similarity_percentage || (r.similarity_score * 100).toFixed(1)}%</div>
                        <div class="small text-muted">Similarity Score</div>
                    </div>
                    <div class="col-md-4">
                        <div class="fw-bold">${ka.keyword_overlap || 0}%</div>
                        <div class="small text-muted">Keyword Match</div>
                    </div>
                </div>

                ${fb.strengths ? `
                <div class="feedback-section">
                    <h6 class="text-success">Strengths</h6>
                    <ul class="mb-0">${fb.strengths.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
                </div>` : ''}

                ${fb.weaknesses && fb.weaknesses.length ? `
                <div class="feedback-section mt-2">
                    <h6 class="text-danger">Areas for Improvement</h6>
                    <ul class="mb-0">${fb.weaknesses.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul>
                </div>` : ''}

                ${fb.suggestions && fb.suggestions.length ? `
                <div class="feedback-section mt-2">
                    <h6 class="text-info">Suggestions</h6>
                    <ul class="mb-0">${fb.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
                </div>` : ''}

                ${ka.matched_keywords ? `
                <div class="feedback-section mt-2">
                    <h6>Keywords</h6>
                    <span class="small fw-bold text-success">Matched: </span>
                    ${ka.matched_keywords.map(k => `<span class="keyword-tag keyword-matched">${escapeHtml(k)}</span>`).join('')}
                    ${ka.missing_keywords && ka.missing_keywords.length ? `
                    <br><span class="small fw-bold text-danger mt-1 d-inline-block">Missing: </span>
                    ${ka.missing_keywords.map(k => `<span class="keyword-tag keyword-missing">${escapeHtml(k)}</span>`).join('')}
                    ` : ''}
                </div>` : ''}

                <a class="btn btn-outline-primary btn-sm mt-2" href="/student/submission.html?id=${encodeURIComponent(r.id)}">View submission details</a>
                ` : `
                <p class="text-muted">${escapeHtml(r.progress_step || (r.status === 'failed' ? r.error_message : 'Waiting to start evaluation...'))}</p>
                <a class="btn btn-outline-primary btn-sm" href="/student/submission.html?id=${encodeURIComponent(r.id)}">Track evaluation</a>
                `}
            </div>`;
        }).join('');

    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
    }
}

// ---- Helpers ----

function getGradeClass(grade) {
    if (!grade) return '';
    const g = grade.charAt(0).toUpperCase();
    if (g === 'O') return 'grade-o';
    if (g === 'A') return 'grade-a';
    if (g === 'B') return 'grade-b';
    if (g === 'C') return 'grade-c';
    return 'grade-f';
}

function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function retryEvaluation(submissionId) {
    try {
        await apiRequest(`/student/retry/${submissionId}`, { method: 'POST' });
        showAlert('Re-evaluation started. Please wait...', 'success');
        loadResults();
    } catch (err) {
        showAlert(err.message);
    }
}

function formatDueDate(iso) {
    if (!iso) return 'No due date';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return 'Date unavailable';
    const remaining = date.getTime() - Date.now();
    const days = Math.ceil(remaining / 86400000);
    const tone = remaining < 86400000 ? 'urgent' : days <= 2 ? 'soon' : '';
    const label = remaining < 0 ? 'Past due' : remaining < 86400000 ? `${Math.max(1, Math.ceil(remaining / 3600000))} hours left` : days === 1 ? '1 day left' : `${days} days left`;
    return `${escapeHtml(date.toLocaleDateString())} <span class="due-chip ${tone}">${label}</span>`;
}

async function loadSubmissionDetail() {
    const root = document.getElementById('submission-detail');
    if (!root) return;
    const id = new URLSearchParams(location.search).get('id');
    if (!id) { root.textContent = 'Submission ID is missing.'; return; }
    let age = 0;
    let stopped = false;
    let fileObjectUrl = '';
    window.addEventListener('beforeunload', () => { if (fileObjectUrl) URL.revokeObjectURL(fileObjectUrl); }, { once: true });
    const render = submission => {
        const status = submission.status;
        const result = submission.final_result || {};
        const questions = result.questions || [];
        const busy = ['queued', 'processing'].includes(status);
        root.innerHTML = `<section class="content-card"><div class="d-flex justify-content-between align-items-center flex-wrap gap-2"><div><span class="text-muted small">${escapeHtml(submission.assignment?.subject || '')}</span><h2>${escapeHtml(submission.assignment?.title || 'Submission')}</h2><span class="small text-muted">Submitted ${formatDate(submission.submitted_at)}</span></div>${AppUI.StatusBadge.render(status)}</div>${busy ? `${AppUI.Stepper.render(submission.stage, status)}<p>${escapeHtml(submission.progress_step || 'Reading your handwriting...')}</p>` : ''}${status === 'failed' ? `<p class="text-danger">${escapeHtml(submission.error || 'Evaluation failed.')}</p><button id="retry-detail" class="btn btn-primary">Retry evaluation</button>` : ''}${!busy && status !== 'failed' ? `<div class="detail-score">${AppUI.ScoreRing.render(result.total ?? submission.marks_obtained, submission.assignment?.total_marks || 0)}<div><strong>${submission.reviewed ? 'Reviewed by faculty' : 'Evaluation complete'}</strong>${submission.reviewed ? `<span class="status-badge status-done">Reviewed by faculty</span>` : ''}<p>${escapeHtml(result.overall_feedback?.summary || '')}</p></div></div><div class="table-responsive"><table class="table table-custom"><thead><tr><th>Question</th><th>Marks</th><th>Feedback</th><th>Confidence</th></tr></thead><tbody>${questions.map(q => `<tr><td>${escapeHtml(q.question || `Question ${q.q_no}`)}</td><td>${q.marks}/${q.max_marks}</td><td>${escapeHtml(q.feedback || '')}</td><td>${Math.round((q.confidence || 0) * 100)}%</td></tr>`).join('')}</tbody></table></div><div class="submission-source"><section><h3>Original answer</h3>${fileObjectUrl ? (['png','jpg','jpeg'].includes(submission.file_type) ? `<img class="submission-image" src="${fileObjectUrl}" alt="Original submitted answer">` : `<iframe class="submission-pdf" title="Original submitted answer" src="${fileObjectUrl}"></iframe>`) : '<p class="text-muted">File preview is unavailable.</p>'}</section><section><h3>Extracted text</h3><pre class="ocr-preview">${escapeHtml(submission.ocr_text || 'No text was extracted.')}</pre></section></div></section>` : ''}`;
        root.querySelector('#retry-detail')?.addEventListener('click', async event => { AppUI.Button.setLoading(event.currentTarget, true, 'Queueing retry…'); try { await apiRequest(`/submissions/${id}/retry`, { method: 'POST' }); age = 0; poll(); } catch (error) { showToast(error.message, 'error'); AppUI.Button.setLoading(event.currentTarget, false); } });
    };
    const poll = async () => {
        if (stopped) return;
        try {
            const { submission } = await apiRequest(`/submissions/${id}`);
            if (!['queued', 'processing', 'failed'].includes(submission.status) && submission.file_url && !fileObjectUrl) {
                const fileResponse = await fetch(submission.file_url, { headers: { Authorization: `Bearer ${getToken()}` } });
                if (fileResponse.ok) { fileObjectUrl = URL.createObjectURL(await fileResponse.blob()); submission.file_object_url = fileObjectUrl; }
            }
            render(submission);
            if (['queued', 'processing'].includes(submission.status)) {
                age += age < 60 ? 2 : 5;
                setTimeout(poll, age <= 60 ? 2000 : 5000);
            } else stopped = true;
        } catch (error) { root.textContent = error.message; stopped = true; }
    };
    poll();
}
