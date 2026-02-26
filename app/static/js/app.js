/* ===== AUTH GUARD ===== */
const token = localStorage.getItem('token');
const user = JSON.parse(localStorage.getItem('user') || 'null');

if (!token || !user) {
  window.location.href = '/login';
}

/* ===== ROLE SETUP ===== */
if (user && user.role === 'admin') {
  document.body.classList.add('role-admin');
}

/* ===== USER INFO IN SIDEBAR ===== */
function initUserInfo() {
  if (!user) return;
  const nameEl = document.getElementById('user-fullname');
  const roleEl = document.getElementById('user-role-label');
  const avatarEl = document.getElementById('user-avatar');

  nameEl.textContent = user.full_name || user.username;
  roleEl.textContent = user.role === 'admin' ? 'Администратор' : 'Инспектор';

  const initials = (user.full_name || user.username)
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
  avatarEl.textContent = initials || 'U';
}
initUserInfo();

/* ===== NAVIGATION ===== */
let currentPage = 'dashboard';

function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
  const page = document.getElementById('page-' + name);
  if (page) page.style.display = 'block';

  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  const navItem = document.querySelector(`.nav-item[data-page="${name}"]`);
  if (navItem) navItem.classList.add('active');

  currentPage = name;

  if (name === 'dashboard') loadDashboard();
  if (name === 'users') loadUsers();
}

/* ===== DETERMINE START PAGE ===== */
const path = window.location.pathname;
if (path === '/admin' && user.role === 'admin') {
  showPage('users');
} else {
  showPage('dashboard');
}

/* ===== API HELPER ===== */
async function api(url, options = {}) {
  const headers = { 'Authorization': 'Bearer ' + token, ...options.headers };
  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
    return;
  }
  return res;
}

/* ===== LOGOUT ===== */
function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = '/login';
}

/* ===== TOAST ===== */
function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast show ' + type;
  setTimeout(() => { toast.className = 'toast'; }, 3000);
}

/* ===== DASHBOARD ===== */
async function loadDashboard() {
  try {
    const res = await api('/api/admin/stats');
    if (res && res.ok) {
      const data = await res.json();
      document.getElementById('stat-total').textContent = data.total_ankety;
      document.getElementById('stat-approved').textContent = data.approved;
      document.getElementById('stat-pending').textContent = data.pending;
      document.getElementById('stat-rejected').textContent = data.rejected;
    }
  } catch (e) { /* silent */ }
}

/* ===== USERS MANAGEMENT ===== */
let allUsers = [];

async function loadUsers() {
  try {
    const res = await api('/api/admin/users');
    if (res && res.ok) {
      allUsers = await res.json();
      renderUsers(allUsers);
    }
  } catch (e) {
    showToast('Ошибка загрузки пользователей', 'error');
  }
}

function renderUsers(users) {
  const tbody = document.getElementById('users-table-body');
  if (users.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-light)">Нет пользователей</td></tr>';
    return;
  }
  tbody.innerHTML = users.map(u => `
    <tr>
      <td style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-light)">${u.id}</td>
      <td style="font-weight:600">${escapeHtml(u.username)}</td>
      <td>${escapeHtml(u.full_name)}</td>
      <td>
        <span class="status-badge" style="background:var(--purple-pale);color:var(--purple)">
          ${u.role === 'admin' ? 'Администратор' : 'Инспектор'}
        </span>
      </td>
      <td>
        <span class="status-badge ${u.is_active ? 'status-active' : 'status-inactive'}">
          <span class="status-dot"></span>
          ${u.is_active ? 'Активен' : 'Деактивирован'}
        </span>
      </td>
      <td style="font-size:12.5px;color:var(--text-light)">${formatDate(u.created_at)}</td>
      <td>
        <div style="display:flex;gap:6px">
          <button class="btn btn-outline btn-sm" onclick="openEditUserModal(${u.id})">Изменить</button>
          ${u.is_active
            ? `<button class="btn btn-sm btn-danger" onclick="toggleUser(${u.id}, false)">Деактивировать</button>`
            : `<button class="btn btn-sm btn-success" onclick="toggleUser(${u.id}, true)">Активировать</button>`
          }
        </div>
      </td>
    </tr>
  `).join('');
}

