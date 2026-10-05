/* ================================================================
   faculty Module — Dashboard, Assignment Management, Reports
   ================================================================ */

// ---- Skeleton Loaders ----

function showfacultyStatSkeletons() {
    ['stat-assignments', 'stat-submissions', 'stat-evaluated', 'stat-avg'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<div class="skeleton skeleton-stat"></div>';
    });
}

function showfacultyTableSkeleton(tbody, cols = 6, rows = 5) {
    if (!tbody) return;
    let html = '';
    for (let i = 0; i < rows; i++) {
        html += '<tr>';
        for (let j = 0; j < cols; j++) {
            const width = j === 0 ? 'medium' : (j === cols - 1 ? 'short' : 'medium');
            html += `<td><div class="skeleton skeleton-text ${width}"></div></td>`;
        }
        html += '</tr>';
    }
    tbody.innerHTML = html;
}

function showReportsSkeletons(container) {
    if (!container) return;
    let html = '';
    for (let i = 0; i < 2; i++) {
        html += `
        <div class="content-card">
            <div class="skeleton-row">
                <div class="skeleton skeleton-text long" style="flex: 1"></div>
            </div>
            <div class="row g-3 mt-2">
                <div class="col-md-2"><div class="skeleton skeleton-stat"></div></div>
                <div class="col-md-2"><div class="skeleton skeleton-stat"></div></div>
                <div class="col-md-2"><div class="skeleton skeleton-stat"></div></div>
                <div class="col-md-3"><div class="skeleton skeleton-stat"></div></div>
                <div class="col-md-3"><div class="skeleton skeleton-stat"></div></div>
            </div>
        </div>`;
    }
    container.innerHTML = html;
}

// ---- Animate Value ----

function animatefacultyValue(elementId, endValue, duration = 500) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    const isNumber = !isNaN(parseFloat(endValue.toString().replace('%', '')));
    if (!isNumber) {
        el.textContent = endValue;
        return;
    }
    
    const hasPercent = endValue.toString().includes('%');
    const numValue = parseFloat(endValue.toString().replace('%', ''));
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = numValue * easeOut;
        el.textContent = (hasPercent ? current.toFixed(1) + '%' : Math.round(current));
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

// ---- Dashboard ----

let _facultyRefreshTimer = null;
let _facultyFirstLoad = true;

