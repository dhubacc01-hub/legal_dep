const COUNTRY_STORAGE_KEY = "legal-department-country";

const INCOMING_CLAIM_CATEGORY = "Претензия";
const AUTHORITY_COURT = "court";
const AUTHORITY_OTHER = "other";
const RECEIVE_METHOD_OPTIONS = ["Почта", "Эл. почта", "Telegram", "Сайт суда", "Ватсап", "Нарочно"];
const RESPONSE_OPTIONS = ["Удовлетворить", "Возврат", "Отказ", "Возражение", "Не требует ответа", "На оплату", "На контроле", "Обработано", "Мировое"];

const TAB_COLUMNS = {
  claims: [
    { key: "action", label: "Действие", type: "action" },
    { key: "received_date", label: "Дата получения письма", type: "date" },
    { key: "receive_method", label: "Способ получения", type: "select" },
    { key: "company", label: "Компания", type: "select" },
    { key: "client_name", label: "ФИО клиента", type: "text" },
    { key: "authority_display", label: "Суд или другой орган", type: "text" },
    { key: "contract_number", label: "Номер договора", type: "text" },
    { key: "category", label: "Категория", type: "select" },
    { key: "responsible_person", label: "Ответственный за подготовку ответа", type: "text" },
    { key: "response_text", label: "Ответ", type: "select" },
    { key: "comment", label: "Комментарий", type: "text" },
    { key: "claim_response", label: "Ответ на претензию", type: "action" },
    { key: "delete", label: "Удалить", type: "action" },
  ],
  other: [
    { key: "action", label: "Действие", type: "action" },
    { key: "received_date", label: "Дата получения письма", type: "date" },
    { key: "receive_method", label: "Способ получения", type: "select" },
    { key: "company", label: "Компания", type: "select" },
    { key: "client_name", label: "ФИО клиента", type: "text" },
    { key: "authority_display", label: "Суд или другой орган", type: "text" },
    { key: "contract_number", label: "Номер договора", type: "text" },
    { key: "category", label: "Категория", type: "select" },
    { key: "delete", label: "Удалить", type: "action" },
  ],
};

const state = {
  referenceData: null,
  records: [],
  currentCountry: localStorage.getItem(COUNTRY_STORAGE_KEY) || "kz",
  currentTab: "claims",
  modalMode: "create",
  editingId: null,
  deleteId: null,
  claimResponseId: null,
  filters: {},
  datePicker: {
    activeInput: null,
    visibleMonth: null,
    view: "days",
  },
};

const countrySelect = document.getElementById("incoming-country-select");
const tabButtons = Array.from(document.querySelectorAll("[data-tab]"));
const activeFiltersSection = document.getElementById("incoming-active-filters");
const activeFiltersList = document.getElementById("incoming-active-filters-list");
const thead = document.getElementById("incoming-thead");
const tbody = document.getElementById("incoming-tbody");
const openModalButton = document.getElementById("open-incoming-modal");
const modalBackdrop = document.getElementById("incoming-modal-backdrop");
const modalElement = document.getElementById("incoming-modal");
const closeModalButton = document.getElementById("close-incoming-modal");
const cancelModalButton = document.getElementById("cancel-incoming-modal");
const form = document.getElementById("incoming-form");
const categorySelect = document.getElementById("incoming-category-select");
const categoryHint = document.getElementById("incoming-category-hint");
const detailsBlock = document.getElementById("incoming-details");
const companySelect = document.getElementById("incoming-company-select");
const receiveMethodSelect = document.getElementById("incoming-receive-method-select");
const responseSelect = document.getElementById("incoming-response-select");
const crmStatus = document.getElementById("incoming-crm-status");
const lookupButton = document.getElementById("incoming-lookup-contract-button");
const claimOnlyBlock = document.getElementById("incoming-claim-only");
const otherOnlyBlock = document.getElementById("incoming-other-only");
const authorityCourtCheckbox = document.getElementById("incoming-authority-court");
const authorityOtherCheckbox = document.getElementById("incoming-authority-other");
const authorityKindInput = form.elements.authority_kind;
const courtBlock = document.getElementById("incoming-court-block");
const otherAuthorityBlock = document.getElementById("incoming-other-authority-block");
const courtSearchInput = document.getElementById("incoming-court-search");
const courtSelect = document.getElementById("incoming-court-select");
const openCourtModalButton = document.getElementById("open-incoming-court-modal");
const courtModalBackdrop = document.getElementById("incoming-court-modal-backdrop");
const courtForm = document.getElementById("incoming-court-form");
const closeCourtModalButton = document.getElementById("close-incoming-court-modal");
const cancelCourtModalButton = document.getElementById("cancel-incoming-court-modal");
const deleteModalBackdrop = document.getElementById("incoming-delete-modal-backdrop");
const closeDeleteModalButton = document.getElementById("close-incoming-delete-modal");
const cancelDeleteModalButton = document.getElementById("cancel-incoming-delete-modal");
const confirmDeleteModalButton = document.getElementById("confirm-incoming-delete-button");
const claimResponseModalBackdrop = document.getElementById("incoming-claim-response-modal-backdrop");
const claimResponseForm = document.getElementById("incoming-claim-response-form");
const closeClaimResponseModalButton = document.getElementById("close-incoming-claim-response-modal");
const cancelClaimResponseModalButton = document.getElementById("cancel-incoming-claim-response-modal");
const claimResponseClientNameInput = document.getElementById("incoming-claim-response-client-name");
const claimResponseOutgoingNumberInput = document.getElementById("incoming-claim-response-outgoing-number");
const claimResponseBodyTextarea = document.getElementById("incoming-claim-response-body-text");
const datePickerPopover = document.getElementById("incoming-date-picker-popover");
const datePickerGrid = document.getElementById("incoming-date-picker-grid");
const datePickerWeekdays = document.getElementById("incoming-date-picker-weekdays");
const datePickerTitleMonth = datePickerPopover?.querySelector(".date-picker-title-month");
const datePickerTitleYear = datePickerPopover?.querySelector(".date-picker-title-year");

