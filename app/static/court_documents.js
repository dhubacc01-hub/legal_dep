window.CourtDocuments = (() => {
  let activeId = null;
  let loadVersion = 0;
  let uploading = false;
  let returnFocus = null;
  let previousOverflow = "";
  let previousInert = false;
  let shell, backdrop, panel, modal, uploadForm, list, status, uploadStatus, retry;
  const $ = id => document.getElementById(id);

  function render(documents) {
    list.innerHTML = documents.map(doc => {
      const date = new Date(doc.created_at);
      const when = Number.isNaN(date.getTime()) ? "" : date.toLocaleString("ru-RU");
      return `<a class="court-document-card" href="${escapeHtmlAttribute(doc.download_url)}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHtmlAttribute('Открыть документ: ' + doc.title)}">
        <div class="court-document-meta"><time>${escapeHtml(when)}</time><span>${doc.source === "correspondence" ? "Из корреспонденции" : "Загружен"}</span></div>
        <h4>${escapeHtml(doc.title)}</h4>
        ${doc.description ? `<p class="court-document-description">${escapeHtml(doc.description)}</p>` : ""}
        <p class="court-document-filename">${escapeHtml(doc.filename)} · ${Math.max(1, Math.ceil(doc.size_bytes / 1024))} КБ</p>
      </a>`;
    }).join("");
  }

  async function load() {
    const id = activeId;
    const version = ++loadVersion;
    retry.classList.add("hidden");
    status.textContent = "Загружаем документы…";
    list.innerHTML = "";
    try {
      const response = await fetch(`/api/court-cases/${id}/documents`);
      if (!response.ok) throw new Error("Не удалось загрузить документы.");
      const documents = await response.json();
      if (version !== loadVersion || activeId !== id) return;
      status.textContent = documents.length ? "Свежие документы сверху" : "Документов пока нет.";
      render(documents);
    } catch (error) {
      if (version !== loadVersion || activeId !== id) return;
      status.textContent = error.message || "Не удалось загрузить документы.";
      retry.classList.remove("hidden");
    }
  }

  function open(id, trigger) {
    const record = state.records.find(item => item.id === id);
    if (!record) return;
    closeDatePicker();
    activeId = id;
    returnFocus = trigger;
    previousOverflow = document.body.style.overflow;
    previousInert = shell.inert;
    shell.inert = true;
    document.body.style.overflow = "hidden";
    $("court-documents-title").textContent = record.client_name;
    $("court-documents-contract").textContent = `${record.contract_number} · ${record.company}`;
    backdrop.classList.remove("hidden");
    backdrop.inert = false;
    $("close-court-documents").focus();
    load();
  }

  function closeUpload() {
    if (uploading) return;
    modal.classList.add("hidden");
    backdrop.inert = false;
    $("add-court-document").focus();
  }

  function close() {
    if (uploading || activeId === null || !modal.classList.contains("hidden")) return;
    ++loadVersion;
    activeId = null;
    modal.classList.add("hidden");
    backdrop.classList.add("hidden");
    backdrop.inert = false;
    shell.inert = previousInert;
    document.body.style.overflow = previousOverflow;
    if (returnFocus?.isConnected) returnFocus.focus();
  }

  async function upload(event) {
    event.preventDefault();
    if (uploading || activeId === null) return;
    const file = uploadForm.elements.file.files[0];
    if (!file || !file.size || file.size > 20 * 1024 * 1024) {
      uploadStatus.textContent = "Выберите непустой файл размером до 20 МБ.";
      return;
    }
    if (!uploadForm.elements.title.value.trim()) {
      uploadStatus.textContent = "Укажите название документа.";
      return;
    }
    const id = activeId;
    uploading = true;
    for (const button of modal.querySelectorAll("button")) button.disabled = true;
    uploadStatus.textContent = "Загружаем документ…";
    let saved = false;
    try {
      const response = await fetch(`/api/court-cases/${id}/documents`, { method: "POST", body: new FormData(uploadForm) });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(typeof error.detail === "string" ? error.detail : "Не удалось загрузить документ.");
      }
      saved = true;
    } catch (error) { uploadStatus.textContent = error.message || "Ошибка соединения."; }
    finally {
      uploading = false;
      for (const button of modal.querySelectorAll("button")) button.disabled = false;
    }
    if (saved && activeId === id) { closeUpload(); await load(); }
  }

  function bind() {
    shell = document.querySelector(".app-shell");
    backdrop = $("court-documents-backdrop"); panel = $("court-documents-panel");
    modal = $("court-document-modal-backdrop"); uploadForm = $("court-document-form");
    list = $("court-documents-list"); status = $("court-documents-status");
    uploadStatus = $("court-document-upload-status"); retry = $("retry-court-documents");
    tbody.addEventListener("click", event => {
      const button = event.target.closest("[data-case-documents]");
      if (button) open(Number(button.dataset.caseDocuments), button);
    });
    $("close-court-documents").addEventListener("click", close);
    backdrop.addEventListener("click", event => { if (event.target === backdrop) close(); });
    for (const id of ["close-court-document-modal", "cancel-court-document-modal"]) $(id).addEventListener("click", closeUpload);
    modal.addEventListener("click", event => { if (event.target === modal) closeUpload(); });
    retry.addEventListener("click", load);
    $("add-court-document").addEventListener("click", () => {
      uploadForm.reset(); uploadStatus.textContent = "";
      modal.classList.remove("hidden"); backdrop.inert = true;
      uploadForm.elements.title.focus();
    });
    uploadForm.addEventListener("submit", upload);
    document.addEventListener("keydown", event => {
      if (activeId === null) return;
      if (event.key === "Escape") {
        event.preventDefault();
        if (!modal.classList.contains("hidden")) closeUpload(); else close();
      }
      if (event.key === "Tab") {
        const root = modal.classList.contains("hidden") ? panel : modal;
        const controls = [...root.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled)')]
          .filter(node => node.getClientRects().length);
        if (!controls.length) { event.preventDefault(); return; }
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
  }
  return { bind };
})();
