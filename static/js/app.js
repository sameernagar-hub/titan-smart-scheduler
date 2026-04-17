const pageName = document.body.dataset.page || "";

function initializePageMotion() {
  window.requestAnimationFrame(() => {
    document.body.classList.add("page-ready");
  });
}

function applyStoredTheme() {
  const root = document.documentElement;
  const picker = document.getElementById("themePicker");
  const theme = localStorage.getItem("titan-theme") || "nightfall";
  root.dataset.theme = theme;
  if (picker) {
    picker.querySelectorAll("[data-theme]").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.theme === theme);
      chip.setAttribute("aria-pressed", chip.dataset.theme === theme ? "true" : "false");
    });
  }
}

function initializeThemePicker() {
  const picker = document.getElementById("themePicker");
  if (!picker) return;
  picker.querySelectorAll("[data-theme]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const theme = chip.dataset.theme;
      document.documentElement.dataset.theme = theme;
      localStorage.setItem("titan-theme", theme);
      applyStoredTheme();
    });
  });
}

function initializeDetailsDismiss() {
  document.addEventListener("click", (event) => {
    document.querySelectorAll("details.help-pop[open], details.help-inline[open]").forEach((details) => {
      if (!details.contains(event.target)) details.removeAttribute("open");
    });
  });
}

function initializeHomeCarousel() {
  const carousel = document.getElementById("homeCarousel");
  const dots = Array.from(document.querySelectorAll("#homeCarouselDots .carousel-dot"));
  if (!carousel || dots.length <= 1) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const slides = Array.from(carousel.querySelectorAll(".carousel-slide"));
  let activeIndex = 0;
  let intervalId = null;

  function render(index) {
    activeIndex = index;
    slides.forEach((slide, slideIndex) => slide.classList.toggle("active", slideIndex === index));
    dots.forEach((dot, dotIndex) => dot.classList.toggle("active", dotIndex === index));
  }

  function startRotation() {
    if (intervalId) return;
    intervalId = window.setInterval(() => {
      render((activeIndex + 1) % slides.length);
    }, 4000);
  }

  function stopRotation() {
    if (!intervalId) return;
    window.clearInterval(intervalId);
    intervalId = null;
  }

  dots.forEach((dot) => {
    dot.addEventListener("click", () => render(Number(dot.dataset.index)));
  });

  carousel.addEventListener("mouseenter", stopRotation);
  carousel.addEventListener("mouseleave", startRotation);
  startRotation();
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));
}

function formatDate(iso) {
  const date = new Date(`${iso}T00:00:00`);
  return date.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
}

