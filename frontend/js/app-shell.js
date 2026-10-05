/* Wrap existing role pages in one responsive, role-aware application shell. */
(function () {
  const pages = {
    student: [
      ['/student/dashboard.html', 'Dashboard', '◫'],
      ['/student/results.html', 'My submissions', '▤'],
      ['/student/submit.html', 'Submit work', '＋']
    ],
    faculty: [
      ['/faculty/dashboard.html', 'Dashboard', '◫'],
      ['/faculty/upload_model.html', 'Assignments', '▧'],
      ['/faculty/dashboard.html#review-queue', 'Review queue', '✓'],
      ['/faculty/reports.html', 'Analytics', '⌁']
    ],
    admin: [
      ['/admin/manage.html#panel-users', 'Users', '♙'],
      ['/admin/manage.html#panel-assignments', 'Assignments', '▧'],
      ['/admin/manage.html#panel-submissions', 'Submissions', '▤'],
      ['/admin/dashboard.html', 'System', '⌘']
    ]
  };
  const titles = {
    '/student/dashboard.html': 'Student dashboard', '/student/submit.html': 'Submit answer script', '/student/results.html': 'My submissions',
    '/faculty/dashboard.html': 'Faculty dashboard', '/faculty/upload_model.html': 'Assignments', '/faculty/reports.html': 'Analytics',
    '/faculty/edit_evaluation.html': 'Submission review', '/faculty/edit_marks.html': 'Edit marks',
    '/student/submission.html': 'Submission detail',
    '/admin/dashboard.html': 'System overview', '/admin/manage.html': 'System management'
  };

  function mount() {
    const path = location.pathname.replace(/\/$/, '') || '/';
    const role = path.startsWith('/student/') ? 'student' : path.startsWith('/faculty/') ? 'faculty' : path.startsWith('/admin/') ? 'admin' : '';
    if (!role || document.querySelector('.app-shell')) return;

    const user = (() => { try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch (_) { return {}; } })();
    const main = document.querySelector('.dashboard-container, .main-wrapper, main.container, .container.my-5');
    if (!main) return;
    const pageHeading = main.querySelector('.page-header h1');
    const adminSectionTitles = {
      '#panel-users': ['Users', 'Manage user accounts and access.'],
      '#panel-assignments': ['Assignments', 'Review assignments created across the system.'],
      '#panel-submissions': ['Submissions', 'Review submitted work and evaluation status.']
    };
    const initialAdminSection = role === 'admin' && path === '/admin/manage.html'
      ? (adminSectionTitles[location.hash] || adminSectionTitles['#panel-users'])
      : null;
    const pageTitle = initialAdminSection?.[0] || pageHeading?.textContent.trim() || titles[path] || 'Workspace';
    const initials = (user.name || role).split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase();
    const shell = document.createElement('div'); shell.className = 'app-shell'; shell.dataset.role = role; shell.dataset.page = path;
    const nav = pages[role].map(([href, label, icon]) => {
      const [targetPath, targetHash] = href.split('#');
      const current = targetPath === path && (targetHash
        ? location.hash === `#${targetHash}` || (!location.hash && role === 'admin' && targetHash === 'panel-users')
        : !(role === 'faculty' && path === '/faculty/dashboard.html' && location.hash));
      return `<a class="shell-link${current ? ' active' : ''}" href="${href}"${current ? ' aria-current="page"' : ''}><span aria-hidden="true">${icon}</span><span>${label}</span></a>`;
    }).join('');
    shell.innerHTML = `<aside class="shell-sidebar" id="shell-sidebar"><a class="shell-brand" href="${pages[role][0][0]}"><span class="brand-mark">AG</span><span>AutoGrade<span class="brand-dot">.</span><small>AI evaluation workspace</small></span></a><div class="shell-section-label">WORKSPACE</div><nav aria-label="${role} navigation">${nav}</nav><div class="shell-user"><span class="shell-avatar">${initials}</span><span class="shell-user-copy"><strong>${escapeText(user.name || role)}</strong><small>${escapeText(role)}</small></span><button type="button" class="shell-logout" title="Log out" aria-label="Log out">↗</button></div></aside><div class="shell-main"><header class="shell-topbar"><button type="button" class="shell-menu" aria-label="Open navigation" aria-expanded="false">☰</button><div class="shell-heading"><span>WORKSPACE / ${role.toUpperCase()}</span><h1>${escapeText(pageTitle)}</h1></div><div class="shell-actions"><button type="button" class="shell-theme" aria-label="Toggle light theme" title="Toggle theme">◐</button></div></header><main class="shell-content"></main></div><button type="button" class="shell-scrim" aria-label="Close navigation"></button>`;
    document.body.classList.add('has-app-shell');
    const content = shell.querySelector('.shell-content'); content.append(main);
    // Keep one visible page title in the sticky shell header; retain the
    // original heading's child fields until DOMContentLoaded handlers finish.
    pageHeading?.remove();
    document.body.prepend(shell);
    if (initialAdminSection) {
      const heading = shell.querySelector('.shell-heading h1');
      const description = main.querySelector('.page-header p');
      const syncAdminSection = () => {
        const section = adminSectionTitles[location.hash] || adminSectionTitles['#panel-users'];
        heading.textContent = section[0];
        if (description) description.textContent = section[1];
        shell.querySelectorAll('.shell-link').forEach(link => {
          const active = link.getAttribute('href') === `/admin/manage.html${location.hash || '#panel-users'}`;
          link.classList.toggle('active', active);
          if (active) link.setAttribute('aria-current', 'page');
          else link.removeAttribute('aria-current');
        });
      };
      window.addEventListener('hashchange', syncAdminSection);
      syncAdminSection();
    }
    document.querySelector('.navbar-custom')?.remove();
    document.querySelectorAll('body > .modal, body > .spinner-overlay').forEach(node => shell.append(node));
    const addMobileTableLabels = () => main.querySelectorAll('table').forEach(table => {
      const labels = [...table.querySelectorAll('thead th')].map(cell => cell.textContent.trim());
      table.querySelectorAll('tbody tr').forEach(row => [...row.cells].forEach((cell, index) => { if (labels[index] && !cell.hasAttribute('data-label')) cell.dataset.label = labels[index]; }));
    });
    addMobileTableLabels();
    new MutationObserver(addMobileTableLabels).observe(main, { childList: true, subtree: true });

    const sidebar = shell.querySelector('.shell-sidebar'), menu = shell.querySelector('.shell-menu'), scrim = shell.querySelector('.shell-scrim');
    const closeNav = () => { sidebar.classList.remove('open'); scrim.classList.remove('visible'); menu.setAttribute('aria-expanded', 'false'); };
    menu.addEventListener('click', () => { sidebar.classList.toggle('open'); scrim.classList.toggle('visible'); menu.setAttribute('aria-expanded', sidebar.classList.contains('open')); });
    scrim.addEventListener('click', closeNav);
    shell.querySelector('.shell-logout').addEventListener('click', () => window.logout?.());
    shell.querySelector('.shell-theme').addEventListener('click', () => {
      const light = document.documentElement.dataset.theme !== 'light';
      if (typeof window.applyTheme === 'function') window.applyTheme(light ? 'light' : 'dark');
      else { document.documentElement.dataset.theme = light ? 'light' : 'dark'; localStorage.setItem('theme', light ? 'light' : 'dark'); }
    });
    if (role === 'faculty') {
      const syncFacultyNavigation = () => {
        shell.querySelectorAll('.shell-link').forEach(link => {
          const [targetPath, targetHash] = link.getAttribute('href').split('#');
          const active = targetPath === location.pathname && (targetHash
            ? location.hash === `#${targetHash}`
            : !(location.pathname === '/faculty/dashboard.html' && location.hash));
          link.classList.toggle('active', active);
          if (active) link.setAttribute('aria-current', 'page');
          else link.removeAttribute('aria-current');
        });
      };
      window.addEventListener('hashchange', syncFacultyNavigation);
      shell.querySelectorAll('a[href*="#"]').forEach(link => link.addEventListener('click', () => {
        const id = link.getAttribute('href').split('#')[1];
        if (id) setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }), 0);
      }));
    }
  }

  function escapeText(value) { return String(value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]); }
  document.addEventListener('DOMContentLoaded', mount);
})();