function getColumns() {
  return TAB_COLUMNS[state.currentTab];
}

function buildDefaultFilters() {
  return Object.fromEntries(
    getColumns()
      .filter((column) => !["action", "delete"].includes(column.key))
      .map((column) => {
        if (column.type === "date") {
          return [column.key, { from: "", to: "" }];
        }
        if (column.type === "select") {
          return [column.key, []];
        }
        return [column.key, ""];
      }),
  );
}

async function init() {
  countrySelect.value = state.currentCountry;
  state.filters = buildDefaultFilters();
  bindEvents();
  await reloadData();
}

function bindEvents() {
  countrySelect.addEventListener("change", async () => {
    state.currentCountry = countrySelect.value;
    localStorage.setItem(COUNTRY_STORAGE_KEY, state.currentCountry);
    state.filters = buildDefaultFilters();
    await reloadData();
  });

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      state.currentTab = button.dataset.tab;
      state.filters = buildDefaultFilters();
      renderTabs();
      renderTable();
    });
  });

  openModalButton.addEventListener("click", () => openModal("create"));
  closeModalButton.addEventListener("click", closeModal);
  cancelModalButton.addEventListener("click", closeModal);
  modalBackdrop.addEventListener("click", (event) => {
    if (event.target === modalBackdrop) {
      closeModal();
    }
  });

  categorySelect.addEventListener("change", handleCategoryChange);
  authorityCourtCheckbox.addEventListener("change", () => setAuthorityKind(AUTHORITY_COURT));
  authorityOtherCheckbox.addEventListener("change", () => setAuthorityKind(AUTHORITY_OTHER));
  courtSearchInput.addEventListener("input", renderCourtOptions);
  lookupButton.addEventListener("click", handleCrmLookup);
  form.addEventListener("submit", handleSubmit);
  openCourtModalButton.addEventListener("click", openCourtModal);
  closeCourtModalButton.addEventListener("click", closeCourtModal);
  cancelCourtModalButton.addEventListener("click", closeCourtModal);
  courtForm.addEventListener("submit", handleCourtSubmit);
  courtModalBackdrop.addEventListener("click", (event) => {
    if (event.target === courtModalBackdrop) {
      closeCourtModal();
    }
  });
  closeDeleteModalButton.addEventListener("click", closeDeleteModal);
  cancelDeleteModalButton.addEventListener("click", closeDeleteModal);
  confirmDeleteModalButton.addEventListener("click", handleDeleteConfirm);
  deleteModalBackdrop.addEventListener("click", (event) => {
    if (event.target === deleteModalBackdrop) {
      closeDeleteModal();
    }
  });
  closeClaimResponseModalButton.addEventListener("click", closeClaimResponseModal);
  cancelClaimResponseModalButton.addEventListener("click", closeClaimResponseModal);
  claimResponseForm.addEventListener("submit", handleClaimResponseSubmit);
  claimResponseBodyTextarea.addEventListener("input", () => autoResizeTextarea(claimResponseBodyTextarea));
  claimResponseModalBackdrop.addEventListener("click", (event) => {
    if (event.target === claimResponseModalBackdrop) {
      closeClaimResponseModal();
    }
  });

  document.addEventListener("click", handleDocumentClick);
  document.addEventListener("mousedown", handleDateMouseDown);
  document.addEventListener("focusin", handleDateFocusIn);
  document.addEventListener("focusout", handleDateBlur);
  document.addEventListener("input", handleDateInput);
  document.addEventListener("keydown", handleDateKeydown);
}

async function reloadData() {
  await Promise.all([loadReferenceData(), loadRecords()]);
  renderTabs();
  renderTable();
}

async function loadReferenceData() {
  const response = await fetch(`/api/incoming-correspondence/reference-data?country=${encodeURIComponent(state.currentCountry)}`, {
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new Error("Failed to load reference data");
  }
  state.referenceData = await response.json();
  renderCategoryOptions();
  renderReceiveMethodOptions();
  renderResponseOptions();
  renderCompanyOptions();
  renderCourtOptions();
}

async function loadRecords() {
  const response = await fetch(`/api/incoming-correspondence?country=${encodeURIComponent(state.currentCountry)}`, {
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new Error("Failed to load correspondence");
  }
  state.records = await response.json();
}

function renderTabs() {
  tabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === state.currentTab);
  });
}

function renderCategoryOptions() {
  const categories = state.referenceData?.categories ?? [];
  categorySelect.innerHTML = `
    <option value="">Выберите категорию</option>
    ${categories.map((item) => `<option value="${escapeHtmlAttribute(item)}">${escapeHtml(item)}</option>`).join("")}
  `;
}

