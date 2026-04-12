const state = {
  mode: 'round_robin',
  resultView: 'list',
  currentWeekOffset: 0,
  assignments: [],
  conflicts: [],
  warnings: [],
  stats: null,
  calloutPlan: [],
};

const els = {
  studentsContainer: document.getElementById('studentsContainer'),
  shiftTemplates: document.getElementById('shiftTemplates'),
  addStudentBtn: document.getElementById('addStudentBtn'),
  addShiftBtn: document.getElementById('addShiftBtn'),
  generateBtn: document.getElementById('generateBtn'),
  resetBtn: document.getElementById('resetBtn'),
  algorithm: document.getElementById('algorithm'),
  weeks: document.getElementById('weeks'),
  flashBox: document.getElementById('flashBox'),
  customShiftCard: document.getElementById('customShiftCard'),
  scheduleList: document.getElementById('scheduleList'),
  calendarPane: document.getElementById('calendarPane'),
  calendarGrid: document.getElementById('calendarGrid'),
  calendarTitle: document.getElementById('calendarTitle'),
  workloadBars: document.getElementById('workloadBars'),
  conflictBox: document.getElementById('conflictBox'),
  conflictList: document.getElementById('conflictList'),
  warningBox: document.getElementById('warningBox'),
  warningList: document.getElementById('warningList'),
  calloutBox: document.getElementById('calloutBox'),
  calloutList: document.getElementById('calloutList'),
  statStudents: document.getElementById('statStudents'),
  statAssignments: document.getElementById('statAssignments'),
  statBackups: document.getElementById('statBackups'),
  statCoverage: document.getElementById('statCoverage'),
  statAverage: document.getElementById('statAverage'),
  statSpread: document.getElementById('statSpread'),
};

function flash(message, type='success') {
  els.flashBox.textContent = message;
  els.flashBox.className = `flash ${type}`;
  els.flashBox.classList.remove('hidden');
}

