/* ================================================================
   Admin Module — Dashboard Stats, User Management
   ================================================================ */

// ---- Skeleton Loaders ----

function showAdminStatSkeletons() {
    ['stat-users', 'stat-students', 'stat-teachers', 'stat-assignments',
     'stat-submissions', 'stat-evaluated', 'stat-pending', 'stat-errors', 'stat-avg-sim'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<div class="skeleton skeleton-stat"></div>';
    });
}

function showUsersTableSkeleton(tbody, rows = 5) {
    if (!tbody) return;
    let html = '';
    for (let i = 0; i < rows; i++) {
        html += `<tr>
            <td><div class="skeleton skeleton-text medium"></div></td>
            <td><div class="skeleton skeleton-text long"></div></td>
            <td><div class="skeleton skeleton-text short"></div></td>
            <td><div class="skeleton skeleton-text short"></div></td>
            <td><div class="skeleton skeleton-text medium"></div></td>
            <td><div class="skeleton skeleton-text short"></div></td>
        </tr>`;
    }
    tbody.innerHTML = html;
}

// ---- Animate Value ----

function animateAdminValue(elementId, endValue, duration = 500) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    const isNumber = !isNaN(parseFloat(endValue.toString().replace('%', '')));
    if (!isNumber || endValue === 'N/A') {
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

let _adminFirstLoad = true;

async function loadAdminDashboard() {
    // Show skeletons on first load
    if (_adminFirstLoad) {
        showAdminStatSkeletons();
        _adminFirstLoad = false;
    }
    
    try {
        const data = await apiRequest('/admin/stats');
        const s = data.stats;

        // Animate stats
        animateAdminValue('stat-users', s.total_users);
        animateAdminValue('stat-students', s.total_students);
        animateAdminValue('stat-teachers', s.total_teachers);
        animateAdminValue('stat-assignments', s.total_assignments);
        animateAdminValue('stat-submissions', s.total_submissions);
        animateAdminValue('stat-evaluated', s.evaluated_submissions);
        animateAdminValue('stat-pending', s.pending_submissions);
        animateAdminValue('stat-errors', s.error_submissions);
        animateAdminValue('stat-avg-sim', s.average_similarity > 0 ? s.average_similarity + '%' : 'N/A');

    } catch (err) {
        console.error('Admin dashboard error:', err);
        showToast('Failed to load dashboard stats', 'error');
    }
}

// ---- User Management ----

let _usersFirstLoad = true;

async function loadUsers() {
    const tbody = document.getElementById('users-body');
    if (!tbody) return;
    
    // Show skeleton on first load
    if (_usersFirstLoad) {
        showUsersTableSkeleton(tbody, 5);
        _usersFirstLoad = false;
    }

    const role = document.getElementById('role-filter')?.value || '';
    const url = role ? `/admin/users?role=${role}` : '/admin/users';

    try {
        const data = await apiRequest(url);
        const users = data.users || [];
        _allUsers = users; // Store for filtering
        renderUsersTable(users);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-danger">${err.message}</td></tr>`;
        showToast('Failed to load users', 'error');
    }
}

// ---- Edit Modal ----

function openEditModal(id, name, role, isActive) {
    document.getElementById('edit-user-id').value = id;
    document.getElementById('edit-name').value = name;
    document.getElementById('edit-role').value = role;
    document.getElementById('edit-status').value = isActive.toString();

    const modal = new bootstrap.Modal(document.getElementById('editUserModal'));
    modal.show();
}

async function saveUserEdit() {
    const userId = document.getElementById('edit-user-id').value;
    const updates = {
        name: document.getElementById('edit-name').value,
        role: document.getElementById('edit-role').value,
        is_active: document.getElementById('edit-status').value === 'true',
    };

    try {
        await apiRequest(`/admin/users/${userId}`, {
            method: 'PUT',
            body: JSON.stringify(updates),
        });

        // Close modal
        bootstrap.Modal.getInstance(document.getElementById('editUserModal')).hide();
        showAlert('User updated successfully', 'success');
        loadUsers();

    } catch (err) {
        showAlert(err.message);
    }
}

// ---- Delete User ----

async function deleteUser(userId, userName) {
    if (!confirm(`Are you sure you want to delete "${userName}"? This cannot be undone.`)) {
        return;
    }

    try {
        await apiRequest(`/admin/users/${userId}`, { method: 'DELETE' });
        showAlert('User deleted', 'success');
        loadUsers();
    } catch (err) {
        showAlert(err.message);
    }
}

// ---- Helpers ----

function getRoleBadge(role) {
    if (role === 'admin') return 'danger';
    if (role === 'teacher') return 'success';
    return 'primary';
}

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

function escapeAttr(text) {
    if (!text) return '';
    return text.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ---- Admin Tabs ----

let _currentAdminTab = 'users';
let _allUsers = [];
let _allAssignments = [];
let _allSubmissions = [];

function switchAdminTab(tabName) {
    _currentAdminTab = tabName;
    
    // Update tab buttons
    document.querySelectorAll('.admin-tab').forEach(tab => {
        tab.classList.toggle('active', tab.textContent.toLowerCase().includes(tabName));
    });
    
    // Update panels
    document.querySelectorAll('.admin-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`panel-${tabName}`)?.classList.add('active');
    
    // Load data for the tab
    if (tabName === 'assignments' && _allAssignments.length === 0) {
        loadAllAssignments();
    } else if (tabName === 'submissions' && _allSubmissions.length === 0) {
        loadAllSubmissions();
    }
}

// ---- Filter Functions ----

function filterUsers() {
    const search = document.getElementById('user-search')?.value.toLowerCase() || '';
    const tbody = document.getElementById('users-body');
    if (!tbody || _allUsers.length === 0) return;
    
    const filtered = _allUsers.filter(u => 
        u.name.toLowerCase().includes(search) || 
        u.email.toLowerCase().includes(search)
    );
    
    renderUsersTable(filtered);
}

function filterAssignments() {
    const search = document.getElementById('assignment-search')?.value.toLowerCase() || '';
    const tbody = document.getElementById('assignments-body');
    if (!tbody || _allAssignments.length === 0) return;
    
    const filtered = _allAssignments.filter(a => 
        a.title.toLowerCase().includes(search) || 
        a.subject.toLowerCase().includes(search) ||
        (a.teacher_name && a.teacher_name.toLowerCase().includes(search))
    );
    
    renderAssignmentsTable(filtered);
}

function filterSubmissions() {
    const search = document.getElementById('submission-search')?.value.toLowerCase() || '';
    const tbody = document.getElementById('submissions-body');
    if (!tbody || _allSubmissions.length === 0) return;
    
    const filtered = _allSubmissions.filter(s => 
        (s.student_name && s.student_name.toLowerCase().includes(search)) || 
        (s.assignment_title && s.assignment_title.toLowerCase().includes(search))
    );
    
    renderSubmissionsTable(filtered);
}

// ---- Load Teacher Filter ----

async function loadTeacherFilter() {
    try {
        const data = await apiRequest('/admin/users?role=teacher');
        const teachers = data.users || [];
        const select = document.getElementById('teacher-filter');
        if (select) {
            teachers.forEach(t => {
                const option = document.createElement('option');
                option.value = t.id;
                option.textContent = t.name;
                select.appendChild(option);
            });
        }
    } catch (err) {
        console.error('Failed to load teachers:', err);
    }
}

// ---- All Assignments ----

async function loadAllAssignments() {
    const tbody = document.getElementById('assignments-body');
    if (!tbody) return;
    
    showUsersTableSkeleton(tbody, 5);
    
    const teacherId = document.getElementById('teacher-filter')?.value || '';
    const url = teacherId ? `/admin/assignments?teacher_id=${teacherId}` : '/admin/assignments';
    
    try {
        const data = await apiRequest(url);
        _allAssignments = data.assignments || [];
        renderAssignmentsTable(_allAssignments);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-danger">${err.message}</td></tr>`;
        showToast('Failed to load assignments', 'error');
    }
}

function renderAssignmentsTable(assignments) {
    const tbody = document.getElementById('assignments-body');
    if (!tbody) return;
    
    if (assignments.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-state-icon">📝</div>
                        <div class="empty-state-title">No assignments found</div>
                        <div class="empty-state-text">No assignments match your current filter.</div>
                    </div>
                </td>
            </tr>`;
        return;
    }
    
    tbody.innerHTML = assignments.map((a, idx) => `
        <tr style="animation: cardSlideUp 0.3s ease-out ${idx * 0.05}s both">
            <td><strong>${escapeHtml(a.title)}</strong></td>
            <td>${escapeHtml(a.subject)}</td>
            <td>${escapeHtml(a.teacher_name || 'Unknown')}</td>
            <td>${a.total_marks}</td>
            <td>${a.submission_count || 0}</td>
            <td>${formatDate(a.created_at)}</td>
            <td>
                <button class="btn btn-outline-danger btn-sm" onclick="confirmDeleteAssignment('${a.id}', '${escapeAttr(a.title)}')">
                    Delete
                </button>
            </td>
        </tr>
    `).join('');
}

// ---- All Submissions ----

async function loadAllSubmissions() {
    const tbody = document.getElementById('submissions-body');
    if (!tbody) return;
    
    showUsersTableSkeleton(tbody, 5);
    
    const status = document.getElementById('status-filter')?.value || '';
    const url = status ? `/admin/submissions?status=${status}` : '/admin/submissions';
    
    try {
        const data = await apiRequest(url);
        _allSubmissions = data.submissions || [];
        renderSubmissionsTable(_allSubmissions);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-danger">${err.message}</td></tr>`;
        showToast('Failed to load submissions', 'error');
    }
}

function renderSubmissionsTable(submissions) {
    const tbody = document.getElementById('submissions-body');
    if (!tbody) return;
    
    if (submissions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-state-icon">📄</div>
                        <div class="empty-state-title">No submissions found</div>
                        <div class="empty-state-text">No submissions match your current filter.</div>
                    </div>
                </td>
            </tr>`;
        return;
    }
    
    tbody.innerHTML = submissions.map((s, idx) => `
        <tr style="animation: cardSlideUp 0.3s ease-out ${idx * 0.05}s both">
            <td><strong>${escapeHtml(s.student_name || 'Unknown')}</strong></td>
            <td>${escapeHtml(s.assignment_title || 'Unknown')}</td>
            <td><span class="badge-status badge-${s.status}">${s.status.toUpperCase()}</span></td>
            <td>${s.status === 'evaluated' ? (s.similarity_score * 100).toFixed(1) + '%' : '-'}</td>
            <td>${s.status === 'evaluated' ? s.marks_obtained + '/' + (s.total_marks || '-') : '-'}</td>
            <td>${formatDate(s.submitted_at)}</td>
            <td>
                <button class="btn btn-outline-danger btn-sm" onclick="confirmDeleteSubmission('${s.id}', '${escapeAttr(s.student_name || 'Unknown')}')">
                    Delete
                </button>
            </td>
        </tr>
    `).join('');
}

// ---- Render Users Table (refactored) ----

function renderUsersTable(users) {
    const tbody = document.getElementById('users-body');
    if (!tbody) return;
    
    if (users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6">
                    <div class="empty-state">
                        <div class="empty-state-icon">👥</div>
                        <div class="empty-state-title">No users found</div>
                        <div class="empty-state-text">No users match your current filter.</div>
                    </div>
                </td>
            </tr>`;
        return;
    }
    
    tbody.innerHTML = users.map((u, idx) => `
        <tr style="animation: cardSlideUp 0.3s ease-out ${idx * 0.05}s both">
            <td><strong>${escapeHtml(u.name)}</strong></td>
            <td>${escapeHtml(u.email)}</td>
            <td><span class="badge bg-${getRoleBadge(u.role)}">${u.role.toUpperCase()}</span></td>
            <td>
                <span class="badge-status ${u.is_active ? 'badge-evaluated' : 'badge-error'}">
                    ${u.is_active ? 'Active' : 'Deactivated'}
                </span>
            </td>
            <td>${formatDate(u.created_at)}</td>
            <td>
                <button class="btn btn-outline-primary btn-sm me-1" onclick="openEditModal('${u.id}', '${escapeAttr(u.name)}', '${u.role}', ${u.is_active})">
                    Edit
                </button>
                ${u.role !== 'admin' ? `
                <button class="btn btn-outline-danger btn-sm" onclick="confirmDeleteUser('${u.id}', '${escapeAttr(u.name)}')">
                    Delete
                </button>` : ''}
            </td>
        </tr>
    `).join('');
}

// ---- Confirm Delete Modal ----

let _deleteCallback = null;

function showConfirmDeleteModal(message, onConfirm) {
    document.getElementById('delete-message').textContent = message;
    _deleteCallback = onConfirm;
    
    const btn = document.getElementById('confirm-delete-btn');
    btn.onclick = async () => {
        btn.disabled = true;
        btn.textContent = 'Deleting...';
        try {
            await _deleteCallback();
            bootstrap.Modal.getInstance(document.getElementById('confirmDeleteModal')).hide();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Delete';
        }
    };
    
    new bootstrap.Modal(document.getElementById('confirmDeleteModal')).show();
}

function confirmDeleteUser(userId, userName) {
    showConfirmDeleteModal(
        `Are you sure you want to delete "${userName}"?`,
        async () => {
            await apiRequest(`/admin/users/${userId}`, { method: 'DELETE' });
            showToast('User deleted successfully', 'success');
            loadUsers();
        }
    );
}

function confirmDeleteAssignment(assignmentId, title) {
    showConfirmDeleteModal(
        `Are you sure you want to delete assignment "${title}"? All associated submissions will also be deleted.`,
        async () => {
            await apiRequest(`/admin/assignments/${assignmentId}`, { method: 'DELETE' });
            showToast('Assignment deleted successfully', 'success');
            loadAllAssignments();
        }
    );
}

function confirmDeleteSubmission(submissionId, studentName) {
    showConfirmDeleteModal(
        `Are you sure you want to delete the submission by "${studentName}"?`,
        async () => {
            await apiRequest(`/admin/submissions/${submissionId}`, { method: 'DELETE' });
            showToast('Submission deleted successfully', 'success');
            loadAllSubmissions();
        }
    );
}