function renderCompanyOptions() {
  const companies = state.referenceData?.companies ?? [];
  companySelect.innerHTML = `
    <option value="">Выберите компанию</option>
    ${companies.map((item) => `<option value="${escapeHtmlAttribute(item)}">${escapeHtml(item)}</option>`).join("")}
  `;
}

function renderReceiveMethodOptions() {
  receiveMethodSelect.innerHTML = `
    <option value="">Выберите способ получения</option>
    ${RECEIVE_METHOD_OPTIONS.map((item) => `<option value="${escapeHtmlAttribute(item)}">${escapeHtml(item)}</option>`).join("")}
  `;
}

function renderResponseOptions() {
  responseSelect.innerHTML = `
    <option value="">Выберите ответ</option>
    ${RESPONSE_OPTIONS.map((item) => `<option value="${escapeHtmlAttribute(item)}">${escapeHtml(item)}</option>`).join("")}
  `;
}

function renderCourtOptions() {
  const query = String(courtSearchInput.value || "").trim().toLowerCase();
  const courts = [...(state.referenceData?.courts ?? [])]
    .filter((court) => !query || court.toLowerCase().includes(query))
    .sort((left, right) => left.localeCompare(right, "ru"));

  courtSelect.innerHTML = courts
    .map((court) => `<option value="${escapeHtmlAttribute(court)}">${escapeHtml(court)}</option>`)
    .join("");
}

function handleCategoryChange() {
  const category = categorySelect.value;
  const hasCategory = Boolean(category);
  detailsBlock.classList.toggle("hidden", !hasCategory);
  categoryHint.classList.toggle("hidden", hasCategory);
  modalElement.classList.toggle("is-expanded", hasCategory);

  const isClaim = category === INCOMING_CLAIM_CATEGORY;
  claimOnlyBlock.classList.toggle("hidden", !isClaim);
  otherOnlyBlock.classList.toggle("hidden", isClaim);
  lookupButton.classList.toggle("hidden", !hasCategory);

  if (!hasCategory) {
    crmStatus.classList.add("hidden");
  }

  if (!isClaim) {
    crmStatus.classList.add("hidden");
    form.elements.responsible_person.value = form.elements.responsible_person.value || "";
    form.elements.response_text.value = form.elements.response_text.value || "";
  }
}

function setAuthorityKind(kind) {
  authorityKindInput.value = kind;
  authorityCourtCheckbox.checked = kind === AUTHORITY_COURT;
  authorityOtherCheckbox.checked = kind === AUTHORITY_OTHER;
  courtBlock.classList.toggle("hidden", kind !== AUTHORITY_COURT);
  otherAuthorityBlock.classList.toggle("hidden", kind !== AUTHORITY_OTHER);
}

function filteredRecords() {
  return state.records
    .filter((record) => (state.currentTab === "claims" ? record.category === INCOMING_CLAIM_CATEGORY : record.category !== INCOMING_CLAIM_CATEGORY))
    .filter((record) => matchesFilters(record));
}

function matchesFilters(record) {
  return getColumns()
    .filter((column) => !["action", "delete"].includes(column.key))
    .every((column) => {
      const filterValue = state.filters[column.key];
      if (column.type === "date") {
        if (!filterValue.from && !filterValue.to) {
          return true;
        }
        const isoValue = record[`${column.key}_iso`];
        if (!isoValue) {
          return false;
        }
        if (filterValue.from && isoValue < filterValue.from) {
          return false;
        }
        if (filterValue.to && isoValue > filterValue.to) {
          return false;
        }
        return true;
      }

      if (Array.isArray(filterValue)) {
        if (!filterValue.length) {
          return true;
        }
        const value = String(record[column.key] ?? "");
        return filterValue.includes(value);
      }

      if (!filterValue) {
        return true;
      }

      const value = String(record[column.key] ?? "").toLowerCase();
      return value.includes(String(filterValue).toLowerCase());
    });
}

