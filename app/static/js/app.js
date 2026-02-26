/* ============================================
   Fintech Drive — Андеррайтинг
   Main application JS
   ============================================ */

// ---------- AUTH ----------

function getToken() {
  return localStorage.getItem('token');
}

function getUser() {
  try {
    return JSON.parse(localStorage.getItem('user'));
  } catch {
    return null;
  }
}

function authHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + getToken(),
  };
}

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = '/login';
}

function checkAuth() {
  if (!getToken()) {
    window.location.href = '/login';
    return false;
  }
  return true;
}

// ---------- TOAST ----------

function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = 'toast ' + type;
  toast.textContent = (type === 'success' ? '✓ ' : '✕ ') + message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ---------- NAVIGATION ----------

let currentPage = 'dashboard';

function navigate(page) {
  currentPage = page;

  // Hide all pages
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

  // Show target page
  const target = document.getElementById('page-' + page);
  if (target) target.classList.add('active');

  // Update sidebar active state
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.page === page);
  });

  // Load page data
  if (page === 'users') loadUsers();

  // Update URL without reload
  const urlMap = {
    dashboard: '/',
    users: '/admin',
  };
  const url = urlMap[page] || '/' + page;
  history.pushState({ page }, '', url);
}

// Handle browser back/forward
window.addEventListener('popstate', (e) => {
  if (e.state && e.state.page) {
    navigate(e.state.page);
  }
});

// ---------- INIT ----------

function initApp() {
  if (!checkAuth()) return;

  const user = getUser();
  if (!user) { logout(); return; }

  // Set user info in sidebar
  const initials = user.full_name
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  document.getElementById('userAvatar').textContent = initials;
  document.getElementById('userName').textContent = user.full_name;

  const roleLabels = { admin: 'Администратор', inspector: 'Инспектор' };
  document.getElementById('userRole').textContent = roleLabels[user.role] || user.role;

  // Hide admin section for non-admins
  if (user.role !== 'admin') {
    document.getElementById('adminSection').style.display = 'none';
    document.getElementById('usersNavItem').style.display = 'none';
  }

  // Route based on URL
  const path = window.location.pathname;
  if (path === '/admin') {
    if (user.role === 'admin') {
      navigate('users');
    } else {
      navigate('dashboard');
    }
  } else if (path === '/dashboard') {
    navigate('dashboard');
  } else {
    navigate('dashboard');
  }
}

// ---------- USERS MANAGEMENT ----------

let usersData = [];

