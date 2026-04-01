const state = {
  page: resolvePage(location.pathname),
  system: null,
  meetings: [],
  meetingDetails: {},
  loadingMeetings: false,
  upload: {
    file: null,
    title: "",
    date: new Date().toISOString().slice(0, 10),
    uploading: false,
    job: null,
    dragging: false,
    progress: {
      jobId: null,
      stageKey: null,
      stageEnteredAt: 0,
      display: 0,
    },
  },
  search: {
    query: "",
    searching: false,
    searched: false,
    results: [],
  },
};

const appEl = document.getElementById("app");
const toastEl = document.getElementById("toast");
const runtimePillEl = document.getElementById("runtime-pill");
const JOB_STAGE_TIMINGS = [
  { key: "queued", durationMs: 1800 },
  { key: "transcribing", durationMs: 14000 },
  { key: "summarizing", durationMs: 5200 },
  { key: "extracting", durationMs: 4400 },
  { key: "reporting", durationMs: 3200 },
  { key: "indexing", durationMs: 2400 },
  { key: "saving", durationMs: 1800 },
];

window.addEventListener("popstate", () => {
  state.page = resolvePage(location.pathname);
  render();
  loadPageData();
});

document.addEventListener("click", async (event) => {
  const link = event.target.closest("[data-link]");
  if (link) {
    event.preventDefault();
    navigate(link.getAttribute("href"));
    return;
  }

  const action = event.target.closest("[data-action]");
  if (!action) return;

  const { action: type, meetingId, taskId, target } = action.dataset;
  if (type === "pick-file") document.getElementById("audio-file")?.click();
  if (type === "expand-meeting") await toggleMeeting(meetingId);
  if (type === "toggle-task") await toggleTask(taskId, meetingId);
  if (type === "copy-command") copyText(target);
  if (type === "jump-to-meetings") navigate("/app/meetings");
});

document.addEventListener("change", (event) => {
  if (event.target.id === "audio-file" && event.target.files?.[0]) {
    const file = event.target.files[0];
    state.upload.file = file;
    state.upload.title ||= file.name.replace(/\.[^/.]+$/, "");
    render();
  }
});

document.addEventListener("input", (event) => {
  if (event.target.id === "meeting-title") state.upload.title = event.target.value;
  if (event.target.id === "meeting-date") state.upload.date = event.target.value;
  if (event.target.id === "search-query") state.search.query = event.target.value;
});

document.addEventListener("submit", async (event) => {
  if (event.target.id === "upload-form") {
    event.preventDefault();
    await uploadMeeting();
  }
  if (event.target.id === "search-form") {
    event.preventDefault();
    await runSearch();
  }
});

document.addEventListener("dragover", (event) => {
  if (event.target.closest(".dropzone")) event.preventDefault();
});

document.addEventListener("dragenter", (event) => {
  if (event.target.closest(".dropzone")) {
    state.upload.dragging = true;
    render();
  }
});

document.addEventListener("dragleave", (event) => {
  if (event.target.closest(".dropzone") && event.target === event.target.closest(".dropzone")) {
    state.upload.dragging = false;
    render();
  }
});

document.addEventListener("drop", (event) => {
  const zone = event.target.closest(".dropzone");
  if (!zone) return;
  event.preventDefault();
  state.upload.dragging = false;
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    state.upload.file = file;
    state.upload.title ||= file.name.replace(/\.[^/.]+$/, "");
  }
  render();
});

init();

async function init() {
  startUploadProgressLoop();
  render();
  await hydrateSystem();
  await loadPageData();
}

function resolvePage(pathname) {
  const map = { "/": "home", "/app/upload": "upload", "/app/meetings": "meetings", "/app/search": "search", "/app/setup": "setup" };
  return map[pathname] || "home";
}

function navigate(path) {
  history.pushState({}, "", path);
  state.page = resolvePage(path);
  render();
  loadPageData();
}

async function loadPageData() {
  if (["home", "meetings"].includes(state.page) && !state.meetings.length) await loadMeetings();
}

async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail || response.statusText);
  }
  return response.json();
}

async function hydrateSystem() {
  try {
    state.system = await api("/system/status");
  } catch (error) {
    state.system = null;
    showToast(`No se pudo leer el runtime: ${error.message}`);
  }
  syncRuntimePill();
  render();
}

function syncRuntimePill() {
  const apiStatus = state.system?.api?.status;
  runtimePillEl.className = `runtime-pill ${apiStatus === "online" ? "online" : "offline"}`;
  runtimePillEl.innerHTML = `<span class="runtime-dot"></span><span>${apiStatus === "online" ? "Runtime listo" : "Runtime no disponible"}</span>`;
}

async function loadMeetings() {
  state.loadingMeetings = true;
  render();
  try {
    state.meetings = await api("/meetings");
  } catch (error) {
    showToast(`No se pudieron cargar reuniones: ${error.message}`);
  } finally {
    state.loadingMeetings = false;
    render();
  }
}

async function toggleMeeting(meetingId) {
  if (state.meetingDetails[meetingId]?.open) {
    state.meetingDetails[meetingId].open = false;
    render();
    return;
  }
  const current = state.meetingDetails[meetingId] || {};
  state.meetingDetails[meetingId] = { ...current, open: true, loading: !current.data };
  render();
  if (current.data) return;
  try {
    const data = await api(`/meetings/${meetingId}`);
    state.meetingDetails[meetingId] = { open: true, loading: false, data };
  } catch (error) {
    state.meetingDetails[meetingId] = { open: false, loading: false, data: null };
    showToast(`No se pudo abrir la reunión: ${error.message}`);
  }
  render();
}