function escapeHtml(value='') {
  return value.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

function toggleTheme() {
  const root = document.documentElement;
  const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
  root.dataset.theme = next;
  localStorage.setItem('titan-theme', next);
}

function applyStoredTheme() {
  document.documentElement.dataset.theme = localStorage.getItem('titan-theme') || 'dark';
}

function switchMode(mode) {
  state.mode = mode;
  document.querySelectorAll('#modeSwitch .segment').forEach(btn => btn.classList.toggle('active', btn.dataset.mode === mode));
  els.customShiftCard.classList.toggle('hidden', mode !== 'custom');
  els.algorithm.disabled = mode === 'custom';
}

function switchResultView(view) {
  state.resultView = view;
  document.querySelectorAll('#resultSwitch .segment').forEach(btn => btn.classList.toggle('active', btn.dataset.view === view));
  updateResultVisibility();
}

function updateResultVisibility() {
  els.scheduleList.classList.toggle('hidden', state.resultView !== 'list');
  els.calendarPane.classList.toggle('hidden', state.resultView !== 'calendar');
}

function createStudentCard(student={}) {
  const wrapper = document.createElement('div');
  wrapper.className = 'student-card';
  wrapper.innerHTML = `
    <div class="row">
      <label><span>Name</span><input class="student-name" value="${escapeHtml(student.name || '')}" placeholder="Student name"></label>
      <label><span>Preferred shift</span>
        <select class="student-pref">
          <option value="any">Any</option>
          <option value="morning">Morning</option>
          <option value="afternoon">Afternoon</option>
          <option value="evening">Evening</option>
        </select>
      </label>
    </div>
    <label><span>Academic profile</span><textarea class="student-profile" rows="2" placeholder="Mon Wed 9-10am, Final Exam Dec 16 1-3pm">${escapeHtml(student.profile || '')}</textarea></label>
    <div class="row row-3">
      <label><span>Reliability %</span><input class="student-reliability" type="number" min="50" max="100" value="${student.reliability ?? 85}"></label>
      <label><span>Max hrs / week</span><input class="student-hours" type="number" min="1" max="40" value="${student.max_hours ?? 12}"></label>
      <label><span>Recent callouts</span><input class="student-callouts" type="number" min="0" max="10" value="${student.recent_callouts ?? 0}"></label>
    </div>
    <button class="mini-btn remove-btn" type="button">Remove</button>
  `;
  wrapper.querySelector('.student-pref').value = student.preferred_shift || 'any';
  wrapper.querySelector('.remove-btn').addEventListener('click', () => {
    if (els.studentsContainer.children.length > 2) wrapper.remove();
    else flash('Keep at least two students in the list.', 'error');
  });
  return wrapper;
}

function createShiftCard(template={}, config={}) {
  const item = { id: template.id || Date.now(), name: template.name || 'Signature Shift', start: template.start || '10:00', end: template.end || '14:00', students_needed: template.students_needed || 2 };
  const cfg = { days: config.days || 'Mon Wed Fri', count: config.count || 3 };
  const wrapper = document.createElement('div');
  wrapper.className = 'shift-card';
  wrapper.dataset.id = item.id;
  wrapper.innerHTML = `
    <div class="row">
      <label><span>Shift name</span><input class="shift-name" value="${escapeHtml(item.name)}"></label>
      <label><span>Students needed</span><input class="shift-needed" type="number" min="1" max="10" value="${item.students_needed}"></label>
    </div>
    <div class="row">
      <label><span>Start</span><input class="shift-start" type="time" value="${item.start}"></label>
      <label><span>End</span><input class="shift-end" type="time" value="${item.end}"></label>
    </div>
    <div class="row">
      <label><span>Days</span><input class="shift-days" value="${escapeHtml(cfg.days)}"></label>
      <label><span>Times / week</span><input class="shift-count" type="number" min="1" max="7" value="${cfg.count}"></label>
    </div>
    <button class="mini-btn remove-btn" type="button">Remove Shift</button>
  `;
  wrapper.querySelector('.remove-btn').addEventListener('click', () => {
    if (els.shiftTemplates.children.length > 1) wrapper.remove();
    else flash('Keep at least one shift template in custom mode.', 'error');
  });
  return wrapper;
}

function seedInitialCards() {
  els.studentsContainer.innerHTML = '';
  window.DEFAULT_STUDENTS.forEach(student => els.studentsContainer.appendChild(createStudentCard(student)));
  els.shiftTemplates.innerHTML = '';
  window.DEFAULT_SHIFT_TEMPLATES.forEach(template => {
    els.shiftTemplates.appendChild(createShiftCard(template, window.DEFAULT_CUSTOM_CONFIG[`shift_${template.id}`]));
  });
}

function collectPayload() {
  const students = Array.from(els.studentsContainer.querySelectorAll('.student-card')).map(card => ({
    name: card.querySelector('.student-name').value.trim(),
    profile: card.querySelector('.student-profile').value.trim(),
    reliability: Number(card.querySelector('.student-reliability').value || 85),
    max_hours: Number(card.querySelector('.student-hours').value || 12),
    preferred_shift: card.querySelector('.student-pref').value,
    recent_callouts: Number(card.querySelector('.student-callouts').value || 0),
  }));
  const payload = { mode: state.mode, algorithm: els.algorithm.value, weeks: Number(els.weeks.value || 4), students };
  if (state.mode === 'custom') {
    const shift_templates = [];
    const schedule_config = {};
    Array.from(els.shiftTemplates.querySelectorAll('.shift-card')).forEach(card => {
      const id = Number(card.dataset.id);
      shift_templates.push({ id, name: card.querySelector('.shift-name').value.trim() || 'Untitled Shift', start: card.querySelector('.shift-start').value, end: card.querySelector('.shift-end').value, students_needed: Number(card.querySelector('.shift-needed').value || 1) });
      schedule_config[`shift_${id}`] = { days: card.querySelector('.shift-days').value.trim() || 'Mon Wed Fri', count: Number(card.querySelector('.shift-count').value || 1) };
    });
    payload.shift_templates = shift_templates;
    payload.schedule_config = schedule_config;
  }
  return payload;
}

async function generateSchedule() {
  const payload = collectPayload();
  if (payload.students.filter(s => s.name).length < 2) {
    flash('Please enter at least two student names.', 'error');
    return;
  }
  els.generateBtn.disabled = true;
  flash('Generating smart schedule with coverage planning...', 'success');
  try {
    const response = await fetch('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Unable to generate schedule.');
    state.assignments = data.assignments;
    state.conflicts = data.conflicts;
    state.warnings = data.warnings;
    state.stats = data.stats;
    state.calloutPlan = data.callout_plan;
    state.currentWeekOffset = 0;
    renderStats();
    renderWorkloadBars();
    renderConflicts();
    renderWarnings();
    renderCalloutPlan();
    renderList();
    renderCalendar();
    const msg = data.conflicts.length
      ? `Smart schedule created with ${data.conflicts.length} academic conflict flag(s). Check warnings and backups.`
      : 'Smart schedule created with coverage planning and no academic conflicts.';
    flash(msg, data.conflicts.length ? 'error' : 'success');
  } catch (err) {
    flash(err.message, 'error');
  } finally {
    els.generateBtn.disabled = false;
  }
}

function renderStats() {
  const s = state.stats || {};
  els.statStudents.textContent = s.total_students || 0;
  els.statAssignments.textContent = s.total_assignments || 0;
  els.statBackups.textContent = s.total_backup_assignments || 0;
  els.statCoverage.textContent = `${s.coverage_ready_percent || 0}%`;
  els.statAverage.textContent = s.average_assignments || 0;
  els.statSpread.textContent = s.fairness_spread || 0;
}

function renderWorkloadBars() {
  const s = state.stats;
  if (!s) return;
  const entries = Object.keys(s.assignments_by_student || {});
  const maxPrimary = Math.max(...entries.map(name => s.assignments_by_student[name]), 1);
  els.workloadBars.innerHTML = entries.map(name => {
    const primary = s.assignments_by_student[name] || 0;
    const backups = s.backup_by_student[name] || 0;
    const hours = s.hours_by_student[name] || 0;
    const risk = s.risk_by_student[name] || 0;
    const reliability = s.reliability_by_student[name] || 0;
    return `
      <div class="bar-row stacked">
        <div class="bar-copy">
          <strong>${escapeHtml(name)}</strong>
          <span>${primary} primary · ${backups} backup · ${hours}h · reliability ${reliability}%</span>
        </div>
        <div class="bar-track"><div class="bar-fill" style="width:${(primary / maxPrimary) * 100}%"></div></div>
        <span class="risk-chip ${risk >= 70 ? 'high' : risk >= 40 ? 'medium' : 'low'}">Risk ${risk}</span>
      </div>`;
  }).join('');
}

function renderConflicts() {
  if (!state.conflicts.length) {
    els.conflictBox.classList.add('hidden');
    els.conflictList.innerHTML = '';
    return;
  }
  els.conflictBox.classList.remove('hidden');
  els.conflictList.innerHTML = state.conflicts.map(item => `
    <div class="list-item danger-left">
      <strong>${escapeHtml(item.student)}</strong> · ${formatDate(item.date)} · ${escapeHtml(item.time)}<br>
      ${escapeHtml(item.reason)} — ${escapeHtml(item.commitment)}
    </div>`).join('');
}

function renderWarnings() {
  if (!state.warnings.length) {
    els.warningBox.classList.add('hidden');
    els.warningList.innerHTML = '';
    return;
  }
  els.warningBox.classList.remove('hidden');
  els.warningList.innerHTML = state.warnings.map(item => `
    <div class="list-item ${item.severity === 'high' ? 'danger-left' : 'warn-left'}">
      <strong>${escapeHtml(item.student)}</strong> · ${formatDate(item.date)}<br>
      ${escapeHtml(item.reason)}
    </div>`).join('');
}

function renderCalloutPlan() {
  if (!state.calloutPlan.length) {
    els.calloutBox.classList.add('hidden');
    els.calloutList.innerHTML = '';
    return;
  }
  els.calloutBox.classList.remove('hidden');
  els.calloutList.innerHTML = state.calloutPlan.map(item => `
    <div class="list-item">
      <strong>${escapeHtml(item.shift_name)}</strong> · ${formatDate(item.date)} · ${escapeHtml(item.time)}<br>
      Primary: ${escapeHtml(item.primaries.join(', ') || 'None')}<br>
      Backup: ${escapeHtml(item.backups.join(', ') || 'No backup assigned')}
    </div>`).join('');
}

function renderList() {
  const primary = state.assignments.filter(item => item.role === 'primary');
  if (!primary.length) {
    els.scheduleList.className = 'schedule-list empty-state';
    els.scheduleList.textContent = 'Generate a schedule to see the polished view.';
    return;
  }
  const grouped = groupAssignmentsByDate(primary);
  els.scheduleList.className = 'schedule-list';
  els.scheduleList.innerHTML = Object.entries(grouped).map(([iso, items]) => `
    <article class="day-card">
      <h3>${formatDate(iso)}</h3>
      ${items.map(item => {
        const plan = state.calloutPlan.find(plan => plan.shift_instance_id === item.shift_instance_id) || { backups: [] };
        return `
          <div class="assignment-pill ${item.conflict ? 'conflict' : ''}">
            <div><strong>${escapeHtml(item.shift_name)}</strong><br><span>${escapeHtml(item.time)}</span></div>
            <div><strong>${escapeHtml(item.student)}</strong><br><span>${escapeHtml(item.round_label || '')}</span></div>
            <div><span class="badge">Backup: ${escapeHtml(plan.backups.join(', ') || '—')}</span></div>
          </div>`;
      }).join('')}
    </article>`).join('');
  updateResultVisibility();
}

function renderCalendar() {
  const weekDates = getWeekDates(state.currentWeekOffset);
  els.calendarTitle.textContent = `${formatShortDate(weekDates[0])} – ${formatShortDate(weekDates[6])}`;
  const grouped = groupAssignmentsByDate(state.assignments.filter(item => item.role === 'primary'));
  els.calendarGrid.innerHTML = weekDates.map(dt => {
    const iso = toISODate(dt);
    const items = grouped[iso] || [];
    return `
      <article class="calendar-day">
        <h4>${dt.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' })}</h4>
        ${items.length ? items.map(item => `<div class="calendar-chip ${item.conflict ? 'conflict' : ''}"><strong>${escapeHtml(item.student)}</strong><br>${escapeHtml(item.time)}<br><span>${escapeHtml(item.shift_name)}</span></div>`).join('') : '<div class="hint">No shifts</div>'}
      </article>`;
  }).join('');
  updateResultVisibility();
}

function groupAssignmentsByDate(assignments) {
  return assignments.reduce((acc, item) => {
    if (!acc[item.date]) acc[item.date] = [];
    acc[item.date].push(item);
    acc[item.date].sort((a, b) => a.start_minutes - b.start_minutes || a.student.localeCompare(b.student));
    return acc;
  }, {});
}

function getWeekDates(offset) {
  const today = new Date();
  const day = today.getDay();
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const monday = new Date(today);
  monday.setHours(0,0,0,0);
  monday.setDate(today.getDate() + diffToMonday + offset * 7);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d;
  });
}