function renderTable() {
  renderHead();
  renderActiveFilters();
  const rows = filteredRecords();
  if (!rows.length) {
    tbody.innerHTML = `
      <tr class="empty-row">
        <td colspan="${getColumns().length}">Записей не найдено.</td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = rows
    .map((record) => {
      const cells = getColumns().map((column) => renderCell(record, column)).join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");

  tbody.querySelectorAll("[data-action='edit']").forEach((button) => {
    button.addEventListener("click", () => openModal("edit", Number(button.dataset.id)));
  });

  tbody.querySelectorAll("[data-action='delete']").forEach((button) => {
    button.addEventListener("click", () => openDeleteModal(Number(button.dataset.id)));
  });
  tbody.querySelectorAll("[data-action='claim-response']").forEach((button) => {
    button.addEventListener("click", () => openClaimResponseModal(Number(button.dataset.id)));
  });
}

function renderHead() {
  const columns = getColumns();
  thead.innerHTML = `
    <tr class="filter-row">
      ${columns.map((column) => renderFilterCell(column)).join("")}
    </tr>
    <tr class="header-row">
      ${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}
    </tr>
  `;

  thead.querySelectorAll("[data-filter-key]").forEach((element) => {
    element.addEventListener("input", handleFilterChange);
    element.addEventListener("change", handleFilterChange);
  });
  thead.querySelectorAll(".filter-multi").forEach((details) => {
    details.addEventListener("toggle", handleFilterToggle);
  });
  thead.querySelectorAll("[data-filter-clear-group]").forEach((button) => {
    button.addEventListener("click", handleFilterClick);
  });
}

function renderFilterCell(column) {
  if (column.type === "action") {
    return `<th class="filter-header-cell filter-header-cell-empty"></th>`;
  }
  if (column.type === "date") {
    const value = state.filters[column.key];
    return `
      <th class="filter-header-cell">
        <div class="filter-range">
          <input class="filter-control date-input" data-date-input="true" data-filter-key="${column.key}" data-bound="from" type="text" placeholder="от" value="${escapeHtmlAttribute(formatDisplayDate(value.from) || "")}" autocomplete="off" />
          <input class="filter-control date-input" data-date-input="true" data-filter-key="${column.key}" data-bound="to" type="text" placeholder="до" value="${escapeHtmlAttribute(formatDisplayDate(value.to) || "")}" autocomplete="off" />
        </div>
      </th>
    `;
  }
  if (column.type === "select") {
    let options;
    if (column.key === "company") {
      options = state.referenceData?.companies ?? [];
    } else if (column.key === "receive_method") {
      options = RECEIVE_METHOD_OPTIONS;
    } else if (column.key === "response_text") {
      options = RESPONSE_OPTIONS;
    } else {
      options = state.referenceData?.categories ?? [];
    }
    return `
      <th class="filter-header-cell">
        <details class="filter-multi" data-filter-group="${column.key}">
          <summary class="filter-control filter-multi-summary" data-filter-summary="${column.key}">Все</summary>
          <div class="filter-multi-popover">
            <button class="ghost-button filter-mini-button" type="button" data-filter-clear-group="${column.key}">
              Очистить
            </button>
            <div class="filter-multi-options">
              ${options
                .map(
                  (item) => `
                    <label class="filter-option">
                      <input
                        type="checkbox"
                        data-filter-key="${column.key}"
                        value="${escapeHtmlAttribute(item)}"
                        ${state.filters[column.key].includes(item) ? "checked" : ""}
                      />
                      <span>${escapeHtml(item)}</span>
                    </label>
                  `,
                )
                .join("")}
            </div>
          </div>
        </details>
      </th>
    `;
  }
  return `
    <th class="filter-header-cell">
      <input class="filter-control" data-filter-key="${column.key}" type="text" value="${escapeHtmlAttribute(state.filters[column.key] || "")}" placeholder="${escapeHtmlAttribute(column.label)}" />
    </th>
  `;
}

function renderCell(record, column) {
  if (column.key === "action") {
    return `<td><button class="secondary-button compact-button" type="button" data-action="edit" data-id="${record.id}">Ред.</button></td>`;
  }
  if (column.key === "claim_response") {
    return `<td><button class="primary-button compact-button" type="button" data-action="claim-response" data-id="${record.id}">Ответ</button></td>`;
  }
  if (column.key === "delete") {
    return `<td><button class="danger-button compact-button" type="button" data-action="delete" data-id="${record.id}">Удалить</button></td>`;
  }
  const value = record[column.key];
  return `<td>${renderPlain(value)}</td>`;
}

function renderActiveFilters() {
  const chips = [];
  for (const [key, value] of Object.entries(state.filters)) {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        chips.push({ key, text: `${labelForColumn(key)}: ${item}`, item });
      });
      continue;
    }
    if (value && typeof value === "object") {
      if (value.from || value.to) {
        chips.push({
          key,
          text: `${labelForColumn(key)}: ${formatDisplayDate(value.from) || "—"} -> ${formatDisplayDate(value.to) || "—"}`,
        });
      }
      continue;
    }
    if (value) {
      chips.push({ key, text: `${labelForColumn(key)}: ${value}` });
    }
  }

  activeFiltersSection.classList.toggle("hidden", chips.length === 0);
  activeFiltersList.innerHTML = chips
    .map(
      (chip) => `
        <button class="active-filter-chip" type="button" data-remove-filter="${chip.key}" data-remove-filter-item="${escapeHtmlAttribute(chip.item || "")}">
          <span class="active-filter-chip-text">${escapeHtml(chip.text)}</span>
          <span class="active-filter-chip-close">&times;</span>
        </button>
      `,
    )
    .join("");

  activeFiltersList.querySelectorAll("[data-remove-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.removeFilter;
      if (Array.isArray(state.filters[key])) {
        state.filters[key] = state.filters[key].filter((item) => item !== button.dataset.removeFilterItem);
      } else if (state.filters[key] && typeof state.filters[key] === "object") {
        state.filters[key] = { from: "", to: "" };
      } else {
        state.filters[key] = "";
      }
      renderTable();
    });
  });
}

function labelForColumn(key) {
  return getColumns().find((column) => column.key === key)?.label || key;
}

function handleFilterChange(event) {
  const key = event.target.dataset.filterKey;
  if (!key) {
    return;
  }
  if (event.target.dataset.bound) {
    state.filters[key][event.target.dataset.bound] = parseDisplayDateValue(event.target.value) || "";
  } else if (event.target.type === "checkbox") {
    state.filters[key] = [...thead.querySelectorAll(`input[type="checkbox"][data-filter-key="${key}"]:checked`)].map(
      (checkbox) => checkbox.value,
    );
    updateFilterSummary(key);
  } else {
    state.filters[key] = event.target.value;
  }
  renderTable();
}

function handleFilterClick(event) {
  const clearButton = event.target.closest("[data-filter-clear-group]");
  if (!clearButton) {
    return;
  }
  const key = clearButton.dataset.filterClearGroup;
  state.filters[key] = [];
  thead.querySelectorAll(`input[type="checkbox"][data-filter-key="${key}"]`).forEach((checkbox) => {
    checkbox.checked = false;
  });
  updateFilterSummary(key);
  renderTable();
}

function handleFilterToggle(event) {
  const details = event.target;
  if (!(details instanceof HTMLDetailsElement) || !details.matches(".filter-multi")) {
    return;
  }
  if (details.open) {
    closeAllFilterDropdowns(details);
    details.closest("th")?.classList.add("filter-open");
  } else {
    details.closest("th")?.classList.remove("filter-open");
  }
}

function closeAllFilterDropdowns(exceptDetails = null) {
  thead.querySelectorAll(".filter-multi").forEach((details) => {
    if (details === exceptDetails) {
      return;
    }
    details.open = false;
    details.closest("th")?.classList.remove("filter-open");
  });
}

function updateFilterSummary(key) {
  const summary = thead.querySelector(`[data-filter-summary="${key}"]`);
  if (!summary) {
    return;
  }
  const selected = state.filters[key] ?? [];
  if (!selected.length) {
    summary.textContent = "Все";
    return;
  }
  if (selected.length === 1) {
    summary.textContent = selected[0];
    return;
  }
  summary.textContent = `Выбрано: ${selected.length}`;
}

function autoResizeTextarea(textarea) {
  if (!textarea) {
    return;
  }
  textarea.style.height = "auto";
  textarea.style.height = `${Math.max(textarea.scrollHeight, 240)}px`;
}

function openClaimResponseModal(recordId) {
  const record = state.records.find((item) => item.id === recordId);
  if (!record) {
    return;
  }
  state.claimResponseId = recordId;
  claimResponseForm.reset();
  claimResponseClientNameInput.value = record.client_name || "";
  claimResponseOutgoingNumberInput.value = "";
  claimResponseBodyTextarea.value = "";
  autoResizeTextarea(claimResponseBodyTextarea);
  claimResponseModalBackdrop.classList.remove("hidden");
  claimResponseBodyTextarea.focus();
}

function closeClaimResponseModal() {
  state.claimResponseId = null;
  claimResponseModalBackdrop.classList.add("hidden");
}

function openModal(mode, recordId = null) {
  state.modalMode = mode;
  state.editingId = recordId;
  form.reset();
  crmStatus.classList.add("hidden");
  modalElement.classList.remove("is-expanded");
  detailsBlock.classList.add("hidden");
  categoryHint.classList.remove("hidden");
  setAuthorityKind(AUTHORITY_COURT);
  renderCategoryOptions();
  renderCompanyOptions();
  renderCourtOptions();
  form.elements.record_id.value = recordId ?? "";
  form.elements.company.value = "";
  form.elements.authority_kind.value = AUTHORITY_COURT;
  form.elements.generic_comment.value = "";
  receiveMethodSelect.value = "";
  responseSelect.value = "";

  if (mode === "edit" && recordId !== null) {
    const record = state.records.find((item) => item.id === recordId);
    if (record) {
      categorySelect.value = record.category || "";
      handleCategoryChange();
      form.elements.received_date.value = formatDisplayDate(record.received_date_iso) || "";
      form.elements.receive_method.value = record.receive_method || "";
      form.elements.company.value = record.company || "";
      form.elements.client_name.value = record.client_name || "";
      form.elements.contract_number.value = record.contract_number || "";
      setAuthorityKind(record.authority_kind || AUTHORITY_COURT);
      form.elements.court.value = record.court || "";
      form.elements.other_authority.value = record.other_authority || "";
      form.elements.responsible_person.value = record.responsible_person || "";
      form.elements.response_text.value = record.response_text || "";
      form.elements.comment.value = record.comment || "";
      form.elements.generic_comment.value = record.comment || "";
    }
  }

  modalBackdrop.classList.remove("hidden");
}

function closeModal() {
  modalBackdrop.classList.add("hidden");
}

async function handleCrmLookup() {
  const contractNumber = String(form.elements.contract_number.value || "").trim();
  if (!contractNumber) {
    showCrmStatus("Сначала введите номер договора.", "error");
    return;
  }

  showCrmStatus("Ищу клиента в CRM...", "loading");
  try {
    const response = await fetch(
      `/api/crm/debtor-prefill?contract_number=${encodeURIComponent(contractNumber)}&country=${encodeURIComponent(state.currentCountry)}`,
      { credentials: "same-origin" },
    );
    if (!response.ok) {
      showCrmStatus("Не удалось получить данные из CRM.", "error");
      return;
    }
    const payload = await response.json();
    form.elements.client_name.value = payload.client_name || "";
    if (!form.elements.company.value && payload.company) {
      form.elements.company.value = payload.company;
    }
    showCrmStatus("ФИО клиента подтянуто из CRM.", "success");
  } catch (error) {
    console.error(error);
    showCrmStatus("Не удалось связаться с CRM.", "error");
  }
}

function showCrmStatus(message, kind) {
  crmStatus.textContent = message;
  crmStatus.classList.remove("hidden", "is-loading", "is-success", "is-error");
  if (kind === "loading") {
    crmStatus.classList.add("is-loading");
  } else if (kind === "success") {
    crmStatus.classList.add("is-success");
  } else {
    crmStatus.classList.add("is-error");
  }
}

function parseFileNameFromDisposition(value, fallbackName) {
  if (!value) {
    return fallbackName;
  }
  const utfMatch = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utfMatch) {
    return decodeURIComponent(utfMatch[1]);
  }
  const plainMatch = value.match(/filename="?([^"]+)"?/i);
  if (plainMatch) {
    return plainMatch[1];
  }
  return fallbackName;
}

function downloadBlob(blob, filename) {
  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(blobUrl);
}

async function handleClaimResponseSubmit(event) {
  event.preventDefault();
  if (state.claimResponseId === null) {
    return;
  }

  const payload = {
    outgoing_number: String(claimResponseOutgoingNumberInput.value || "").trim(),
    body_text: String(claimResponseBodyTextarea.value || "").trim(),
  };

  if (!payload.body_text) {
    alert("Заполните текст ответа на претензию.");
    claimResponseBodyTextarea.focus();
    return;
  }

  const response = await fetch(`/api/incoming-correspondence/${state.claimResponseId}/claim-response-pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    alert(errorPayload.detail || "Не удалось сформировать ответ на претензию.");
    return;
  }

  const blob = await response.blob();
  const filename = parseFileNameFromDisposition(
    response.headers.get("Content-Disposition"),
    `otvet_na_pretenziyu_${state.claimResponseId}.pdf`,
  );
  downloadBlob(blob, filename);
  closeClaimResponseModal();
}