async function loadUsers() {
  const user = getUser();
  if (!user || user.role !== 'admin') {
    navigate('dashboard');
    return;
  }

  try {
    const res = await fetch('/api/admin/users', { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Failed to load users');

    usersData = await res.json();
    renderUsersTable();
  } catch (err) {
    showToast('Ошибка загрузки пользователей', 'error');
  }
}

function renderUsersTable() {
  const tbody = document.getElementById('usersTableBody');

  if (usersData.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-light)">Нет пользователей</td></tr>';
    return;
  }

  const roleLabels = { admin: 'Администратор', inspector: 'Инспектор' };

  tbody.innerHTML = usersData.map(u => {
    const roleBadge = u.role === 'admin'
      ? '<span class="role-badge role-admin">Администратор</span>'
      : '<span class="role-badge role-inspector">Инспектор</span>';

    const statusBadge = u.is_active
      ? '<span class="status-badge status-active"><span class="status-dot"></span>Активен</span>'
      : '<span class="status-badge status-inactive"><span class="status-dot"></span>Неактивен</span>';

    const created = u.created_at
      ? new Date(u.created_at).toLocaleDateString('ru-RU')
      : '—';

    return `
      <tr>
        <td><div class="td-main">${escapeHtml(u.full_name)}</div></td>
        <td><code style="font-family:'JetBrains Mono',monospace;font-size:12.5px;background:var(--bg);padding:2px 8px;border-radius:4px">${escapeHtml(u.email)}</code></td>
        <td>${roleBadge}</td>
        <td>${statusBadge}</td>
        <td>${created}</td>
        <td>
          <div style="display:flex;gap:6px">
            <button class="btn btn-outline btn-sm" onclick="openEditUserModal(${u.id})">Изменить</button>
            <button class="btn btn-sm btn-danger" onclick="deleteUser(${u.id})">Удалить</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

// ---------- CREATE USER MODAL ----------

function openCreateUserModal() {
  document.getElementById('newFullName').value = '';
  document.getElementById('newEmail').value = '';
  document.getElementById('newRole').value = 'inspector';
  document.getElementById('createUserError').classList.remove('show');
  document.getElementById('createUserModal').classList.add('show');
}

function closeCreateUserModal() {
  document.getElementById('createUserModal').classList.remove('show');
}

async function createUser() {
  const errEl = document.getElementById('createUserError');
  const btn = document.getElementById('createUserBtn');
  errEl.classList.remove('show');

  const fullName = document.getElementById('newFullName').value.trim();
  const email = document.getElementById('newEmail').value.trim();
  const role = document.getElementById('newRole').value;

  if (!fullName || !email) {
    errEl.textContent = 'Заполните все обязательные поля';
    errEl.classList.add('show');
    return;
  }

  if (!email.includes('@')) {
    errEl.textContent = 'Введите корректный email';
    errEl.classList.add('show');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Создание...';

  try {
    const res = await fetch('/api/admin/users', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ full_name: fullName, email, role }),
    });

    if (res.status === 401) { logout(); return; }

    const data = await res.json();

    if (!res.ok) {
      const msg = typeof data.detail === 'string' ? data.detail : 'Ошибка создания';
      throw new Error(msg);
    }
    closeCreateUserModal();
    showCredentials(data.email, data.generated_password);
    loadUsers();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.add('show');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Создать';
  }
}

// ---------- EDIT USER MODAL ----------

function openEditUserModal(userId) {
  const user = usersData.find(u => u.id === userId);
  if (!user) return;

  document.getElementById('editUserId').value = userId;
  document.getElementById('editFullName').value = user.full_name;
  document.getElementById('editPassword').value = '';
  document.getElementById('editRole').value = user.role;
  document.getElementById('editIsActive').checked = user.is_active;
  document.getElementById('editUserError').classList.remove('show');
  document.getElementById('editUserModal').classList.add('show');
}

function closeEditUserModal() {
  document.getElementById('editUserModal').classList.remove('show');
}

async function saveUser() {
  const errEl = document.getElementById('editUserError');
  const btn = document.getElementById('saveUserBtn');
  errEl.classList.remove('show');

  const userId = document.getElementById('editUserId').value;
  const fullName = document.getElementById('editFullName').value.trim();
  const password = document.getElementById('editPassword').value;
  const role = document.getElementById('editRole').value;

  if (!fullName) {
    errEl.textContent = 'ФИО обязательно';
    errEl.classList.add('show');
    return;
  }

  if (password && password.length < 6) {
    errEl.textContent = 'Пароль должен быть минимум 6 символов';
    errEl.classList.add('show');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Сохранение...';

  const isActive = document.getElementById('editIsActive').checked;
  const body = { full_name: fullName, role, is_active: isActive };
  if (password) body.password = password;

  try {
    const res = await fetch('/api/admin/users/' + userId, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(body),
    });

    if (res.status === 401) { logout(); return; }

    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Ошибка сохранения');
    }

    closeEditUserModal();
    showToast('Пользователь обновлён');
    loadUsers();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.add('show');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Сохранить';
  }
}

// ---------- RESET PASSWORD ----------

async function resetUserPassword() {
  const userId = document.getElementById('editUserId').value;
  if (!confirm('Сгенерировать новый пароль для этого пользователя?')) return;

  const btn = document.getElementById('resetPwdBtn');
  btn.disabled = true;
  btn.textContent = 'Сброс...';

  try {
    const res = await fetch('/api/admin/users/' + userId + '/reset-password', {
      method: 'POST',
      headers: authHeaders(),
    });

    if (res.status === 401) { logout(); return; }

    const data = await res.json();
    if (!res.ok) {
      const msg = typeof data.detail === 'string' ? data.detail : 'Ошибка сброса';
      throw new Error(msg);
    }

    closeEditUserModal();
    showCredentials(data.email, data.generated_password);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Сбросить';
  }
}

// ---------- DELETE USER ----------

async function deleteUser(userId) {
  if (!confirm('Вы уверены, что хотите удалить пользователя?')) return;

  try {
    const res = await fetch('/api/admin/users/' + userId, {
      method: 'DELETE',
      headers: authHeaders(),
    });

    if (res.status === 401) { logout(); return; }

    if (!res.ok) {
      const data = await res.json();
      const msg = typeof data.detail === 'string' ? data.detail : 'Ошибка удаления';
      throw new Error(msg);
    }

    showToast('Пользователь удалён');
    loadUsers();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ---------- CREDENTIALS MODAL ----------

let _credentialsText = '';

function showCredentials(email, password) {
  _credentialsText = 'Логин: ' + email + '\nПароль: ' + password;
  document.getElementById('credentialsText').innerHTML =
    '<div><span style="color:var(--text-light)">Логин:</span> ' + escapeHtml(email) + '</div>' +
    '<div><span style="color:var(--text-light)">Пароль:</span> ' + escapeHtml(password) + '</div>';
  document.getElementById('copyCredBtn').textContent = 'Скопировать';
  document.getElementById('credentialsModal').classList.add('show');
}

function closeCredentialsModal() {
  document.getElementById('credentialsModal').classList.remove('show');
}

function copyCredentials() {
  navigator.clipboard.writeText(_credentialsText).then(() => {
    document.getElementById('copyCredBtn').textContent = 'Скопировано!';
    setTimeout(() => {
      document.getElementById('copyCredBtn').textContent = 'Скопировать';
    }, 2000);
  });
}

// ---------- UTILS ----------

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// Close modals on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.classList.remove('show');
  });
});

// Close modals on Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.show').forEach(m => m.classList.remove('show'));
  }
});

// ---------- START ----------

initApp();