function toISODate(dateObj) {
  return dateObj.toISOString().split('T')[0];
}

function formatDate(iso) {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
}

function formatShortDate(dateObj) {
  return dateObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function resetAll() {
  seedInitialCards();
  state.assignments = [];
  state.conflicts = [];
  state.warnings = [];
  state.stats = null;
  state.calloutPlan = [];
  renderStats();
  renderWorkloadBars();
  renderConflicts();
  renderWarnings();
  renderCalloutPlan();
  renderList();
  renderCalendar();
  flash('Reset to Smart Scheduler V2 defaults.', 'success');
}

function initialize() {
  document.querySelectorAll('#modeSwitch .segment').forEach(btn => btn.addEventListener('click', () => switchMode(btn.dataset.mode)));
  document.querySelectorAll('#resultSwitch .segment').forEach(btn => btn.addEventListener('click', () => switchResultView(btn.dataset.view)));
  document.getElementById('themeToggle').addEventListener('click', toggleTheme);
  document.getElementById('prevWeekBtn').addEventListener('click', () => { state.currentWeekOffset -= 1; renderCalendar(); });
  document.getElementById('nextWeekBtn').addEventListener('click', () => { state.currentWeekOffset += 1; renderCalendar(); });
  els.addStudentBtn.addEventListener('click', () => els.studentsContainer.appendChild(createStudentCard()));
  els.addShiftBtn.addEventListener('click', () => els.shiftTemplates.appendChild(createShiftCard()));
  els.generateBtn.addEventListener('click', generateSchedule);
  els.resetBtn.addEventListener('click', resetAll);
  seedInitialCards();
  applyStoredTheme();
  switchMode('round_robin');
  switchResultView('list');
}

initialize();