function formatShortDate(dateObj) {
  return dateObj.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function toISODate(dateObj) {
  return dateObj.toISOString().split("T")[0];
}

function getWeekDates(offset) {
  const today = new Date();
  const day = today.getDay();
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const monday = new Date(today);
  monday.setHours(0, 0, 0, 0);
  monday.setDate(today.getDate() + diffToMonday + offset * 7);
  return Array.from({ length: 7 }, (_, index) => {
    const value = new Date(monday);
    value.setDate(monday.getDate() + index);
    return value;
  });
}

function initializeSchedulerPage() {
  const DEFAULT_MODE = "round_robin";
  const DEFAULT_ALGORITHM = "constraint_shield";
  const DEFAULT_WEEKS = 4;
  const state = {
    mode: DEFAULT_MODE,
    resultView: "list",
    currentWeekOffset: 0,
    assignments: [],
    conflicts: [],
    warnings: [],
    stats: null,
    algorithmInsights: null,
    ethics: null,
    calloutPlan: [],
    historyUrl: "",
    exportJsonUrl: "",
    exportCsvUrl: "",
  };

  const els = {
    scheduleName: document.getElementById("scheduleName"),
    templateUpload: document.getElementById("templateUpload"),
    studentsContainer: document.getElementById("studentsContainer"),
    shiftTemplates: document.getElementById("shiftTemplates"),
    addStudentBtn: document.getElementById("addStudentBtn"),
    addShiftBtn: document.getElementById("addShiftBtn"),
    generateBtn: document.getElementById("generateBtn"),
    resetBtn: document.getElementById("resetBtn"),
    algorithm: document.getElementById("algorithm"),
    weeks: document.getElementById("weeks"),
    flashBox: document.getElementById("flashBox"),
    customShiftCard: document.getElementById("customShiftCard"),
    scheduleList: document.getElementById("scheduleList"),
    calendarPane: document.getElementById("calendarPane"),
    calendarGrid: document.getElementById("calendarGrid"),
    calendarTitle: document.getElementById("calendarTitle"),
    workloadBars: document.getElementById("workloadBars"),
    conflictBox: document.getElementById("conflictBox"),
    conflictList: document.getElementById("conflictList"),
    warningBox: document.getElementById("warningBox"),
    warningList: document.getElementById("warningList"),
    calloutBox: document.getElementById("calloutBox"),
    calloutList: document.getElementById("calloutList"),
    algorithmInsightBox: document.getElementById("algorithmInsightBox"),
    algorithmInsightContent: document.getElementById("algorithmInsightContent"),
    historyLinkBox: document.getElementById("historyLinkBox"),
    statStudents: document.getElementById("statStudents"),
    statAssignments: document.getElementById("statAssignments"),
    statBackups: document.getElementById("statBackups"),
    statCoverage: document.getElementById("statCoverage"),
    statConflictFree: document.getElementById("statConflictFree"),
    statAverage: document.getElementById("statAverage"),
    statSpread: document.getElementById("statSpread"),
    statAlgorithm: document.getElementById("statAlgorithm"),
  };

  function syncAlgorithmShowcase() {
    document.querySelectorAll(".algorithm-card[data-algorithm]").forEach((card) => {
      card.classList.toggle("active", card.dataset.algorithm === els.algorithm.value);
    });
  }

  function flash(message, type = "success") {
    els.flashBox.textContent = message;
    els.flashBox.className = `flash ${type}`;
    els.flashBox.classList.remove("hidden");
  }

  function switchMode(mode) {
    state.mode = mode;
    document.querySelectorAll("#modeSwitch .segment").forEach((button) => {
      button.classList.toggle("active", button.dataset.mode === mode);
    });
    els.customShiftCard.classList.toggle("hidden", mode !== "custom");
  }

  function switchResultView(view) {
    state.resultView = view;
    document.querySelectorAll("#resultSwitch .segment").forEach((button) => {
      button.classList.toggle("active", button.dataset.view === view);
    });
    els.scheduleList.classList.toggle("hidden", view !== "list");
    els.calendarPane.classList.toggle("hidden", view !== "calendar");
  }

  function createStudentCard(student = {}) {
    const wrapper = document.createElement("div");
    wrapper.className = "student-card";
    wrapper.innerHTML = `
      <div class="row">
        <label><span>Name</span><input class="student-name" value="${escapeHtml(student.name || "")}" placeholder="Student name"></label>
        <label><span>Preferred shift</span>
          <select class="student-pref">
            <option value="any">Any</option>
            <option value="morning">Morning</option>
            <option value="afternoon">Afternoon</option>
            <option value="evening">Evening</option>
          </select>
        </label>
      </div>
      <label><span>Academic profile</span><textarea class="student-profile" rows="2" placeholder="Mon Wed 9-10am, Final Exam Dec 16 1-3pm">${escapeHtml(student.profile || "")}</textarea></label>
      <div class="row row-3">
        <label><span>Reliability %</span><input class="student-reliability" type="number" min="50" max="100" value="${student.reliability ?? 85}"></label>
        <label><span>Max hrs / week</span><input class="student-hours" type="number" min="1" max="40" value="${student.max_hours ?? 12}"></label>
        <label><span>Recent callouts</span><input class="student-callouts" type="number" min="0" max="10" value="${student.recent_callouts ?? 0}"></label>
      </div>
      <button class="mini-btn remove-btn" type="button">Remove</button>
    `;
    wrapper.querySelector(".student-pref").value = student.preferred_shift || "any";
    wrapper.querySelector(".remove-btn").addEventListener("click", () => {
      if (els.studentsContainer.children.length > 2) wrapper.remove();
      else flash("Keep at least two students in the list.", "error");
    });
    return wrapper;
  }

  function createShiftCard(template = {}, config = {}) {
    const item = {
      id: template.id || Date.now(),
      name: template.name || "Signature Shift",
      start: template.start || "10:00",
      end: template.end || "14:00",
      students_needed: template.students_needed || 2,
    };
    const cfg = { days: config.days || "Mon Wed Fri", count: config.count || 3 };
    const wrapper = document.createElement("div");
    wrapper.className = "shift-card";
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
    wrapper.querySelector(".remove-btn").addEventListener("click", () => {
      if (els.shiftTemplates.children.length > 1) wrapper.remove();
      else flash("Keep at least one shift template in custom mode.", "error");
    });
    return wrapper;
  }

  function seedInitialCards() {
    els.studentsContainer.innerHTML = "";
    (window.DEFAULT_STUDENTS || []).forEach((student) => els.studentsContainer.appendChild(createStudentCard(student)));
    els.shiftTemplates.innerHTML = "";
    (window.DEFAULT_SHIFT_TEMPLATES || []).forEach((template) => {
      els.shiftTemplates.appendChild(createShiftCard(template, window.DEFAULT_CUSTOM_CONFIG[`shift_${template.id}`]));
    });
  }

  function populateFromImportedPayload(payload) {
    els.scheduleName.value = payload.schedule_name || "";
    els.algorithm.value = payload.algorithm || DEFAULT_ALGORITHM;
    els.weeks.value = payload.weeks || DEFAULT_WEEKS;
    switchMode(payload.mode || DEFAULT_MODE);
    syncAlgorithmShowcase();

    els.studentsContainer.innerHTML = "";
    (payload.students || []).forEach((student) => {
      els.studentsContainer.appendChild(createStudentCard(student));
    });

    els.shiftTemplates.innerHTML = "";
    if (payload.mode === "custom") {
      (payload.shift_templates || []).forEach((template) => {
        els.shiftTemplates.appendChild(createShiftCard(template, (payload.schedule_config || {})[`shift_${template.id}`] || {}));
      });
    } else {
      (window.DEFAULT_SHIFT_TEMPLATES || []).forEach((template) => {
        els.shiftTemplates.appendChild(createShiftCard(template, window.DEFAULT_CUSTOM_CONFIG[`shift_${template.id}`]));
      });
    }
  }

  async function importTemplateFile(file) {
    const text = await file.text();
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      throw new Error("Uploaded template must be valid JSON.");
    }

    const response = await fetch("/api/import-template", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to import template.");
    populateFromImportedPayload(data.payload);
    flash("Planning file imported and form populated.", "success");
  }

  function collectPayload() {
    const students = Array.from(els.studentsContainer.querySelectorAll(".student-card")).map((card) => ({
      name: card.querySelector(".student-name").value.trim(),
      profile: card.querySelector(".student-profile").value.trim(),
      reliability: Number(card.querySelector(".student-reliability").value || 85),
      max_hours: Number(card.querySelector(".student-hours").value || 12),
      preferred_shift: card.querySelector(".student-pref").value,
      recent_callouts: Number(card.querySelector(".student-callouts").value || 0),
    }));
    const payload = {
      schedule_name: els.scheduleName.value.trim(),
      mode: state.mode,
      algorithm: els.algorithm.value,
      weeks: Number(els.weeks.value || 4),
      students,
    };
    if (state.mode === "custom") {
      const shiftTemplates = [];
      const scheduleConfig = {};
      Array.from(els.shiftTemplates.querySelectorAll(".shift-card")).forEach((card) => {
        const id = Number(card.dataset.id);
        shiftTemplates.push({
          id,
          name: card.querySelector(".shift-name").value.trim() || "Untitled Shift",
          start: card.querySelector(".shift-start").value,
          end: card.querySelector(".shift-end").value,
          students_needed: Number(card.querySelector(".shift-needed").value || 1),
        });
        scheduleConfig[`shift_${id}`] = {
          days: card.querySelector(".shift-days").value.trim() || "Mon Wed Fri",
          count: Number(card.querySelector(".shift-count").value || 1),
        };
      });
      payload.shift_templates = shiftTemplates;
      payload.schedule_config = scheduleConfig;
    }
    return payload;
  }

  function renderStats() {
    const stats = state.stats || {};
    els.statStudents.textContent = stats.total_students || 0;
    els.statAssignments.textContent = stats.total_assignments || 0;
    els.statBackups.textContent = stats.total_backup_assignments || 0;
    els.statCoverage.textContent = `${stats.coverage_ready_percent || 0}%`;
    els.statConflictFree.textContent = `${stats.conflict_free_percent || 0}%`;
    els.statAverage.textContent = stats.average_assignments || 0;
    els.statSpread.textContent = stats.fairness_spread || 0;
    els.statAlgorithm.textContent = stats.algorithm_label || "-";
  }

  function renderAlgorithmInsights() {
    const insight = state.algorithmInsights;
    if (!insight) {
      els.algorithmInsightBox.classList.add("hidden");
      els.algorithmInsightContent.innerHTML = "";
      return;
    }
    els.algorithmInsightBox.classList.remove("hidden");
    els.algorithmInsightContent.innerHTML = `
      <div class="algorithm-hero">
        <strong>${escapeHtml(insight.label)}</strong>
        <span>${escapeHtml(insight.family)} / ${escapeHtml(insight.headline)}</span>
      </div>
      <p>${escapeHtml(insight.summary)}</p>
      <div class="algorithm-pills">
        <span class="badge soft">Preference match ${insight.preference_match_rate}%</span>
        <span class="badge soft">Conflict free ${insight.conflict_free_percent}%</span>
        <span class="badge soft">Coverage ${insight.coverage_ready_percent}%</span>
        <span class="badge soft">Avg risk ${insight.average_risk}</span>
      </div>
    `;
  }

  function renderWorkloadBars() {
    const stats = state.stats;
    if (!stats) {
      els.workloadBars.innerHTML = "";
      return;
    }
    const entries = Object.keys(stats.assignments_by_student || {});
    const maxPrimary = Math.max(...entries.map((name) => stats.assignments_by_student[name]), 1);
    els.workloadBars.innerHTML = entries.map((name) => {
      const primary = stats.assignments_by_student[name] || 0;
      const backups = stats.backup_by_student[name] || 0;
      const hours = stats.hours_by_student[name] || 0;
      const risk = stats.risk_by_student[name] || 0;
      const reliability = stats.reliability_by_student[name] || 0;
      return `
        <div class="bar-row stacked">
          <div class="bar-copy">
            <strong>${escapeHtml(name)}</strong>
            <span>${primary} primary / ${backups} backup / ${hours}h / reliability ${reliability}%</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:${(primary / maxPrimary) * 100}%"></div></div>
          <span class="risk-chip ${risk >= 70 ? "high" : risk >= 40 ? "medium" : "low"}">Risk ${risk}</span>
        </div>`;
    }).join("");
  }

  function renderConflicts() {
    if (!state.conflicts.length) {
      els.conflictBox.classList.add("hidden");
      els.conflictList.innerHTML = "";
      return;
    }
    els.conflictBox.classList.remove("hidden");
    els.conflictList.innerHTML = state.conflicts.map((item) => `
      <div class="list-item danger-left">
        <strong>${escapeHtml(item.student)}</strong> / ${formatDate(item.date)} / ${escapeHtml(item.time)}<br>
        ${escapeHtml(item.reason)}: ${escapeHtml(item.commitment)}
      </div>`).join("");
  }

  function renderWarnings() {
    if (!state.warnings.length) {
      els.warningBox.classList.add("hidden");
      els.warningList.innerHTML = "";
      return;
    }
    els.warningBox.classList.remove("hidden");
    els.warningList.innerHTML = state.warnings.map((item) => `
      <div class="list-item ${item.severity === "high" ? "danger-left" : "warn-left"}">
        <strong>${escapeHtml(item.student)}</strong> / ${formatDate(item.date)}<br>
        ${escapeHtml(item.reason)}
      </div>`).join("");
  }

  function renderCalloutPlan() {
    if (!state.calloutPlan.length) {
      els.calloutBox.classList.add("hidden");
      els.calloutList.innerHTML = "";
      return;
    }
    els.calloutBox.classList.remove("hidden");
    els.calloutList.innerHTML = state.calloutPlan.map((item) => `
      <div class="list-item">
        <strong>${escapeHtml(item.shift_name)}</strong> / ${formatDate(item.date)} / ${escapeHtml(item.time)}<br>
        Primary: ${escapeHtml(item.primaries.join(", ") || "None")}<br>
        Backup: ${escapeHtml(item.backups.join(", ") || "No backup assigned")}
      </div>`).join("");
  }

  function groupAssignmentsByDate(assignments) {
    return assignments.reduce((accumulator, item) => {
      if (!accumulator[item.date]) accumulator[item.date] = [];
      accumulator[item.date].push(item);
      accumulator[item.date].sort((a, b) => a.start_minutes - b.start_minutes || a.student.localeCompare(b.student));
      return accumulator;
    }, {});
  }

  function renderList() {
    const primary = state.assignments.filter((item) => item.role === "primary");
    if (!primary.length) {
      els.scheduleList.className = "schedule-list empty-state";
      els.scheduleList.textContent = "Generate a staffing plan to see the results.";
      return;
    }
    const grouped = groupAssignmentsByDate(primary);
    els.scheduleList.className = "schedule-list";
    els.scheduleList.innerHTML = Object.entries(grouped).map(([iso, items]) => `
      <article class="day-card">
        <h3>${formatDate(iso)}</h3>
        ${items.map((item) => {
          const plan = state.calloutPlan.find((row) => row.shift_instance_id === item.shift_instance_id) || { backups: [] };
          return `
            <div class="assignment-pill ${item.conflict ? "conflict" : ""}">
              <div><strong>${escapeHtml(item.shift_name)}</strong><br><span>${escapeHtml(item.time)}</span></div>
              <div><strong>${escapeHtml(item.student)}</strong><br><span>${escapeHtml(item.round_label || "")}</span></div>
              <div><span class="badge">Backup: ${escapeHtml(plan.backups.join(", ") || "None")}</span></div>
            </div>`;
        }).join("")}
      </article>`).join("");
  }

  function renderCalendar() {
    const weekDates = getWeekDates(state.currentWeekOffset);
    els.calendarTitle.textContent = `${formatShortDate(weekDates[0])} - ${formatShortDate(weekDates[6])}`;
    const grouped = groupAssignmentsByDate(state.assignments.filter((item) => item.role === "primary"));
    els.calendarGrid.innerHTML = weekDates.map((dateValue) => {
      const iso = toISODate(dateValue);
      const items = grouped[iso] || [];
      return `
        <article class="calendar-day">
          <h4>${dateValue.toLocaleDateString(undefined, { weekday: "short", day: "numeric" })}</h4>
          ${items.length ? items.map((item) => `<div class="calendar-chip ${item.conflict ? "conflict" : ""}"><strong>${escapeHtml(item.student)}</strong><br>${escapeHtml(item.time)}<br><span>${escapeHtml(item.shift_name)}</span></div>`).join("") : '<div class="hint">No shifts</div>'}
        </article>`;
    }).join("");
  }

  function renderHistoryLink() {
    if (!state.historyUrl) {
      els.historyLinkBox.classList.add("hidden");
      els.historyLinkBox.innerHTML = "";
      return;
    }
    els.historyLinkBox.classList.remove("hidden");
    const algorithmSnippet = state.algorithmInsights ? ` Algorithm: <strong>${escapeHtml(state.algorithmInsights.label)}</strong>.` : "";
    const ethicsSnippet = state.ethics ? ` Ethics review: <strong>${escapeHtml(state.ethics.overall_status)}</strong> (${state.ethics.overall_score}).` : "";
    const exportJson = state.exportJsonUrl ? `<a href="${state.exportJsonUrl}">Download JSON</a>` : "";
    const exportCsv = state.exportCsvUrl ? `<a href="${state.exportCsvUrl}">Download CSV</a>` : "";
    els.historyLinkBox.innerHTML = `Saved to the archive. <a href="${state.historyUrl}">Open this plan</a> or <a href="/history">browse all plans</a>.${algorithmSnippet}${ethicsSnippet} ${exportJson} ${exportCsv}`.trim();
  }

  async function generateSchedule() {
    const payload = collectPayload();
    if (payload.students.filter((student) => student.name).length < 2) {
      flash("Please enter at least two student names.", "error");
      return;
    }
    if (state.mode === "custom" && !(payload.shift_templates || []).length) {
      flash("Add at least one shift template before generating a custom plan.", "error");
      return;
    }
    els.generateBtn.disabled = true;
    els.generateBtn.textContent = "Generating...";
    flash("Building staffing plan with backup coverage...", "success");
    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to generate schedule.");
      state.assignments = data.assignments;
      state.conflicts = data.conflicts;
      state.warnings = data.warnings;
      state.stats = data.stats;
      state.algorithmInsights = data.algorithm_insights;
      state.ethics = data.ethics;
      state.calloutPlan = data.callout_plan;
      state.historyUrl = data.history_url || "";
      state.exportJsonUrl = data.export_json_url || "";
      state.exportCsvUrl = data.export_csv_url || "";
      state.currentWeekOffset = 0;
      renderStats();
      renderWorkloadBars();
      renderAlgorithmInsights();
      renderConflicts();
      renderWarnings();
      renderCalloutPlan();
      renderList();
      renderCalendar();
      renderHistoryLink();
      document.getElementById("scheduleList").scrollIntoView({ behavior: "smooth", block: "start" });
      flash(data.conflicts.length ? `Plan saved with ${data.conflicts.length} academic conflict flag(s).` : "Plan saved with no academic conflicts.", data.conflicts.length ? "error" : "success");
    } catch (error) {
      flash(error.message, "error");
    } finally {
      els.generateBtn.disabled = false;
      els.generateBtn.textContent = "Generate Plan";
    }
  }

  function resetAll() {
    seedInitialCards();
    els.scheduleName.value = "";
    switchMode(DEFAULT_MODE);
    els.algorithm.value = DEFAULT_ALGORITHM;
    els.weeks.value = DEFAULT_WEEKS;
    syncAlgorithmShowcase();
    state.assignments = [];
    state.conflicts = [];
    state.warnings = [];
    state.stats = null;
    state.algorithmInsights = null;
    state.ethics = null;
    state.calloutPlan = [];
    state.historyUrl = "";
    state.exportJsonUrl = "";
    state.exportCsvUrl = "";
    renderStats();
    renderWorkloadBars();
    renderAlgorithmInsights();
    renderConflicts();
    renderWarnings();
    renderCalloutPlan();
    renderList();
    renderCalendar();
    renderHistoryLink();
    flash("Reset to planning defaults.", "success");
  }

  document.querySelectorAll("#modeSwitch .segment").forEach((button) => {
    button.addEventListener("click", () => switchMode(button.dataset.mode));
  });
  document.querySelectorAll("#resultSwitch .segment").forEach((button) => {
    button.addEventListener("click", () => switchResultView(button.dataset.view));
  });
  document.getElementById("prevWeekBtn").addEventListener("click", () => {
    state.currentWeekOffset -= 1;
    renderCalendar();
  });
  document.getElementById("nextWeekBtn").addEventListener("click", () => {
    state.currentWeekOffset += 1;
    renderCalendar();
  });
  els.addStudentBtn.addEventListener("click", () => els.studentsContainer.appendChild(createStudentCard()));
  els.addShiftBtn.addEventListener("click", () => els.shiftTemplates.appendChild(createShiftCard()));
  els.algorithm.addEventListener("change", syncAlgorithmShowcase);
  els.generateBtn.addEventListener("click", generateSchedule);
  els.resetBtn.addEventListener("click", resetAll);
  els.templateUpload.addEventListener("change", async () => {
    const [file] = els.templateUpload.files || [];
    if (!file) return;
    try {
      await importTemplateFile(file);
    } catch (error) {
      flash(error.message, "error");
    } finally {
      els.templateUpload.value = "";
    }
  });

  seedInitialCards();
  switchMode(DEFAULT_MODE);
  els.algorithm.value = DEFAULT_ALGORITHM;
  syncAlgorithmShowcase();
  switchResultView("list");
}

