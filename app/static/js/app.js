/* ============================================
   Fintech Drive — Андеррайтинг
   Main application JS
   ============================================ */

// ---------- GLOBAL STATUS MAP ----------

const STATUS_MAP = {
  draft:    { label: 'Черновик',       cls: 'status-draft' },
  saved:    { label: 'Сохранена',      cls: 'status-saved' },
  approved: { label: 'Одобрена',       cls: 'status-approved' },
  review:   { label: 'На рассмотр.',   cls: 'status-review' },
  rejected: { label: 'Отказ',          cls: 'status-rejected' },
  rejected_underwriter: { label: 'Отказ андерр.', cls: 'status-rejected_underwriter' },
  rejected_client:      { label: 'Отказ клиента', cls: 'status-rejected_client' },
  deleted:  { label: 'Удалена',        cls: 'status-deleted' },
};

let currentUser = null;
let _verdictRules = null;
let _clientRiskRules = [];
let rulesData = [];
let riskRulesData = [];
let _currentClientType = 'individual';
let _dashboardClientType = '';
let _editRequestAnketaId = null;

// ---------- MONEY FIELDS & FORMATTING ----------

const MONEY_FIELDS = [
  'purchase_price', 'total_salary', 'main_activity_income', 'additional_income_total', 'other_income_total',
  'total_obligations_amount', 'monthly_obligations_payment', 'max_overdue_principal_amount', 'max_overdue_percent_amount',
  'company_revenue_total', 'company_net_profit', 'director_income_total',
  'company_obligations_amount', 'company_monthly_payment', 'director_obligations_amount', 'director_monthly_payment',
  'guarantor_monthly_income',
];

function parseNum(s) {
  return parseFloat(String(s).replace(/\s/g, '')) || 0;
}

function formatInputNumber(input) {
  const raw = input.value.replace(/[^0-9.,\-]/g, '').replace(',', '.');
  if (!raw || isNaN(Number(raw))) return;
  const pos = input.selectionStart;
  const lenBefore = input.value.length;
  input.value = Number(raw).toLocaleString('ru-RU');
  const lenAfter = input.value.length;
  const newPos = pos + (lenAfter - lenBefore);
  input.setSelectionRange(newPos, newPos);
}

function initMoneyFields() {
  MONEY_FIELDS.forEach(field => {
    const el = document.getElementById('f-' + field);
    if (el) el.addEventListener('input', () => formatInputNumber(el));
  });
}

// ---------- PASSPORT FORMATTING ----------

function formatPassport(input) {
  let v = input.value.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  let letters = v.substring(0, 2).replace(/[^A-Z]/g, '');
  let digits = v.substring(letters.length).replace(/\D/g, '').substring(0, 7);
  input.value = letters + (digits || letters.length === 2 ? ' ' : '') + digits;
}

function initPassportFields() {
  ['f-passport_series', 'f-guarantor_passport'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => formatPassport(el));
  });
}

// ---------- PINFL VALIDATION ----------

function validatePinfl(pinflId, birthDateId, errorId) {
  const pinflEl = document.getElementById(pinflId);
  const birthEl = document.getElementById(birthDateId);
  const errorEl = document.getElementById(errorId);
  if (!pinflEl || !birthEl || !errorEl) return;

  const pinfl = pinflEl.value.trim();
  const birthDate = birthEl.value; // yyyy-mm-dd

  if (!pinfl || pinfl.length !== 14 || !birthDate) {
    errorEl.style.display = 'none';
    pinflEl.style.borderColor = '';
    return;
  }

  const parts = birthDate.split('-');
  if (parts.length !== 3) return;
  const dd = parts[2];
  const mm = parts[1];
  const yy = parts[0].substring(2);
  const expected = dd + mm + yy;
  const actual = pinfl.substring(1, 7);

  if (actual !== expected) {
    errorEl.textContent = 'ПИНФЛ не совпадает с датой рождения (ожидается: ...' + expected + '...)';
    errorEl.style.display = 'block';
    pinflEl.style.borderColor = 'var(--red)';
  } else {
    errorEl.style.display = 'none';
    pinflEl.style.borderColor = '';
  }
}

function initPinflValidation() {
  const pinfl = document.getElementById('f-pinfl');
  const birthDate = document.getElementById('f-birth_date');
  if (pinfl) {
    pinfl.addEventListener('blur', () => validatePinfl('f-pinfl', 'f-birth_date', 'pinfl-error'));
  }
  if (birthDate) {
    birthDate.addEventListener('change', () => validatePinfl('f-pinfl', 'f-birth_date', 'pinfl-error'));
  }
  const gPinfl = document.getElementById('f-guarantor_pinfl');
  if (gPinfl) {
    gPinfl.addEventListener('blur', () => validatePinfl('f-guarantor_pinfl', 'f-birth_date', 'guarantor-pinfl-error'));
  }
}

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

function navigate(page, data) {
  currentPage = page;

  // Hide all pages
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

  // Show target page
  const target = document.getElementById('page-' + page);
  if (target) target.classList.add('active');

  // Update sidebar active state
  document.querySelectorAll('.nav-item').forEach(item => {
    const p = item.dataset.page;
    // view-anketa and new-anketa share the ankety nav highlight
    const match = p === page || (p === 'ankety' && (page === 'view-anketa' || page === 'new-anketa'));
    item.classList.toggle('active', match);
  });

  // Load page data
  if (page === 'dashboard') loadDashboardStats();
  if (page === 'users') loadUsers();
  if (page === 'rules') loadRules();
  if (page === 'risk-rules') loadRiskRules();
  if (page === 'ankety') loadAnketas();
  if (page === 'approvals') loadEditRequests();
  if (page === 'calculator') runLeaseCalc();
  if (page === 'roles') loadRoles();
  if (page === 'employee-stats') loadEmployeeStats();
  if (page === 'new-anketa') {
    if (data && data.loadExisting && data.anketaId) {
      currentAnketaId = data.anketaId;
      loadAnketaIntoForm(data.anketaId);
    } else if (data && data.isNew) {
      currentAnketaId = null;
      resetAnketaForm();
    }
  }
  if (page === 'view-anketa' && data && data.anketaId) {
    loadAnketaView(data.anketaId);
  }

  // Update URL without reload
  const urlMap = {
    dashboard: '/',
    users: '/admin',
    rules: '/admin/rules',
    'risk-rules': '/admin/risk-rules',
  };
  let url;
  if (page === 'view-anketa' && data && data.anketaId) {
    url = '/anketa/' + data.anketaId;
  } else {
    url = urlMap[page] || '/' + page;
  }
  history.pushState({ page, data }, '', url);
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
  currentUser = user;

  // Set user info in sidebar
  const initials = user.full_name
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  document.getElementById('userAvatar').textContent = initials;
  document.getElementById('userName').textContent = user.full_name;

  const perms = user.permissions || {};
  document.getElementById('userRole').textContent = user.role_name || (user.role === 'admin' ? 'Администратор' : 'Инспектор');

  // Permissions-based UI visibility
  const hasUserManage = perms.user_manage || user.role === 'admin';
  const hasRulesManage = perms.rules_manage || user.role === 'admin';
  const hasAnalyticsView = perms.analytics_view || user.role === 'admin';
  const hasExportExcel = perms.export_excel || user.role === 'admin';

  if (!hasUserManage && !hasRulesManage) {
    document.getElementById('adminSection').style.display = 'none';
  }
  document.getElementById('usersNavItem').style.display = hasUserManage ? '' : 'none';
  document.getElementById('rolesNavItem').style.display = hasUserManage ? '' : 'none';
  document.getElementById('rulesNavItem').style.display = hasRulesManage ? '' : 'none';
  document.getElementById('riskRulesNavItem').style.display = hasRulesManage ? '' : 'none';
  document.getElementById('empStatsNavItem').style.display = hasAnalyticsView ? '' : 'none';

  // Hide new-anketa nav and buttons if no anketa_create permission
  const hasAnketaCreate = perms.anketa_create !== false;
  const newAnketaNav = document.getElementById('newAnketaNavItem');
  if (newAnketaNav) newAnketaNav.style.display = hasAnketaCreate ? '' : 'none';
  document.querySelectorAll('.new-anketa-btn').forEach(btn => {
    btn.style.display = hasAnketaCreate ? '' : 'none';
  });

  // Setup anketa auto-calculations
  setupAnketaCalcListeners();

  // Load verdict rules for client-side preview
  loadVerdictRules();

  // Load risk rules for PV validation
  loadClientRiskRules();

  // Setup risk grade listeners
  setupRiskGradeListeners();

  // Setup money field formatting, passport masks, and PINFL validation
  initMoneyFields();
  initPassportFields();
  initPinflValidation();

  // Load pending edit requests count
  loadPendingRequestsCount();

  // Load notification count and start polling
  loadNotificationCount();
  setInterval(loadNotificationCount, 30000);

  // Route based on URL
  const path = window.location.pathname;
  const anketaMatch = path.match(/^\/anketa\/(\d+)$/);
  if (path === '/admin/risk-rules') {
    if (user.role === 'admin') {
      navigate('risk-rules');
    } else {
      navigate('dashboard');
    }
  } else if (path === '/admin/rules') {
    if (user.role === 'admin') {
      navigate('rules');
    } else {
      navigate('dashboard');
    }
  } else if (path === '/admin') {
    if (user.role === 'admin') {
      navigate('users');
    } else {
      navigate('dashboard');
    }
  } else if (path === '/dashboard' || path === '/') {
    navigate('dashboard');
  } else if (path === '/ankety') {
    navigate('ankety');
  } else if (path === '/new-anketa') {
    navigate('new-anketa');
  } else if (path === '/approvals') {
    navigate('approvals');
  } else if (path === '/calculator') {
    navigate('calculator');
  } else if (path === '/roles') {
    navigate('roles');
  } else if (path === '/employee-stats') {
    navigate('employee-stats');
  } else if (anketaMatch) {
    navigate('view-anketa', { anketaId: parseInt(anketaMatch[1]) });
  } else {
    navigate('dashboard');
  }
}

// ---------- USERS MANAGEMENT ----------

let usersData = [];