async function handleSubmit(event) {
  event.preventDefault();
  const category = String(categorySelect.value || "");
  if (!category) {
    alert("Сначала выберите категорию.");
    categorySelect.focus();
    return;
  }

  const payload = {
    country: state.currentCountry,
    category,
    received_date: getDateInputIsoValue(form.elements.received_date),
    receive_method: String(form.elements.receive_method.value || "").trim(),
    company: String(form.elements.company.value || "").trim(),
    client_name: String(form.elements.client_name.value || "").trim(),
    authority_kind: authorityKindInput.value,
    court: String(form.elements.court.value || "").trim(),
    other_authority: String(form.elements.other_authority.value || "").trim(),
    contract_number: String(form.elements.contract_number.value || "").trim(),
    responsible_person: category === INCOMING_CLAIM_CATEGORY ? String(form.elements.responsible_person.value || "").trim() : "",
    response_text: category === INCOMING_CLAIM_CATEGORY ? String(form.elements.response_text.value || "").trim() : "",
    response_date: null,
    sent_date: null,
    comment:
      category === INCOMING_CLAIM_CATEGORY
        ? String(form.elements.comment.value || "").trim()
        : String(form.elements.generic_comment.value || "").trim(),
  };

  if (!payload.received_date) {
    alert("Заполните дату получения письма.");
    form.elements.received_date.focus();
    return;
  }

  const isEdit = state.modalMode === "edit" && state.editingId !== null;
  const url = isEdit ? `/api/incoming-correspondence/${state.editingId}` : "/api/incoming-correspondence";
  const method = isEdit ? "PATCH" : "POST";

  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    alert(errorPayload.detail || "Не удалось сохранить запись.");
    return;
  }

  closeModal();
  await loadRecords();
  renderTable();
}