async function toggleTask(taskId, meetingId) {
  const detail = state.meetingDetails[meetingId]?.data;
  const item = detail?.action_items?.find((task) => task.id === taskId);
  if (!item) return;
  const nextStatus = item.status === "done" ? "pending" : "done";
  item.status = nextStatus;
  render();
  try {
    await api(`/tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: nextStatus }),
    });
    if (state.system?.stats) {
      state.system.stats.tasks_done += nextStatus === "done" ? 1 : -1;
      state.system.stats.tasks_pending += nextStatus === "done" ? -1 : 1;
    }
  } catch (error) {
    item.status = nextStatus === "done" ? "pending" : "done";
    showToast(`No se pudo actualizar la task: ${error.message}`);
  }
  render();
}

async function uploadMeeting() {
  if (!state.upload.file || state.upload.uploading) return;
  state.upload.uploading = true;
  state.upload.job = null;
  resetUploadProgress();
  render();
  try {
    const body = new FormData();
    body.append("file", state.upload.file);
    body.append("title", state.upload.title || state.upload.file.name.replace(/\.[^/.]+$/, ""));
    body.append("meeting_date", state.upload.date);
    const job = await api("/meetings/audio", { method: "POST", body });
    state.upload.job = job;
    syncUploadProgressState(job);
    render();
    scrollToUploadJobPanel();
    await pollJob(job.job_id);
  } catch (error) {
    state.upload.job = { status: "error", error: error.message };
    syncUploadProgressState(state.upload.job);
    showToast(`No se pudo subir el audio: ${error.message}`);
  } finally {
    state.upload.uploading = false;
    render();
  }
}

async function pollJob(jobId) {
  let done = false;
  while (!done) {
    const job = await api(`/jobs/${jobId}`);
    state.upload.job = job;
    syncUploadProgressState(job);
    render();
    done = job.status === "done" || job.status === "error";
    if (job.status === "done") {
      state.upload.file = null;
      await Promise.all([hydrateSystem(), loadMeetings()]);
      continue;
    }
    await sleep(700);
  }
}

async function runSearch() {
  if (!state.search.query.trim() || state.search.searching) return;
  state.search.searching = true;
  state.search.searched = false;
  render();
  try {
    const result = await api("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: state.search.query, top_k: 8 }),
    });
    state.search.results = dedupeSearchResults(result.results || []);
    state.search.searched = true;
  } catch (error) {
    state.search.results = [];
    state.search.searched = true;
    showToast(`No se pudo ejecutar la búsqueda: ${error.message}`);
  } finally {
    state.search.searching = false;
    render();
  }
}

function render() {
  markActiveNav();
  appEl.innerHTML = pageTemplate();
}

function markActiveNav() {
  document.querySelectorAll(".nav a").forEach((link) => {
    link.classList.toggle("active", link.dataset.page === state.page);
  });
}

function pageTemplate() {
  if (state.page === "upload") return uploadPage();
  if (state.page === "meetings") return meetingsPage();
  if (state.page === "search") return searchPage();
  if (state.page === "setup") return setupPage();
  return homePage();
}

function homePage() {
  const stats = state.system?.stats || { meetings: 0, tasks_pending: 0, tasks_done: 0 };
  return `<section class="stack-lg">
    <div class="hero">
      <div class="hero-grid">
        <div>
          <div class="eyebrow"><span>En local y listo para operar</span></div>
          <h1>Tus reuniones <span class="gradient-word">a acción</span> sin perder contexto.</h1>
          <p class="lede">MeetingAgent hereda la presencia visual de la demo, pero aquí todo es utilizable: subes audio, sigues el pipeline, recuperas reuniones y validas el runtime real.</p>
          <div class="hero-actions">
            <a href="/app/upload" data-link class="primary-button">Nueva reunión</a>
            <a href="/app/meetings" data-link class="secondary-button">Ver reuniones</a>
            <a href="/app/search" data-link class="secondary-button">Buscar contexto</a>
          </div>
        </div>
      </div>
      <div class="status-strip">
        ${statCard("Reuniones indexadas", String(stats.meetings), "Base operativa actual")}
        ${statCard("Tasks pendientes", String(stats.tasks_pending), "Seguimiento pendiente")}
        ${statCard("Tasks cerradas", String(stats.tasks_done), "Acciones completadas")}
        ${statCard("Modo", "100% local", "Sin APIs de pago")}
      </div>
    </div>
    <div class="home-system-grid">
      <div class="home-system-pair">
        ${runtimeInfoCard()}
        <div class="card stack-md">
          <div><div class="section-kicker">Control del sistema</div><h2 class="card-title">Runtime operativo</h2></div>
          <p class="muted">Una lectura rápida del stack local para saber si el motor está listo antes de subir o consultar reuniones.</p>
          <div class="system-overview">
            <div class="system-signal-row">
              ${statusPill("API", state.system?.api?.status)}
              ${statusPill("Chroma", state.system?.chroma?.status)}
              ${statusPill("Ollama", state.system?.ollama?.status)}
            </div>
            <div class="system-overview-grid">
              ${signalCard("Proveedor", state.system?.config?.llm_provider || "--", "Proveedor LLM activo")}
              ${signalCard("Modelo", state.system?.config?.ollama_model || "--", "Modelo principal")}
              ${signalCard("Whisper", state.system?.config?.whisper_device || "--", "Dispositivo de transcripción")}
              ${signalCard("Vector store", `${state.system?.config?.chroma_host || "--"}:${state.system?.config?.chroma_port || "--"}`, "Endpoint Chroma")}
            </div>
          </div>
          <div class="button-row">
            <a href="/app/setup" data-link class="secondary-button">Abrir setup técnico</a>
          </div>
        </div>
      </div>
    </div>
  </section>`;
}

function uploadPage() {
  const hasFile = Boolean(state.upload.file);
  const job = state.upload.job;
  return `<section class="stack-lg">
    <div class="page-header"><div class="section-kicker">Nueva reunión</div><h1>Sube audio, observa el pipeline y valida el resultado.</h1><p>Esta pantalla está centrada en una sola tarea: convertir una reunión en resumen, decisiones y action items sin desviar la atención.</p></div>
    <form id="upload-form" class="stack-lg">
      <div class="dropzone ${state.upload.dragging ? "dragging" : ""} ${hasFile ? "has-file" : ""}" data-action="pick-file">
        <input id="audio-file" type="file" accept=".mp3,.mp4,.wav,.m4a,.ogg,.flac,.webm" hidden>
        <div class="stack-sm">
          <strong>${hasFile ? escapeHtml(state.upload.file.name) : "Arrastra audio aquí o haz clic para seleccionar"}</strong>
          <span class="muted mono">${hasFile ? formatFileSize(state.upload.file.size) : "mp3 · wav · m4a · webm · máximo 500 MB"}</span>
        </div>
      </div>
      <div class="grid-2">
        <label class="stack-sm"><span class="muted mono">Título</span><input id="meeting-title" class="field" value="${escapeAttribute(state.upload.title)}" placeholder="Sprint sync marzo"></label>
        <label class="stack-sm"><span class="muted mono">Fecha</span><input id="meeting-date" class="field" type="date" value="${escapeAttribute(state.upload.date)}"></label>
      </div>
      <div class="button-row"><button class="primary-button" type="submit" ${!hasFile || state.upload.uploading ? "disabled" : ""}>${state.upload.uploading ? "Procesando..." : "Analizar reunión"}</button></div>
    </form>
    ${job ? uploadJobPanel(job) : ""}
  </section>`;
}

function meetingsPage() {
  const totalDecisions = state.meetings.reduce((sum, meeting) => sum + (meeting.decisions?.length || 0), 0);
  const totalSpeakers = state.meetings.reduce((sum, meeting) => sum + (meeting.speakers?.length || 0), 0);
  return `<section class="stack-lg">
    <div class="page-header"><div class="section-kicker">Reuniones</div><h1>Consulta cada reunión sin salir del contexto de lista.</h1><p>El detalle se expande en la misma página para mantener ritmo de revisión, tareas y exportación sin abrir pantallas extra.</p></div>
    ${state.loadingMeetings ? loadingState("Cargando reuniones...") : state.meetings.length ? `<div class="meetings-overview">
      ${statCard("Reuniones", String(state.meetings.length), "Sesiones disponibles")}
      ${statCard("Decisiones", String(totalDecisions), "Detectadas en total")}
      ${statCard("Speakers", String(totalSpeakers), "Participaciones registradas")}
      ${statCard("Vista", "Inline", "Detalle sin salir de la lista")}
    </div><div class="meetings-list">${state.meetings.map(meetingCard).join("")}</div>` : emptyState("Aún no hay reuniones procesadas.", "Sube tu primer audio desde Nueva reunión.") }
  </section>`;
}

function searchPage() {
  return `<section class="stack-lg">
    <div class="page-header"><div class="section-kicker">Búsqueda semántica</div><h1>Recupera contexto transversal sin recorrer reunión por reunión.</h1><p>Busca por temas, decisiones o frases concretas y salta luego a la reunión adecuada.</p></div>
    <form id="search-form" class="card stack-md">
      <input id="search-query" class="search-input" value="${escapeAttribute(state.search.query)}" placeholder="Ejemplo: compromisos para el cliente, deadline del sprint, blockers del backend">
      <div class="button-row"><button class="primary-button" type="submit">${state.search.searching ? "Buscando..." : "Buscar"}</button></div>
    </form>
    ${renderSearchResults()}
  </section>`;
}

function setupPage() {
  const config = state.system?.config || {};
  return `<section class="stack-lg">
    <div class="page-header"><div class="section-kicker">Setup / Runtime</div><h1>Diagnóstico técnico del sistema local.</h1><p>Esta página prioriza señales de runtime reales: servicios, configuración efectiva y comandos base para operar el stack local.</p></div>
    <div class="setup-dashboard-grid">
      <div class="diagnostic-card stack-md">
        <div><div class="section-kicker">Servicios</div><h2 class="card-title">Estado del stack</h2></div>
        <div class="stack-sm">
          ${serviceRow("FastAPI", state.system?.api)}
          ${serviceRow("SQLite", state.system?.database)}
          ${serviceRow("Chroma", state.system?.chroma)}
          ${serviceRow("Ollama", state.system?.ollama)}
        </div>
      </div>
      <div class="diagnostic-card stack-md">
        <div><div class="section-kicker">Configuración</div><h2 class="card-title">Valores efectivos</h2></div>
        <div class="setup-config-grid">
          ${signalCard("LLM provider", config.llm_provider || "--", "Proveedor configurado")}
          ${signalCard("Modelo", config.ollama_model || "--", "Modelo principal")}
          ${signalCard("Whisper model", config.whisper_model || "--", "Modelo STT")}
          ${signalCard("Whisper device", config.whisper_device || "--", "Dispositivo")}
          ${signalCard("Whisper compute", config.whisper_compute_type || "--", "Precisión")}
          ${signalCard("Chroma endpoint", `${config.chroma_host || "--"}:${config.chroma_port || "--"}`, "Vector store")}
        </div>
      </div>
      <div class="diagnostic-card stack-md">
        <div><div class="section-kicker">Comandos</div><h2 class="card-title">Operación local</h2></div>
        <div class="stack-sm">
          ${commandCard("Backend", "cmd-backend", "venvMA\\\\Scripts\\\\python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000")}
          ${commandCard("Chroma", "cmd-chroma", "venvMA\\\\Scripts\\\\activate\\nchroma run --host localhost --port 8001 --path ./chroma")}
          ${commandCard("Ollama", "cmd-ollama", "ollama serve")}
        </div>
      </div>
      <div class="diagnostic-card stack-md">
        <div><div class="section-kicker">Volumen</div><h2 class="card-title">Actividad operativa</h2></div>
        <div class="setup-stats-grid">
          ${statCard("Meetings", String(state.system?.stats?.meetings || 0), "Guardadas en SQLite")}
          ${statCard("Pending", String(state.system?.stats?.tasks_pending || 0), "Pendientes")}
          ${statCard("Done", String(state.system?.stats?.tasks_done || 0), "Completadas")}
        </div>
      </div>
    </div>
  </section>`;
}

function meetingCard(meeting) {
  const detailState = state.meetingDetails[meeting.id] || {};
  const detail = detailState.data;
  const loadedTaskCount = detail?.action_items?.length ?? null;
  const pendingTaskCount = detail?.action_items?.filter((task) => task.status !== "done").length ?? null;
  const decisionsPreview = meeting.decisions?.slice(0, 2) || [];
  const speakersLabel = meeting.speakers?.length ? meeting.speakers.join(", ") : "Sin speakers detectados";
  return `<article class="meeting-card">
    <div class="meeting-shell">
      <div class="meeting-topbar">
        <div class="meeting-date-badge">${escapeHtml(meeting.date || "--")}</div>
        <div class="meeting-state-group">
          <span class="meeting-state-chip ${detailState.open ? "active" : "idle"}">${detailState.open ? "Detalle abierto" : "Vista resumida"}</span>
          ${loadedTaskCount !== null ? `<span class="meeting-state-chip ${pendingTaskCount ? "pending" : "done"}">${pendingTaskCount ? `${pendingTaskCount} tasks pendientes` : "Tasks al día"}</span>` : `<span class="meeting-state-chip idle">Tasks al abrir</span>`}
        </div>
      </div>
      <div class="meeting-card-grid">
        <div class="meeting-main">
          <div class="stack-sm">
            <h2 class="meeting-title">${escapeHtml(meeting.title)}</h2>
            <p class="meeting-summary">${escapeHtml(meeting.summary || "Sin resumen todavía.")}</p>
          </div>
          <div class="meeting-meta-band">
            ${meetingMetaItem("Duración", meeting.duration_s ? `${Math.round(meeting.duration_s / 60)} min` : "--")}
            ${meetingMetaItem("Speakers", String(meeting.speakers?.length || 0))}
            ${meetingMetaItem("Decisiones", String(meeting.decisions?.length || 0))}
            ${meetingMetaItem("Tasks", loadedTaskCount !== null ? String(loadedTaskCount) : "Abrir")}
          </div>
          <div class="meeting-speakers-line"><span class="muted mono">Participantes</span><strong>${escapeHtml(speakersLabel)}</strong></div>
          ${decisionsPreview.length ? `<div class="meeting-preview-group"><div class="muted mono">Decisiones clave</div><div class="meeting-chip-row">${decisionsPreview.map((item) => `<span class="meeting-highlight-chip">${escapeHtml(item)}</span>`).join("")}</div></div>` : ""}
        </div>
        <div class="meeting-sidecard">
          <div class="muted mono">Próximo paso</div>
          <strong>${pendingTaskCount ? "Revisar tareas pendientes" : "Abrir resumen operativo"}</strong>
          <span class="muted">${pendingTaskCount ? "Esta reunión ya tiene acción pendiente y conviene entrar por el bloque de tasks." : "La tarjeta expandida te enseña resumen, decisiones y reporte sin salir de la lista."}</span>
          <div class="button-row"><button class="tiny-button meeting-expand-button" data-action="expand-meeting" data-meeting-id="${meeting.id}">${detailState.open ? "Ocultar detalle" : "Abrir briefing"}</button></div>
        </div>
      </div>
    </div>
    ${detailState.open ? meetingDetail(detailState, meeting.id) : ""}
  </article>`;
}

function meetingDetail(detailState, meetingId) {
  if (detailState.loading) return `<div class="meeting-detail">${loadingState("Cargando detalle...")}</div>`;
  const detail = detailState.data;
  if (!detail) return "";
  const pendingItems = detail.action_items?.filter((task) => task.status !== "done") || [];
  const doneItems = detail.action_items?.filter((task) => task.status === "done") || [];
  return `<div class="meeting-detail">
    <div class="details-grid">
      <div class="stack-md">
        <section class="detail-panel detail-summary-panel">
          <div class="detail-panel-head"><div class="muted mono">Resumen operativo</div><h3 class="detail-panel-title">Lo importante de esta reunión</h3></div>
          <p class="muted">${escapeHtml(detail.summary || "Sin resumen.")}</p>
        </section>
        <section class="detail-panel">
          <div class="detail-panel-head"><div class="muted mono">Decisiones</div><h3 class="detail-panel-title">Acordado durante la sesión</h3></div>
          ${detail.decisions?.length ? `<ul class="bullet-list list-reset">${detail.decisions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : `<p class="muted">Sin decisiones extraídas.</p>`}
        </section>
        <details class="detail-panel report-collapse">
          <summary class="report-collapse-summary"><span><span class="muted mono">Reporte</span><strong>Ver markdown completo</strong></span><span class="report-collapse-icon">Expandir</span></summary>
          <pre class="code-block">${escapeHtml(detail.report_md || "Sin reporte markdown.")}</pre>
        </details>
      </div>
      <div class="stack-md">
        <section class="detail-panel task-panel">
          <div class="detail-panel-head"><div class="muted mono">Action items</div><h3 class="detail-panel-title">Seguimiento operativo</h3></div>
          <div class="task-summary-strip">
            ${taskSummaryPill("Pendientes", String(pendingItems.length), "pending")}
            ${taskSummaryPill("Completadas", String(doneItems.length), "done")}
          </div>
          ${detail.action_items?.length ? `<div class="stack-sm">${detail.action_items.map((task) => renderActionTask(task, meetingId)).join("")}</div>` : `<p class="muted">No hay tasks para esta reunión.</p>`}
        </section>
      </div>
    </div>
  </div>`;
}

function meetingMetaItem(label, value) {
  return `<div class="meeting-meta-item"><span class="muted mono">${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function taskSummaryPill(label, value, tone) {
  return `<div class="task-summary-pill ${tone}"><span class="muted mono">${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function renderActionTask(task, meetingId) {
  const statusLabel = task.status === "done" ? "Completada" : "Pendiente";
  const ownerLabel = task.owner || "Sin owner";
  const dueLabel = task.due_date || "Sin fecha";
  return `<div class="task-card ${task.status === "done" ? "done" : "pending"}">
    <input class="task-toggle" type="checkbox" ${task.status === "done" ? "checked" : ""} data-action="toggle-task" data-task-id="${task.id}" data-meeting-id="${meetingId}">
    <div class="task-card-body">
      <strong>${escapeHtml(task.task)}</strong>
      <div class="task-chip-row">
        <span class="task-info-chip owner">${escapeHtml(ownerLabel)}</span>
        <span class="task-info-chip due">${escapeHtml(dueLabel)}</span>
        <span class="task-info-chip status ${task.status === "done" ? "done" : "pending"}">${escapeHtml(statusLabel)}</span>
      </div>
    </div>
  </div>`;
}

function renderSearchResults() {
  if (state.search.searching) return loadingState("Buscando contexto...");
  if (!state.search.searched) return emptyState("Todavía no se ha ejecutado ninguna búsqueda.", "Prueba con temas, decisiones o frases concretas.");
  if (!state.search.results.length) return emptyState("No hubo coincidencias para esta consulta.", "Prueba con una formulación más amplia o keywords distintas.");
  const meetingCount = new Set(state.search.results.map((result) => result.meeting_id)).size;
  return `<div class="search-results-stack">
    <div class="search-results-overview">
      ${statCard("Resultados", String(state.search.results.length), "Segmentos útiles devueltos")}
      ${statCard("Reuniones", String(meetingCount), "Origen de los resultados")}
      ${statCard("Consulta", state.search.query.trim().slice(0, 18) || "--", "Búsqueda actual")}
    </div>
    <div class="search-results-list">${state.search.results.map(renderSearchResultCard).join("")}</div>
  </div>`;
}

function dedupeSearchResults(results) {
  const seen = new Set();
  return results.filter((result) => {
    const key = [
      result.meeting_id || "",
      result.speaker || "",
      Math.round((result.start || 0) * 10) / 10,
      Math.round((result.end || 0) * 10) / 10,
      String(result.text || "").trim().toLowerCase(),
    ].join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function renderSearchResultCard(result) {
  const excerpt = truncateText(result.text || "", 240);
  return `<article class="search-result-card">
    <div class="search-result-header">
      <div class="stack-sm">
        <div class="section-kicker">Resultado semántico</div>
        <h3 class="search-result-title">${escapeHtml(result.meeting_title || "Reunión sin título")}</h3>
      </div>
      <div class="search-result-meta">
        <span class="search-meta-chip">${escapeHtml(result.date || "--")}</span>
        <span class="search-meta-chip">${escapeHtml(result.speaker || "Sin speaker")}</span>
        <span class="search-meta-chip">${Math.round(result.start || 0)}s - ${Math.round(result.end || 0)}s</span>
      </div>
    </div>
    <p class="search-result-excerpt">${escapeHtml(excerpt)}</p>
    <div class="button-row"><a href="/app/meetings" data-link class="secondary-button">Ir a reuniones</a></div>
  </article>`;
}

function truncateText(text, limit) {
  const normalized = String(text || "").trim();
  if (normalized.length <= limit) return normalized;
  return `${normalized.slice(0, limit).trimEnd()}...`;
}

function uploadJobPanel(job) {
  const currentStage = activeJobStage(job);
  const currentStageLabel = currentStage.label;
  const currentStageDetail = currentStage.detail;
  const progress = getDisplayJobProgress(job);
  const latestLog = latestJobLog(job.logs || []);
  const stageCaption = jobLiveCaption(job);
  if (job.status === "error") return `<div class="card"><h2 class="card-title">Pipeline con error</h2><p class="muted">${escapeHtml(job.error || "Error desconocido")}</p></div>`;
  if (job.status !== "done") {
    return `<div id="upload-job-panel" class="card stack-md">
      <div><h2 class="card-title">Pipeline activo</h2><p class="muted">Seguimiento paso a paso del procesamiento actual.</p></div>
      <div class="job-live-banner">
        <div class="job-live-indicator"><span></span><span></span><span></span></div>
        <div>
          <strong>${escapeHtml(stageCaption.title)}</strong>
          <div class="muted">${escapeHtml(stageCaption.detail)}</div>
        </div>
      </div>
      <div class="status-pill degraded">Proceso actual: ${escapeHtml(currentStageLabel)}</div>
      <div class="job-progress">
        <div class="job-progress-bar"><span style="width:${progress}%"></span></div>
        <div class="muted mono">${progress}% completado</div>
      </div>
      <div class="pipeline-detail stage-engine-detail">
        <div class="muted mono">Motor activo</div>
        <strong>${escapeHtml(currentStage.engine)}</strong>
        <span class="muted">${escapeHtml(currentStage.explainer)}</span>
      </div>
      <div class="pipeline-steps">${(job.steps || []).map(renderJobStep).join("")}</div>
      <div class="pipeline-detail">
        <div class="muted mono">Detalle activo</div>
        <strong>${escapeHtml(currentStageLabel)}</strong>
        <span class="muted">${escapeHtml(currentStageDetail)}</span>
      </div>
      ${latestLog ? `<div class="pipeline-detail live-log-detail"><div class="muted mono">Último evento</div><strong>${escapeHtml(latestLog.message)}</strong><span class="muted">${escapeHtml(formatLogTime(latestLog.timestamp))} · ${escapeHtml(latestLog.level)}</span></div>` : ""}
      ${renderJobLogs(job.logs || [])}
      <p class="muted mono">job ${escapeHtml(job.job_id)}</p>
    </div>`;
  }
  return `<div id="upload-job-panel" class="card stack-md"><h2 class="card-title">Resultado generado</h2><div class="job-progress"><div class="job-progress-bar"><span style="width:100%"></span></div><div class="muted mono">100% completado</div></div><div class="pipeline-steps">${(job.steps || []).map(renderJobStep).join("")}</div>${renderJobLogs(job.logs || [])}<p class="muted">${escapeHtml(job.summary || "Sin resumen devuelto.")}</p>${job.decisions?.length ? `<section><h3 class="card-title">Decisiones</h3><ul class="bullet-list list-reset">${job.decisions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>` : ""}${job.action_items?.length ? `<section><h3 class="card-title">Action items</h3><div class="stack-sm">${job.action_items.map((item) => `<div class="task-item"><div><strong>${escapeHtml(item.task)}</strong><div class="muted mono">${escapeHtml([item.owner, item.due_date, item.status].filter(Boolean).join(" · "))}</div></div></div>`).join("")}</div></section>` : ""}<div class="button-row"><button class="secondary-button" data-action="jump-to-meetings">Ver en reuniones</button></div></div>`;
}

function recentMeetings() {
  if (!state.meetings.length) return emptyState("Todavía no hay actividad reciente.", "La home empezará a poblarse cuando analices reuniones.");
  return `<div class="stack-sm">${state.meetings.slice(0, 4).map((meeting) => `<article class="panel stack-sm"><div class="section-kicker">${escapeHtml(meeting.date || "--")}</div><h3 class="card-title">${escapeHtml(meeting.title)}</h3><p class="muted">${escapeHtml(meeting.summary || "Sin resumen.")}</p><div class="button-row"><a href="/app/meetings" data-link class="secondary-button">Abrir reuniones</a></div></article>`).join("")}</div>`;
}

function serviceRow(label, service) {
  return `<div class="panel stack-sm"><div class="button-row"><strong>${escapeHtml(label)}</strong>${statusPill(service?.status || "offline", service?.status)}</div><div class="muted mono">${escapeHtml(service?.detail || "Sin detalle")}</div></div>`;
}

function commandCard(label, key, command) {
  return `<div class="panel stack-sm"><div class="button-row"><strong>${escapeHtml(label)}</strong><button class="tiny-button" type="button" data-action="copy-command" data-target="${key}">Copiar</button></div><pre class="code-block" id="${key}">${escapeHtml(command)}</pre></div>`;
}

function renderJobStep(step) {
  return `<article class="job-step ${escapeHtml(step.status)}">
    <div class="job-step-head">
      <span class="job-step-dot"></span>
      <strong>${escapeHtml(step.label)}</strong>
      <span class="job-step-status">${jobStepStatusLabel(step.status)}</span>
    </div>
    <p class="muted">${escapeHtml(step.detail || "")}</p>
  </article>`;
}

function renderJobLogs(logs) {
  if (!logs.length) return "";
  return `<div class="job-logs"><div class="muted mono">Logs del job</div><div class="job-log-list">${logs.map((log) => `<div class="job-log ${escapeHtml(log.level)}"><span class="job-log-time">${formatLogTime(log.timestamp)}</span><span class="job-log-level">${escapeHtml(log.level)}</span><span>${escapeHtml(log.message)}</span></div>`).join("")}</div></div>`;
}

function computeJobProgress(job) {
  if (job.status === "done") return 100;
  if (job.status === "error") return 100;

  const stageKey = job.steps?.find((step) => step.status === "active")?.step_key || job.stage || "queued";
  const stageProgress = progressWindowForStage(stageKey).start;

  if (!job.steps?.length) return stageProgress;

  const done = job.steps.filter((step) => step.status === "done").length;
  const active = job.steps.some((step) => step.status === "active") ? 0.5 : 0;
  const stepsProgress = Math.round(((done + active) / job.steps.length) * 100);

  return Math.max(stageProgress, stepsProgress);
}

function getDisplayJobProgress(job) {
  if (job.status === "done") return 100;
  if (job.status === "error") return Math.max(Math.floor(state.upload.progress.display || 0), 0);
  if (state.upload.progress.jobId !== job.job_id) return computeJobProgress(job);
  return Math.floor(state.upload.progress.display);
}

function formatLogTime(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return date.toLocaleTimeString("es-ES", { hour12: false });
}

function latestJobLog(logs) {
  return logs.length ? logs[logs.length - 1] : null;
}

function startUploadProgressLoop() {
  window.setInterval(() => {
    const job = state.upload.job;
    if (!job || job.status === "done" || job.status === "error") return;
    if (state.upload.progress.jobId !== job.job_id) return;
    const target = estimateSmoothProgress(job);
    const currentInt = Math.floor(state.upload.progress.display);
    const targetInt = Math.floor(target);
    if (targetInt <= currentInt) return;
    state.upload.progress.display = Math.min(target, currentInt + 1);
    render();
  }, 90);
}

function resetUploadProgress() {
  state.upload.progress = {
    jobId: null,
    stageKey: null,
    stageEnteredAt: 0,
    display: 0,
  };
}

function syncUploadProgressState(job) {
  if (!job?.job_id) {
    if (job?.status === "error") state.upload.progress.display = Math.max(state.upload.progress.display || 0, 0);
    return;
  }

  const stageKey = resolveJobStageKey(job);
  const now = Date.now();

  if (state.upload.progress.jobId !== job.job_id) {
    state.upload.progress = {
      jobId: job.job_id,
      stageKey,
      stageEnteredAt: now,
      display: job.status === "done" ? 100 : 0,
    };
  }

  if (job.status === "done") {
    state.upload.progress.display = 100;
    state.upload.progress.stageKey = "completed";
    return;
  }

  if (job.status === "error") return;

  if (state.upload.progress.stageKey !== stageKey) {
    state.upload.progress.stageKey = stageKey;
    state.upload.progress.stageEnteredAt = now;
  }

  const stageFloor = minimumVisibleProgress(stageKey);
  state.upload.progress.display = Math.max(Math.floor(state.upload.progress.display), stageFloor);
}

function estimateSmoothProgress(job) {
  const stageKey = resolveJobStageKey(job);
  const windowProgress = progressWindowForStage(stageKey);
  const elapsed = Math.max(0, Date.now() - state.upload.progress.stageEnteredAt);
  const ratio = Math.min(elapsed / windowProgress.durationMs, 1);
  const easedRatio = 1 - Math.pow(1 - ratio, 2);
  const smoothTarget = windowProgress.start + (windowProgress.end - windowProgress.start) * easedRatio;
  const computedTarget = computeJobProgress(job);
  return Math.min(99, Math.max(state.upload.progress.display, smoothTarget, computedTarget));
}

function resolveJobStageKey(job) {
  return job.steps?.find((step) => step.status === "active")?.step_key || job.stage || "queued";
}

function progressWindowForStage(stageKey) {
  if (stageKey === "completed") return { start: 100, end: 100, durationMs: 1 };

  const totalDuration = JOB_STAGE_TIMINGS.reduce((sum, stage) => sum + stage.durationMs, 0);
  let elapsed = 0;

  for (const stage of JOB_STAGE_TIMINGS) {
    const start = Math.round((elapsed / totalDuration) * 99);
    elapsed += stage.durationMs;
    const end = Math.round((elapsed / totalDuration) * 99);
    if (stage.key === stageKey) {
      return {
        start,
        end: Math.max(start + 1, end),
        durationMs: stage.durationMs,
      };
    }
  }

  return { start: 0, end: 6, durationMs: 2000 };
}

function minimumVisibleProgress(stageKey) {
  if (stageKey !== "transcribing") return progressWindowForStage(stageKey).start;
  const ageMs = Date.now() - state.upload.progress.stageEnteredAt;
  if (ageMs < 900) return 0;
  return progressWindowForStage(stageKey).start;
}

function scrollToUploadJobPanel() {
  requestAnimationFrame(() => {
    const panel = document.getElementById("upload-job-panel");
    if (!panel) return;
    const targetTop = Math.max(panel.getBoundingClientRect().top + window.scrollY - 96, 0);
    const startTop = window.scrollY;
    const distance = targetTop - startTop;
    const duration = 720;
    const startedAt = performance.now();

    if (Math.abs(distance) < 8) return;

    const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

    const step = (now) => {
      const progress = Math.min((now - startedAt) / duration, 1);
      const eased = easeInOutCubic(progress);
      window.scrollTo(0, startTop + distance * eased);
      if (progress < 1) window.requestAnimationFrame(step);
    };

    window.requestAnimationFrame(step);
  });
}

function activeJobStage(job) {
  const activeStep = job.steps?.find((step) => step.status === "active");
  return describeStage(activeStep?.step_key || job.stage, activeStep?.label, job.stage_detail || activeStep?.detail);
}

function describeStage(stageKey, fallbackLabel, fallbackDetail) {
  const modelName = state.system?.config?.ollama_model || "modelo local";
  const stageMap = {
    queued: {
      label: "Preparando pipeline",
      detail: "Audio recibido. Se está preparando Whisper para empezar la transcripción.",
      engine: "Inicialización local",
      explainer: "Arranque del job y preparación de dependencias del pipeline.",
    },
    transcribing: {
      label: "Whisper transcribiendo audio",
      detail: "Whisper está convirtiendo el audio en texto segmentado.",
      engine: "Whisper",
      explainer: "Lee el archivo, detecta segmentos y produce la transcripción base.",
    },
    summarizing: {
      label: "Ollama resumiendo la reunión",
      detail: `Ollama (${modelName}) está leyendo la transcripción para resumirla y detectar decisiones.`,
      engine: `Ollama · ${modelName}`,
      explainer: "Primera pasada LLM sobre el transcript para obtener resumen ejecutivo y decisiones.",
    },
    extracting: {
      label: "Ollama extrayendo action items",
      detail: `Ollama (${modelName}) está detectando tareas, responsables y fechas.`,
      engine: `Ollama · ${modelName}`,
      explainer: "Segunda pasada LLM para identificar tareas accionables de la reunión.",
    },
    reporting: {
      label: "Ollama montando el reporte",
      detail: `Ollama (${modelName}) está componiendo el markdown final de la reunión.`,
      engine: `Ollama · ${modelName}`,
      explainer: "Generación del reporte estructurado que verás al terminar.",
    },
    indexing: {
      label: "ChromaDB indexando contexto",
      detail: "ChromaDB está guardando segmentos para la búsqueda semántica.",
      engine: "ChromaDB",
      explainer: "El contenido queda preparado para búsquedas posteriores por contexto.",
    },
    saving: {
      label: "SQLite guardando reunión",
      detail: "SQLite está persistiendo la reunión y sus action items.",
      engine: "SQLite",
      explainer: "Último guardado estructurado antes de cerrar el pipeline.",
    },
    completed: {
      label: "Pipeline completado",
      detail: "Todos los pasos han terminado correctamente y el resultado ya está disponible.",
      engine: "Finalizado",
      explainer: "Transcripción, análisis e indexado completados.",
    },
  };
  return stageMap[stageKey] || {
    label: fallbackLabel || "Procesamiento en curso",
    detail: fallbackDetail || "El pipeline está avanzando.",
    engine: "Pipeline",
    explainer: "Procesamiento en curso.",
  };
}

function jobLiveCaption(job) {
  const latestLog = latestJobLog(job.logs || []);
  const currentStage = activeJobStage(job);
  if (latestLog) {
    return {
      title: currentStage.label,
      detail: latestLog.message,
    };
  }
  return {
    title: currentStage.label,
    detail: currentStage.detail,
  };
}

function jobStepStatusLabel(status) {
  if (status === "done") return "Completado";
  if (status === "active") return "En curso";
  if (status === "error") return "Error";
  return "Pendiente";
}

function signalCard(label, value, description) {
  return `<article class="signal-card"><div class="muted mono">${escapeHtml(label)}</div><strong>${escapeHtml(value)}</strong><span class="muted">${escapeHtml(description)}</span></article>`;
}

function runtimeInfoCard() {
  const mode = state.system?.config?.runtime_mode || "local";
  const isDocker = mode === "docker" || mode === "container";
  return `<div class="card stack-md">
    <div><div class="section-kicker">Información</div><h2 class="card-title">Modo de ejecución</h2></div>
    <div class="runtime-info-hero ${isDocker ? "docker" : "local"}">
      <div class="runtime-info-badge">${isDocker ? "Docker" : "Local"}</div>
      <strong>${isDocker ? "El servicio está corriendo en contenedor." : "El servicio está corriendo en entorno local."}</strong>
      <p class="muted">${isDocker ? "Buen encaje para levantar todo el stack de una vez, aislar dependencias y compartir setup reproducible." : "Ideal para iterar más rápido, depurar con menos fricción y ajustar componentes del pipeline uno a uno."}</p>
    </div>
    <div class="runtime-info-grid">
      <article class="signal-card">
        <div class="muted mono">Diferencias</div>
        <strong>${isDocker ? "Stack empaquetado" : "Control directo del host"}</strong>
        <span class="muted">${isDocker ? "Docker simplifica el arranque conjunto, pero añade una capa extra al depurar servicios y volúmenes." : "Local da trazabilidad inmediata sobre Python, Ollama y Chroma, pero depende más de que tu máquina esté bien preparada."}</span>
      </article>
      <article class="signal-card">
        <div class="muted mono">Recomendación</div>
        <strong>${isDocker ? "Úsalo para demos y setups estables" : "Úsalo para desarrollo y ajuste fino"}</strong>
        <span class="muted">${isDocker ? "Recomendado cuando quieres consistencia entre máquinas o enseñar el producto sin pelearte con dependencias." : "Recomendado cuando vas a iterar UI, backend o modelos y necesitas feedback rápido de cada cambio."}</span>
      </article>
    </div>
  </div>`;
}

function statusPill(label, status) {
  return `<span class="status-pill ${status || "degraded"}">${escapeHtml(label)}</span>`;
}

function statCard(title, value, description) {
  return `<div class="card"><div class="muted mono">${escapeHtml(title)}</div><div class="metric">${escapeHtml(value)}</div><div class="muted">${escapeHtml(description)}</div></div>`;
}

function diagnosticRow(label, value) {
  return `<div><div class="muted mono">${escapeHtml(label)}</div><div>${escapeHtml(value)}</div></div>`;
}

function loadingState(message) {
  return `<div class="loading-state">${escapeHtml(message)}</div>`;
}

function emptyState(title, subtitle) {
  return `<div class="empty-state"><strong>${escapeHtml(title)}</strong><div class="muted" style="margin-top:8px;">${escapeHtml(subtitle)}</div></div>`;
}

function formatFileSize(bytes) {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function showToast(message) {
  toastEl.textContent = message;
  toastEl.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toastEl.hidden = true; }, 2400);
}

function copyText(targetId) {
  const text = document.getElementById(targetId)?.textContent || "";
  navigator.clipboard.writeText(text).then(() => showToast("Comando copiado"));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}