async function loadUsers() {
  const user = getUser();
  const _p = user && user.permissions;
  if (!user || (!(_p && _p.user_manage) && user.role !== 'admin')) {
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

  tbody.innerHTML = usersData.map(u => {
    const roleName = u.role_name || (u.role === 'admin' ? 'Администратор' : 'Инспектор');
    const roleBadge = u.role === 'admin'
      ? `<span class="role-badge role-admin">${escapeHtml(roleName)}</span>`
      : `<span class="role-badge role-inspector">${escapeHtml(roleName)}</span>`;

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
  loadRolesDropdown('newRoleId');
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
  const role_id = parseInt(document.getElementById('newRoleId').value);

  if (!fullName || !email || !role_id) {
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
      body: JSON.stringify({ full_name: fullName, email, role_id }),
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
  loadRolesDropdown('editRoleId', user.role_id);
  document.getElementById('editIsActive').checked = user.is_active;
  document.getElementById('editTelegramChatId').value = user.telegram_chat_id || '';
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
  const role_id = parseInt(document.getElementById('editRoleId').value);
  const telegram_chat_id = document.getElementById('editTelegramChatId').value.trim();

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
  const body = { full_name: fullName, role_id, is_active: isActive, telegram_chat_id };
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

// ---------- ANKETA: STATE ----------

let currentAnketaId = null;
let anketasData = [];

// All form field IDs (without f- prefix)
const anketaFields = [
  'consent_personal_data', 'full_name', 'birth_date', 'passport_series',
  'passport_issue_date', 'passport_issued_by', 'pinfl', 'registration_address',
  'registration_landmark', 'actual_address', 'actual_landmark', 'phone_numbers',
  'partner', 'car_brand', 'car_model', 'car_specs', 'car_year',
  'mileage', 'purchase_price', 'down_payment_percent',
  'lease_term_months', 'interest_rate', 'purchase_purpose',
  'has_official_employment', 'employer_name', 'salary_period_months', 'total_salary',
  'main_activity', 'main_activity_period', 'main_activity_income',
  'additional_income_source', 'additional_income_period', 'additional_income_total',
  'other_income_source', 'other_income_period', 'other_income_total',
  'property_type', 'property_details',
  'has_current_obligations', 'total_obligations_amount', 'obligations_count',
  'monthly_obligations_payment', 'closed_obligations_count',
  'max_overdue_principal_days', 'max_overdue_principal_amount',
  'max_continuous_overdue_percent_days', 'max_overdue_percent_amount',
  'overdue_category', 'last_overdue_date', 'overdue_reason',
  'risk_grade', 'no_scoring_response',
];

const leFields = [
  'company_name', 'company_inn', 'company_oked', 'company_legal_address',
  'company_actual_address', 'company_phone', 'director_full_name', 'director_phone',
  'director_family_phone', 'director_family_relation', 'contact_person_name',
  'contact_person_role', 'contact_person_phone',
  'company_revenue_period', 'company_revenue_total', 'company_net_profit',
  'director_income_period', 'director_income_total',
  'company_has_obligations', 'company_obligations_amount', 'company_obligations_count',
  'company_monthly_payment', 'company_overdue_category', 'company_last_overdue_date',
  'company_overdue_reason',
  'director_has_obligations', 'director_obligations_amount', 'director_obligations_count',
  'director_monthly_payment', 'director_overdue_category', 'director_last_overdue_date',
  'director_overdue_reason',
  'guarantor_full_name', 'guarantor_pinfl', 'guarantor_passport', 'guarantor_phone',
  'guarantor_monthly_income', 'guarantor_overdue_category', 'guarantor_last_overdue_date',
];

const leFloatFields = new Set([
  'company_revenue_period', 'company_revenue_total', 'company_net_profit',
  'director_income_period', 'director_income_total',
  'company_obligations_amount', 'company_monthly_payment',
  'director_obligations_amount', 'director_monthly_payment',
  'guarantor_monthly_income',
]);

const leIntFields = new Set([
  'company_obligations_count', 'director_obligations_count',
]);

// ---------- ANKETA: CREATE ----------

function createAnketa() {
  const _cp = currentUser && currentUser.permissions || {};
  if (_cp.anketa_create === false) {
    showToast('Нет права на создание анкет', 'error');
    return;
  }
  currentAnketaId = null;
  navigate('new-anketa', { anketaId: null, isNew: true });
}

function selectClientType(type) {
  _currentClientType = type;
  document.querySelectorAll('.client-type-option').forEach(opt => {
    opt.classList.toggle('selected', opt.dataset.type === type);
  });
  // Show/hide appropriate tabs
  const indTabs = document.getElementById('individualTabs');
  const leTabs = document.getElementById('legalTabs');
  if (indTabs) indTabs.style.display = type === 'individual' ? 'flex' : 'none';
  if (leTabs) leTabs.style.display = type === 'legal_entity' ? 'flex' : 'none';

  // Hide all tab content first
  document.querySelectorAll('#page-new-anketa .tab-content').forEach(c => c.classList.remove('active'));
  // Activate first tab of selected type
  if (type === 'individual') {
    document.getElementById('tab-personal')?.classList.add('active');
    switchTab('personal');
  } else {
    document.getElementById('tab-le-company')?.classList.add('active');
    switchTab('le-company');
  }
  renderFormSidebar();
}

// ---------- ANKETA: LIST ----------

async function loadAnketas() {
  try {
    const res = await fetch('/api/anketas', { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Ошибка загрузки');

    anketasData = await res.json();
    renderAnketasTable(anketasData);

    // Update badge count
    const badge = document.getElementById('anketyBadge');
    if (badge) badge.textContent = anketasData.length;
  } catch (err) {
    showToast('Ошибка загрузки анкет', 'error');
  }
}

function renderAnketasTable(data) {
  const tbody = document.getElementById('anketyTableBody');
  if (!data || data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-light)">Анкеты пока не созданы. Нажмите «+ Новая анкета»</td></tr>';
    return;
  }

  tbody.innerHTML = data.map(a => {
    const st = STATUS_MAP[a.status] || { label: a.status, cls: '' };
    const isLegal = a.client_type === 'legal_entity';
    const name = isLegal ? (a.company_name || 'Без названия') : (a.full_name || 'Без имени');
    const typeBadge = isLegal
      ? '<span class="type-badge type-legal">ЮР</span>'
      : '<span class="type-badge type-individual">ФИЗ</span>';
    const car = (a.car_brand && a.car_model)
      ? escapeHtml(a.car_brand + ' ' + a.car_model) + (a.car_year ? ' ' + a.car_year : '')
      : '—';
    const created = a.created_at ? new Date(a.created_at).toLocaleDateString('ru-RU') : '—';
    const creator = a.creator_name ? escapeHtml(a.creator_name) : '—';

    // Delete button — for own anketas or users with anketa_delete permission, not already deleted
    const _p = currentUser && currentUser.permissions || {};
    const canDelete = currentUser && (a.created_by === currentUser.id || _p.anketa_delete) && a.status !== 'deleted';
    const deleteBtn = canDelete
      ? `<button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); openDeleteAnketaModal(${a.id}, '${escapeHtml(name)}')">Удалить</button>`
      : '';

    return `
      <tr onclick="openAnketa(${a.id}, '${a.status}')">
        <td style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-light)">#${a.id}</td>
        <td><div class="td-main">${typeBadge} ${escapeHtml(name)}</div></td>
        <td><span class="status-badge ${st.cls}"><span class="status-dot"></span>${st.label}</span></td>
        <td>${car}</td>
        <td>${creator}</td>
        <td>${created}</td>
        <td>
          <div style="display:flex;gap:6px">
            <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); openAnketa(${a.id}, '${a.status}')">Открыть</button>
            ${deleteBtn}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function filterAnketas() {
  const q = (document.getElementById('anketySearch').value || '').toLowerCase();
  const status = document.getElementById('filterStatus').value;
  const clientType = document.getElementById('filterClientType').value;
  const dateFrom = document.getElementById('filterDateFrom').value;
  const dateTo = document.getElementById('filterDateTo').value;

  let filtered = anketasData;

  if (q) {
    filtered = filtered.filter(a =>
      (a.full_name || '').toLowerCase().includes(q) ||
      (a.company_name || '').toLowerCase().includes(q) ||
      String(a.id).includes(q) ||
      (a.car_brand || '').toLowerCase().includes(q) ||
      (a.car_model || '').toLowerCase().includes(q) ||
      (a.creator_name || '').toLowerCase().includes(q)
    );
  }
  if (status) {
    filtered = filtered.filter(a => a.status === status);
  }
  if (clientType) {
    filtered = filtered.filter(a => (a.client_type || 'individual') === clientType);
  }
  if (dateFrom) {
    const from = new Date(dateFrom);
    filtered = filtered.filter(a => a.created_at && new Date(a.created_at) >= from);
  }
  if (dateTo) {
    const to = new Date(dateTo);
    to.setDate(to.getDate() + 1);
    filtered = filtered.filter(a => a.created_at && new Date(a.created_at) <= to);
  }

  renderAnketasTable(filtered);
}

function clearAnketaFilters() {
  document.getElementById('anketySearch').value = '';
  document.getElementById('filterStatus').value = '';
  document.getElementById('filterClientType').value = '';
  document.getElementById('filterDateFrom').value = '';
  document.getElementById('filterDateTo').value = '';
  renderAnketasTable(anketasData);
}

function openAnketa(id, status) {
  if (status === 'draft') {
    // Only open in edit mode if user is the creator or has anketa_edit permission
    const perms = currentUser && currentUser.permissions || {};
    const canEdit = perms.anketa_edit !== false || perms.anketa_create !== false;
    if (canEdit) {
      navigate('new-anketa', { anketaId: id, loadExisting: true });
    } else {
      navigate('view-anketa', { anketaId: id });
    }
  } else {
    navigate('view-anketa', { anketaId: id });
  }
}

// ---------- ANKETA: LOAD INTO FORM ----------

async function loadAnketaIntoForm(id) {
  try {
    const res = await fetch('/api/anketas/' + id, { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Ошибка загрузки анкеты');

    const data = await res.json();
    fillAnketaForm(data);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function fillAnketaForm(data) {
  anketaFields.forEach(field => {
    const el = document.getElementById('f-' + field);
    if (!el) return;

    if (field === 'consent_personal_data' || field === 'no_scoring_response') {
      el.checked = !!data[field];
    } else if (MONEY_FIELDS.includes(field) && data[field] != null && typeof data[field] === 'number') {
      el.value = formatNumber(data[field]);
    } else if ((field === 'passport_series' || field === 'guarantor_passport') && data[field]) {
      // Format stored passport "AC1234567" → "AC 1234567"
      const v = String(data[field]).replace(/\s/g, '');
      el.value = v.length >= 2 ? v.substring(0, 2) + ' ' + v.substring(2) : v;
    } else {
      el.value = data[field] !== null && data[field] !== undefined ? data[field] : '';
    }
  });

  // Fill read-only calculated fields
  const calcFields = ['down_payment_amount', 'remaining_amount', 'monthly_payment', 'total_monthly_income', 'overdue_check_result'];
  calcFields.forEach(field => {
    const el = document.getElementById('f-' + field);
    if (el && data[field] !== null && data[field] !== undefined) {
      el.value = typeof data[field] === 'number' ? formatNumber(data[field]) : data[field];
    }
  });

  // Fill relative phones
  fillRelativePhones(data);

  // Set client type and fill LE fields
  if (data.client_type === 'legal_entity') {
    _currentClientType = 'legal_entity';
    selectClientType('legal_entity');

    // Fill consent checkbox for LE
    const leConsent = document.getElementById('f-le-consent_personal_data');
    if (leConsent) leConsent.checked = !!data.consent_personal_data;

    leFields.forEach(field => {
      const el = document.getElementById('f-' + field);
      if (!el) return;
      if (MONEY_FIELDS.includes(field) && data[field] != null && typeof data[field] === 'number') {
        el.value = formatNumber(data[field]);
      } else if (field === 'guarantor_passport' && data[field]) {
        const v = String(data[field]).replace(/\s/g, '');
        el.value = v.length >= 2 ? v.substring(0, 2) + ' ' + v.substring(2) : v;
      } else {
        el.value = data[field] !== null && data[field] !== undefined ? data[field] : '';
      }
    });

    // LE total monthly income
    const leIncome = document.getElementById('f-le-total_monthly_income');
    if (leIncome && data.total_monthly_income) leIncome.value = formatNumber(data.total_monthly_income);

    // LE risk grade fields
    const leRiskGrade = document.getElementById('f-le-risk_grade');
    if (leRiskGrade) leRiskGrade.value = data.risk_grade || '';
    const leNoScoring = document.getElementById('f-le-no_scoring_response');
    if (leNoScoring) leNoScoring.checked = !!data.no_scoring_response;
  } else {
    _currentClientType = 'individual';
    selectClientType('individual');
  }

  // Update DTI display
  updateDtiDisplay(data.dti, data.monthly_payment, data.monthly_obligations_payment, data.total_monthly_income);

  // Update form sidebar preview
  renderFormSidebar();

  // Update risk grade warning
  checkRiskGradePV();
}

function resetAnketaForm() {
  anketaFields.forEach(field => {
    const el = document.getElementById('f-' + field);
    if (!el) return;
    if (field === 'consent_personal_data' || field === 'no_scoring_response') {
      el.checked = false;
    } else {
      el.value = '';
    }
  });
  ['down_payment_amount', 'remaining_amount', 'monthly_payment', 'total_monthly_income', 'overdue_check_result'].forEach(f => {
    const el = document.getElementById('f-' + f);
    if (el) el.value = '';
  });
  // Reset relative phones to 1 empty row
  fillRelativePhones(null);
  // Reset LE fields
  leFields.forEach(field => {
    const el = document.getElementById('f-' + field);
    if (el) el.value = '';
  });
  const leConsent = document.getElementById('f-le-consent_personal_data');
  if (leConsent) leConsent.checked = false;
  const leIncome = document.getElementById('f-le-total_monthly_income');
  if (leIncome) leIncome.value = '';
  // Reset LE risk grade fields
  const leRiskGrade = document.getElementById('f-le-risk_grade');
  if (leRiskGrade) leRiskGrade.value = '';
  const leNoScoring = document.getElementById('f-le-no_scoring_response');
  if (leNoScoring) leNoScoring.checked = false;
  // Hide risk grade warnings
  const rgw = document.getElementById('riskGradeWarning');
  if (rgw) rgw.style.display = 'none';
  const lergw = document.getElementById('leRiskGradeWarning');
  if (lergw) lergw.style.display = 'none';
  _currentClientType = 'individual';
  selectClientType('individual');
  updateDtiDisplay(null);
  renderFormSidebar();
}

// ---------- ANKETA: COLLECT FORM DATA ----------

// Numeric fields that should be sent as floats
const floatFields = new Set([
  'purchase_price', 'down_payment_percent', 'interest_rate',
  'salary_period_months', 'total_salary',
  'main_activity_period', 'main_activity_income',
  'additional_income_period', 'additional_income_total',
  'other_income_period', 'other_income_total',
  'total_obligations_amount', 'monthly_obligations_payment',
  'max_overdue_principal_amount', 'max_overdue_percent_amount',
]);

// Integer fields
const intFields = new Set([
  'car_year', 'mileage', 'lease_term_months', 'obligations_count', 'closed_obligations_count',
  'max_overdue_principal_days', 'max_continuous_overdue_percent_days',
]);

function collectAnketaData() {
  const data = {};
  anketaFields.forEach(field => {
    const el = document.getElementById('f-' + field);
    if (!el) return;

    if (field === 'consent_personal_data' || field === 'no_scoring_response') {
      data[field] = el.checked;
    } else if (intFields.has(field)) {
      const v = el.value.trim();
      data[field] = v ? parseInt(v) || null : null;
    } else if (floatFields.has(field)) {
      const v = el.value.trim();
      data[field] = v ? parseNum(v) || null : null;
    } else if (el.type === 'number') {
      data[field] = el.value ? parseFloat(el.value) : null;
    } else if (el.value === '') {
      data[field] = null;
    } else {
      data[field] = el.value || null;
    }
  });
  // Collect relative phones as JSON
  data.relative_phones = JSON.stringify(collectRelativePhones());

  // Collect legal entity fields
  if (_currentClientType === 'legal_entity') {
    data.client_type = 'legal_entity';
    // Consent from LE checkbox
    const leConsent = document.getElementById('f-le-consent_personal_data');
    if (leConsent) data.consent_personal_data = leConsent.checked;

    leFields.forEach(field => {
      const el = document.getElementById('f-' + field);
      if (!el) return;
      if (leIntFields.has(field)) {
        const v = el.value.trim();
        data[field] = v ? parseInt(v) || null : null;
      } else if (leFloatFields.has(field)) {
        const v = el.value.trim();
        data[field] = v ? parseNum(v) || null : null;
      } else if (el.value === '') {
        data[field] = null;
      } else {
        data[field] = el.value || null;
      }
    });
    // LE risk grade fields
    const leRiskGrade = document.getElementById('f-le-risk_grade');
    if (leRiskGrade) data.risk_grade = leRiskGrade.value || null;
    const leNoScoring = document.getElementById('f-le-no_scoring_response');
    if (leNoScoring) data.no_scoring_response = leNoScoring.checked;
  } else {
    data.client_type = 'individual';
  }

  // Normalize passport fields — strip spaces
  if (data.passport_series) data.passport_series = data.passport_series.replace(/\s/g, '');
  if (data.guarantor_passport) data.guarantor_passport = data.guarantor_passport.replace(/\s/g, '');

  return data;
}

// ---------- ANKETA: RELATIVE PHONES ----------

let _relativePhoneCounter = 0;

function addRelativePhoneRow(phone, relation) {
  const container = document.getElementById('relativePhonesContainer');
  if (!container) return;
  _relativePhoneCounter++;
  const idx = _relativePhoneCounter;
  const row = document.createElement('div');
  row.className = 'relative-phone-row';
  row.id = 'rp-row-' + idx;
  row.style.cssText = 'display:flex;gap:8px;margin-bottom:8px;align-items:center';
  row.innerHTML = `
    <input class="form-input mono" style="flex:1" placeholder="+998 90 000-00-00" value="${escapeHtml(phone || '')}" data-rp-phone="${idx}">
    <select class="form-input" style="width:160px" data-rp-relation="${idx}">
      <option value="">— кем приходится —</option>
      <option value="Отец" ${relation === 'Отец' ? 'selected' : ''}>Отец</option>
      <option value="Мать" ${relation === 'Мать' ? 'selected' : ''}>Мать</option>
      <option value="Брат" ${relation === 'Брат' ? 'selected' : ''}>Брат</option>
      <option value="Сестра" ${relation === 'Сестра' ? 'selected' : ''}>Сестра</option>
      <option value="Супруг(а)" ${relation === 'Супруг(а)' ? 'selected' : ''}>Супруг(а)</option>
      <option value="Друг" ${relation === 'Друг' ? 'selected' : ''}>Друг</option>
      <option value="Коллега" ${relation === 'Коллега' ? 'selected' : ''}>Коллега</option>
      <option value="Другое" ${relation === 'Другое' ? 'selected' : ''}>Другое</option>
    </select>
    <button type="button" class="btn btn-sm btn-outline" onclick="removeRelativePhoneRow(${idx})" style="padding:6px 8px;color:var(--red);border-color:var(--red)">&times;</button>
  `;
  container.appendChild(row);
}

function removeRelativePhoneRow(idx) {
  const row = document.getElementById('rp-row-' + idx);
  if (row) row.remove();
}

function collectRelativePhones() {
  const result = [];
  const container = document.getElementById('relativePhonesContainer');
  if (!container) return result;
  container.querySelectorAll('.relative-phone-row').forEach(row => {
    const phoneEl = row.querySelector('[data-rp-phone]');
    const relEl = row.querySelector('[data-rp-relation]');
    const phone = (phoneEl?.value || '').trim();
    const relation = (relEl?.value || '').trim();
    if (phone) {
      result.push({ phone, relation });
    }
  });
  return result;
}

function fillRelativePhones(data) {
  const container = document.getElementById('relativePhonesContainer');
  if (!container) return;
  container.innerHTML = '';
  _relativePhoneCounter = 0;

  let phones = [];
  if (data && data.relative_phones) {
    try {
      const parsed = JSON.parse(data.relative_phones);
      if (Array.isArray(parsed)) {
        phones = parsed;
      }
    } catch {
      // Legacy format: plain comma-separated text
      const parts = data.relative_phones.split(',').map(s => s.trim()).filter(Boolean);
      phones = parts.map(p => ({ phone: p, relation: '' }));
    }
  }

  if (phones.length === 0) {
    addRelativePhoneRow();
    addRelativePhoneRow();
  } else {
    phones.forEach(p => addRelativePhoneRow(p.phone, p.relation));
  }
}

// ---------- ANKETA: SAVE DRAFT ----------

async function ensureAnketaCreated() {
  if (currentAnketaId) return true;
  try {
    const res = await fetch('/api/anketas?client_type=' + encodeURIComponent(_currentClientType), {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + getToken() },
    });
    if (res.status === 401) { logout(); return false; }
    if (!res.ok) throw new Error('Не удалось создать анкету');
    const created = await res.json();
    currentAnketaId = created.id;
    return true;
  } catch (err) {
    showToast(err.message, 'error');
    return false;
  }
}

async function saveAnketaDraft() {
  if (!(await ensureAnketaCreated())) return;

  const data = collectAnketaData();
  console.log('Saving draft, anketaId:', currentAnketaId, 'data:', data);

  try {
    const res = await fetch('/api/anketas/' + currentAnketaId, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    if (res.status === 401) { logout(); return; }

    const body = await res.json();
    if (!res.ok) {
      const msg = body.detail;
      throw new Error(Array.isArray(msg) ? msg.join(', ') : (typeof msg === 'string' ? msg : JSON.stringify(msg)));
    }

    fillAnketaForm(body);
    showToast('Черновик сохранён');
  } catch (err) {
    console.error('Save draft error:', err);
    showToast(err.message, 'error');
  }
}

// ---------- ANKETA: SAVE FINAL ----------

async function saveAnketaFinal() {
  // Check consent first
  const consentId = _currentClientType === 'legal_entity' ? 'f-le-consent_personal_data' : 'f-consent_personal_data';
  const consent = document.getElementById(consentId);
  if (!consent || !consent.checked) {
    showToast('Необходимо согласие на обработку персональных данных', 'error');
    switchTab('personal');
    return;
  }

  // Client-side PV validation against risk grade
  const pvError = checkRiskGradePV();
  if (pvError) {
    showToast(pvError, 'error');
    return;
  }

  // PINFL birth date warning (non-blocking)
  validatePinfl('f-pinfl', 'f-birth_date', 'pinfl-error');

  // Auto-create anketa if needed
  if (!(await ensureAnketaCreated())) return;

  // Save draft first to sync data
  const data = collectAnketaData();
  console.log('Saving final, anketaId:', currentAnketaId, 'data:', data);

  try {
    const patchRes = await fetch('/api/anketas/' + currentAnketaId, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    if (patchRes.status === 401) { logout(); return; }
    if (!patchRes.ok) {
      const body = await patchRes.json();
      const msg = body.detail;
      throw new Error(Array.isArray(msg) ? msg.join(', ') : (typeof msg === 'string' ? msg : JSON.stringify(msg)));
    }
  } catch (err) {
    console.error('Patch error:', err);
    showToast(err.message, 'error');
    return;
  }

  // Finalize
  try {
    const res = await fetch('/api/anketas/' + currentAnketaId + '/save', {
      method: 'POST',
      headers: authHeaders(),
    });
    if (res.status === 401) { logout(); return; }

    const body = await res.json();
    if (!res.ok) {
      const msg = body.detail;
      throw new Error(Array.isArray(msg) ? msg.join('\n') : (typeof msg === 'string' ? msg : JSON.stringify(msg)));
    }

    showToast('Анкета сохранена');
    navigate('view-anketa', { anketaId: currentAnketaId });
  } catch (err) {
    console.error('Save final error:', err);
    showToast(err.message, 'error');
  }
}

// ---------- ANKETA: TABS ----------

const TAB_ORDER_INDIVIDUAL = ['personal', 'deal', 'income', 'credit'];
const TAB_ORDER_LEGAL = ['le-company', 'deal', 'le-income', 'le-credit', 'le-guarantor'];

function getCurrentTabOrder() {
  return _currentClientType === 'legal_entity' ? TAB_ORDER_LEGAL : TAB_ORDER_INDIVIDUAL;
}

// Required fields per tab for validation
const TAB_REQUIRED = {
  personal: [
    { id: 'f-full_name', label: 'ФИО' },
    { id: 'f-birth_date', label: 'Дата рождения' },
    { id: 'f-pinfl', label: 'ПИНФЛ' },
    { id: 'f-passport_series', label: 'Паспорт' },
    { id: 'f-passport_issue_date', label: 'Дата выдачи' },
    { id: 'f-passport_issued_by', label: 'Кем выдан' },
    { id: 'f-registration_address', label: 'Адрес прописки' },
    { id: 'f-phone_numbers', label: 'Телефон клиента' },
    { id: 'f-consent_personal_data', label: 'Согласие на ПД', type: 'checkbox' },
    { id: '_relative_phones', label: 'Мин. 2 доп. контакта', type: 'custom', validate: validateRelativePhones },
  ],
  deal: [
    { id: 'f-car_brand', label: 'Марка' },
    { id: 'f-car_model', label: 'Модель' },
    { id: 'f-purchase_price', label: 'Стоимость' },
    { id: 'f-down_payment_percent', label: 'ПВ %' },
    { id: 'f-lease_term_months', label: 'Срок' },
    { id: 'f-interest_rate', label: 'Ставка %' },
  ],
  income: [],  // no strictly required fields
  credit: [
    { id: 'f-has_current_obligations', label: 'Наличие обязательств' },
    { id: 'f-overdue_category', label: 'Категория просрочки' },
  ],
};

// Legal entity tab required fields
TAB_REQUIRED['le-company'] = [
  { id: 'f-company_name', label: 'Наименование компании' },
  { id: 'f-company_inn', label: 'ИНН' },
  { id: 'f-director_full_name', label: 'ФИО директора' },
  { id: 'f-le-consent_personal_data', label: 'Согласие на ПД', type: 'checkbox' },
];
TAB_REQUIRED['le-income'] = [];
TAB_REQUIRED['le-credit'] = [];
TAB_REQUIRED['le-guarantor'] = [];

function validateRelativePhones() {
  const phones = collectRelativePhones();
  return phones.length >= 2;
}

function switchTab(tab) {
  // Deactivate all tabs and content
  document.querySelectorAll('#page-new-anketa .tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('#page-new-anketa .tab-content').forEach(c => c.classList.remove('active'));

  // Activate selected tab in both tab bars
  document.querySelectorAll('#page-new-anketa .tab[data-tab="' + tab + '"]').forEach(t => t.classList.add('active'));
  const content = document.getElementById('tab-' + tab);
  if (content) content.classList.add('active');

  updateTabProgress(tab);
  updateTabCheckmarks();
}

function updateTabProgress(currentTab) {
  const order = getCurrentTabOrder();
  const idx = order.indexOf(currentTab);
  const pct = ((idx + 1) / order.length) * 100;
  const fill = document.getElementById('tabProgressFill');
  if (fill) fill.style.width = pct + '%';
}

function updateTabCheckmarks() {
  getCurrentTabOrder().forEach(tab => {
    document.querySelectorAll('#page-new-anketa .tab[data-tab="' + tab + '"]').forEach(tabEl => {
      const existing = tabEl.querySelector('.tab-check');
      if (existing) existing.remove();

      const required = TAB_REQUIRED[tab] || [];
      if (required.length === 0) return;

      const allFilled = required.every(f => {
        if (f.type === 'custom' && f.validate) return f.validate();
        const el = document.getElementById(f.id);
        if (!el) return false;
        if (f.type === 'checkbox') return el.checked;
        return el.value.trim() !== '';
      });

      if (allFilled) {
        const check = document.createElement('span');
        check.className = 'tab-check';
        check.innerHTML = '&#10003;';
        tabEl.appendChild(check);
      }
    });
  });
}

function validateTab(tab) {
  const required = TAB_REQUIRED[tab] || [];
  if (required.length === 0) return true;

  // Clear previous errors
  document.querySelectorAll('.field-error').forEach(el => el.classList.remove('field-error'));
  document.querySelectorAll('.field-error-hint').forEach(el => el.remove());

  const missing = [];
  required.forEach(f => {
    if (f.type === 'custom' && f.validate) {
      if (!f.validate()) missing.push(f);
      return;
    }
    const el = document.getElementById(f.id);
    if (!el) return;
    if (f.type === 'checkbox') {
      if (!el.checked) missing.push(f);
    } else {
      if (el.value.trim() === '') {
        missing.push(f);
        el.classList.add('field-error');
        // Add hint below field
        const hint = document.createElement('div');
        hint.className = 'field-error-hint';
        hint.textContent = 'Обязательное поле';
        el.parentNode.appendChild(hint);
      }
    }
  });

  if (missing.length > 0) {
    // Scroll to first error
    const firstId = missing[0].id;
    if (firstId && firstId !== '_relative_phones') {
      const firstEl = document.getElementById(firstId);
      if (firstEl) firstEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    showToast('Заполните обязательные поля (' + missing.length + ')', 'error');
    return false;
  }
  return true;
}

function goNextTab(currentTab) {
  if (!validateTab(currentTab)) return;
  const order = getCurrentTabOrder();
  const idx = order.indexOf(currentTab);
  if (idx < order.length - 1) {
    switchTab(order[idx + 1]);
    document.querySelector('#page-new-anketa .content')?.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function goPrevTab(currentTab) {
  const order = getCurrentTabOrder();
  const idx = order.indexOf(currentTab);
  if (idx > 0) {
    switchTab(order[idx - 1]);
    document.querySelector('#page-new-anketa .content')?.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function switchViewTab(tab) {
  document.querySelectorAll('#page-view-anketa .tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('#page-view-anketa .tab-content').forEach(c => c.classList.remove('active'));

  const tabEl = document.querySelector('#page-view-anketa .tab[data-vtab="' + tab + '"]');
  if (tabEl) tabEl.classList.add('active');
  const content = document.getElementById('tab-' + tab);
  if (content) content.classList.add('active');
}

// ---------- ANKETA: VIEW ----------

let _currentViewData = null;

async function loadAnketaView(id) {
  try {
    const res = await fetch('/api/anketas/' + id, { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Анкета не найдена');

    const data = await res.json();
    renderAnketaView(data);
    // Reset history subtab to 'changes'
    _historySubtab = 'changes';
    const sc = document.getElementById('subtabChanges');
    const sv = document.getElementById('subtabViews');
    if (sc) sc.classList.add('active');
    if (sv) sv.classList.remove('active');
    const hc = document.getElementById('historyChanges');
    const hv = document.getElementById('historyViews');
    if (hc) hc.style.display = '';
    if (hv) hv.style.display = 'none';
    resetHistoryFilters();
    loadAnketaHistory(id);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function renderAnketaView(data) {
  _currentViewData = data;

  // Duplicate banner
  const banner = document.getElementById('duplicateBanner');
  if (data.duplicates && data.duplicates.length > 0) {
    document.getElementById('duplicateBannerList').innerHTML = data.duplicates.map(d => {
      const st = STATUS_MAP[d.status] || {label: d.status};
      return `<a class="duplicate-link" onclick="navigate('view-anketa',{anketaId:${d.id}})">#${d.id} — ${escapeHtml(d.full_name)} (${st.label}) — ${escapeHtml(d.match_field)}</a>`;
    }).join('');
    banner.style.display = 'flex';
  } else {
    banner.style.display = 'none';
  }

  document.getElementById('viewAnketaId').textContent = '#' + data.id;
  const isLegal = data.client_type === 'legal_entity';
  document.getElementById('viewAnketaName').textContent = isLegal
    ? (data.company_name || 'Анкета #' + data.id)
    : (data.full_name || 'Анкета #' + data.id);

  const st = STATUS_MAP[data.status] || { label: data.status, cls: '' };
  document.getElementById('viewAnketaStatus').className = 'status-badge ' + st.cls;
  document.getElementById('viewAnketaStatus').innerHTML = '<span class="status-dot"></span>' + st.label;

  // Update view tab labels based on client type
  const viewTabs = document.querySelectorAll('#page-view-anketa .tab');
  if (isLegal) {
    if (viewTabs[0]) viewTabs[0].textContent = '1. Компания';
    if (viewTabs[2]) viewTabs[2].textContent = '3. Доходы';
    if (viewTabs[3]) viewTabs[3].textContent = '4. КИ + Поруч.';
  } else {
    if (viewTabs[0]) viewTabs[0].textContent = '1. Личные данные';
    if (viewTabs[2]) viewTabs[2].textContent = '3. Доходы';
    if (viewTabs[3]) viewTabs[3].textContent = '4. Кред. история';
  }

  // Render personal / company data
  if (isLegal) {
    document.getElementById('view-personal').innerHTML = viewFieldsHtml([
      ['Наименование', data.company_name],
      ['ИНН', data.company_inn],
      ['ОКЭД', data.company_oked],
      ['Юр. адрес', data.company_legal_address, true],
      ['Факт. адрес', data.company_actual_address, true],
      ['Телефон компании', data.company_phone],
      ['ФИО директора', data.director_full_name],
      ['Телефон директора', data.director_phone],
      ['Тел. родственника', data.director_family_phone],
      ['Кем приходится', data.director_family_relation],
      ['Контактное лицо', data.contact_person_name],
      ['Должность', data.contact_person_role],
      ['Телефон конт. лица', data.contact_person_phone],
      ['Согласие на ПД', data.consent_personal_data ? 'Да' : 'Нет'],
    ]);
  } else {
    document.getElementById('view-personal').innerHTML = viewFieldsHtml([
      ['ФИО', data.full_name],
      ['Дата рождения', data.birth_date],
      ['ПИНФЛ', data.pinfl],
      ['Паспорт', data.passport_series],
      ['Дата выдачи', data.passport_issue_date],
      ['Кем выдан', data.passport_issued_by],
      ['Адрес прописки', data.registration_address, true],
      ['Ориентир (прописка)', data.registration_landmark, true],
      ['Адрес фактический', data.actual_address, true],
      ['Ориентир (факт.)', data.actual_landmark, true],
      ['Телефон', data.phone_numbers],
      ['Согласие на ПД', data.consent_personal_data ? 'Да' : 'Нет'],
    ]);

    // Add relative phones to personal view
    let rpHtml = '';
    if (data.relative_phones) {
      let phones = [];
      try {
        const parsed = JSON.parse(data.relative_phones);
        if (Array.isArray(parsed)) phones = parsed;
      } catch {
        phones = data.relative_phones.split(',').map(s => s.trim()).filter(Boolean).map(p => ({ phone: p, relation: '' }));
      }
      if (phones.length > 0) {
        const rpRows = phones.map(p => {
          const rel = p.relation ? ' (' + escapeHtml(p.relation) + ')' : '';
          return '<div style="padding:4px 0;font-size:13px">' + escapeHtml(p.phone) + rel + '</div>';
        }).join('');
        rpHtml = '<div class="form-group full"><label class="form-label">Дополнительные контакты</label><div style="padding:10px 14px;background:var(--bg);border-radius:8px;border:1px solid var(--border)">' + rpRows + '</div></div>';
      }
    }
    document.getElementById('view-personal').innerHTML += rpHtml;
  }

  // Render deal
  document.getElementById('view-deal').innerHTML = viewFieldsHtml([
    ['Партнёр', data.partner],
    ['Цель покупки', data.purchase_purpose],
    ['Марка', data.car_brand],
    ['Модель', data.car_model],
    ['Комплектация', data.car_specs],
    ['Год', data.car_year],
    ['Пробег', data.mileage ? formatNumber(data.mileage) + ' км' : null],
    ['Стоимость', data.purchase_price ? formatNumber(data.purchase_price) + ' сум' : null],
    ['ПВ %', data.down_payment_percent ? data.down_payment_percent + '%' : null],
    ['ПВ сумма', data.down_payment_amount ? formatNumber(data.down_payment_amount) + ' сум' : null],
    ['Остаток', data.remaining_amount ? formatNumber(data.remaining_amount) + ' сум' : null],
    ['Срок (мес)', data.lease_term_months],
    ['Ставка %', data.interest_rate ? data.interest_rate + '%' : null],
    ['Ежемесячный платёж', data.monthly_payment ? formatNumber(data.monthly_payment) + ' сум' : null, true],
  ]);

  // Render income
  if (isLegal) {
    document.getElementById('view-income').innerHTML = viewFieldsHtml([
      ['Период выручки (мес)', data.company_revenue_period],
      ['Выручка за период', data.company_revenue_total ? formatNumber(data.company_revenue_total) : null],
      ['Чистая прибыль', data.company_net_profit ? formatNumber(data.company_net_profit) : null],
      ['Период дохода директора (мес)', data.director_income_period],
      ['Доход директора за период', data.director_income_total ? formatNumber(data.director_income_total) : null],
      ['Общий месячный доход', data.total_monthly_income ? formatNumber(data.total_monthly_income) + ' сум' : null, true],
    ]);
  } else {
    document.getElementById('view-income').innerHTML = viewFieldsHtml([
      ['Официальное трудоустройство', data.has_official_employment],
      ['Работодатель', data.employer_name],
      ['Период ЗП (мес)', data.salary_period_months],
      ['Зарплата за период', data.total_salary ? formatNumber(data.total_salary) : null],
      ['Основная деятельность', data.main_activity],
      ['Период (мес)', data.main_activity_period],
      ['Доход', data.main_activity_income ? formatNumber(data.main_activity_income) : null],
      ['Доп. источник', data.additional_income_source],
      ['Период (мес)', data.additional_income_period],
      ['Доход', data.additional_income_total ? formatNumber(data.additional_income_total) : null],
      ['Прочий источник', data.other_income_source],
      ['Период (мес)', data.other_income_period],
      ['Доход', data.other_income_total ? formatNumber(data.other_income_total) : null],
      ['Общий месячный доход', data.total_monthly_income ? formatNumber(data.total_monthly_income) + ' сум' : null, true],
      ['Тип имущества', data.property_type],
      ['Описание имущества', data.property_details, true],
    ]);
  }

  // Render credit
  if (isLegal) {
    // DTI block
    const dtiHtml = data.dti !== null && data.dti !== undefined
      ? `<div class="form-group full"><div class="dti-block ${data.dti <= 50 ? '' : data.dti <= 70 ? 'warning' : 'danger'}">
          <div><div class="dti-label">${data.dti <= 50 ? 'DTI — В ПРЕДЕЛАХ НОРМЫ' : data.dti <= 70 ? 'DTI — ПОВЫШЕННЫЙ' : 'DTI — КРИТИЧЕСКИЙ'}</div></div>
          <div style="text-align:right"><div class="dti-value">${data.dti.toFixed(1)}%</div></div>
        </div></div>` : '';

    document.getElementById('view-credit').innerHTML =
      '<div class="section-divider" style="margin:0">Кредитная история компании</div>' +
      viewFieldsHtml([
        ['Обязательства', data.company_has_obligations],
        ['Кол-во', data.company_obligations_count],
        ['Сумма', data.company_obligations_amount ? formatNumber(data.company_obligations_amount) : null],
        ['Ежемесячный платёж', data.company_monthly_payment ? formatNumber(data.company_monthly_payment) : null],
        ['Просрочка', data.company_overdue_category],
        ['Дата просрочки', data.company_last_overdue_date],
        ['Причина', data.company_overdue_reason, true],
      ]) +
      '<div class="section-divider" style="margin:0">Кредитная история директора</div>' +
      viewFieldsHtml([
        ['Обязательства', data.director_has_obligations],
        ['Кол-во', data.director_obligations_count],
        ['Сумма', data.director_obligations_amount ? formatNumber(data.director_obligations_amount) : null],
        ['Ежемесячный платёж', data.director_monthly_payment ? formatNumber(data.director_monthly_payment) : null],
        ['Просрочка', data.director_overdue_category],
        ['Дата просрочки', data.director_last_overdue_date],
        ['Причина', data.director_overdue_reason, true],
      ]) +
      dtiHtml +
      '<div class="section-divider" style="margin:0">Поручитель</div>' +
      viewFieldsHtml([
        ['ФИО', data.guarantor_full_name],
        ['ПИНФЛ', data.guarantor_pinfl],
        ['Паспорт', data.guarantor_passport],
        ['Телефон', data.guarantor_phone],
        ['Доход', data.guarantor_monthly_income ? formatNumber(data.guarantor_monthly_income) : null],
        ['Просрочка', data.guarantor_overdue_category],
        ['Дата просрочки', data.guarantor_last_overdue_date],
      ]) +
      '<div class="section-divider" style="margin:0">Риск-грейд</div>' +
      viewFieldsHtml([
        ['Риск-грейд', data.risk_grade],
        ['Нет ответа от скоринга', data.no_scoring_response ? 'Да' : 'Нет'],
      ]);
  } else {
    const dtiHtml = data.dti !== null && data.dti !== undefined
      ? `<div class="form-group full"><div class="dti-block ${data.dti <= 50 ? '' : data.dti <= 70 ? 'warning' : 'danger'}">
          <div><div class="dti-label">${data.dti <= 50 ? 'DTI — В ПРЕДЕЛАХ НОРМЫ' : data.dti <= 70 ? 'DTI — ПОВЫШЕННЫЙ' : 'DTI — КРИТИЧЕСКИЙ'}</div></div>
          <div style="text-align:right"><div class="dti-value">${data.dti.toFixed(1)}%</div></div>
        </div></div>` : '';

    document.getElementById('view-credit').innerHTML = viewFieldsHtml([
      ['Наличие обязательств', data.has_current_obligations],
      ['Кол-во обязательств', data.obligations_count],
      ['Общая сумма обяз.', data.total_obligations_amount ? formatNumber(data.total_obligations_amount) : null],
      ['Ежемесячный платёж', data.monthly_obligations_payment ? formatNumber(data.monthly_obligations_payment) : null],
    ]) + dtiHtml + viewFieldsHtml([
      ['Закрытых обязательств', data.closed_obligations_count],
      ['Макс. просрочка ОД (дни)', data.max_overdue_principal_days],
      ['Сумма просрочки ОД', data.max_overdue_principal_amount ? formatNumber(data.max_overdue_principal_amount) : null],
      ['Непрерыв. просрочка % (дни)', data.max_continuous_overdue_percent_days],
      ['Сумма просрочки %', data.max_overdue_percent_amount ? formatNumber(data.max_overdue_percent_amount) : null],
      ['Категория просрочки', data.overdue_category],
      ['Дата последней просрочки', data.last_overdue_date],
      ['Результат проверки', data.overdue_check_result],
      ['Причина просрочки', data.overdue_reason, true],
    ]) +
    '<div class="section-divider" style="margin:0">Риск-грейд</div>' +
    viewFieldsHtml([
      ['Риск-грейд', data.risk_grade],
      ['Нет ответа от скоринга', data.no_scoring_response ? 'Да' : 'Нет'],
    ]);
  }

  // Render conclusion panel in sidebar
  renderConclusionPanel(data);
}

function viewFieldsHtml(fields) {
  return fields.map(([label, value, full]) => {
    const v = value !== null && value !== undefined && value !== '' ? escapeHtml(String(value)) : '<span style="color:var(--text-light)">—</span>';
    return `<div class="form-group${full ? ' full' : ''}">
      <label class="form-label">${escapeHtml(label)}</label>
      <div style="padding:10px 14px;background:var(--bg);border-radius:8px;font-size:13.5px;min-height:38px;border:1px solid var(--border)">${v}</div>
    </div>`;
  }).join('');
}

// ---------- ANKETA: AUTO-CALCULATIONS (CLIENT-SIDE) ----------

function calcAnnuity(principal, annualRate, months) {
  if (!principal || !annualRate || !months) return 0;
  const r = annualRate / 100 / 12;
  if (r === 0) return principal / months;
  return principal * (r * Math.pow(1 + r, months)) / (Math.pow(1 + r, months) - 1);
}

function runClientCalc() {
  const price = parseNum(document.getElementById('f-purchase_price').value);
  const dpPercent = parseFloat(document.getElementById('f-down_payment_percent').value) || 0;
  const term = parseInt(document.getElementById('f-lease_term_months').value) || 0;
  const rate = parseFloat(document.getElementById('f-interest_rate').value) || 0;

  // Down payment & remaining
  const dpAmount = price * dpPercent / 100;
  const remaining = price - dpAmount;
  document.getElementById('f-down_payment_amount').value = dpAmount ? formatNumber(dpAmount) : '';
  document.getElementById('f-remaining_amount').value = remaining ? formatNumber(remaining) : '';

  // Monthly payment
  const payment = calcAnnuity(remaining, rate, term);
  document.getElementById('f-monthly_payment').value = payment ? formatNumber(Math.round(payment)) : '';

  // Total monthly income
  let totalIncome = 0;
  if (_currentClientType === 'legal_entity') {
    const compRevPeriod = parseFloat(document.getElementById('f-company_revenue_period')?.value) || 0;
    const compRevTotal = parseNum(document.getElementById('f-company_revenue_total')?.value);
    const dirIncPeriod = parseFloat(document.getElementById('f-director_income_period')?.value) || 0;
    const dirIncTotal = parseNum(document.getElementById('f-director_income_total')?.value);
    if (compRevPeriod > 0 && compRevTotal > 0) totalIncome += compRevTotal / compRevPeriod;
    if (dirIncPeriod > 0 && dirIncTotal > 0) totalIncome += dirIncTotal / dirIncPeriod;
    const leIncomeEl = document.getElementById('f-le-total_monthly_income');
    if (leIncomeEl) leIncomeEl.value = totalIncome ? formatNumber(Math.round(totalIncome)) : '';
    // Also update hidden individual field for consistency
    document.getElementById('f-total_monthly_income').value = totalIncome ? formatNumber(Math.round(totalIncome)) : '';
  } else {
    const salaryPeriod = parseFloat(document.getElementById('f-salary_period_months').value) || 0;
    const totalSalary = parseNum(document.getElementById('f-total_salary').value);
    const mainPeriod = parseFloat(document.getElementById('f-main_activity_period').value) || 0;
    const mainIncome = parseNum(document.getElementById('f-main_activity_income').value);
    const addPeriod = parseFloat(document.getElementById('f-additional_income_period').value) || 0;
    const addIncome = parseNum(document.getElementById('f-additional_income_total').value);
    const otherPeriod = parseFloat(document.getElementById('f-other_income_period').value) || 0;
    const otherIncome = parseNum(document.getElementById('f-other_income_total').value);
    if (salaryPeriod > 0 && totalSalary > 0) totalIncome += totalSalary / salaryPeriod;
    if (mainPeriod > 0 && mainIncome > 0) totalIncome += mainIncome / mainPeriod;
    if (addPeriod > 0 && addIncome > 0) totalIncome += addIncome / addPeriod;
    if (otherPeriod > 0 && otherIncome > 0) totalIncome += otherIncome / otherPeriod;
    document.getElementById('f-total_monthly_income').value = totalIncome ? formatNumber(Math.round(totalIncome)) : '';
  }

  // DTI
  const obligations = parseNum(document.getElementById('f-monthly_obligations_payment').value);
  let dti = null;
  if (totalIncome > 0) {
    dti = (payment + obligations) / totalIncome * 100;
  }
  updateDtiDisplay(dti, payment, obligations, totalIncome);

  // Update LE DTI display (same value)
  if (_currentClientType === 'legal_entity') {
    updateLeDtiDisplay(dti, payment, obligations, totalIncome);
  }

  // Overdue check result
  const cat = document.getElementById('f-overdue_category').value;
  let checkResult = '';
  if (cat === 'до 30 дней') checkResult = 'ОК — допустимая просрочка';
  else if (cat === '31-60') checkResult = 'Внимание — умеренная просрочка';
  else if (cat === '61-90') checkResult = 'Риск — значительная просрочка';
  else if (cat === '90+') checkResult = 'Отказ — критическая просрочка';
  document.getElementById('f-overdue_check_result').value = checkResult;

  // Update form sidebar preview
  renderFormSidebar();
}

function updateDtiDisplay(dti, payment, obligations, income) {
  const block = document.getElementById('dtiBlock');
  const label = document.getElementById('dtiLabel');
  const value = document.getElementById('dtiValue');
  const sub = document.getElementById('dtiSub');
  const threshold = document.getElementById('dtiThreshold');

  if (!block) return;

  if (dti === null || dti === undefined || isNaN(dti)) {
    block.className = 'dti-block';
    label.textContent = 'DTI — нет данных';
    value.textContent = '—';
    sub.textContent = 'Заполните доходы и условия сделки';
    threshold.textContent = '';
    return;
  }

  const dtiRound = dti.toFixed(1);
  value.textContent = dtiRound + '%';

  const p = payment ? formatNumber(Math.round(payment)) : '0';
  const o = obligations ? formatNumber(Math.round(obligations)) : '0';
  const i = income ? formatNumber(Math.round(income)) : '0';
  sub.textContent = 'Платёж ' + p + ' + Обязательства ' + o + ' / Доход ' + i;

  if (dti <= 50) {
    block.className = 'dti-block';
    label.textContent = 'DTI — В ПРЕДЕЛАХ НОРМЫ';
    threshold.textContent = '≤ 50% — Одобрено';
  } else if (dti <= 70) {
    block.className = 'dti-block warning';
    label.textContent = 'DTI — ПОВЫШЕННЫЙ';
    threshold.textContent = '50-70% — Риск';
  } else {
    block.className = 'dti-block danger';
    label.textContent = 'DTI — КРИТИЧЕСКИЙ';
    threshold.textContent = '> 70% — Отказ';
  }
}

function updateLeDtiDisplay(dti, payment, obligations, income) {
  const block = document.getElementById('leDtiBlock');
  const label = document.getElementById('leDtiLabel');
  const value = document.getElementById('leDtiValue');
  const sub = document.getElementById('leDtiSub');
  const threshold = document.getElementById('leDtiThreshold');
  if (!block) return;

  if (dti === null || dti === undefined || isNaN(dti)) {
    block.className = 'dti-block';
    label.textContent = 'DTI — нет данных';
    value.textContent = '—';
    sub.textContent = 'Заполните доходы и условия сделки';
    threshold.textContent = '';
    return;
  }

  const dtiRound = dti.toFixed(1);
  value.textContent = dtiRound + '%';
  const p = payment ? formatNumber(Math.round(payment)) : '0';
  const o = obligations ? formatNumber(Math.round(obligations)) : '0';
  const i = income ? formatNumber(Math.round(income)) : '0';
  sub.textContent = 'Платёж ' + p + ' + Обязательства ' + o + ' / Доход ' + i;

  if (dti <= 50) {
    block.className = 'dti-block';
    label.textContent = 'DTI — В ПРЕДЕЛАХ НОРМЫ';
    threshold.textContent = '≤ 50% — Одобрено';
  } else if (dti <= 70) {
    block.className = 'dti-block warning';
    label.textContent = 'DTI — ПОВЫШЕННЫЙ';
    threshold.textContent = '50-70% — Риск';
  } else {
    block.className = 'dti-block danger';
    label.textContent = 'DTI — КРИТИЧЕСКИЙ';
    threshold.textContent = '> 70% — Отказ';
  }
}

function setupAnketaCalcListeners() {
  // Fields that trigger recalculation
  const calcTriggers = [
    'f-purchase_price', 'f-down_payment_percent', 'f-lease_term_months', 'f-interest_rate',
    'f-salary_period_months', 'f-total_salary',
    'f-main_activity_period', 'f-main_activity_income',
    'f-additional_income_period', 'f-additional_income_total',
    'f-other_income_period', 'f-other_income_total',
    'f-monthly_obligations_payment', 'f-overdue_category', 'f-last_overdue_date',
  ];

  calcTriggers.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', runClientCalc);
      el.addEventListener('change', runClientCalc);
    }
  });

  // Legal entity calc triggers
  const leCalcTriggers = [
    'f-company_revenue_period', 'f-company_revenue_total',
    'f-director_income_period', 'f-director_income_total',
    'f-company_monthly_payment', 'f-director_monthly_payment',
    'f-company_overdue_category', 'f-company_last_overdue_date',
    'f-director_overdue_category', 'f-director_last_overdue_date',
    'f-guarantor_overdue_category', 'f-guarantor_last_overdue_date',
  ];
  leCalcTriggers.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', runClientCalc);
      el.addEventListener('change', runClientCalc);
    }
  });

  // Listen to all required fields for checkmark updates
  const allRequiredIds = [];
  Object.values(TAB_REQUIRED).forEach(fields => {
    fields.forEach(f => {
      if (f.id && f.id !== '_relative_phones') allRequiredIds.push(f.id);
    });
  });
  allRequiredIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      const handler = () => {
        // Clear error styling on input
        el.classList.remove('field-error');
        const hint = el.parentNode?.querySelector('.field-error-hint');
        if (hint) hint.remove();
        updateTabCheckmarks();
      };
      el.addEventListener('input', handler);
      el.addEventListener('change', handler);
    }
  });
}