async function loadfacultyDashboard() {
    // Show skeletons on first load
    if (_facultyFirstLoad) {
        showfacultyStatSkeletons();
        showfacultyTableSkeleton(document.getElementById('submissions-body'), 6, 5);
        _facultyFirstLoad = false;
    }
    
    try {
        const [subData, reportData] = await Promise.all([
            apiRequest('/faculty/submissions'),
            apiRequest('/faculty/reports'),
        ]);

        const submissions = subData.submissions || [];
        const reports = reportData.reports || [];
        const reviewQueue = document.getElementById('review-queue-list');
        const flagged = submissions.filter(submission => submission.status === 'needs_review');
        if (reviewQueue) reviewQueue.innerHTML = flagged.length ? flagged.slice(0, 8).map(submission => `<div class="review-queue-row"><span><strong>${escapeHtml(submission.student_name)}</strong><small>${escapeHtml(submission.assignment_title)} · ${formatDate(submission.submitted_at)}</small></span><a class="btn btn-sm btn-outline-warning" href="/faculty/edit_evaluation.html?submission_id=${encodeURIComponent(submission.id)}">Review</a></div>`).join('') : '<p class="text-muted small mb-0">No submissions need review.</p>';

        // Stats with animation
        animatefacultyValue('stat-assignments', reports.length);
        animatefacultyValue('stat-submissions', submissions.length);

        const evaluated = submissions.filter(s => ['done', 'needs_review', 'evaluated'].includes(s.status));
        animatefacultyValue('stat-evaluated', evaluated.length);

        if (evaluated.length > 0) {
            const avg = evaluated.reduce((sum, s) => sum + s.similarity_score, 0) / evaluated.length;
            animatefacultyValue('stat-avg', (avg * 100).toFixed(1) + '%');
        } else {
            document.getElementById('stat-avg').textContent = 'N/A';
        }

        // Auto-refresh if any submissions are still processing
        const hasPending = submissions.some(s => ['queued', 'processing', 'pending'].includes(s.status));
        if (hasPending) {
            clearTimeout(_facultyRefreshTimer); // Clear existing to avoid duplicates
            _facultyRefreshTimer = setTimeout(() => loadfacultyDashboard(), 3000);
        } else if (!hasPending && _facultyRefreshTimer) {
            clearTimeout(_facultyRefreshTimer);
            _facultyRefreshTimer = null;
        }

        // Submissions table
        const tbody = document.getElementById('submissions-body');
        if (submissions.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6">
                        <div class="empty-state">
                            <div class="empty-state-icon" aria-hidden="true"><svg class="theme-empty-icon" viewBox="0 0 48 48"><path d="M8 10.5A4.5 4.5 0 0 1 12.5 6H40v30H12.5A4.5 4.5 0 0 0 8 40.5v-30Z"/><path d="M8 34.5a4.5 4.5 0 0 1 4.5-4.5H40M17 14h15M17 20h15"/></svg></div>
                            <div class="empty-state-title">No submissions yet</div>
                            <div class="empty-state-text">Student submissions will appear here once they start submitting.</div>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = submissions.slice(0, 20).map((s, idx) => {
            const isProcessing = ['queued', 'processing'].includes(s.status);
            return `
            <tr style="animation: cardSlideUp 0.3s ease-out ${idx * 0.05}s both">
                <td>${escapeHtml(s.student_name)}</td>
                <td>${escapeHtml(s.assignment_title)}</td>
                <td>
                    <span class="badge-status badge-${s.status}">${s.status.toUpperCase()}</span>
                    ${isProcessing ? `
                    <div class="eval-progress mt-1">
                        <div class="progress" style="height:14px">
                            <div class="progress-bar" style="width:${s.progress || 0}%;font-size:0.65rem">${s.progress || 0}%</div>
                        </div>
                        <div class="progress-step" style="font-size:0.7rem">${escapeHtml(s.progress_step) || ''}</div>
                    </div>` : ''}
                    ${s.status === 'failed' && s.error_message ? `
                    <div class="progress-step text-danger mt-1" style="font-size:0.7rem">${escapeHtml(s.error_message)}</div>
                    ` : ''}
                </td>
                <td>${['done', 'needs_review', 'evaluated'].includes(s.status) ? (s.similarity_score * 100).toFixed(1) + '%' : '-'}</td>
                <td>${['done', 'needs_review', 'evaluated'].includes(s.status) ? s.marks_obtained + '/' + s.total_marks : '-'}</td>
                <td>${formatDate(s.submitted_at)} ${s.status === 'needs_review' ? `<a class="btn btn-sm btn-outline-warning ms-1" href="/faculty/edit_evaluation.html?submission_id=${encodeURIComponent(s.id)}">Review</a>` : ''}</td>
            </tr>`;
        }).join('');

    } catch (err) {
        console.error('faculty dashboard error:', err);
        showToast('Failed to load dashboard data', 'error');
    }
}

// ---- Assignment Form ----

function setupAssignmentForm() {
    const form = document.getElementById('assignment-form');
    if (!form) return;

    const studentCopiesInput = document.getElementById('student-copies');
    const createBtn = document.getElementById('create-btn');
    const rubricRows = document.getElementById('rubric-rows');
    let questionIndex = 0;
    const addRubricRow = (maximum = 0) => {
        const id = questionIndex++;
        const row = document.createElement('fieldset'); row.className = 'rubric-row'; row.dataset.rubricRow = '';
        row.innerHTML = `<legend>Question ${id + 1}</legend><label>Question<input class="form-control rubric-question"></label><label>Max marks<input class="form-control rubric-marks" type="number" min="0" step="0.5" value="${maximum}"></label><label>Model answer / key points<textarea class="form-control rubric-answer" rows="3"></textarea></label><label>Keywords (comma separated)<input class="form-control rubric-keywords"></label><button type="button" class="btn btn-sm btn-outline-danger remove-rubric" aria-label="Remove question"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 14h10l1-14M9 7V4h6v3"/></svg><span>Remove</span></button>`;
        rubricRows?.append(row);
    };
    if (rubricRows) {
        addRubricRow(Number(document.getElementById('total-marks')?.value) || 100);
        document.getElementById('add-rubric-row')?.addEventListener('click', () => addRubricRow());
        rubricRows.addEventListener('click', event => { if (event.target.closest('.remove-rubric')) { event.target.closest('[data-rubric-row]').remove(); [...rubricRows.children].forEach((row, index) => row.querySelector('legend').textContent = `Question ${index + 1}`); } });
    }

    if (studentCopiesInput && createBtn) {
        studentCopiesInput.addEventListener('change', () => {
            if (studentCopiesInput.files.length > 0) {
                createBtn.innerHTML = `
                    <svg width="20" height="20" fill="currentColor" class="me-2" viewBox="0 0 16 16">
                        <path d="M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z"/>
                        <path fill-rule="evenodd" d="M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z"/>
                    </svg> Evaluate All (${studentCopiesInput.files.length} Files)`;
                createBtn.classList.remove('btn-primary');
                createBtn.classList.add('btn-success');
            } else {
                createBtn.textContent = 'Create Assignment';
                createBtn.classList.remove('btn-success');
                createBtn.classList.add('btn-primary');
            }
        });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = e.submitter || document.getElementById('create-btn');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.textContent = 'Processing...';

        try {
            const formData = new FormData();
            formData.append('title', document.getElementById('title').value);
            formData.append('subject', document.getElementById('subject').value);
            formData.append('total_marks', document.getElementById('total-marks').value || '100');
            const rubric = [...(rubricRows?.querySelectorAll('[data-rubric-row]') || [])].map((row, index) => ({
                q_no: index + 1,
                question: row.querySelector('.rubric-question').value.trim(),
                max_marks: Number(row.querySelector('.rubric-marks').value),
                model_answer: row.querySelector('.rubric-answer').value.trim(),
                keywords: row.querySelector('.rubric-keywords').value.split(',').map(value => value.trim()).filter(Boolean),
            })).filter(row => row.question || row.model_answer || row.max_marks > 0);
            const totalMarks = Number(document.getElementById('total-marks').value || 0);
            const hasRubric = rubric.length > 0 && rubric.every(row => row.question && row.model_answer && row.max_marks > 0);
            const status = e.submitter?.dataset.status || 'published';
            if (status === 'published' && !hasRubric && !document.getElementById('model-answer').value.trim()) throw new Error('Add a complete rubric question or a model answer before publishing.');
            if (status === 'published' && hasRubric && Math.abs(rubric.reduce((sum, row) => sum + row.max_marks, 0) - totalMarks) > .001) throw new Error('Rubric question marks must add up to the assignment maximum.');
            if (hasRubric) formData.append('rubric', JSON.stringify(rubric));
            else formData.append('model_answer', document.getElementById('model-answer').value);
            formData.append('description', document.getElementById('description')?.value || '');
            formData.append('due_date', document.getElementById('due-date')?.value || '');
            formData.append('status', status);
            
            const markingScheme = document.getElementById('marking-scheme');
            if (markingScheme) formData.append('marking_scheme', markingScheme.value);

            if (studentCopiesInput && studentCopiesInput.files.length > 0) {
                for (let i = 0; i < studentCopiesInput.files.length; i++) {
                    formData.append('student_copies', studentCopiesInput.files[i]);
                }
            }

            const data = await apiRequest('/faculty/assignment', {
                method: 'POST',
                body: formData, // apiRequest needs to handle FormData by NOT setting Content-Type to application/json
            });

            showAlert(data.message || 'Assignment created successfully!', 'success');
            form.reset();
            if (rubricRows) { rubricRows.innerHTML = ''; questionIndex = 0; addRubricRow(Number(document.getElementById('total-marks')?.value) || 100); }
            createBtn.textContent = 'Create Assignment';
            createBtn.classList.remove('btn-success');
            createBtn.classList.add('btn-primary');
            
            loadMyAssignments();
            if (studentCopiesInput && studentCopiesInput.files.length > 0) {
                 // Redirect to dashboard to see evaluations
                 setTimeout(() => window.location.href = 'dashboard.html', 1500);
            }

        } catch (err) {
            showAlert(err.message);
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });
}

// ---- My Assignments (sidebar) ----

async function loadMyAssignments() {
    const container = document.getElementById('my-assignments');
    if (!container) return;

    try {
        const data = await apiRequest('/faculty/assignments');
        const assignments = data.assignments || [];

        if (assignments.length === 0) {
            container.innerHTML = '<p class="text-muted small">No assignments created yet.</p>';
            return;
        }

        container.innerHTML = assignments.map(a => `
            <div class="border-bottom pb-2 mb-2">
                <div class="fw-bold small">${escapeHtml(a.title)}</div>
                <div class="text-muted" style="font-size: 0.75rem">${escapeHtml(a.subject)} | ${a.total_marks} marks</div>
            </div>
        `).join('');

    } catch (err) {
        container.innerHTML = '<p class="text-danger small">Failed to load.</p>';
    }
}

// ---- Reports ----

let _reportsFirstLoad = true;
let _reportSubmissions = {}; // Cache for loaded submissions

async function loadReports() {
    const container = document.getElementById('reports-container');
    if (!container) return;
    
    // Show skeleton on first load
    if (_reportsFirstLoad) {
        showReportsSkeletons(container);
        _reportsFirstLoad = false;
    }

    try {
        const data = await apiRequest('/faculty/reports');
        const reports = data.reports || [];

        if (reports.length === 0) {
            container.innerHTML = `
                <div class="content-card">
                    <div class="empty-state">
                        <div class="empty-state-icon" aria-hidden="true"><svg class="theme-empty-icon" viewBox="0 0 48 48"><path d="M7 39h34M11 35V23h7v12M21 35V13h7v22M31 35V19h7v16"/><path d="m10 17 10-7 8 3 10-8"/></svg></div>
                        <div class="empty-state-title">No assignments yet</div>
                        <div class="empty-state-text">Create your first assignment to start receiving submissions.</div>
                        <a href="/faculty/upload_model.html" class="btn btn-primary">Create Assignment</a>
                    </div>
                </div>`;
            return;
        }

        container.innerHTML = reports.map(r => `
            <div class="report-card" id="report-${r.assignment_id}">
                <div class="report-card-header" onclick="toggleReportCard('${r.assignment_id}')">
                    <div class="report-card-title">
                        <h5>${escapeHtml(r.title)}</h5>
                        <span class="subject-badge">${escapeHtml(r.subject)}</span>
                    </div>
                    <div class="report-card-actions">
                        <button class="download-btn" onclick="event.stopPropagation(); downloadReportExcel('${r.assignment_id}', '${escapeAttr(r.title)}')" title="Download Excel">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                <polyline points="7 10 12 15 17 10"></polyline>
                                <line x1="12" y1="15" x2="12" y2="3"></line>
                            </svg>
                            Download Excel
                        </button>
                        <a class="download-btn" href="#" onclick="event.stopPropagation(); downloadAssignmentCSV(event, '${r.assignment_id}')" title="Download CSV">Export CSV</a>
                        <button class="expand-btn" title="View Details">
                            <svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="report-card-stats">
                    <div class="stat-card text-center p-2" style="flex:1">
                        <div class="fw-bold fs-4">${r.total_submissions}</div>
                        <div class="small text-muted">Submissions</div>
                    </div>
                    <div class="stat-card success text-center p-2" style="flex:1">
                        <div class="fw-bold fs-4">${r.evaluated_count}</div>
                        <div class="small text-muted">Evaluated</div>
                    </div>
                    <div class="stat-card warning text-center p-2" style="flex:1">
                        <div class="fw-bold fs-4">${r.pending_count}</div>
                        <div class="small text-muted">Pending</div>
                    </div>
                    <div class="stat-card info text-center p-2" style="flex:1">
                        <div class="fw-bold fs-4">${r.average_similarity}%</div>
                        <div class="small text-muted">Avg Similarity</div>
                    </div>
                    <div class="stat-card text-center p-2" style="flex:1">
                        <div class="fw-bold fs-4">${r.average_marks}</div>
                        <div class="small text-muted">Avg Marks</div>
                    </div>
                </div>
                <div class="assignment-analytics" id="analytics-${r.assignment_id}"><div class="text-muted small">Loading analytics…</div></div>
                <div class="report-card-content">
                    <div class="report-card-body" id="report-body-${r.assignment_id}">
                        <div class="text-center py-3 text-muted">Loading submissions...</div>
                    </div>
                </div>
            </div>
        `).join('');
        reports.forEach(report => loadAssignmentAnalytics(report.assignment_id));

    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
        showToast('Failed to load reports', 'error');
    }
}

async function toggleReportCard(assignmentId) {
    const card = document.getElementById(`report-${assignmentId}`);
    if (!card) return;
    
    const isExpanded = card.classList.contains('expanded');
    
    if (isExpanded) {
        card.classList.remove('expanded');
    } else {
        card.classList.add('expanded');
        // Load submissions if not cached
        if (!_reportSubmissions[assignmentId]) {
            await loadAssignmentSubmissions(assignmentId);
        } else {
            renderSubmissionsTable(assignmentId, _reportSubmissions[assignmentId]);
        }
    }
}

async function loadAssignmentAnalytics(assignmentId) {
    const host = document.getElementById(`analytics-${assignmentId}`);
    if (!host) return;
    try {
        const data = await apiRequest(`/assignments/${assignmentId}/analytics`);
        host.innerHTML = `<div class="analytics-inline"><div><h6>Score distribution</h6><canvas width="360" height="130" aria-label="Submission score distribution"></canvas></div><div><h6>Topics to review</h6>${data.per_question.length ? data.per_question.slice().sort((a,b) => a.average_percentage - b.average_percentage).slice(0,4).map(q => `<div class="topic-score"><span>Q${q.q_no} · ${escapeHtml(q.question || 'Question')}</span><strong>${q.average_percentage}%</strong></div>`).join('') : '<p class="text-muted small">No scored submissions yet.</p>'}<p class="small text-muted">${data.evaluated_count} of ${data.total_count} submissions evaluated</p></div></div>`;
        const canvas = host.querySelector('canvas');
        const ctx = canvas?.getContext('2d');
        if (!ctx) return;
        const max = Math.max(1, ...data.score_distribution.map(bin => bin.count));
        const barWidth = canvas.width / data.score_distribution.length;
        data.score_distribution.forEach((bin, index) => {
            const height = (bin.count / max) * 86;
            ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--primary').trim() || '#22d3ee';
            ctx.fillRect(index * barWidth + 5, 100 - height, barWidth - 10, height);
            ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#8b97b3';
            ctx.font = '9px monospace'; ctx.fillText(`${index * 10}`, index * barWidth + 5, 118);
        });
    } catch (error) { host.textContent = 'Analytics are temporarily unavailable.'; }
}

async function downloadAssignmentCSV(event, assignmentId) {
    event.preventDefault();
    try {
        const response = await fetch(`/api/assignments/${encodeURIComponent(assignmentId)}/export.csv`, { headers: { Authorization: `Bearer ${getToken()}` } });
        if (!response.ok) throw new Error('Could not export this assignment.');
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement('a'); link.href = url; link.download = `assignment-${assignmentId}.csv`; link.click(); URL.revokeObjectURL(url);
    } catch (error) { showToast(error.message, 'error'); }
}

async function loadAssignmentSubmissions(assignmentId) {
    const body = document.getElementById(`report-body-${assignmentId}`);
    if (!body) return;
    
    try {
        const data = await apiRequest(`/faculty/submissions?assignment_id=${assignmentId}`);
        const submissions = data.submissions || [];
        _reportSubmissions[assignmentId] = submissions;
        renderSubmissionsTable(assignmentId, submissions);
    } catch (err) {
        body.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
    }
}

function renderSubmissionsTable(assignmentId, submissions) {
    const body = document.getElementById(`report-body-${assignmentId}`);
    if (!body) return;
    
    if (submissions.length === 0) {
        body.innerHTML = `<div class="text-center py-3 text-muted">No submissions yet for this assignment.</div>`;
        return;
    }
    
    body.innerHTML = `
        <h6 class="mb-3">Student Submissions (${submissions.length})</h6>
        <div class="table-responsive">
            <table class="student-submissions-table">
                <thead>
                    <tr>
                        <th>Student Name</th>
                        <th>Status</th>
                        <th>Similarity</th>
                        <th>Marks</th>
                        <th>Manual Check</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${submissions.map(s => `
                        <tr>
                            <td><strong>${escapeHtml(s.student_name)}</strong></td>
                            <td>
                                ${AppUI.StatusBadge.render(s.status)}
                                ${s.status === 'failed' && s.error_message ? `<div class="small text-danger mt-1">${escapeHtml(s.error_message)}</div>` : ''}
                            </td>
                            <td>${['done', 'needs_review', 'evaluated'].includes(s.status) ? (s.similarity_score * 100).toFixed(1) + '%' : '-'}</td>
                            <td>${['done', 'needs_review', 'evaluated'].includes(s.status) ? s.marks_obtained + '/' + s.total_marks : '-'}</td>
                            <td>${s.faculty_reviewed ? '<span class="text-success">Yes</span>' : '<span class="text-muted">No</span>'}</td>
                            <td>
                                ${['done', 'needs_review', 'evaluated'].includes(s.status) ? `
                                <a href="/faculty/edit_evaluation.html?submission_id=${s.id}" class="btn btn-sm btn-outline-primary">
                                    <svg width="16" height="16" fill="currentColor" class="bi bi-pencil-square" viewBox="0 0 16 16">
                                      <path d="M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z"/>
                                      <path fill-rule="evenodd" d="M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z"/>
                                    </svg> Edit
                                </a>` : '-'}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

// ---- New Evaluation UI (Split View) ----

async function setupNewEvaluationUI() {
    const params = new URLSearchParams(window.location.search);
    const submissionId = params.get('submission_id');
    
    if (!submissionId) {
        showToast('No submission ID provided', 'error');
        return;
    }
    
    const tbody = document.getElementById('marking-tbody');
    const pdfViewer = document.getElementById('pdf-viewer-frame');
    const studentDisplay = document.getElementById('student-name-display');
    const totalMarksSummary = document.getElementById('total-marks-summary');
    const aiTotalMarksEl = document.getElementById('ai-total-marks');
    const commentsArea = document.getElementById('faculty-comments');

    try {
        const data = await apiRequest(`/faculty/evaluation/${submissionId}`);
        
        studentDisplay.textContent = `Submission ID: ${data.submission_id}`;
        if (data.pdf_url) {
            const fileResponse = await fetch(data.pdf_url, { headers: { Authorization: `Bearer ${getToken()}` } });
            if (fileResponse.ok) {
                const objectUrl = URL.createObjectURL(await fileResponse.blob());
                pdfViewer.dataset.objectUrl = objectUrl;
                pdfViewer.src = objectUrl;
                window.addEventListener('beforeunload', () => URL.revokeObjectURL(objectUrl), { once: true });
            }
            else pdfViewer.src = 'about:blank';
        }
        commentsArea.value = data.faculty_comments || '';
        
        const questions = data.questions || [];
        const results = data.results || [];
        const facultyMarks = data.faculty_marks || {};
        const editedAnswers = data.edited_answers || {};

        let aiTotal = 0;
        let maxTotal = 0;
        
        tbody.innerHTML = questions.map((q, idx) => {
            const res = results.find(r => r.question_index === idx) || {};
            const q_num = idx + 1;
            const max = q.marks || 0;
            const ai_mark = res.ai_marks || 0;
            const faculty_mark = facultyMarks[idx] ?? ai_mark;
            const student_ans = editedAnswers[idx] ?? (res.extracted_answer || "");

            aiTotal += ai_mark;
            maxTotal += max;

            return `
                <tr class="q-row" data-idx="${idx}">
                    <td class="q-num">${q_num}</td>
                    <td class="marks-col">
                        <div class="marks-input-wrapper">
                            <input type="number" 
                                   step="0.5" 
                                   class="form-control marks-input" 
                                   data-idx="${idx}" 
                                   value="${faculty_mark}" 
                                   min="0" 
                                   max="${max}">
                            <div class="ai-label">AI Sug: ${ai_mark}</div>
                        </div>
                    </td>
                    <td class="max-marks-col">${max}</td>
                    <td><span class="confidence-pill">Confidence ${Math.round((res.confidence ?? 0) * 100)}%</span><label class="visually-hidden" for="feedback-${idx}">Feedback for question ${q_num}</label><textarea class="form-control faculty-feedback" id="feedback-${idx}" data-idx="${idx}" rows="3">${escapeHtml(res.feedback || '')}</textarea><div class="small text-muted mt-1">AI feedback is editable; the original AI result is preserved.</div></td>
                </tr>
            `;
        }).join('');

        aiTotalMarksEl.textContent = `${aiTotal.toFixed(1)} / ${maxTotal}`;
        updateNewTotalMarksAcrossUI(maxTotal);

        // Add listeners for total marks updates
        tbody.querySelectorAll('.marks-input').forEach(input => {
            input.addEventListener('input', () => updateNewTotalMarksAcrossUI(maxTotal));
        });

        // Form Submission
        document.getElementById('evaluation-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn = document.getElementById('save-evaluation-btn');
            btn.disabled = true;
            btn.textContent = 'Saving...';

            const reviewedQuestions = [...tbody.querySelectorAll('.marks-input')].map(input => ({
                q_no: Number(input.dataset.idx) + 1,
                marks: Number(input.value),
                feedback: tbody.querySelector(`.faculty-feedback[data-idx="${input.dataset.idx}"]`)?.value.trim() || '',
            }));

            try {
                await apiRequest(`/submissions/${submissionId}/review`, {
                    method: 'PUT',
                    body: JSON.stringify({
                        questions: reviewedQuestions,
                        overall_feedback: commentsArea.value.trim()
                    })
                });

                showToast('Evaluation updated successfully!', 'success');
                setTimeout(() => history.back(), 1500);

            } catch (err) {
                showToast(err.message, 'error');
                btn.disabled = false;
                btn.textContent = 'Save Changes';
            }
        };

    } catch (err) {
        showToast('Failed to load evaluation details: ' + err.message, 'error');
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">Error: ${err.message}</td></tr>`;
    }
}

function updateNewTotalMarksAcrossUI(maxTotal) {
    let currentTotal = 0;
    document.querySelectorAll('.marks-input').forEach(input => {
        currentTotal += parseFloat(input.value) || 0;
    });
    const summaryEl = document.getElementById('total-marks-summary');
    if (summaryEl) {
        summaryEl.textContent = `Total: ${currentTotal.toFixed(1)} / ${maxTotal}`;
    }
}

// ---- Legacy Support ----
async function setupEditMarksPage() {
    setupNewEvaluationUI();
}

async function downloadReportExcel(assignmentId, assignmentTitle) {
    if (typeof XLSX === 'undefined') {
        showToast('Excel export library not loaded. Please refresh the page.', 'error');
        return;
    }
    
    try {
        if (!_reportSubmissions[assignmentId]) {
            const data = await apiRequest(`/faculty/submissions?assignment_id=${assignmentId}`);
            _reportSubmissions[assignmentId] = data.submissions || [];
        }
        
        const submissions = _reportSubmissions[assignmentId];
        
        if (submissions.length === 0) {
            showToast('No submissions to export', 'warning');
            return;
        }
        
        const excelData = submissions.map((s, idx) => ({
            'S.No': idx + 1,
            'Student Name': s.student_name,
            'Status': s.status.toUpperCase(),
            'Similarity Score (%)': s.status === 'evaluated' ? (s.similarity_score * 100).toFixed(2) : 'N/A',
            'Marks Obtained': s.status === 'evaluated' ? s.marks_obtained : 'N/A',
            'Total Marks': s.total_marks,
            'Faculty Reviewed': s.faculty_reviewed ? 'Yes' : 'No',
            'Submitted At': s.submitted_at ? new Date(s.submitted_at).toLocaleString() : 'N/A'
        }));
        
        const ws = XLSX.utils.json_to_sheet(excelData);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, 'Submissions');
        
        const filename = `report_${assignmentId}.xlsx`;
        XLSX.writeFile(wb, filename);
        showToast('Excel downloaded', 'success');
    } catch (err) {
        showToast('Export failed: ' + err.message, 'error');
    }
}

function escapeAttr(text) {
    if (!text) return '';
    return text.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ---- Helpers ----

function formatDate(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