/* ===== CREATE USER ===== */
function openCreateUserModal() {
  document.getElementById('create-user-modal').classList.add('show');
  document.getElementById('create-user-form').reset();
  document.getElementById('modal-error').classList.remove('show');
}

function closeCreateUserModal() {
  document.getElementById('create-user-modal').classList.remove('show');
}

document.getElementById('create-user-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errEl = document.getElementById('modal-error');
  errEl.classList.remove('show');

  const data = {
    username: document.getElementById('new-username').value.trim(),
    full_name: document.getElementById('new-fullname').value.trim(),
    password: document.getElementById('new-password').value,
    role: document.getElementById('new-role').value,
  };

  if (data.username.length < 3) {
    errEl.textContent = 'Логин должен быть не менее 3 символов';
    errEl.classList.add('show');
    return;
  }
  if (data.password.length < 6) {
    errEl.textContent = 'Пароль должен быть не менее 6 символов';
    errEl.classList.add('show');
    return;
  }

  try {
    const res = await api('/api/admin/users', { method: 'POST', body: data });
    const result = await res.json();
    if (!res.ok) {
      errEl.textContent = result.detail || 'Ошибка создания';
      errEl.classList.add('show');
      return;
    }
    closeCreateUserModal();
    showToast('Пользователь создан', 'success');
    loadUsers();
  } catch (err) {
    errEl.textContent = 'Ошибка подключения';
    errEl.classList.add('show');
  }
});

/* ===== EDIT USER ===== */
function openEditUserModal(userId) {
  const u = allUsers.find(x => x.id === userId);
  if (!u) return;
  document.getElementById('edit-user-id').value = u.id;
  document.getElementById('edit-fullname').value = u.full_name;
  document.getElementById('edit-password').value = '';
  document.getElementById('edit-role').value = u.role;
  document.getElementById('edit-user-subtitle').textContent = `Логин: ${u.username}`;
  document.getElementById('edit-modal-error').classList.remove('show');
  document.getElementById('edit-user-modal').classList.add('show');
}

function closeEditUserModal() {
  document.getElementById('edit-user-modal').classList.remove('show');
}

document.getElementById('edit-user-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errEl = document.getElementById('edit-modal-error');
  errEl.classList.remove('show');

  const userId = document.getElementById('edit-user-id').value;
  const data = {
    full_name: document.getElementById('edit-fullname').value.trim(),
    role: document.getElementById('edit-role').value,
  };

  const pw = document.getElementById('edit-password').value;
  if (pw) {
    if (pw.length < 6) {
      errEl.textContent = 'Пароль должен быть не менее 6 символов';
      errEl.classList.add('show');
      return;
    }
    data.password = pw;
  }

  try {
    const res = await api(`/api/admin/users/${userId}`, { method: 'PUT', body: data });
    const result = await res.json();
    if (!res.ok) {
      errEl.textContent = result.detail || 'Ошибка обновления';
      errEl.classList.add('show');
      return;
    }
    closeEditUserModal();
    showToast('Пользователь обновлён', 'success');
    loadUsers();
  } catch (err) {
    errEl.textContent = 'Ошибка подключения';
    errEl.classList.add('show');
  }
});

/* ===== TOGGLE USER ===== */
async function toggleUser(userId, activate) {
  try {
    const res = await api(`/api/admin/users/${userId}`, {
      method: 'PUT',
      body: { is_active: activate },
    });
    if (res && res.ok) {
      showToast(activate ? 'Пользователь активирован' : 'Пользователь деактивирован', 'success');
      loadUsers();
    }
  } catch (e) {
    showToast('Ошибка', 'error');
  }
}

/* ===== UTILS ===== */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

/* ===== CLOSE MODALS ON OVERLAY CLICK ===== */
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.classList.remove('show');
  });
});