// ---------- ANKETA: FORMAT ----------

function formatNumber(n) {
  if (n === null || n === undefined) return '';
  return Math.round(n).toLocaleString('ru-RU');
}

// ---------- UTILS ----------

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ---------- CONCLUSION PANEL ----------

let _selectedDecision = null;

function renderConclusionPanel(data) {
  const panel = document.getElementById('conclusionPanel');
  if (!panel) return;

  // Summary metrics (always shown)
  const price = data.purchase_price ? formatNumber(data.purchase_price) + ' сум' : '—';
  const dp = data.down_payment_percent ? data.down_payment_percent + '%' : '—';
  const payment = data.monthly_payment ? formatNumber(data.monthly_payment) + ' сум' : '—';
  const income = data.total_monthly_income ? formatNumber(data.total_monthly_income) + ' сум' : '—';
  const dti = data.dti !== null && data.dti !== undefined ? data.dti.toFixed(1) + '%' : '—';
  const overdue = data.overdue_category || '—';

  const summaryHtml = `
    <div class="conclusion-summary">
      <div class="conclusion-summary-row"><span class="conclusion-summary-label">Стоимость</span><span class="conclusion-summary-value">${price}</span></div>
      <div class="conclusion-summary-row"><span class="conclusion-summary-label">ПВ %</span><span class="conclusion-summary-value">${dp}</span></div>
      <div class="conclusion-summary-row"><span class="conclusion-summary-label">Платёж</span><span class="conclusion-summary-value">${payment}</span></div>
      <div class="conclusion-summary-row"><span class="conclusion-summary-label">Доход</span><span class="conclusion-summary-value">${income}</span></div>
      <div class="conclusion-summary-row"><span class="conclusion-summary-label">DTI</span><span class="conclusion-summary-value">${dti}</span></div>
      <div class="conclusion-summary-row"><span class="conclusion-summary-label">Просрочка</span><span class="conclusion-summary-value">${escapeHtml(overdue)}</span></div>
    </div>
  `;

  // Granular permission checks
  const _permsC = currentUser && currentUser.permissions || {};
  const canConclude = currentUser && _permsC.anketa_conclude;
  const canEdit = currentUser && (currentUser.id === data.created_by || _permsC.anketa_edit);

  // Mode 1: decision already made — show result
  if (data.decision) {
    const decisionLabels = {
      approved: 'Одобрена',
      review: 'На рассмотрение',
      rejected_underwriter: 'Отказ андеррайтера',
      rejected_client: 'Отказ клиента',
    };
    const label = decisionLabels[data.decision] || data.decision;
    const concluder = data.concluder_name || '—';
    const concludedAt = data.concluded_at ? new Date(data.concluded_at).toLocaleString('ru-RU') : '—';
    const comment = data.conclusion_comment ? `<div class="conclusion-result-comment">${escapeHtml(data.conclusion_comment)}</div>` : '';
    const finalPvHtml = data.final_pv != null ? `<div class="conclusion-result-comment" style="font-weight:600">Итоговый ПВ: ${data.final_pv}%</div>` : '';

    // Auto-verdict info (if available)
    const autoDecisionLabels = { approved: 'Одобрено', review: 'На рассмотрение', rejected: 'Отказ' };
    let autoInfoHtml = '';
    if (data.auto_decision) {
      const avLabel = autoDecisionLabels[data.auto_decision] || data.auto_decision;
      const avCls = 'av-' + data.auto_decision;
      const reasons = (data.auto_decision_reasons || []);
      const reasonsHtml = reasons.length
        ? '<ul class="auto-verdict-reasons" style="margin:0;padding-left:16px">' + reasons.map(r => '<li>' + escapeHtml(r) + '</li>').join('') + '</ul>'
        : '';
      autoInfoHtml = `
        <div class="auto-verdict-block ${avCls}" style="margin-bottom:12px">
          <div class="auto-verdict-title">Авто-вердикт: ${escapeHtml(avLabel)}</div>
          ${reasonsHtml}
        </div>
      `;
    }

    // Edit request button
    let editRequestBtnHtml = '';
    if (canEdit && !data.has_pending_edit_request) {
      editRequestBtnHtml = `<button class="btn btn-outline" style="width:100%;margin-top:12px" onclick="showEditRequestModal(${data.id})">Запросить правку</button>`;
    } else if (data.has_pending_edit_request) {
      editRequestBtnHtml = `<div style="text-align:center;font-size:12px;color:var(--yellow);margin-top:12px;padding:8px;background:var(--yellow-bg);border-radius:8px">Запрос на правку ожидает рассмотрения</div>`;
    }

    panel.innerHTML = `
      <div class="conclusion-card">
        <div class="conclusion-card-title">Заключение</div>
        <div class="conclusion-result result-${data.decision}">
          <div class="conclusion-result-title">${escapeHtml(label)}</div>
          ${comment}
          ${finalPvHtml}
          <div class="conclusion-result-meta">${escapeHtml(concluder)} &middot; ${concludedAt}</div>
        </div>
        ${autoInfoHtml}
        ${summaryHtml}
        ${editRequestBtnHtml}
      </div>
    `;
    return;
  }

  // Mode 2: status === saved or review — show auto-verdict + conclusion form
  if ((data.status === 'saved' || data.status === 'review') && canConclude) {
    // Pre-select auto_decision
    _selectedDecision = data.auto_decision || null;

    // Auto-verdict block
    const autoDecisionLabels = { approved: 'Одобрено', review: 'На рассмотрение', rejected: 'Отказ' };
    let autoVerdictHtml = '';
    if (data.auto_decision) {
      const avLabel = autoDecisionLabels[data.auto_decision] || data.auto_decision;
      const avCls = 'av-' + data.auto_decision;
      const reasons = (data.auto_decision_reasons || []);
      const reasonsHtml = reasons.length
        ? '<ul class="auto-verdict-reasons" style="margin:0;padding-left:16px">' + reasons.map(r => '<li>' + escapeHtml(r) + '</li>').join('') + '</ul>'
        : '';
      const pvHtml = data.recommended_pv ? '<div style="font-size:12px;font-weight:600;margin-top:6px">Рекомендуемый ПВ: ' + data.recommended_pv + '%</div>' : '';
      autoVerdictHtml = `
        <div class="auto-verdict-block ${avCls}">
          <div class="auto-verdict-title">Авто-вердикт: ${escapeHtml(avLabel)}</div>
          ${reasonsHtml}
          ${pvHtml}
        </div>
      `;
    }

    // Build decision buttons with auto_decision pre-selected
    const decisions = [
      { key: 'approved', label: 'Одобрить' },
      { key: 'review', label: 'На рассмотр.' },
      { key: 'rejected_underwriter', label: 'Отказ андерр.' },
      { key: 'rejected_client', label: 'Отказ клиента' },
    ];
    const btnsHtml = decisions.map(d => {
      const sel = (d.key === _selectedDecision) ? ' selected-' + d.key : '';
      return `<button class="decision-btn${sel}" id="dbtn-${d.key}" onclick="selectDecision('${d.key}', this)">${d.label}</button>`;
    }).join('');

    panel.innerHTML = `
      <div class="conclusion-card">
        <div class="conclusion-card-title">Заключение андеррайтера</div>
        ${autoVerdictHtml}
        ${summaryHtml}
        <div style="font-size:12px;font-weight:600;color:var(--text-mid);margin-bottom:8px">Подтвердить или изменить решение:</div>
        <div class="decision-buttons">
          ${btnsHtml}
        </div>
        <div class="form-group" style="margin-bottom:12px">
          <label class="form-label">Итоговый ПВ%</label>
          <input type="number" id="conclusionFinalPv" class="form-input" step="0.1" min="0" max="100" placeholder="Укажите итоговый ПВ%" value="${data.final_pv != null ? data.final_pv : ''}">
          <div id="finalPvHint" class="field-hint-msg">${getFinalPvHint(data)}</div>
          <div id="finalPvError" class="field-error-msg" style="display:none"></div>
        </div>
        <div class="form-group" style="margin-bottom:12px">
          <label class="form-label">Комментарий</label>
          <textarea class="form-input" id="conclusionComment" rows="3" placeholder="Комментарий к решению (необязательно)"></textarea>
        </div>
        <button class="btn btn-primary" style="width:100%" id="saveConclusionBtn" onclick="saveConclusion(${data.id})">Сохранить заключение</button>
      </div>
    `;
    // Setup final PV validation listener
    const fpvInput = document.getElementById('conclusionFinalPv');
    if (fpvInput) {
      fpvInput.addEventListener('input', () => validateFinalPvInput(data));
    }
    return;
  }

  // Mode 3: draft or other — just summary
  const statusMsg = (data.status === 'saved' || data.status === 'review')
    ? 'Заключение ожидается от андеррайтера'
    : 'Заключение доступно после сохранения анкеты';
  panel.innerHTML = `
    <div class="conclusion-card">
      <div class="conclusion-card-title">Сводка</div>
      ${summaryHtml}
      <div style="font-size:12px;color:var(--text-light);text-align:center;padding:8px 0">${statusMsg}</div>
    </div>
  `;
}