function initializeHistoryDetailPage() {
  const root = document.getElementById("outcomeBuilderRoot");
  if (!root) return;

  const runId = root.dataset.runId;
  const outcomesMeta = window.OUTCOME_BUILDER || {};
  const els = {
    goalPicker: document.getElementById("outcomeGoalPicker"),
    generateBtn: document.getElementById("generateOutcomesBtn"),
    status: document.getElementById("outcomeStatus"),
    results: document.getElementById("outcomeResults"),
  };
  const state = {
    goal: Object.keys(outcomesMeta)[0] || "balanced",
    loading: false,
  };

  function formatSigned(value, suffix = "") {
    if (value > 0) return `+${value}${suffix}`;
    return `${value}${suffix}`;
  }

  function setStatus(message, pending = false) {
    if (!message) {
      els.status.classList.add("hidden");
      els.status.textContent = "";
      els.status.classList.remove("pending");
      return;
    }
    els.status.classList.remove("hidden");
    els.status.textContent = message;
    els.status.classList.toggle("pending", pending);
  }

  function syncGoalSelection() {
    els.goalPicker.querySelectorAll("[data-goal]").forEach((button) => {
      button.classList.toggle("active", button.dataset.goal === state.goal);
    });
  }

  function renderCandidates(payload) {
    const candidates = payload.candidates || [];
    if (!candidates.length) {
      els.results.classList.remove("hidden");
      els.results.innerHTML = `<div class="card inset">No alternate outcomes were available for this run.</div>`;
      return;
    }
    els.results.classList.remove("hidden");
    els.results.innerHTML = `
      <div class="outcome-summary-bar">
        <span class="metric-chip">Current conflicts ${payload.baseline.conflicts}</span>
        <span class="metric-chip">Current coverage ${payload.baseline.coverage_ready_percent}%</span>
        <span class="metric-chip">Current fairness ${payload.baseline.fairness_spread}</span>
        <span class="metric-chip">Current ethics ${payload.baseline.ethics_score}</span>
      </div>
      <div class="outcome-card-grid">
        ${candidates.map((candidate) => `
          <article class="outcome-card${candidate.recommended ? " recommended" : ""}">
            <div class="outcome-card-topline">
              <span class="badge soft">${escapeHtml(candidate.goal_label)}</span>
              <span class="badge soft">${candidate.recommended ? "Recommended" : `Option ${candidate.rank}`}</span>
            </div>
            <div class="outcome-card-head">
              <div>
                <h3>${escapeHtml(candidate.title)}</h3>
                <p>${escapeHtml(candidate.subtitle)}</p>
              </div>
              <strong class="outcome-score">${candidate.score}</strong>
            </div>
            <p class="outcome-narrative">${escapeHtml(candidate.narrative)}</p>
            <div class="outcome-metrics">
              <span class="metric-chip">Conflicts ${candidate.summary.conflicts}</span>
              <span class="metric-chip">Coverage ${candidate.summary.coverage_ready_percent}%</span>
              <span class="metric-chip">Fairness ${candidate.summary.fairness_spread}</span>
              <span class="metric-chip">Ethics ${candidate.summary.ethics_score}</span>
              <span class="metric-chip">Warnings ${candidate.summary.warnings}</span>
              <span class="metric-chip">Preference ${candidate.summary.preference_match_rate}%</span>
            </div>
            <div class="outcome-deltas">
              <span class="delta-pill ${candidate.deltas.conflicts < 0 ? "better" : candidate.deltas.conflicts > 0 ? "worse" : ""}">Conflicts ${formatSigned(candidate.deltas.conflicts)}</span>
              <span class="delta-pill ${candidate.deltas.coverage_ready_percent > 0 ? "better" : candidate.deltas.coverage_ready_percent < 0 ? "worse" : ""}">Coverage ${formatSigned(candidate.deltas.coverage_ready_percent, " pts")}</span>
              <span class="delta-pill ${candidate.deltas.ethics_score > 0 ? "better" : candidate.deltas.ethics_score < 0 ? "worse" : ""}">Ethics ${formatSigned(candidate.deltas.ethics_score)}</span>
              <span class="delta-pill ${candidate.deltas.fairness_spread < 0 ? "better" : candidate.deltas.fairness_spread > 0 ? "worse" : ""}">Fairness ${formatSigned(candidate.deltas.fairness_spread)}</span>
            </div>
            <div class="cta-row outcome-card-actions">
              <button class="ghost-btn" type="button" data-action="save-revision" data-candidate="${candidate.key}">Save Revision</button>
              <button class="primary-btn" type="button" data-action="accept-final" data-candidate="${candidate.key}">Accept Final</button>
            </div>
          </article>
        `).join("")}
      </div>
    `;
  }

  async function saveCandidate(candidateKey, finalize) {
    setStatus(finalize ? "Saving final outcome..." : "Saving revision...", true);
    try {
      const response = await fetch(`/history/${runId}/outcomes/${candidateKey}/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: state.goal, finalize }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to save this outcome.");
      window.location.href = data.history_url;
    } catch (error) {
      setStatus(error.message, false);
    }
  }

  async function generateOutcomes() {
    if (state.loading) return;
    state.loading = true;
    els.generateBtn.disabled = true;
    els.generateBtn.textContent = "Generating...";
    setStatus("Reading the run, testing outcome variants, and scoring the best revisions...", true);
    try {
      const response = await fetch(`/history/${runId}/outcomes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: state.goal }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to generate outcomes.");
      renderCandidates(data);
      setStatus(`${data.goal_label} outcomes are ready. Compare the revisions and save the one you want.`, false);
      root.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      setStatus(error.message, false);
    } finally {
      state.loading = false;
      els.generateBtn.disabled = false;
      els.generateBtn.textContent = "Generate Outcomes";
    }
  }

  els.goalPicker.querySelectorAll("[data-goal]").forEach((button) => {
    button.addEventListener("click", () => {
      state.goal = button.dataset.goal;
      syncGoalSelection();
    });
  });
  els.generateBtn.addEventListener("click", generateOutcomes);
  els.results.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    saveCandidate(button.dataset.candidate, button.dataset.action === "accept-final");
  });

  syncGoalSelection();
}

applyStoredTheme();
initializePageMotion();
initializeThemePicker();
initializeDetailsDismiss();
if (pageName === "home") initializeHomeCarousel();
if (pageName === "scheduler") initializeSchedulerPage();
if (pageName === "history") initializeHistoryDetailPage();