async function deleteRecord(id) {
  const response = await fetch(`/api/incoming-correspondence/${id}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  if (!response.ok) {
    alert("Не удалось удалить запись.");
    return;
  }
  await loadRecords();
  renderTable();
}

function openDeleteModal(id) {
  state.deleteId = id;
  deleteModalBackdrop.classList.remove("hidden");
}

function closeDeleteModal() {
  state.deleteId = null;
  deleteModalBackdrop.classList.add("hidden");
}

async function handleDeleteConfirm() {
  if (state.deleteId === null) {
    return;
  }
  const id = state.deleteId;
  closeDeleteModal();
  await deleteRecord(id);
}

function openCourtModal() {
  courtForm.reset();
  courtModalBackdrop.classList.remove("hidden");
}

function closeCourtModal() {
  courtModalBackdrop.classList.add("hidden");
}

async function handleCourtSubmit(event) {
  event.preventDefault();
  const payload = {
    country: state.currentCountry,
    name: String(courtForm.elements.name.value || "").trim(),
    city: String(courtForm.elements.city.value || "").trim(),
    region: String(courtForm.elements.region.value || "").trim(),
  };
  const response = await fetch("/api/courts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    alert(errorPayload.detail || "Не удалось сохранить новый суд.");
    return;
  }
  closeCourtModal();
  await loadReferenceData();
  renderTable();
  courtSearchInput.value = payload.name;
  renderCourtOptions();
  if (courtSelect.options.length > 0) {
    courtSelect.selectedIndex = 0;
  }
}

function renderPlain(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return escapeHtml(String(value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeHtmlAttribute(value) {
  return escapeHtml(value);
}

function handleDocumentClick(event) {
  if (event.target.closest("#incoming-date-picker-popover")) {
    return;
  }

  const input = event.target.closest(".date-input");
  if (input && !input.disabled) {
    openDatePicker(input);
    return;
  }

  closeDatePicker();
}

function handleDateMouseDown(event) {
  if (processDatePickerTarget(event.target)) {
    event.preventDefault();
  }
}

function processDatePickerTarget(target) {
  const navButton = target.closest("[data-date-nav]");
  if (navButton) {
    if (navButton.dataset.dateNav === "month-select") {
      state.datePicker.view = "months";
      renderDatePicker();
      return true;
    }
    if (navButton.dataset.dateNav === "year-select") {
      state.datePicker.view = "years";
      renderDatePicker();
      return true;
    }
    shiftDatePickerMonth(Number(navButton.dataset.dateNav));
    return true;
  }

  const actionButton = target.closest("[data-date-action]");
  if (actionButton) {
    handleDatePickerAction(actionButton.dataset.dateAction);
    return true;
  }

  const dayButton = target.closest("[data-date-value]");
  if (dayButton) {
    applyDatePickerValue(dayButton.dataset.dateValue);
    return true;
  }

  const monthButton = target.closest("[data-date-month]");
  if (monthButton) {
    selectDatePickerMonth(Number(monthButton.dataset.dateMonth));
    return true;
  }

  const yearButton = target.closest("[data-date-year]");
  if (yearButton) {
    selectDatePickerYear(Number(yearButton.dataset.dateYear));
    return true;
  }

  return false;
}

function handleDateFocusIn(event) {
  const input = event.target.closest(".date-input");
  if (!input || input.disabled) {
    return;
  }
  openDatePicker(input);
}

function handleDateBlur(event) {
  const input = event.target.closest(".date-input");
  if (!input) {
    return;
  }
  normalizeDateInput(input);
}

function handleDateInput(event) {
  const input = event.target.closest(".date-input");
  if (!input || input.disabled) {
    return;
  }
  applyDateInputMask(input);
}

function handleDateKeydown(event) {
  const activeInput = event.target.closest(".date-input");
  if (event.key === "Escape") {
    closeDatePicker();
    return;
  }
  if (!activeInput) {
    return;
  }
  if (event.key === "Enter") {
    normalizeDateInput(activeInput);
  }
}

function openDatePicker(input) {
  if (!datePickerPopover || input.disabled) {
    return;
  }
  state.datePicker.activeInput = input;
  state.datePicker.visibleMonth = getInitialVisibleMonth(input.value);
  state.datePicker.view = "days";
  positionDatePicker(input);
  renderDatePicker();
  datePickerPopover.classList.remove("hidden");
}

function closeDatePicker() {
  state.datePicker.activeInput = null;
  state.datePicker.visibleMonth = null;
  state.datePicker.view = "days";
  datePickerPopover?.classList.add("hidden");
}

function positionDatePicker(input) {
  const inputRect = input.getBoundingClientRect();
  const scrollY = window.scrollY || document.documentElement.scrollTop;
  const scrollX = window.scrollX || document.documentElement.scrollLeft;
  datePickerPopover.style.top = `${inputRect.bottom + scrollY + 8}px`;
  datePickerPopover.style.left = `${inputRect.left + scrollX}px`;
}

function renderDatePicker() {
  if (!state.datePicker.visibleMonth || !datePickerGrid || !datePickerTitleMonth || !datePickerTitleYear) {
    return;
  }
  const baseDate = new Date(`${state.datePicker.visibleMonth}-01T12:00:00`);
  datePickerTitleMonth.textContent = formatMonthLabel(baseDate);
  datePickerTitleYear.textContent = String(baseDate.getFullYear());
  datePickerGrid.dataset.view = state.datePicker.view;
  if (datePickerWeekdays) {
    datePickerWeekdays.hidden = state.datePicker.view !== "days";
  }
  if (state.datePicker.view === "months") {
    renderDatePickerMonths(baseDate);
    return;
  }
  if (state.datePicker.view === "years") {
    renderDatePickerYears(baseDate);
    return;
  }

  const selectedIso = parseDisplayDateValue(state.datePicker.activeInput?.value ?? "");
  const todayIso = toIsoDateFromDate(new Date());
  const gridDays = buildCalendarDays(baseDate);
  datePickerGrid.innerHTML = gridDays
    .map((item) => {
      const classes = ["date-picker-day"];
      if (!item.currentMonth) {
        classes.push("is-outside");
      }
      if (item.iso === selectedIso) {
        classes.push("is-selected");
      }
      if (item.iso === todayIso) {
        classes.push("is-today");
      }
      return `<button class="${classes.join(" ")}" type="button" data-date-value="${item.iso}">${item.day}</button>`;
    })
    .join("");
}

function shiftDatePickerMonth(offset) {
  if (!state.datePicker.visibleMonth) {
    return;
  }
  const baseDate = new Date(`${state.datePicker.visibleMonth}-01T12:00:00`);
  if (state.datePicker.view === "years") {
    baseDate.setFullYear(baseDate.getFullYear() + offset * 12);
  } else if (state.datePicker.view === "months") {
    baseDate.setFullYear(baseDate.getFullYear() + offset);
  } else {
    baseDate.setMonth(baseDate.getMonth() + offset);
  }
  state.datePicker.visibleMonth = `${baseDate.getFullYear()}-${String(baseDate.getMonth() + 1).padStart(2, "0")}`;
  renderDatePicker();
}

function handleDatePickerAction(action) {
  if (!state.datePicker.activeInput) {
    return;
  }
  if (action === "today") {
    applyDatePickerValue(toIsoDateFromDate(new Date()));
    return;
  }
  if (action === "clear") {
    state.datePicker.activeInput.value = "";
    if (state.datePicker.activeInput.dataset.filterKey) {
      handleFilterChange({ target: state.datePicker.activeInput });
    }
    closeDatePicker();
  }
}

function applyDatePickerValue(isoValue) {
  const input = state.datePicker.activeInput;
  if (!input) {
    return;
  }
  input.value = formatDisplayDate(isoValue) ?? "";
  if (input.dataset.filterKey) {
    handleFilterChange({ target: input });
  }
  closeDatePicker();
}

function applyDateInputMask(input) {
  const rawValue = String(input.value ?? "");
  const digits = rawValue.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) {
    input.value = digits;
  } else if (digits.length <= 4) {
    input.value = `${digits.slice(0, 2)}.${digits.slice(2)}`;
  } else {
    input.value = `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`;
  }
}

function normalizeDateInput(input) {
  applyDateInputMask(input);
  const isoValue = parseDisplayDateValue(input.value);
  input.value = formatDisplayDate(isoValue) ?? input.value.trim();
}

function getDateInputIsoValue(input) {
  return parseDisplayDateValue(input.value);
}

function getInitialVisibleMonth(value) {
  const isoValue = parseDisplayDateValue(value);
  if (isoValue) {
    return isoValue.slice(0, 7);
  }
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
}

function formatDisplayDate(isoValue) {
  if (!isoValue) {
    return null;
  }
  const match = String(isoValue).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }
  const [, year, month, day] = match;
  return `${day}.${month}.${year}`;
}

function parseDisplayDateValue(value) {
  const text = String(value ?? "").trim();
  if (!text) {
    return null;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return text;
  }
  if (/^\d{8}$/.test(text)) {
    return parseDisplayDateValue(`${text.slice(0, 2)}.${text.slice(2, 4)}.${text.slice(4)}`);
  }
  const normalized = text.replaceAll("/", ".").replaceAll("-", ".");
  const match = normalized.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (!match) {
    return null;
  }
  const [, dayRaw, monthRaw, yearRaw] = match;
  const day = Number(dayRaw);
  const month = Number(monthRaw);
  const year = Number(yearRaw);
  const dateValue = new Date(year, month - 1, day, 12);
  if (dateValue.getFullYear() !== year || dateValue.getMonth() !== month - 1 || dateValue.getDate() !== day) {
    return null;
  }
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function buildCalendarDays(baseDate) {
  const year = baseDate.getFullYear();
  const month = baseDate.getMonth();
  const firstOfMonth = new Date(year, month, 1, 12);
  const startOffset = (firstOfMonth.getDay() + 6) % 7;
  const gridStart = new Date(year, month, 1 - startOffset, 12);
  return Array.from({ length: 42 }, (_, index) => {
    const itemDate = new Date(gridStart);
    itemDate.setDate(gridStart.getDate() + index);
    return {
      day: itemDate.getDate(),
      iso: toIsoDateFromDate(itemDate),
      currentMonth: itemDate.getMonth() === month,
    };
  });
}

function renderDatePickerMonths(baseDate) {
  const selectedMonth = baseDate.getMonth();
  const monthNames = Array.from({ length: 12 }, (_, monthIndex) =>
    new Intl.DateTimeFormat("ru-RU", { month: "short" }).format(new Date(2026, monthIndex, 1, 12)),
  );
  datePickerGrid.innerHTML = monthNames
    .map((monthName, monthIndex) => {
      const classes = ["date-picker-day", "date-picker-choice"];
      if (monthIndex === selectedMonth) {
        classes.push("is-selected");
      }
      return `<button class="${classes.join(" ")}" type="button" data-date-month="${monthIndex}">${capitalize(monthName)}</button>`;
    })
    .join("");
}

function renderDatePickerYears(baseDate) {
  const currentYear = baseDate.getFullYear();
  const startYear = currentYear - 5;
  datePickerGrid.innerHTML = Array.from({ length: 12 }, (_, index) => startYear + index)
    .map((year) => {
      const classes = ["date-picker-day", "date-picker-choice"];
      if (year === currentYear) {
        classes.push("is-selected");
      }
      return `<button class="${classes.join(" ")}" type="button" data-date-year="${year}">${year}</button>`;
    })
    .join("");
}

function selectDatePickerMonth(monthIndex) {
  const baseDate = new Date(`${state.datePicker.visibleMonth}-01T12:00:00`);
  baseDate.setMonth(monthIndex);
  state.datePicker.visibleMonth = `${baseDate.getFullYear()}-${String(baseDate.getMonth() + 1).padStart(2, "0")}`;
  state.datePicker.view = "days";
  renderDatePicker();
}

function selectDatePickerYear(year) {
  const baseDate = new Date(`${state.datePicker.visibleMonth}-01T12:00:00`);
  baseDate.setFullYear(year);
  state.datePicker.visibleMonth = `${baseDate.getFullYear()}-${String(baseDate.getMonth() + 1).padStart(2, "0")}`;
  state.datePicker.view = "days";
  renderDatePicker();
}

function formatMonthLabel(date) {
  return capitalize(new Intl.DateTimeFormat("ru-RU", { month: "long" }).format(date));
}

function capitalize(value) {
  const text = String(value ?? "");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function toIsoDateFromDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

init().catch((error) => {
  console.error(error);
  tbody.innerHTML = `<tr class="empty-row"><td colspan="14">Не удалось загрузить страницу.</td></tr>`;
});