function selectDecision(decision, btn) {
  _selectedDecision = decision;
  // Clear all selections
  document.querySelectorAll('.decision-btn').forEach(b => {
    b.className = 'decision-btn';
  });
  // Highlight selected
  btn.classList.add('selected-' + decision);
}

async function saveConclusion(anketaId) {
  if (!_selectedDecision) {
    showToast('Выберите решение', 'error');
    return;
  }

  // Validate final PV before saving (required)
  const finalPvStr = document.getElementById('conclusionFinalPv')?.value;
  const finalPv = finalPvStr ? parseFloat(finalPvStr) : null;

  if (finalPv === null || isNaN(finalPv)) {
    showToast('Укажите итоговый ПВ%', 'error');
    document.getElementById('conclusionFinalPv')?.focus();
    return;
  }

  // Client-side check against risk grade
  if (finalPv !== null && _currentViewData) {
    const grade = _currentViewData.risk_grade;
    const noScoring = _currentViewData.no_scoring_response;
    if (grade && !noScoring) {
      const rule = _clientRiskRules.find(r => r.category.toLowerCase() === grade.toLowerCase());
      if (rule && finalPv < rule.min_pv) {
        showToast(`Итоговый ПВ (${finalPv}%) ниже минимума для грейда ${grade} (${rule.min_pv}%)`, 'error');
        return;
      }
    }
  }

  if (!confirm('Сохранить заключение?')) return;

  const comment = (document.getElementById('conclusionComment')?.value || '').trim();
  const reqBody = { decision: _selectedDecision, comment: comment || null };
  if (finalPv !== null) reqBody.final_pv = finalPv;

  try {
    const res = await fetch('/api/anketas/' + anketaId + '/conclude', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(reqBody),
    });
    if (res.status === 401) { logout(); return; }

    const resBody = await res.json();
    if (!res.ok) {
      const msg = typeof resBody.detail === 'string' ? resBody.detail : JSON.stringify(resBody.detail);
      throw new Error(msg);
    }

    showToast('Заключение сохранено');
    renderAnketaView(resBody);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ---------- DELETE ANKETA ----------

function openDeleteAnketaModal(id, name) {
  document.getElementById('deleteAnketaId').value = id;
  document.getElementById('deleteAnketaLabel').textContent = '#' + id + ' — ' + name;
  document.getElementById('deleteAnketaReason').value = '';
  document.getElementById('deleteAnketaModal').classList.add('show');
}

function closeDeleteAnketaModal() {
  document.getElementById('deleteAnketaModal').classList.remove('show');
}

async function confirmDeleteAnketa() {
  const id = document.getElementById('deleteAnketaId').value;
  const reason = (document.getElementById('deleteAnketaReason').value || '').trim();

  if (!reason) {
    showToast('Укажите причину удаления', 'error');
    return;
  }

  const btn = document.getElementById('confirmDeleteBtn');
  btn.disabled = true;
  btn.textContent = 'Удаление...';

  try {
    const res = await fetch('/api/anketas/' + id, {
      method: 'DELETE',
      headers: authHeaders(),
      body: JSON.stringify({ reason }),
    });
    if (res.status === 401) { logout(); return; }

    if (!res.ok) {
      const body = await res.json();
      const msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      throw new Error(msg);
    }

    closeDeleteAnketaModal();
    showToast('Анкета удалена');
    loadAnketas();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Удалить';
  }
}

// ---------- DASHBOARD ----------

let _dashboardPeriod = 'week';

async function loadDashboardStats() {
  let url = '/api/anketas/stats?period=' + _dashboardPeriod;
  if (_dashboardPeriod === 'custom') {
    const from = document.getElementById('periodFrom')?.value;
    const to = document.getElementById('periodTo')?.value;
    if (from && to) {
      url += '&date_from=' + from + '&date_to=' + to;
    }
  }

  if (_dashboardClientType) {
    url += '&client_type=' + encodeURIComponent(_dashboardClientType);
  }

  try {
    const res = await fetch(url, { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Ошибка загрузки статистики');

    const stats = await res.json();
    renderDashboard(stats);
    loadAnalytics();
  } catch (err) {
    console.error('Dashboard error:', err);
  }
}

function renderDashboard(stats) {
  const rejected = stats.rejected_underwriter + stats.rejected_client;

  // Stat cards
  const cardsHtml = `
    <div class="stat-card">
      <div class="stat-label">Всего анкет</div>
      <div class="stat-value">${stats.total}</div>
      <div class="stat-sub">За выбранный период</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Одобрено</div>
      <div class="stat-value" style="color:var(--green)">${stats.approved}</div>
      <div class="stat-sub">Решение: одобрено</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">На рассмотрении</div>
      <div class="stat-value" style="color:var(--yellow)">${stats.review + stats.saved}</div>
      <div class="stat-sub">Сохранённые + на рассмотр.</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Отказано</div>
      <div class="stat-value" style="color:var(--red)">${rejected}</div>
      <div class="stat-sub">Андерр. ${stats.rejected_underwriter} / Клиент ${stats.rejected_client}</div>
    </div>
  `;
  document.getElementById('dashboardStats').innerHTML = cardsHtml;

  // Funnel bars
  const max = stats.total || 1;
  const funnelData = [
    { label: 'Всего',           count: stats.total,                  fill: 'fill-total' },
    { label: 'Сохранённые',     count: stats.saved,                  fill: 'fill-saved' },
    { label: 'Одобренные',      count: stats.approved,               fill: 'fill-approved' },
    { label: 'На рассмотр.',    count: stats.review,                 fill: 'fill-review' },
    { label: 'Отказ андерр.',   count: stats.rejected_underwriter,   fill: 'fill-rejected_underwriter' },
    { label: 'Отказ клиента',   count: stats.rejected_client,        fill: 'fill-rejected_client' },
  ];

  const funnelHtml = funnelData.map(f => {
    const pct = max > 0 ? Math.max(f.count / max * 100, f.count > 0 ? 8 : 0) : 0;
    return `
      <div class="funnel-row">
        <div class="funnel-label">${f.label}</div>
        <div class="funnel-bar">
          <div class="funnel-bar-fill ${f.fill}" style="width:${pct}%">${f.count > 0 ? f.count : ''}</div>
        </div>
        <div class="funnel-count">${f.count}</div>
      </div>
    `;
  }).join('');
  document.getElementById('funnelBody').innerHTML = funnelHtml;

  // Deleted count
  document.getElementById('deletedCount').innerHTML = stats.deleted > 0
    ? 'Удалённых анкет: <span>' + stats.deleted + '</span>'
    : '';
}

function setDashboardPeriod(period) {
  _dashboardPeriod = period;

  // Update buttons
  document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
  const btns = document.querySelectorAll('.period-btn');
  if (period === 'week') btns[0]?.classList.add('active');
  else if (period === 'month') btns[1]?.classList.add('active');
  else if (period === 'custom') btns[2]?.classList.add('active');

  // Show/hide date pickers
  const dates = document.getElementById('periodDates');
  if (dates) {
    dates.classList.toggle('show', period === 'custom');
  }

  if (period !== 'custom') {
    loadDashboardStats();
  }
}

function applyCustomPeriod() {
  const from = document.getElementById('periodFrom')?.value;
  const to = document.getElementById('periodTo')?.value;
  if (!from || !to) {
    showToast('Укажите обе даты', 'error');
    return;
  }
  loadDashboardStats();
}

function setClientTypeFilter(ct) {
  _dashboardClientType = ct;
  document.querySelectorAll('.client-filter-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.ct === ct);
  });
  loadDashboardStats();
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

// ---------- VERDICT RULES (for client preview) ----------

async function loadVerdictRules() {
  try {
    const res = await fetch('/api/anketas/verdict-rules', { headers: authHeaders() });
    if (res.ok) {
      _verdictRules = await res.json();
    }
  } catch (e) {
    console.warn('Could not load verdict rules', e);
  }
}

// ---------- UNDERWRITING RULES (admin page) ----------

async function loadRules() {
  const user = getUser();
  if (!user || user.role !== 'admin') {
    navigate('dashboard');
    return;
  }
  try {
    const res = await fetch('/api/admin/rules', { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Ошибка загрузки правил');
    rulesData = await res.json();
    renderRules();
  } catch (err) {
    showToast('Ошибка загрузки правил', 'error');
  }
}

function renderRules() {
  const container = document.getElementById('rulesContainer');
  if (!container) return;

  const categoryLabels = {
    dti: 'DTI (долговая нагрузка)',
    pv: 'Первоначальный взнос (ПВ)',
    overdue: 'Просрочки',
  };
  const categoryOrder = ['dti', 'pv', 'overdue'];

  // Group rules by category
  const groups = {};
  rulesData.forEach(r => {
    if (!groups[r.category]) groups[r.category] = [];
    groups[r.category].push(r);
  });

  let html = '';
  categoryOrder.forEach(cat => {
    const rules = groups[cat];
    if (!rules || !rules.length) return;

    html += `
      <div class="card">
        <div class="rule-category-title">${escapeHtml(categoryLabels[cat] || cat)}</div>
        <table>
          <thead>
            <tr>
              <th style="width:50%">Параметр</th>
              <th style="width:30%">Значение</th>
              <th style="width:20%">Действие</th>
            </tr>
          </thead>
          <tbody>
    `;
    rules.forEach(r => {
      let inputHtml;
      if (r.value_type === 'string') {
        inputHtml = `
          <select class="form-input" id="rule-val-${r.id}" style="width:100%">
            <option value="approved" ${r.value === 'approved' ? 'selected' : ''}>Одобрено</option>
            <option value="review" ${r.value === 'review' ? 'selected' : ''}>На рассмотрение</option>
            <option value="rejected" ${r.value === 'rejected' ? 'selected' : ''}>Отказ</option>
          </select>`;
      } else {
        inputHtml = `<input class="form-input" type="number" id="rule-val-${r.id}" value="${escapeHtml(r.value)}" step="${r.value_type === 'int' ? '1' : '0.1'}" style="width:100%">`;
      }
      html += `
        <tr>
          <td><div style="font-size:13px">${escapeHtml(r.label)}</div><div style="font-size:11px;color:var(--text-light);margin-top:2px">${escapeHtml(r.rule_key)}</div></td>
          <td>${inputHtml}</td>
          <td><button class="btn btn-outline btn-sm" onclick="saveRule(${r.id})">Сохранить</button></td>
        </tr>`;
    });
    html += '</tbody></table></div>';
  });

  container.innerHTML = html;
}

async function saveRule(ruleId) {
  const el = document.getElementById('rule-val-' + ruleId);
  if (!el) return;
  const value = el.value.trim();

  try {
    const res = await fetch('/api/admin/rules/' + ruleId, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ value }),
    });
    if (res.status === 401) { logout(); return; }
    const body = await res.json();
    if (!res.ok) {
      throw new Error(body.detail || 'Ошибка сохранения');
    }
    showToast('Правило обновлено');
    // Refresh verdict rules cache
    loadVerdictRules();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ---------- FORM SIDEBAR (new-anketa auto-verdict preview) ----------

function renderFormSidebar() {
  const panel = document.getElementById('formConclusionPanel');
  if (!panel) return;

  // Read current form values
  const price = parseFloat(document.getElementById('f-purchase_price')?.value) || 0;
  const dpPercent = parseFloat(document.getElementById('f-down_payment_percent')?.value) || 0;
  const payment = parseFloat((document.getElementById('f-monthly_payment')?.value || '').replace(/\s/g, '').replace(/,/g, '')) || 0;
  const income = parseFloat((document.getElementById('f-total_monthly_income')?.value || '').replace(/\s/g, '').replace(/,/g, '')) || 0;
  const obligations = parseFloat(document.getElementById('f-monthly_obligations_payment')?.value) || 0;
  const overdueCat = document.getElementById('f-overdue_category')?.value || '';
  const lastOverdueDate = document.getElementById('f-last_overdue_date')?.value || '';

  let dti = null;
  if (income > 0) {
    dti = (payment + obligations) / income * 100;
  }

  // Summary metrics
  const summaryRows = [
    { label: 'Стоимость', value: price ? formatNumber(price) + ' сум' : '—' },
    { label: 'ПВ %', value: dpPercent ? dpPercent + '%' : '—' },
    { label: 'Платёж', value: payment ? formatNumber(Math.round(payment)) + ' сум' : '—' },
    { label: 'Доход', value: income ? formatNumber(Math.round(income)) + ' сум' : '—' },
    { label: 'DTI', value: dti !== null ? dti.toFixed(1) + '%' : '—' },
    { label: 'Просрочка', value: overdueCat || '—' },
  ];

  const summaryHtml = summaryRows.map(r =>
    `<div class="conclusion-summary-row"><span class="conclusion-summary-label">${r.label}</span><span class="conclusion-summary-value">${escapeHtml(r.value)}</span></div>`
  ).join('');

  // Auto-verdict preview
  let verdictHtml = '';
  if (_verdictRules && dti !== null) {
    const verdict = calcClientAutoVerdict(dti, overdueCat, lastOverdueDate, dpPercent, _verdictRules);
    if (verdict) {
      const verdictLabels = { approved: 'Одобрено', review: 'На рассмотрение', rejected: 'Отказ' };
      const vLabel = verdictLabels[verdict.decision] || verdict.decision;
      const vCls = 'verdict-' + verdict.decision;
      const reasonsList = verdict.reasons.map(r => escapeHtml(r)).join('<br>');
      const pvLine = verdict.recommendedPv ? '<div class="verdict-preview-pv">Рекоменд. ПВ: ' + verdict.recommendedPv.toFixed(0) + '%</div>' : '';
      verdictHtml = `
        <div class="verdict-preview ${vCls}">
          <div class="verdict-preview-title">${escapeHtml(vLabel)}</div>
          <div class="verdict-preview-reasons">${reasonsList}</div>
          ${pvLine}
        </div>
      `;
    }
  } else if (!_verdictRules) {
    verdictHtml = '<div style="font-size:12px;color:var(--text-light);text-align:center;padding:8px 0">Загрузка правил...</div>';
  } else {
    verdictHtml = '<div style="font-size:12px;color:var(--text-light);text-align:center;padding:8px 0">Заполните данные для превью вердикта</div>';
  }

  panel.innerHTML = `
    <div class="form-sidebar-card">
      <div class="form-sidebar-title">Превью метрик</div>
      <div class="conclusion-summary">
        ${summaryHtml}
      </div>
      <div class="form-sidebar-title">Авто-вердикт</div>
      ${verdictHtml}
    </div>
  `;
}

// ---------- CLIENT AUTO-VERDICT CALCULATION ----------

function calcClientAutoVerdict(dti, overdueCat, lastOverdueDate, currentPv, rules) {
  if (!rules) return null;

  const reasons = [];
  let pvAdd = 0;

  // DTI check
  let dtiDecision = 'approved';
  const maxApprove = rules.max_dti_approve || 50;
  const maxReview = rules.max_dti_review || 60;

  if (dti !== null && dti !== undefined) {
    if (dti <= maxApprove) {
      dtiDecision = 'approved';
      reasons.push('DTI ' + dti.toFixed(1) + '% \u2264 ' + maxApprove + '% \u2014 одобрено');
    } else if (dti <= maxReview) {
      dtiDecision = 'review';
      reasons.push('DTI ' + dti.toFixed(1) + '% > ' + maxApprove + '%, \u2264 ' + maxReview + '% \u2014 на рассмотрение');
    } else {
      dtiDecision = 'rejected';
      reasons.push('DTI ' + dti.toFixed(1) + '% > ' + maxReview + '% \u2014 отказ');
    }
  }

  // Overdue check
  let overdueDecision = 'approved';
  const months = lastOverdueDate ? monthsSince(lastOverdueDate) : null;

  if (overdueCat && overdueCat !== 'до 30 дней' && overdueCat !== '') {
    if (overdueCat === '31-60') {
      const near = rules.overdue_31_60_threshold_near || 6;
      const far = rules.overdue_31_60_threshold_far || 12;
      if (months !== null && months < near) {
        overdueDecision = rules.overdue_31_60_lt_near_result || 'rejected';
        reasons.push('Просрочка 31-60, давность ' + months + ' мес < ' + near + ' мес \u2014 ' + overdueDecision);
      } else if (months !== null && months <= far) {
        overdueDecision = rules.overdue_31_60_near_to_far_result || 'review';
        pvAdd += rules.overdue_31_60_near_to_far_pv_add || 5;
        reasons.push('Просрочка 31-60, давность ' + months + ' мес (' + near + '\u2013' + far + ') \u2014 ' + overdueDecision);
      } else {
        overdueDecision = rules.overdue_31_60_gt_far_result || 'approved';
        pvAdd += rules.overdue_31_60_gt_far_pv_add || 5;
        const mStr = months !== null ? months + ' мес' : 'нет даты';
        reasons.push('Просрочка 31-60, давность ' + mStr + ' > ' + far + ' мес \u2014 ' + overdueDecision);
      }
    } else if (overdueCat === '61-90') {
      const thr = rules.overdue_61_90_threshold || 12;
      if (months !== null && months > thr) {
        overdueDecision = rules.overdue_61_90_gt_result || 'review';
        reasons.push('Просрочка 61-90, давность ' + months + ' мес > ' + thr + ' мес \u2014 ' + overdueDecision);
      } else {
        overdueDecision = rules.overdue_61_90_lte_result || 'rejected';
        const mStr = months !== null ? months + ' мес' : 'нет даты';
        reasons.push('Просрочка 61-90, давность ' + mStr + ' \u2264 ' + thr + ' мес \u2014 ' + overdueDecision);
      }
    } else if (overdueCat === '90+') {
      const thr = rules.overdue_90plus_threshold || 24;
      if (months !== null && months > thr) {
        overdueDecision = rules.overdue_90plus_gt_result || 'review';
        reasons.push('Просрочка 90+, давность ' + months + ' мес > ' + thr + ' мес \u2014 ' + overdueDecision);
      } else {
        overdueDecision = rules.overdue_90plus_lte_result || 'rejected';
        const mStr = months !== null ? months + ' мес' : 'нет даты';
        reasons.push('Просрочка 90+, давность ' + mStr + ' \u2264 ' + thr + ' мес \u2014 ' + overdueDecision);
      }
    }
  } else if (overdueCat === 'до 30 дней') {
    overdueDecision = rules.overdue_30_result || 'approved';
    reasons.push('Просрочка до 30 дней \u2014 ' + overdueDecision);
  }

  // Worst decision
  const order = { approved: 0, review: 1, rejected: 2 };
  const final = (order[dtiDecision] || 0) >= (order[overdueDecision] || 0) ? dtiDecision : overdueDecision;

  // Recommended PV — системная рекомендация, не зависит от выбора клиента
  const minPv = rules.min_pv_percent || 5;
  const recommendedPv = minPv + pvAdd;

  return { decision: final, reasons, recommendedPv };
}

function monthsSince(dateStr) {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr);
    const now = new Date();
    return (now.getFullYear() - d.getFullYear()) * 12 + (now.getMonth() - d.getMonth());
  } catch {
    return null;
  }
}

// ---------- EXCEL EXPORT ----------

function openExcelExportModal() {
  document.getElementById('excelDateFrom').value = '';
  document.getElementById('excelDateTo').value = '';
  document.getElementById('excelExportModal').classList.add('show');
}

function closeExcelExportModal() {
  document.getElementById('excelExportModal').classList.remove('show');
}

async function downloadExcel() {
  const btn = document.getElementById('downloadExcelBtn');
  btn.disabled = true;
  btn.textContent = 'Загрузка...';

  let url = '/api/admin/export-excel?';
  const from = document.getElementById('excelDateFrom')?.value;
  const to = document.getElementById('excelDateTo')?.value;
  if (from) url += 'date_from=' + from + '&';
  if (to) url += 'date_to=' + to + '&';

  try {
    const res = await fetch(url, { headers: { 'Authorization': 'Bearer ' + getToken() } });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Ошибка скачивания');

    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'anketas.xlsx';
    a.click();
    URL.revokeObjectURL(a.href);
    closeExcelExportModal();
    showToast('Excel файл скачан');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Скачать';
  }
}

// ---------- RISK RULES (admin page) ----------

async function loadRiskRules() {
  const user = getUser();
  if (!user || user.role !== 'admin') {
    navigate('dashboard');
    return;
  }
  try {
    const res = await fetch('/api/admin/risk-rules', { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Ошибка загрузки риск-правил');
    riskRulesData = await res.json();
    renderRiskRules();
  } catch (err) {
    showToast('Ошибка загрузки риск-правил', 'error');
  }
}

function renderRiskRules() {
  const container = document.getElementById('riskRulesContainer');
  if (!container) return;

  if (!riskRulesData.length) {
    container.innerHTML = '<div class="card"><div class="empty-state"><div class="empty-state-text">Нет риск-правил</div></div></div>';
    return;
  }

  let html = '<div class="card"><table><thead><tr><th>Категория</th><th>Мин. ПВ %</th><th>Активна</th><th>Действия</th></tr></thead><tbody>';
  riskRulesData.forEach(r => {
    html += `
      <tr>
        <td style="font-weight:600">${escapeHtml(r.category)}</td>
        <td><input class="form-input" type="number" id="rr-pv-${r.id}" value="${r.min_pv}" step="0.1" min="0" style="width:100px"></td>
        <td>
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
            <input type="checkbox" id="rr-active-${r.id}" ${r.is_active ? 'checked' : ''} style="width:16px;height:16px;accent-color:var(--purple)">
            ${r.is_active ? 'Да' : 'Нет'}
          </label>
        </td>
        <td>
          <div style="display:flex;gap:6px">
            <button class="btn btn-outline btn-sm" onclick="saveRiskRule(${r.id})">Сохранить</button>
            <button class="btn btn-sm btn-danger" onclick="deleteRiskRule(${r.id}, '${escapeHtml(r.category)}')">Удалить</button>
          </div>
        </td>
      </tr>`;
  });
  html += '</tbody></table></div>';
  container.innerHTML = html;
}

async function saveRiskRule(id) {
  const pvEl = document.getElementById('rr-pv-' + id);
  const activeEl = document.getElementById('rr-active-' + id);
  if (!pvEl) return;

  try {
    const res = await fetch('/api/admin/risk-rules/' + id, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({
        min_pv: parseFloat(pvEl.value),
        is_active: activeEl ? activeEl.checked : true,
      }),
    });
    if (res.status === 401) { logout(); return; }
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || 'Ошибка сохранения');
    showToast('Правило обновлено');
    loadRiskRules();
    loadClientRiskRules();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function deleteRiskRule(id, category) {
  if (!confirm('Удалить риск-правило "' + category + '"?')) return;

  try {
    const res = await fetch('/api/admin/risk-rules/' + id, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (res.status === 401) { logout(); return; }
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || 'Ошибка удаления');
    showToast('Правило удалено');
    loadRiskRules();
    loadClientRiskRules();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function showAddRiskRuleModal() {
  document.getElementById('newRiskRuleCategory').value = '';
  document.getElementById('newRiskRuleMinPv').value = '20';
  const errEl = document.getElementById('addRiskRuleError');
  if (errEl) { errEl.style.display = 'none'; errEl.textContent = ''; }
  document.getElementById('addRiskRuleModal').classList.add('show');
}

function closeAddRiskRuleModal() {
  document.getElementById('addRiskRuleModal').classList.remove('show');
}

async function createRiskRule() {
  const category = (document.getElementById('newRiskRuleCategory').value || '').trim();
  const minPv = parseFloat(document.getElementById('newRiskRuleMinPv').value);
  const errEl = document.getElementById('addRiskRuleError');

  if (!category) {
    errEl.textContent = 'Укажите категорию';
    errEl.style.display = 'block';
    errEl.classList.add('show');
    return;
  }
  if (isNaN(minPv) || minPv < 0) {
    errEl.textContent = 'Мин. ПВ должен быть >= 0';
    errEl.style.display = 'block';
    errEl.classList.add('show');
    return;
  }

  try {
    const res = await fetch('/api/admin/risk-rules', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ category, min_pv: minPv }),
    });
    if (res.status === 401) { logout(); return; }
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || 'Ошибка создания');
    closeAddRiskRuleModal();
    showToast('Правило создано');
    loadRiskRules();
    loadClientRiskRules();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.style.display = 'block';
    errEl.classList.add('show');
  }
}

// ---------- CLIENT RISK RULES (for PV validation) ----------

async function loadClientRiskRules() {
  try {
    const res = await fetch('/api/anketas/risk-rules', { headers: authHeaders() });
    if (res.ok) {
      _clientRiskRules = await res.json();
    }
  } catch (e) {
    console.warn('Could not load risk rules', e);
  }
}

// ---------- RISK GRADE PV VALIDATION ----------

function setupRiskGradeListeners() {
  // Individual fields
  const rgInput = document.getElementById('f-risk_grade');
  const nsCheckbox = document.getElementById('f-no_scoring_response');
  if (rgInput) rgInput.addEventListener('input', checkRiskGradePV);
  if (nsCheckbox) nsCheckbox.addEventListener('change', checkRiskGradePV);

  // Legal entity fields
  const leRgInput = document.getElementById('f-le-risk_grade');
  const leNsCheckbox = document.getElementById('f-le-no_scoring_response');
  if (leRgInput) leRgInput.addEventListener('input', checkRiskGradePV);
  if (leNsCheckbox) leNsCheckbox.addEventListener('change', checkRiskGradePV);

  // Also check when PV % changes
  const pvInput = document.getElementById('f-down_payment_percent');
  if (pvInput) pvInput.addEventListener('input', checkRiskGradePV);
}

function checkRiskGradePV() {
  // Determine which fields to use based on client type
  let gradeEl, noScoringEl, warningEl;
  if (_currentClientType === 'legal_entity') {
    gradeEl = document.getElementById('f-le-risk_grade');
    noScoringEl = document.getElementById('f-le-no_scoring_response');
    warningEl = document.getElementById('leRiskGradeWarning');
  } else {
    gradeEl = document.getElementById('f-risk_grade');
    noScoringEl = document.getElementById('f-no_scoring_response');
    warningEl = document.getElementById('riskGradeWarning');
  }

  if (!gradeEl || !warningEl) return null;

  const grade = (gradeEl.value || '').trim();
  const noScoring = noScoringEl ? noScoringEl.checked : false;

  if (!grade || noScoring) {
    warningEl.style.display = 'none';
    return null;
  }

  // Find matching rule
  const rule = _clientRiskRules.find(r => r.category.toLowerCase() === grade.toLowerCase());
  if (!rule) {
    warningEl.style.display = 'none';
    return null;
  }

  const pvPercent = parseFloat(document.getElementById('f-down_payment_percent')?.value) || 0;

  if (pvPercent < rule.min_pv) {
    warningEl.textContent = `ПВ (${pvPercent}%) ниже минимума для грейда ${rule.category} (${rule.min_pv}%)`;
    warningEl.style.display = 'block';
    warningEl.style.color = '#e74c3c';
    return `ПВ (${pvPercent}%) ниже минимума для грейда ${rule.category} (${rule.min_pv}%)`;
  } else {
    warningEl.textContent = `Мин. ПВ для грейда ${rule.category}: ${rule.min_pv}%`;
    warningEl.style.display = 'block';
    warningEl.style.color = '#e67e22';
    return null;
  }
}

// ---------- FINAL PV HELPERS ----------

function getFinalPvHint(data) {
  if (!data.risk_grade || data.no_scoring_response) {
    return 'Ограничений по ПВ нет';
  }
  const rule = _clientRiskRules.find(r => r.category.toLowerCase() === data.risk_grade.toLowerCase());
  if (rule) {
    return 'Мин. ПВ по грейду ' + rule.category + ': ' + rule.min_pv + '%';
  }
  return 'Грейд не найден в правилах';
}

function validateFinalPvInput(data) {
  const input = document.getElementById('conclusionFinalPv');
  const errorEl = document.getElementById('finalPvError');
  const saveBtn = document.getElementById('saveConclusionBtn');
  if (!input || !errorEl) return;

  const val = parseFloat(input.value);
  if (isNaN(val) || !data.risk_grade || data.no_scoring_response) {
    errorEl.style.display = 'none';
    if (saveBtn) saveBtn.disabled = false;
    return;
  }

  const rule = _clientRiskRules.find(r => r.category.toLowerCase() === data.risk_grade.toLowerCase());
  if (rule && val < rule.min_pv) {
    errorEl.textContent = `ПВ (${val}%) ниже минимума для грейда ${data.risk_grade} (${rule.min_pv}%)`;
    errorEl.style.display = 'block';
    if (saveBtn) saveBtn.disabled = true;
  } else {
    errorEl.style.display = 'none';
    if (saveBtn) saveBtn.disabled = false;
  }
}

// ---------- EDIT REQUESTS ----------

function showEditRequestModal(anketaId) {
  _editRequestAnketaId = anketaId;
  document.getElementById('editRequestReason').value = '';
  document.getElementById('editRequestModal').classList.add('show');
}

function closeEditRequestModal() {
  document.getElementById('editRequestModal').classList.remove('show');
  _editRequestAnketaId = null;
}

async function submitEditRequest() {
  const reason = (document.getElementById('editRequestReason').value || '').trim();
  if (!reason) {
    showToast('Укажите причину', 'error');
    return;
  }
  if (!_editRequestAnketaId) return;

  try {
    const res = await fetch('/api/anketas/' + _editRequestAnketaId + '/edit-request', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ reason }),
    });
    if (res.status === 401) { logout(); return; }

    const body = await res.json();
    if (!res.ok) {
      const msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      throw new Error(msg);
    }

    closeEditRequestModal();
    showToast('Запрос на правку отправлен');
    // Reload the anketa view to update the button state
    loadAnketaView(_editRequestAnketaId);
    loadPendingRequestsCount();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadEditRequests() {
  const filterEl = document.getElementById('editRequestsFilter');
  const status = filterEl ? filterEl.value : 'pending';
  const url = '/api/anketas/edit-requests' + (status ? '?status=' + status : '');

  try {
    const res = await fetch(url, { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Ошибка загрузки запросов');

    const requests = await res.json();
    renderEditRequests(requests);
  } catch (err) {
    showToast('Ошибка загрузки запросов', 'error');
  }
}

function renderEditRequests(requests) {
  const container = document.getElementById('editRequestsContainer');
  if (!container) return;

  if (!requests || requests.length === 0) {
    container.innerHTML = '<div class="card"><div class="empty-state"><div class="empty-state-icon" style="font-size:36px;opacity:0.3">&#10003;</div><div class="empty-state-text">Запросов нет</div></div></div>';
    return;
  }

  const statusLabels = { pending: 'Ожидает', approved: 'Одобрен', rejected: 'Отклонён' };
  const isAdmin = currentUser && currentUser.role === 'admin';

  container.innerHTML = requests.map(r => {
    const statusLabel = statusLabels[r.status] || r.status;
    const created = r.created_at ? new Date(r.created_at).toLocaleString('ru-RU') : '—';
    const reviewed = r.reviewed_at ? new Date(r.reviewed_at).toLocaleString('ru-RU') : '';
    const clientName = r.anketa_client_name || 'Анкета #' + r.anketa_id;

    let actionsHtml = '';
    if (r.status === 'pending' && isAdmin) {
      actionsHtml = `
        <div style="display:flex;gap:8px;margin-top:12px">
          <button class="btn btn-success btn-sm" onclick="reviewEditRequest(${r.id}, 'approved')">Одобрить</button>
          <button class="btn btn-danger btn-sm" onclick="reviewEditRequest(${r.id}, 'rejected')">Отклонить</button>
        </div>
      `;
    }

    let reviewInfo = '';
    if (r.status !== 'pending' && r.reviewer_name) {
      reviewInfo = `<div class="request-meta" style="margin-top:8px">Рассмотрел: ${escapeHtml(r.reviewer_name)}${reviewed ? ' — ' + reviewed : ''}${r.review_comment ? '<br>Комментарий: ' + escapeHtml(r.review_comment) : ''}</div>`;
    }

    return `
      <div class="request-card">
        <div class="request-header">
          <div>
            <span style="font-weight:600;font-size:14px;cursor:pointer;color:var(--purple)" onclick="openAnketa(${r.anketa_id}, '${r.anketa_status || ''}')">${escapeHtml(clientName)}</span>
            <span style="font-size:12px;color:var(--text-light);margin-left:8px">#${r.anketa_id}</span>
          </div>
          <span class="request-status ${r.status}">${statusLabel}</span>
        </div>
        <div class="request-reason">${escapeHtml(r.reason)}</div>
        <div class="request-meta">Запросил: ${escapeHtml(r.requester_name)} — ${created}</div>
        ${reviewInfo}
        ${actionsHtml}
      </div>
    `;
  }).join('');
}

async function reviewEditRequest(requestId, status) {
  const comment = prompt(status === 'approved' ? 'Комментарий (необязательно):' : 'Причина отклонения (необязательно):');
  if (comment === null) return; // cancelled

  try {
    const res = await fetch('/api/admin/edit-requests/' + requestId, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ status, comment: comment || null }),
    });
    if (res.status === 401) { logout(); return; }

    const body = await res.json();
    if (!res.ok) {
      const msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      throw new Error(msg);
    }

    showToast(status === 'approved' ? 'Запрос одобрен — анкета возвращена в черновик' : 'Запрос отклонён');
    loadEditRequests();
    loadPendingRequestsCount();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ---------- PENDING REQUESTS BADGE ----------

async function loadPendingRequestsCount() {
  if (!currentUser) return;

  const _perms = currentUser.permissions || {};
  if (_perms.user_manage || currentUser.role === 'admin') {
    try {
      const res = await fetch('/api/admin/edit-requests/count', { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        const badge = document.getElementById('approvalsBadge');
        if (badge) {
          if (data.count > 0) {
            badge.textContent = data.count;
            badge.style.display = '';
          } else {
            badge.style.display = 'none';
          }
        }
      }
    } catch (e) {
      // ignore
    }
  } else {
    // For inspectors, check their own pending requests
    try {
      const res = await fetch('/api/anketas/edit-requests?status=pending', { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        const badge = document.getElementById('approvalsBadge');
        if (badge) {
          if (data.length > 0) {
            badge.textContent = data.length;
            badge.style.display = '';
          } else {
            badge.style.display = 'none';
          }
        }
      }
    } catch (e) {
      // ignore
    }
  }
}

// ---------- ANKETA HISTORY ----------

const fieldLabels = {
  full_name: 'ФИО', birth_date: 'Дата рождения', passport_series: 'Серия паспорта',
  passport_issue_date: 'Дата выдачи', passport_issued_by: 'Кем выдан',
  pinfl: 'ПИНФЛ', registration_address: 'Адрес прописки',
  registration_landmark: 'Ориентир (прописка)', actual_address: 'Фактический адрес',
  actual_landmark: 'Ориентир (факт.)', phone_numbers: 'Телефон',
  relative_phones: 'Доп. контакты', partner: 'Партнёр',
  car_brand: 'Марка авто', car_model: 'Модель авто', car_specs: 'Комплектация',
  car_year: 'Год авто', mileage: 'Пробег',
  purchase_price: 'Стоимость', down_payment_percent: 'ПВ %',
  down_payment_amount: 'ПВ сумма', remaining_amount: 'Остаток',
  lease_term_months: 'Срок (мес)', interest_rate: 'Ставка %',
  monthly_payment: 'Ежемесячный платёж', purchase_purpose: 'Цель покупки',
  has_official_employment: 'Офиц. трудоустройство', employer_name: 'Работодатель',
  salary_period_months: 'Период ЗП (мес)', total_salary: 'Зарплата за период',
  main_activity: 'Осн. деятельность', main_activity_period: 'Период (мес)',
  main_activity_income: 'Доход от осн. деят.',
  additional_income_source: 'Доп. источник', additional_income_period: 'Доп. период (мес)',
  additional_income_total: 'Доп. доход',
  other_income_source: 'Прочий источник', other_income_period: 'Прочий период (мес)',
  other_income_total: 'Прочий доход',
  total_monthly_income: 'Общий месячный доход', property_type: 'Тип имущества',
  property_details: 'Описание имущества',
  has_current_obligations: 'Обязательства', total_obligations_amount: 'Сумма обяз.',
  obligations_count: 'Кол-во обяз.', monthly_obligations_payment: 'Ежемес. платёж по обяз.',
  dti: 'DTI', closed_obligations_count: 'Закрытых обяз.',
  overdue_category: 'Категория просрочки', last_overdue_date: 'Дата просрочки',
  overdue_check_result: 'Результат проверки', overdue_reason: 'Причина просрочки',
  decision: 'Решение', conclusion_comment: 'Комментарий', status: 'Статус',
  risk_grade: 'Риск-грейд', no_scoring_response: 'Нет ответа скоринга',
  final_pv: 'Итоговый ПВ',
  consent_personal_data: 'Согласие на ПД', client_type: 'Тип клиента',
  company_name: 'Наименование компании', company_inn: 'ИНН компании',
  company_oked: 'ОКЭД', company_legal_address: 'Юр. адрес',
  company_actual_address: 'Факт. адрес', company_phone: 'Телефон компании',
  director_full_name: 'ФИО директора', director_phone: 'Телефон директора',
  deletion_reason: 'Причина удаления',
};

let _fullHistory = [];
let _historySubtab = 'changes';

async function loadAnketaHistory(anketaId) {
  try {
    const res = await fetch('/api/anketas/' + anketaId + '/history', { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) return;

    const history = await res.json();
    _fullHistory = history;

    // Populate user filter
    const userSelect = document.getElementById('histFilterUser');
    if (userSelect) {
      const users = new Map();
      history.forEach(h => { if (h.changed_by_id && h.changed_by_name) users.set(h.changed_by_id, h.changed_by_name); });
      userSelect.innerHTML = '<option value="">Все пользователи</option>';
      users.forEach((name, id) => { userSelect.innerHTML += `<option value="${id}">${escapeHtml(name)}</option>`; });
    }

    // Populate field filter
    const fieldSelect = document.getElementById('histFilterField');
    if (fieldSelect) {
      const fields = new Set();
      history.forEach(h => { if (h.field_name) fields.add(h.field_name); });
      fieldSelect.innerHTML = '<option value="">Все поля</option>';
      fields.forEach(f => { fieldSelect.innerHTML += `<option value="${f}">${escapeHtml(fieldLabels[f] || f)}</option>`; });
    }

    renderAnketaHistory(history);
  } catch (e) {
    // ignore
  }
}

function applyHistoryFilters() {
  const dateFrom = document.getElementById('histFilterFrom')?.value || '';
  const dateTo = document.getElementById('histFilterTo')?.value || '';
  const userId = document.getElementById('histFilterUser')?.value || '';
  const field = document.getElementById('histFilterField')?.value || '';
  const search = (document.getElementById('histFilterSearch')?.value || '').toLowerCase();

  let filtered = _fullHistory;

  if (dateFrom) {
    filtered = filtered.filter(h => h.changed_at && h.changed_at >= dateFrom);
  }
  if (dateTo) {
    const toEnd = dateTo + 'T23:59:59';
    filtered = filtered.filter(h => h.changed_at && h.changed_at <= toEnd);
  }
  if (userId) {
    filtered = filtered.filter(h => String(h.changed_by_id) === userId);
  }
  if (field) {
    filtered = filtered.filter(h => h.field_name === field);
  }
  if (search) {
    filtered = filtered.filter(h =>
      (h.old_value && h.old_value.toLowerCase().includes(search)) ||
      (h.new_value && h.new_value.toLowerCase().includes(search))
    );
  }

  renderAnketaHistory(filtered);
}

function resetHistoryFilters() {
  const ids = ['histFilterFrom', 'histFilterTo', 'histFilterUser', 'histFilterField', 'histFilterSearch'];
  ids.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  renderAnketaHistory(_fullHistory);
}

function switchHistorySubtab(tab) {
  _historySubtab = tab;
  document.getElementById('subtabChanges').classList.toggle('active', tab === 'changes');
  document.getElementById('subtabViews').classList.toggle('active', tab === 'views');
  document.getElementById('historyChanges').style.display = tab === 'changes' ? '' : 'none';
  document.getElementById('historyViews').style.display = tab === 'views' ? '' : 'none';
  if (tab === 'views') loadViewLog();
}

async function loadViewLog() {
  const anketaId = _currentViewData?.id;
  if (!anketaId) return;
  const container = document.getElementById('historyViews');
  if (!container) return;
  container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-light);font-size:13px">Загрузка...</div>';
  try {
    const res = await fetch('/api/anketas/' + anketaId + '/view-log', { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) { container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-light);font-size:13px">Ошибка загрузки</div>'; return; }
    const log = await res.json();
    renderViewLog(log);
  } catch (e) {
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-light);font-size:13px">Ошибка загрузки</div>';
  }
}

function renderViewLog(log) {
  const container = document.getElementById('historyViews');
  if (!container) return;

  if (!log || log.length === 0) {
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-light);font-size:13px">Просмотров пока нет</div>';
    return;
  }

  let html = '<table class="history-table"><thead><tr><th>Кто</th><th>Когда</th></tr></thead><tbody>';
  log.forEach(v => {
    const who = v.user_name || '—';
    const when = v.viewed_at ? new Date(v.viewed_at).toLocaleString('ru-RU') : '—';
    html += `<tr><td>${escapeHtml(who)}</td><td style="white-space:nowrap">${when}</td></tr>`;
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

function renderAnketaHistory(history) {
  const container = document.getElementById('view-history');
  if (!container) return;

  if (!history || history.length === 0) {
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-light);font-size:13px">История изменений пуста</div>';
    return;
  }

  let html = '<table class="history-table"><thead><tr><th>Поле</th><th>Было</th><th>Стало</th><th>Кто</th><th>Когда</th></tr></thead><tbody>';
  history.forEach(h => {
    const label = fieldLabels[h.field_name] || h.field_name;
    const oldVal = h.old_value || '—';
    const newVal = h.new_value || '—';
    const who = h.changed_by_name || '—';
    const when = h.changed_at ? new Date(h.changed_at).toLocaleString('ru-RU') : '—';
    html += `<tr>
      <td style="font-weight:500">${escapeHtml(label)}</td>
      <td><span class="history-old">${escapeHtml(oldVal)}</span></td>
      <td><span class="history-new">${escapeHtml(newVal)}</span></td>
      <td>${escapeHtml(who)}</td>
      <td style="white-space:nowrap">${when}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

// ---------- LEASE CALCULATOR ----------

let _lcType = 'pervichka';
const lcFmt = n => Math.round(n).toLocaleString('ru-RU') + ' сум';
const lcFmtN = n => Math.round(n).toLocaleString('ru-RU');
const lcYrLabel = y => y === 1 ? 'год' : y < 5 ? 'года' : 'лет';

function setCalcType(t) {
  _lcType = t;
  document.getElementById('calcTypePerv').classList.toggle('active', t === 'pervichka');
  document.getElementById('calcTypeVtor').classList.toggle('active', t === 'vtorichka');
  if (t === 'pervichka') {
    document.getElementById('lc-fin_risk_pct').value = 4;
    document.getElementById('lc-gai').value = 3700000;
    document.getElementById('lc-fin_hint').textContent = '4% первичка';
    document.getElementById('lc-gai_hint').textContent = '3.7 млн';
    document.getElementById('lc-min_pv_pct').value = 5;
  } else {
    document.getElementById('lc-fin_risk_pct').value = 8;
    document.getElementById('lc-gai').value = 6050000;
    document.getElementById('lc-fin_hint').textContent = '8% вторичка';
    document.getElementById('lc-gai_hint').textContent = '6.05 млн';
    document.getElementById('lc-min_pv_pct').value = 0;
  }
  runLeaseCalc();
}

function lcPmt(rate, n, pv) {
  if (rate === 0) return pv / n;
  const f = Math.pow(1 + rate, n);
  return pv * rate * f / (f - 1);
}

function lcCalcDeal(body, years, monthlyPMTrate) {
  const months = years * 12;
  const monthly = lcPmt(monthlyPMTrate, months, body);
  let markup = 0, bal = body;
  for (let i = 0; i < months; i++) {
    const interest = bal * monthlyPMTrate;
    markup += interest;
    bal -= (monthly - interest);
  }
  return { body, months, monthly, markup, years };
}

function lcCalcMaxCar(income, obligations, cash, gai, finRiskPct, pmtRateAnn, minPvPct, isPervichka) {
  const monthlyPMTrate = pmtRateAnn / 12;
  const maxPayment = income * 0.5 - obligations;
  if (maxPayment <= 0) return null;

  return [1,2,3,4,5].map(years => {
    const months = years * 12;
    const f = Math.pow(1 + monthlyPMTrate, months);
    const maxBody = monthlyPMTrate === 0 ? maxPayment * months : maxPayment * (f - 1) / (monthlyPMTrate * f);
    const coeff = 1 + finRiskPct - 0.001;
    const subtracted = cash - gai;
    const carPriceMax = (maxBody + subtracted) / coeff;
    const finRiskAmt = carPriceMax * finRiskPct;
    const pvSum = isPervichka ? cash - finRiskAmt - gai : cash - gai;
    const loanBase = isPervichka ? carPriceMax : carPriceMax + finRiskAmt;
    const body = loanBase - pvSum - carPriceMax * 0.001;
    const payment = lcPmt(monthlyPMTrate, months, body);
    const pvPct = pvSum / carPriceMax;
    const pvOk = pvPct >= minPvPct;
    return { years, months, carPriceMax, pvSum, pvPct, body, payment, maxPayment, pvOk };
  });
}

function runLeaseCalc() {
  const cash        = parseFloat(document.getElementById('lc-cash').value) || 0;
  const income      = parseFloat(document.getElementById('lc-income').value) || 0;
  const obligations = parseFloat(document.getElementById('lc-obligations').value) || 0;
  const carPrice    = parseFloat(document.getElementById('lc-car_price').value) || 0;
  const prefYears   = parseInt(document.getElementById('lc-pref_years').value) || 0;
  const pmtRateAnn  = (parseFloat(document.getElementById('lc-pmt_rate').value) || 30.5) / 100;
  const markupRate  = (parseFloat(document.getElementById('lc-markup_rate').value) || 19.2) / 100;
  const finRiskPct  = (parseFloat(document.getElementById('lc-fin_risk_pct').value) || 4) / 100;
  const gai         = parseFloat(document.getElementById('lc-gai').value) || 0;
  const monthlyPMTrate = pmtRateAnn / 12;
  const buyout    = carPrice * 0.001;
  const finRisk   = carPrice * finRiskPct;
  const minPvPct   = (parseFloat(document.getElementById('lc-min_pv_pct').value) || 0) / 100;
  const minPvSum   = carPrice * minPvPct;
  const isPervichka = _lcType === 'pervichka';

  // ПВ из денег на руках
  const cashDeductions = isPervichka ? finRisk + gai : gai;
  const pvFromCash = cash - cashDeductions;
  const pvSum = Math.max(pvFromCash, minPvSum);
  const pvPct = carPrice > 0 ? pvSum / carPrice : 0;

  // Тело долга
  const loanBase = isPervichka ? carPrice : carPrice + finRisk;
  const body = loanBase - pvSum - buyout;

  // Первоначальные расходы клиента
  const firstPayment = isPervichka ? pvSum + finRisk + gai : pvSum + gai;

  // Предупреждения
  const wb = document.getElementById('lc-warn');
  if (cash < cashDeductions) {
    wb.classList.add('show');
    document.getElementById('lc-warn-text').textContent = isPervichka
      ? 'Денег не хватает на фиксированные расходы. Нужно минимум ' + lcFmt(finRisk + gai) + ' (Фин.риски ' + lcFmt(finRisk) + ' + ГАИ ' + lcFmt(gai) + ').'
      : 'Денег не хватает даже на ГАИ. Нужно минимум ' + lcFmt(gai) + '.';
  } else if (minPvSum > 0 && pvFromCash < minPvSum) {
    wb.classList.add('show');
    const minCash = minPvSum + cashDeductions;
    document.getElementById('lc-warn-text').textContent =
      'После вычета расходов остаток ' + lcFmt(pvFromCash) + ' < установленного мин. ПВ ' + (minPvPct*100).toFixed(0) + '% = ' + lcFmt(minPvSum) + '. Нужно минимум ' + lcFmt(minCash) + ' на руках.';
  } else {
    wb.classList.remove('show');
  }

  // Все варианты
  const deals = [1,2,3,4,5].map(yr => {
    const d = lcCalcDeal(body, yr, monthlyPMTrate);
    const markupDisplay = body * markupRate * yr;
    const dti = income > 0 ? (d.monthly + obligations) / income : 999;
    return { ...d, dti, pvSum, pvPct, firstPayment, markupDisplay };
  });

  // Оптимальный
  let best = null;
  if (prefYears > 0) best = deals.find(d => d.years === prefYears);
  if (!best) best = deals.find(d => d.dti <= 0.5);
  if (!best) best = [...deals].reverse().find(d => d.dti <= 0.6);
  if (!best) best = deals[deals.length - 1];

  // Отображение оптимального
  if (best) {
    document.getElementById('lc-opt_monthly').textContent = lcFmtN(Math.round(best.monthly));
    document.getElementById('lc-opt_monthly_sub').textContent = best.months + ' мес · PMT ' + (pmtRateAnn*100).toFixed(1) + '%/год';
    document.getElementById('lc-opt_term').textContent = best.years + ' ' + lcYrLabel(best.years) + ' (' + best.months + ' мес)';
    document.getElementById('lc-opt_pv_sub').textContent = 'ПВ ' + lcFmt(pvSum) + ' (' + (pvPct*100).toFixed(1) + '%)';
    document.getElementById('lc-opt_body').textContent = lcFmtN(Math.round(best.body));
    document.getElementById('lc-opt_first').textContent = lcFmtN(Math.round(firstPayment));
    document.getElementById('lc-opt_first_sub').textContent = isPervichka
      ? 'ПВ + Фин.риски + ГАИ'
      : 'ПВ + ГАИ (фин.риски в кредите)';
    const dtiTxt = income > 0 ? (best.dti*100).toFixed(1) + '%' : '—';
    document.getElementById('lc-opt_dti').textContent = dtiTxt;
    if (income === 0) {
      document.getElementById('lc-opt_status_title').textContent = 'Укажите доход';
      document.getElementById('lc-opt_status_sub').textContent = 'DTI не рассчитан';
    } else if (best.dti <= 0.5) {
      document.getElementById('lc-opt_status_title').textContent = 'ОДОБРЕНО';
      document.getElementById('lc-opt_status_sub').textContent = 'DTI <= 50% — сделка проходит';
    } else if (best.dti <= 0.6) {
      document.getElementById('lc-opt_status_title').textContent = 'НА РАССМОТРЕНИИ';
      document.getElementById('lc-opt_status_sub').textContent = 'DTI 50-60% — требует доп. проверки';
    } else {
      document.getElementById('lc-opt_status_title').textContent = 'ОТКАЗ';
      document.getElementById('lc-opt_status_sub').textContent = 'DTI > 60% — не одобряется';
    }
  }

  // Таблица вариантов
  let tbody = '';
  deals.forEach(d => {
    const isBest = best && d.years === best.years;
    const dtiTxt = income > 0 ? (d.dti*100).toFixed(1) + '%' : '—';
    let tag = '';
    if (income === 0) tag = '<span class="calc-tag calc-tag-orange">нет дохода</span>';
    else if (d.dti <= 0.5) tag = '<span class="calc-tag calc-tag-green">Одобрено</span>';
    else if (d.dti <= 0.6) tag = '<span class="calc-tag calc-tag-orange">Рассм.</span>';
    else tag = '<span class="calc-tag calc-tag-red">Отказ</span>';
    if (isBest) tag += ' <span class="calc-tag calc-tag-purple">опт.</span>';

    tbody += '<tr class="' + (isBest ? 'best-row' : '') + '">' +
      '<td>' + d.years + ' ' + lcYrLabel(d.years) + ' (' + d.months + ' мес)</td>' +
      '<td>' + lcFmtN(Math.round(pvSum)) + '<br><span style="font-size:10px;color:var(--text-light)">' + (pvPct*100).toFixed(1) + '%</span></td>' +
      '<td><strong>' + lcFmtN(Math.round(d.monthly)) + '</strong></td>' +
      '<td>' + lcFmtN(Math.round(d.markupDisplay)) + '</td>' +
      '<td>' + dtiTxt + '</td>' +
      '<td>' + tag + '</td>' +
      '</tr>';
  });
  document.getElementById('lc-variants_body').innerHTML = tbody;

  // Шаги объяснения
  if (!best) return;
  const bestMarkup = best.body * markupRate * best.years;

  document.getElementById('lc-steps').innerHTML =
    '<div class="calc-step">' +
      '<div class="calc-step-num">1</div>' +
      '<div>' +
        '<div class="calc-step-name">Деньги на руках → распределение</div>' +
        '<div class="calc-step-desc">' + (isPervichka
          ? 'Первичка: вычитаем Фин.риски + ГАИ, остаток → ПВ.'
          : 'Вторичка: вычитаем только ГАИ, остаток → ПВ. Фин.риски войдут в тело кредита.') + '</div>' +
        '<div class="calc-step-formula">' + lcFmtN(cash) + ' − ' + (isPervichka ? lcFmtN(Math.round(finRisk)) + ' − ' : '') + lcFmtN(gai) + ' = ' + lcFmtN(Math.round(pvFromCash)) + ' → ПВ</div>' +
      '</div>' +
      '<div class="calc-step-val">' + lcFmt(pvSum) + '</div>' +
    '</div>' +
    '<div class="calc-sdiv"></div>' +
    '<div class="calc-step">' +
      '<div class="calc-step-num">2</div>' +
      '<div>' +
        '<div class="calc-step-name">Первоначальный взнос</div>' +
        '<div class="calc-step-desc">' + (minPvPct > 0 ? 'Мин. ПВ установлен андеррайтером: ' + (minPvPct*100).toFixed(0) + '%.' : 'Минимальный ПВ не установлен — берём всё что осталось после расходов.') + '</div>' +
        '<div class="calc-step-formula">' + lcFmtN(Math.round(pvSum)) + ' / ' + lcFmtN(carPrice) + ' = ' + (pvPct*100).toFixed(1) + '% ' + (minPvPct > 0 ? (pvPct >= minPvPct ? '(ОК)' : '(ниже мин.)') : '') + '</div>' +
      '</div>' +
      '<div class="calc-step-val">' + (pvPct*100).toFixed(1) + '%</div>' +
    '</div>' +
    '<div class="calc-sdiv"></div>' +
    '<div class="calc-step">' +
      '<div class="calc-step-num">3</div>' +
      '<div>' +
        '<div class="calc-step-name">Тело долга (финансирует Fintech Drive)</div>' +
        '<div class="calc-step-desc">' + (isPervichka
          ? 'Авто − ПВ − Выкуп. Фин.риски клиент уже оплатил отдельно.'
          : 'Авто + Фин.риски − ПВ − Выкуп. Фин.риски включены в финансирование.') + '</div>' +
        '<div class="calc-step-formula">' + lcFmtN(carPrice) + (!isPervichka ? ' + ' + lcFmtN(Math.round(finRisk)) : '') + ' − ' + lcFmtN(Math.round(pvSum)) + ' − ' + lcFmtN(Math.round(buyout)) + ' = ' + lcFmtN(Math.round(best.body)) + ' сум</div>' +
      '</div>' +
      '<div class="calc-step-val">' + lcFmt(best.body) + '</div>' +
    '</div>' +
    '<div class="calc-sdiv"></div>' +
    '<div class="calc-step">' +
      '<div class="calc-step-num">4</div>' +
      '<div>' +
        '<div class="calc-step-name">Ежемесячный платёж — формула PMT</div>' +
        '<div class="calc-step-desc">Аннуитет: равный платёж каждый месяц. Ставка ' + (pmtRateAnn*100).toFixed(1) + '%/год = ' + (monthlyPMTrate*100).toFixed(4) + '%/мес.</div>' +
        '<div class="calc-step-formula">PMT(' + (monthlyPMTrate*100).toFixed(4) + '%/мес, ' + best.months + ' мес, ' + lcFmtN(Math.round(best.body)) + ') = ' + lcFmtN(Math.round(best.monthly)) + ' сум</div>' +
      '</div>' +
      '<div class="calc-step-val green">' + lcFmt(best.monthly) + '</div>' +
    '</div>' +
    '<div class="calc-sdiv"></div>' +
    '<div class="calc-step">' +
      '<div class="calc-step-num">5</div>' +
      '<div>' +
        '<div class="calc-step-name">Наценка итого (для клиента)</div>' +
        '<div class="calc-step-desc">Маркетинговая наценка = Тело x ' + (markupRate*100).toFixed(1) + '% x лет.</div>' +
        '<div class="calc-step-formula">' + lcFmtN(Math.round(best.body)) + ' x ' + (markupRate*100).toFixed(1) + '% x ' + best.years + ' лет = ' + lcFmtN(Math.round(bestMarkup)) + ' сум</div>' +
      '</div>' +
      '<div class="calc-step-val orange">' + lcFmt(bestMarkup) + '</div>' +
    '</div>' +
    '<div class="calc-sdiv"></div>' +
    '<div class="calc-step">' +
      '<div class="calc-step-num">6</div>' +
      '<div>' +
        '<div class="calc-step-name">Выкупной платёж (конец срока)</div>' +
        '<div class="calc-step-desc">0.1% от стоимости авто — символическая сумма для юр. перехода права собственности.</div>' +
        '<div class="calc-step-formula">' + lcFmtN(carPrice) + ' x 0.1% = ' + lcFmtN(Math.round(buyout)) + ' сум</div>' +
      '</div>' +
      '<div class="calc-step-val">' + lcFmt(buyout) + '</div>' +
    '</div>' +
    '<div class="calc-sdiv"></div>' +
    '<div class="calc-step">' +
      '<div class="calc-step-num">7</div>' +
      '<div>' +
        '<div class="calc-step-name">DTI — долговая нагрузка клиента</div>' +
        '<div class="calc-step-desc">≤ 50% → одобрение · 50-60% → на рассмотрении · > 60% → отказ</div>' +
        '<div class="calc-step-formula">(' + lcFmtN(Math.round(best.monthly)) + ' + ' + lcFmtN(obligations) + ') / ' + lcFmtN(income) + ' = ' + (income > 0 ? (best.dti*100).toFixed(1)+'%' : 'нет дохода') + '</div>' +
      '</div>' +
      '<div class="calc-step-val ' + (best.dti <= 0.5 ? 'green' : 'orange') + '">' + (income > 0 ? (best.dti*100).toFixed(1)+'%' : '—') + '</div>' +
    '</div>';

  // Макс авто
  updateLeaseMaxCar(income, obligations, cash, gai, finRiskPct, pmtRateAnn, minPvPct, isPervichka, prefYears, carPrice, monthlyPMTrate);
}

function updateLeaseMaxCar(income, obligations, cash, gai, finRiskPct, pmtRateAnn, minPvPct, isPervichka, prefYears, carPrice, monthlyPMTrate) {
  const card = document.getElementById('lc-maxcar');
  if (income === 0) { card.style.display = 'none'; return; }
  card.style.display = '';

  const results = lcCalcMaxCar(income, obligations, cash, gai, finRiskPct, pmtRateAnn, minPvPct, isPervichka);
  if (!results) { card.style.display = 'none'; return; }

  const best = prefYears > 0
    ? results.find(r => r.years === prefYears)
    : results.find(r => r.pvOk) || results[results.length - 1];

  document.getElementById('lc-mc_price').textContent = lcFmtN(Math.round(best.carPriceMax));
  document.getElementById('lc-mc_price_sub').textContent = best.years + ' ' + lcYrLabel(best.years) + ' · ' + (best.pvPct*100).toFixed(1) + '% ПВ';
  document.getElementById('lc-mc_pv').textContent = lcFmtN(Math.round(best.pvSum));
  document.getElementById('lc-mc_pv_sub').textContent = (best.pvPct*100).toFixed(1) + '% от авто';
  document.getElementById('lc-mc_payment').textContent = lcFmtN(Math.round(best.payment));
  document.getElementById('lc-mc_payment_sub').textContent = 'DTI ровно 50%';

  // Таблица по всем срокам
  let allHtml = '<table class="calc-table" style="margin-top:2px"><thead><tr>';
  ['Срок','Макс. авто','ПВ / %','Платёж/мес','Мин. ПВ'].forEach(h =>
    allHtml += '<th>' + h + '</th>'
  );
  allHtml += '</tr></thead><tbody>';
  results.forEach(r => {
    const isBest = r.years === best.years;
    const pvOkMark = minPvPct > 0 ? (r.pvOk ? ' (ОК)' : ' (!)') : '';
    allHtml += '<tr style="' + (isBest ? 'background:var(--green-bg);font-weight:600' : '') + '">' +
      '<td>' + r.years + ' ' + lcYrLabel(r.years) + '</td>' +
      '<td style="color:var(--green);font-weight:700">' + lcFmtN(Math.round(r.carPriceMax)) + '</td>' +
      '<td>' + lcFmtN(Math.round(r.pvSum)) + '<br><span style="font-size:10px;color:var(--text-light)">' + (r.pvPct*100).toFixed(1) + '%' + pvOkMark + '</span></td>' +
      '<td>' + lcFmtN(Math.round(r.payment)) + '</td>' +
      '<td style="font-size:11px">' + (minPvPct > 0 ? (minPvPct*100).toFixed(0)+'%' : '—') + '</td>' +
      '</tr>';
  });
  allHtml += '</tbody></table>';
  document.getElementById('lc-mc_all_terms').innerHTML = allHtml;

  // DTI бар для текущего авто
  if (carPrice > 0) {
    const finRisk = carPrice * finRiskPct;
    const pvFromCash2 = isPervichka ? cash - finRisk - gai : cash - gai;
    const pvSum2 = Math.max(pvFromCash2, carPrice * minPvPct);
    const loanBase2 = isPervichka ? carPrice : carPrice + finRisk;
    const body2 = loanBase2 - pvSum2 - carPrice * 0.001;
    const months = best.months;
    const f = Math.pow(1 + monthlyPMTrate, months);
    const payment2 = body2 * monthlyPMTrate * f / (f - 1);
    const dti = (payment2 + obligations) / income;
    const dtiPct = Math.min(dti * 100, 100);

    document.getElementById('lc-mc_current_dti').textContent = (dti*100).toFixed(1) + '%';
    const bar = document.getElementById('lc-mc_dti_bar');
    bar.style.width = dtiPct + '%';
    bar.className = 'calc-dti-bar-fill ' + (dti <= 0.5 ? 'green' : dti <= 0.6 ? 'orange' : 'red');
    document.getElementById('lc-mc_dti_bar_wrap').style.display = '';

    const diff = best.carPriceMax - carPrice;
    document.getElementById('lc-mc_note').textContent = diff >= 0
      ? 'Текущее авто (' + lcFmtN(Math.round(carPrice)) + ') вписывается. Клиент может позволить авто до ' + lcFmtN(Math.round(best.carPriceMax)) + ' сум (на ' + lcFmtN(Math.round(diff)) + ' больше).'
      : 'Текущее авто (' + lcFmtN(Math.round(carPrice)) + ') дороже максимума на ' + lcFmtN(Math.round(-diff)) + ' сум. Рекомендуем авто до ' + lcFmtN(Math.round(best.carPriceMax)) + ' сум.';
  } else {
    document.getElementById('lc-mc_dti_bar_wrap').style.display = 'none';
    document.getElementById('lc-mc_note').textContent = 'При текущих параметрах клиент может рассчитывать на авто до ' + lcFmtN(Math.round(best.carPriceMax)) + ' сум.';
  }
}

function resetLeaseCalc() {
  _lcType = 'pervichka';
  document.getElementById('calcTypePerv').classList.add('active');
  document.getElementById('calcTypeVtor').classList.remove('active');
  document.getElementById('lc-cash').value = 30000000;
  document.getElementById('lc-income').value = 5000000;
  document.getElementById('lc-obligations').value = 0;
  document.getElementById('lc-car_price').value = 266700000;
  document.getElementById('lc-pref_years').value = 0;
  document.getElementById('lc-pmt_rate').value = 30.5;
  document.getElementById('lc-markup_rate').value = 19.2;
  document.getElementById('lc-min_pv_pct').value = 5;
  document.getElementById('lc-fin_risk_pct').value = 4;
  document.getElementById('lc-gai').value = 3700000;
  document.getElementById('lc-fin_hint').textContent = '4% первичка';
  document.getElementById('lc-gai_hint').textContent = '3.7 млн';
  runLeaseCalc();
}

// ---------- NOTIFICATIONS ----------

let _notifDropdownOpen = false;

async function loadNotificationCount() {
  try {
    const res = await fetch('/api/anketas/notifications/unread-count', { headers: authHeaders() });
    if (res.status === 401) return;
    if (!res.ok) return;
    const data = await res.json();
    const badge = document.getElementById('notifBadge');
    if (data.count > 0) {
      badge.textContent = data.count > 99 ? '99+' : data.count;
      badge.style.display = '';
    } else {
      badge.style.display = 'none';
    }
  } catch (e) { /* silent */ }
}

function toggleNotificationPanel() {
  _notifDropdownOpen = !_notifDropdownOpen;
  const dd = document.getElementById('notifDropdown');
  dd.style.display = _notifDropdownOpen ? '' : 'none';
  if (_notifDropdownOpen) loadNotifications();
}

async function loadNotifications() {
  try {
    const res = await fetch('/api/anketas/notifications/list', { headers: authHeaders() });
    if (!res.ok) return;
    const notifs = await res.json();
    renderNotifications(notifs);
  } catch (e) { /* silent */ }
}

const NOTIF_ICONS = {
  edit_request_created: '&#9998;',
  edit_request_reviewed: '&#10003;',
  anketa_concluded: '&#128221;',
  duplicate_detected: '&#9888;',
};

function renderNotifications(notifs) {
  const container = document.getElementById('notifList');
  if (!notifs.length) {
    container.innerHTML = '<div class="notif-empty">Нет уведомлений</div>';
    return;
  }
  container.innerHTML = notifs.map(n => {
    const icon = NOTIF_ICONS[n.type] || '&#128276;';
    const cls = n.is_read ? 'notif-item notif-read' : 'notif-item notif-unread';
    const onclick = n.anketa_id
      ? `openNotificationAnketa(${n.id}, ${n.anketa_id})`
      : `markNotificationRead(${n.id})`;
    return `<div class="${cls}" onclick="${onclick}">
      <div class="notif-icon">${icon}</div>
      <div class="notif-content">
        <div class="notif-title">${escapeHtml(n.title)}</div>
        <div class="notif-message">${escapeHtml(n.message || '')}</div>
        <div class="notif-time">${timeAgo(n.created_at)}</div>
      </div>
    </div>`;
  }).join('');
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60) return 'только что';
  if (diff < 3600) return Math.floor(diff / 60) + ' мин. назад';
  if (diff < 86400) return Math.floor(diff / 3600) + ' ч. назад';
  return Math.floor(diff / 86400) + ' дн. назад';
}

async function openNotificationAnketa(notifId, anketaId) {
  try {
    await fetch('/api/anketas/notifications/' + notifId + '/read', {
      method: 'PATCH', headers: authHeaders()
    });
  } catch (e) { /* silent */ }
  _notifDropdownOpen = false;
  document.getElementById('notifDropdown').style.display = 'none';
  loadNotificationCount();
  navigate('view-anketa', { anketaId });
}

async function markNotificationRead(notifId) {
  try {
    await fetch('/api/anketas/notifications/' + notifId + '/read', {
      method: 'PATCH', headers: authHeaders()
    });
    loadNotifications();
    loadNotificationCount();
  } catch (e) { /* silent */ }
}

async function markAllNotificationsRead() {
  try {
    await fetch('/api/anketas/notifications/read-all', {
      method: 'POST', headers: authHeaders()
    });
    loadNotifications();
    loadNotificationCount();
  } catch (e) { /* silent */ }
}

document.addEventListener('click', (e) => {
  const section = document.getElementById('notificationSection');
  if (section && !section.contains(e.target) && _notifDropdownOpen) {
    _notifDropdownOpen = false;
    document.getElementById('notifDropdown').style.display = 'none';
  }
});


// ---------- ANALYTICS ----------

async function loadAnalytics() {
  let url = '/api/anketas/analytics?period=' + _dashboardPeriod;
  if (_dashboardPeriod === 'custom') {
    const from = document.getElementById('periodFrom')?.value;
    const to = document.getElementById('periodTo')?.value;
    if (from && to) url += '&date_from=' + from + '&date_to=' + to;
  }
  if (_dashboardClientType) {
    url += '&client_type=' + encodeURIComponent(_dashboardClientType);
  }
  try {
    const res = await fetch(url, { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) return;
    const data = await res.json();
    renderAnalytics(data);
  } catch (e) {
    console.error('Analytics error:', e);
  }
}

function deltaHtml(val, invert) {
  if (val === 0 || val === null || val === undefined) return '';
  const positive = invert ? val < 0 : val > 0;
  const arrow = positive ? '&#9650;' : '&#9660;';
  const cls = positive ? 'trend-up' : 'trend-down';
  return `<div class="stat-trend ${cls}">${arrow} ${Math.abs(val).toFixed(1)}</div>`;
}

function renderAnalytics(data) {
  // Analytics cards
  const approvalDelta = data.approval_rate - data.prev_approval_rate;
  const dtiDelta = data.avg_dti - data.prev_avg_dti;

  document.getElementById('analyticsCards').innerHTML = `
    <div class="stat-card">
      <div class="stat-label">% одобрения</div>
      <div class="stat-value" style="font-size:24px">${data.approval_rate.toFixed(1)}%</div>
      ${deltaHtml(approvalDelta, false)}
    </div>
    <div class="stat-card">
      <div class="stat-label">Средний DTI</div>
      <div class="stat-value" style="font-size:24px">${data.avg_dti.toFixed(1)}%</div>
      ${deltaHtml(dtiDelta, true)}
    </div>
  `;

  // Trend chart
  const trend = data.trend || [];
  const maxTotal = Math.max(...trend.map(t => t.total), 1);
  const barsHtml = trend.map(t => {
    const totalH = Math.round((t.total / maxTotal) * 120);
    const approvedH = Math.round((t.approved / maxTotal) * 120);
    return `<div class="trend-col">
      <div class="trend-value">${t.total}</div>
      <div class="trend-bars">
        <div class="trend-bar trend-bar-total" style="height:${Math.max(totalH, 4)}px"></div>
        <div class="trend-bar trend-bar-approved" style="height:${Math.max(approvedH, 2)}px"></div>
      </div>
      <div class="trend-label">${t.label}</div>
    </div>`;
  }).join('');

  document.getElementById('trendChart').innerHTML = `
    <div class="trend-chart">${barsHtml}</div>
    <div class="trend-legend">
      <div class="trend-legend-item"><div class="trend-dot" style="background:var(--purple)"></div> Всего</div>
      <div class="trend-legend-item"><div class="trend-dot" style="background:var(--green)"></div> Одобрено</div>
    </div>
  `;

  // Risk distribution
  const riskDist = data.risk_distribution || {};
  const riskKeys = Object.keys(riskDist).sort();
  const maxRisk = Math.max(...Object.values(riskDist), 1);
  if (riskKeys.length === 0) {
    document.getElementById('riskDistribution').innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-light);font-size:13px">Нет данных</div>';
  } else {
    document.getElementById('riskDistribution').innerHTML = riskKeys.map(k => {
      const v = riskDist[k];
      const pct = Math.round((v / maxRisk) * 100);
      return `<div class="funnel-row">
        <div class="funnel-label">${escapeHtml(k)}</div>
        <div class="funnel-bar"><div class="funnel-bar-fill fill-total" style="width:${Math.max(pct, 5)}%">${v}</div></div>
        <div class="funnel-count">${v}</div>
      </div>`;
    }).join('');
  }
}


// ---------- PRINT ----------

function _pv(val, suffix) {
  if (val === null || val === undefined || val === '') return '—';
  return escapeHtml(String(val)) + (suffix || '');
}

function _pd(val) {
  if (!val) return '—';
  try { return new Date(val).toLocaleDateString('ru-RU'); } catch(e) { return String(val); }
}

function _pn(val, suffix) {
  if (val === null || val === undefined) return '—';
  return formatNumber(val) + (suffix || '');
}

function _printRow(label, value) {
  return `<tr><td style="padding:4px 8px;font-size:11px;color:#555;width:220px;border-bottom:1px solid #eee">${label}</td><td style="padding:4px 8px;font-size:11px;font-weight:500;border-bottom:1px solid #eee">${value}</td></tr>`;
}

function _printSection(title) {
  return `<tr><td colspan="2" style="padding:10px 8px 4px;font-size:12px;font-weight:700;background:#f5f3fa;border-bottom:1px solid #ddd">${title}</td></tr>`;
}

function buildPrintContent(data) {
  const isLegal = data.client_type === 'legal_entity';
  let rows = '';

  // --- Блок 1: Клиент ---
  if (isLegal) {
    rows += _printSection('Компания');
    rows += _printRow('Наименование', _pv(data.company_name));
    rows += _printRow('ИНН', _pv(data.company_inn));
    rows += _printRow('ОКЭД', _pv(data.company_oked));
    rows += _printRow('Юридический адрес', _pv(data.company_legal_address));
    rows += _printRow('Фактический адрес', _pv(data.company_actual_address));
    rows += _printRow('Телефон компании', _pv(data.company_phone));
    rows += _printSection('Директор');
    rows += _printRow('ФИО директора', _pv(data.director_full_name));
    rows += _printRow('Телефон директора', _pv(data.director_phone));
    rows += _printRow('Телефон родственника', _pv(data.director_family_phone));
    rows += _printRow('Кем приходится', _pv(data.director_family_relation));
    rows += _printSection('Контактное лицо');
    rows += _printRow('ФИО', _pv(data.contact_person_name));
    rows += _printRow('Должность', _pv(data.contact_person_role));
    rows += _printRow('Телефон', _pv(data.contact_person_phone));
  } else {
    rows += _printSection('Клиент');
    rows += _printRow('ФИО', _pv(data.full_name));
    rows += _printRow('Дата рождения', _pd(data.birth_date));
    rows += _printRow('ПИНФЛ', _pv(data.pinfl));
    rows += _printRow('Серия/номер паспорта', _pv(data.passport_series));
    rows += _printRow('Дата выдачи', _pd(data.passport_issue_date));
    rows += _printRow('Кем выдан', _pv(data.passport_issued_by));
    rows += _printRow('Адрес регистрации', _pv(data.registration_address));
    rows += _printRow('Ориентир (рег.)', _pv(data.registration_landmark));
    rows += _printRow('Фактический адрес', _pv(data.actual_address));
    rows += _printRow('Ориентир (факт.)', _pv(data.actual_landmark));
    rows += _printRow('Телефон', _pv(data.phone_numbers));
    // Relative phones
    if (data.relative_phones) {
      try {
        const rp = JSON.parse(data.relative_phones);
        if (Array.isArray(rp)) {
          rp.forEach((p, i) => {
            if (p && p.phone) rows += _printRow(`Доп. контакт ${i+1}`, _pv(p.phone) + (p.relation ? ' (' + escapeHtml(p.relation) + ')' : ''));
          });
        }
      } catch(e) {
        rows += _printRow('Доп. контакты', _pv(data.relative_phones));
      }
    }
  }

  // --- Блок 2: Автомобиль и сделка ---
  rows += _printSection('Автомобиль и сделка');
  rows += _printRow('Партнёр', _pv(data.partner));
  rows += _printRow('Марка', _pv(data.car_brand));
  rows += _printRow('Модель', _pv(data.car_model));
  rows += _printRow('Комплектация', _pv(data.car_specs));
  rows += _printRow('Год выпуска', _pv(data.car_year));
  rows += _printRow('Пробег', _pn(data.mileage, ' км'));
  rows += _printRow('Стоимость', _pn(data.purchase_price, ' сум'));
  rows += _printRow('ПВ %', _pv(data.down_payment_percent, '%'));
  rows += _printRow('Сумма ПВ', _pn(data.down_payment_amount, ' сум'));
  rows += _printRow('Остаток', _pn(data.remaining_amount, ' сум'));
  rows += _printRow('Срок', _pv(data.lease_term_months, ' мес'));
  rows += _printRow('Ставка', _pv(data.interest_rate, '%'));
  rows += _printRow('Ежемесячный платёж', _pn(data.monthly_payment, ' сум'));
  rows += _printRow('Цель покупки', _pv(data.purchase_purpose));

  // --- Блок 3: Доходы ---
  rows += _printSection('Доходы');
  if (isLegal) {
    rows += _printRow('Выручка (период)', _pv(data.company_revenue_period, ' мес'));
    rows += _printRow('Выручка (сумма)', _pn(data.company_revenue_total, ' сум'));
    rows += _printRow('Чистая прибыль', _pn(data.company_net_profit, ' сум'));
    rows += _printRow('Доход директора (период)', _pv(data.director_income_period, ' мес'));
    rows += _printRow('Доход директора (сумма)', _pn(data.director_income_total, ' сум'));
  } else {
    rows += _printRow('Официальное трудоустройство', _pv(data.has_official_employment));
    rows += _printRow('Работодатель', _pv(data.employer_name));
    rows += _printRow('Зарплата (период)', _pv(data.salary_period_months, ' мес'));
    rows += _printRow('Зарплата (сумма)', _pn(data.total_salary, ' сум'));
    rows += _printRow('Основная деятельность', _pv(data.main_activity));
    rows += _printRow('Осн. деят. (период)', _pv(data.main_activity_period, ' мес'));
    rows += _printRow('Осн. деят. (доход)', _pn(data.main_activity_income, ' сум'));
    rows += _printRow('Доп. доход (источник)', _pv(data.additional_income_source));
    rows += _printRow('Доп. доход (период)', _pv(data.additional_income_period, ' мес'));
    rows += _printRow('Доп. доход (сумма)', _pn(data.additional_income_total, ' сум'));
    rows += _printRow('Прочий доход (источник)', _pv(data.other_income_source));
    rows += _printRow('Прочий доход (период)', _pv(data.other_income_period, ' мес'));
    rows += _printRow('Прочий доход (сумма)', _pn(data.other_income_total, ' сум'));
    rows += _printRow('Имущество', _pv(data.property_type));
    rows += _printRow('Описание имущества', _pv(data.property_details));
  }
  rows += _printRow('Итого месячный доход', _pn(data.total_monthly_income, ' сум'));

  // --- Блок 4: Кредитная история ---
  rows += _printSection('Кредитная история');
  if (isLegal) {
    rows += _printRow('<b>Компания</b>', '');
    rows += _printRow('Наличие обязательств', _pv(data.company_has_obligations));
    rows += _printRow('Сумма обязательств', _pn(data.company_obligations_amount, ' сум'));
    rows += _printRow('Кол-во обязательств', _pv(data.company_obligations_count));
    rows += _printRow('Ежемесячный платёж', _pn(data.company_monthly_payment, ' сум'));
    rows += _printRow('Категория просрочки', _pv(data.company_overdue_category));
    rows += _printRow('Дата последней просрочки', _pd(data.company_last_overdue_date));
    rows += _printRow('Причина просрочки', _pv(data.company_overdue_reason));

    rows += _printRow('<b>Директор</b>', '');
    rows += _printRow('Наличие обязательств', _pv(data.director_has_obligations));
    rows += _printRow('Сумма обязательств', _pn(data.director_obligations_amount, ' сум'));
    rows += _printRow('Кол-во обязательств', _pv(data.director_obligations_count));
    rows += _printRow('Ежемесячный платёж', _pn(data.director_monthly_payment, ' сум'));
    rows += _printRow('Категория просрочки', _pv(data.director_overdue_category));
    rows += _printRow('Дата последней просрочки', _pd(data.director_last_overdue_date));
    rows += _printRow('Причина просрочки', _pv(data.director_overdue_reason));

    rows += _printRow('<b>Поручитель</b>', '');
    rows += _printRow('ФИО', _pv(data.guarantor_full_name));
    rows += _printRow('ПИНФЛ', _pv(data.guarantor_pinfl));
    rows += _printRow('Паспорт', _pv(data.guarantor_passport));
    rows += _printRow('Телефон', _pv(data.guarantor_phone));
    rows += _printRow('Месячный доход', _pn(data.guarantor_monthly_income, ' сум'));
    rows += _printRow('Категория просрочки', _pv(data.guarantor_overdue_category));
    rows += _printRow('Дата последней просрочки', _pd(data.guarantor_last_overdue_date));
  } else {
    rows += _printRow('Наличие обязательств', _pv(data.has_current_obligations));
    rows += _printRow('Сумма обязательств', _pn(data.total_obligations_amount, ' сум'));
    rows += _printRow('Кол-во обязательств', _pv(data.obligations_count));
    rows += _printRow('Ежемесячный платёж', _pn(data.monthly_obligations_payment, ' сум'));
    rows += _printRow('Закрытые обязательства', _pv(data.closed_obligations_count));
    rows += _printRow('Макс. просрочка (дни, осн. долг)', _pv(data.max_overdue_principal_days, ' дн.'));
    rows += _printRow('Макс. просрочка (сумма, осн. долг)', _pn(data.max_overdue_principal_amount, ' сум'));
    rows += _printRow('Макс. просрочка (дни, %)', _pv(data.max_continuous_overdue_percent_days, ' дн.'));
    rows += _printRow('Макс. просрочка (сумма, %)', _pn(data.max_overdue_percent_amount, ' сум'));
    rows += _printRow('Категория просрочки', _pv(data.overdue_category));
    rows += _printRow('Дата последней просрочки', _pd(data.last_overdue_date));
    rows += _printRow('Результат проверки', _pv(data.overdue_check_result));
    rows += _printRow('Причина просрочки', _pv(data.overdue_reason));
  }
  rows += _printRow('DTI', data.dti != null ? data.dti.toFixed(1) + '%' : '—');

  // --- Блок 5: Заключение ---
  rows += _printSection('Заключение');
  if (data.auto_decision) {
    const avLabels = { approved: 'Одобрено', review: 'На рассмотрение', rejected: 'Отказ' };
    rows += _printRow('Авто-вердикт', avLabels[data.auto_decision] || data.auto_decision);
    if (data.auto_decision_reasons && data.auto_decision_reasons.length) {
      rows += _printRow('Причины', data.auto_decision_reasons.map(r => escapeHtml(r)).join('<br>'));
    }
  }
  rows += _printRow('Рекомендуемый ПВ', data.recommended_pv != null ? data.recommended_pv + '%' : '—');
  rows += _printRow('Риск-грейд', _pv(data.risk_grade));
  const decLabels = { approved: 'Одобрена', review: 'На рассмотрение', rejected_underwriter: 'Отказ андеррайтера', rejected_client: 'Отказ клиента' };
  rows += _printRow('Решение', data.decision ? (decLabels[data.decision] || data.decision) : '—');
  rows += _printRow('Итоговый ПВ', data.final_pv != null ? data.final_pv + '%' : '—');
  rows += _printRow('Комментарий', _pv(data.conclusion_comment));
  rows += _printRow('Андеррайтер', _pv(data.concluder_name));
  rows += _printRow('Дата заключения', data.concluded_at ? new Date(data.concluded_at).toLocaleString('ru-RU') : '—');
  rows += _printRow('Версия', _pv(data.conclusion_version));

  return `<table style="width:100%;border-collapse:collapse">${rows}</table>`;
}

function printAnketa() {
  const data = _currentViewData;
  if (!data) { window.print(); return; }

  const isLegal = data.client_type === 'legal_entity';
  const clientName = isLegal ? (data.company_name || '—') : (data.full_name || '—');

  // Status label
  const stMap = {
    draft: 'Черновик', saved: 'Сохранена', approved: 'Одобрена',
    review: 'На рассмотрении', rejected_underwriter: 'Отказ андеррайтера',
    rejected_client: 'Отказ клиента', deleted: 'Удалена',
  };
  const statusLabel = stMap[data.status] || data.status;

  // Print title
  document.getElementById('printTitle').textContent =
    (isLegal ? 'Юр. лицо' : 'Физ. лицо') + ' — ' + clientName;

  // Meta info line
  const created = data.created_at ? new Date(data.created_at).toLocaleString('ru-RU') : '—';
  document.getElementById('printMeta').innerHTML =
    `Анкета #${data.id} | Статус: ${statusLabel} | Создана: ${created} | Автор: ${escapeHtml(data.creator_name || '—')}`;

  // QR code
  const qrContainer = document.getElementById('printQr');
  qrContainer.innerHTML = '';
  try {
    const qrUrl = window.location.origin + '/anketa/' + data.id;
    const qr = qrcode(0, 'M');
    qr.addData(qrUrl);
    qr.make();
    qrContainer.innerHTML = qr.createImgTag(3, 0);
  } catch (e) {
    console.error('QR error:', e);
  }

  // Build full print content and inject
  const printBody = document.getElementById('printFullBody');
  if (printBody) {
    printBody.innerHTML = buildPrintContent(data);
    printBody.style.display = 'block';
  }

  setTimeout(() => {
    window.print();
    // Hide print body after printing
    if (printBody) printBody.style.display = 'none';
  }, 200);
}


// ---------- ROLES MANAGEMENT ----------

let rolesData = [];

async function loadRoles() {
  try {
    const res = await fetch('/api/admin/roles', { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (res.status === 403) { navigate('dashboard'); return; }
    if (!res.ok) throw new Error('Failed to load roles');
    rolesData = await res.json();
    renderRolesTable();
  } catch (err) {
    showToast('Ошибка загрузки должностей', 'error');
  }
}

const PERM_LABELS = {
  anketa_create: 'Создание',
  anketa_edit: 'Редакт.',
  anketa_view_all: 'Просм. всех',
  anketa_conclude: 'Заключ.',
  anketa_delete: 'Удаление',
  user_manage: 'Польз.',
  analytics_view: 'Аналит.',
  export_excel: 'Excel',
  rules_manage: 'Правила',
};

const PERM_KEYS = Object.keys(PERM_LABELS);

function renderRolesTable() {
  const tbody = document.getElementById('rolesTableBody');
  if (!rolesData.length) {
    tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:40px;color:var(--text-light)">Нет должностей</td></tr>';
    return;
  }
  tbody.innerHTML = rolesData.map(r => {
    const permCells = PERM_KEYS.map(k =>
      `<td style="text-align:center">${r[k] ? '<span style="color:var(--green);font-weight:600">✓</span>' : '<span style="color:var(--text-light)">—</span>'}</td>`
    ).join('');
    const sysLabel = r.is_system ? ' <span style="font-size:10px;color:var(--text-light)">(системная)</span>' : '';
    const actions = r.is_system
      ? '<span style="color:var(--text-light);font-size:12px">Системная</span>'
      : `<button class="btn btn-outline btn-sm" onclick="openEditRoleModal(${r.id})">Изменить</button>
         <button class="btn btn-sm btn-danger" onclick="deleteRole(${r.id})">Удалить</button>`;
    return `<tr><td><strong>${escapeHtml(r.name)}</strong>${sysLabel}</td>${permCells}<td><div style="display:flex;gap:6px">${actions}</div></td></tr>`;
  }).join('');
}

function openCreateRoleModal() {
  document.getElementById('newRoleName').value = '';
  PERM_KEYS.forEach(k => { document.getElementById('newRolePerm_' + k).checked = false; });
  document.getElementById('createRoleError').classList.remove('show');
  document.getElementById('createRoleModal').classList.add('show');
}
function closeCreateRoleModal() { document.getElementById('createRoleModal').classList.remove('show'); }

async function createRole() {
  const errEl = document.getElementById('createRoleError');
  errEl.classList.remove('show');
  const name = document.getElementById('newRoleName').value.trim();
  if (!name) { errEl.textContent = 'Введите название'; errEl.classList.add('show'); return; }
  const body = { name };
  PERM_KEYS.forEach(k => { body[k] = document.getElementById('newRolePerm_' + k).checked; });
  try {
    const res = await fetch('/api/admin/roles', { method: 'POST', headers: authHeaders(), body: JSON.stringify(body) });
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Ошибка'); }
    closeCreateRoleModal();
    showToast('Должность создана');
    loadRoles();
  } catch (err) { errEl.textContent = err.message; errEl.classList.add('show'); }
}

function openEditRoleModal(roleId) {
  const role = rolesData.find(r => r.id === roleId);
  if (!role) return;
  document.getElementById('editRoleId').value = roleId;
  document.getElementById('editRoleName').value = role.name;
  PERM_KEYS.forEach(k => { document.getElementById('editRolePerm_' + k).checked = role[k]; });
  document.getElementById('editRoleError').classList.remove('show');
  document.getElementById('editRoleModal').classList.add('show');
}
function closeEditRoleModal() { document.getElementById('editRoleModal').classList.remove('show'); }

async function saveRole() {
  const errEl = document.getElementById('editRoleError');
  errEl.classList.remove('show');
  const roleId = document.getElementById('editRoleId').value;
  const name = document.getElementById('editRoleName').value.trim();
  if (!name) { errEl.textContent = 'Введите название'; errEl.classList.add('show'); return; }
  const body = { name };
  PERM_KEYS.forEach(k => { body[k] = document.getElementById('editRolePerm_' + k).checked; });
  try {
    const res = await fetch('/api/admin/roles/' + roleId, { method: 'PATCH', headers: authHeaders(), body: JSON.stringify(body) });
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Ошибка'); }
    closeEditRoleModal();
    showToast('Должность обновлена');
    loadRoles();
  } catch (err) { errEl.textContent = err.message; errEl.classList.add('show'); }
}

async function deleteRole(roleId) {
  if (!confirm('Удалить эту должность?')) return;
  try {
    const res = await fetch('/api/admin/roles/' + roleId, { method: 'DELETE', headers: authHeaders() });
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Ошибка'); }
    showToast('Должность удалена');
    loadRoles();
  } catch (err) { showToast(err.message, 'error'); }
}

async function loadRolesDropdown(selectId, selectedId) {
  const sel = document.getElementById(selectId);
  sel.innerHTML = '<option value="">— загрузка —</option>';
  try {
    const res = await fetch('/api/admin/roles', { headers: authHeaders() });
    if (!res.ok) throw new Error('Ошибка');
    const roles = await res.json();
    sel.innerHTML = roles.map(r =>
      `<option value="${r.id}" ${r.id === selectedId ? 'selected' : ''}>${escapeHtml(r.name)}</option>`
    ).join('');
  } catch {
    sel.innerHTML = '<option value="">Ошибка загрузки</option>';
  }
}


// ---------- EMPLOYEE STATS ----------

let _empStatsPeriod = 'month';
let _empStatsFrom = '';
let _empStatsTo = '';

async function loadEmployeeStats() {
  const perms = currentUser && currentUser.permissions;
  if (!perms || (!perms.analytics_view && currentUser.role !== 'admin')) {
    navigate('dashboard');
    return;
  }
  let url = '/api/anketas/employee-stats/data?period=' + _empStatsPeriod;
  if (_empStatsPeriod === 'custom' && _empStatsFrom && _empStatsTo) {
    url += '&date_from=' + _empStatsFrom + '&date_to=' + _empStatsTo;
  }
  try {
    const res = await fetch(url, { headers: authHeaders() });
    if (res.status === 401) { logout(); return; }
    if (res.status === 403) { navigate('dashboard'); return; }
    if (!res.ok) throw new Error('Ошибка');
    const data = await res.json();
    renderEmployeeStats(data);
  } catch (err) {
    showToast('Ошибка загрузки аналитики', 'error');
  }
}

function renderEmployeeStats(data) {
  const tbody = document.getElementById('empStatsTableBody');
  if (!data.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--text-light)">Нет данных за выбранный период</td></tr>';
    return;
  }
  tbody.innerHTML = data.map(d => `
    <tr>
      <td><strong>${escapeHtml(d.user_name)}</strong></td>
      <td>${d.total}</td>
      <td style="color:var(--green);font-weight:600">${d.approved}</td>
      <td style="color:var(--red);font-weight:600">${d.rejected}</td>
      <td style="color:var(--amber)">${d.review}</td>
      <td><strong>${d.approval_rate}%</strong></td>
      <td>${d.avg_dti}%</td>
      <td>${d.avg_processing_hours} ч</td>
    </tr>
  `).join('');
}

function setEmpStatsPeriod(period) {
  _empStatsPeriod = period;
  // Update active button
  const container = document.querySelector('#page-employee-stats .period-filter');
  if (container) {
    container.querySelectorAll('.period-btn').forEach(btn => btn.classList.remove('active'));
    const btns = container.querySelectorAll('.period-btn');
    if (period === 'week') btns[0]?.classList.add('active');
    else if (period === 'month') btns[1]?.classList.add('active');
    else if (period === 'custom') btns[2]?.classList.add('active');
  }
  const dates = document.getElementById('empStatsPeriodDates');
  if (dates) dates.style.display = period === 'custom' ? 'flex' : 'none';
  if (period !== 'custom') loadEmployeeStats();
}

function applyEmpStatsCustomPeriod() {
  _empStatsFrom = document.getElementById('empStatsFrom').value;
  _empStatsTo = document.getElementById('empStatsTo').value;
  if (_empStatsFrom && _empStatsTo) loadEmployeeStats();
}


// ---------- TELEGRAM SETTINGS ----------

async function openTelegramSettingsModal() {
  document.getElementById('telegramSettingsModal').classList.add('show');
  try {
    const res = await fetch('/api/admin/settings/telegram', { headers: authHeaders() });
    if (res.ok) {
      const data = await res.json();
      document.getElementById('telegramBotToken').value = data.bot_token || '';
    }
  } catch {}
}

function closeTelegramSettingsModal() {
  document.getElementById('telegramSettingsModal').classList.remove('show');
}

async function saveTelegramSettings() {
  const token = document.getElementById('telegramBotToken').value.trim();
  try {
    const res = await fetch('/api/admin/settings/telegram', {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ bot_token: token || null }),
    });
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Ошибка'); }
    closeTelegramSettingsModal();
    showToast('Настройки Telegram сохранены');
  } catch (err) {
    showToast(err.message, 'error');
  }
}


// ---------- START ----------

initApp();
