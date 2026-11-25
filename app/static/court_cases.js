// Court cases reuse correspondence's table, modal, court catalogue and date picker.
window.CourtCases = (() => {
  const yesNo = ["Да", "Нет"];
  const decisions = ["Удовлетворить", "Частично", "По соглашению сторон", "Не удовлетворен"];
  const dates = ["notification_date", "contract_date", "claim_date", "hearing_date"];
  const textFields = ["client_name", "contract_number", "company", "city", "court", "comment", "case_number", "case_court"];
  const booleanFields = ["claim_sent", "lawsuit_exists"];
  const definitions = [
    ["action", "Действие", "action"], ["entry_date", "Дата внесения", "date"],
    ["notification_date", "Дата уведомления", "date"], ["contract_date", "Дата контракта", "date"],
    ["client_name", "ФИО клиента"], ["contract_number", "Номер договора"],
    ["company", "Компания", "select"], ["city", "Город"], ["court", "Суд"],
    ["claim_sent", "Была претензия?", "select", yesNo], ["claim_date", "Дата претензии", "date"],
    ["response_exists", "Ответ на претензию", "select", yesNo], ["response_file", "Файл", "action"],
    ["lawsuit_exists", "Есть иск", "select", yesNo], ["hearing_date", "Дата заседания", "date"],
    ["decision", "Решение", "select", decisions], ["decision_payout", "Сумма выплаты по решению", "number"],
    ["comment", "Комментарий"], ["case_number", "Номер дела"], ["case_court", "Суд по делу"],
    ["delete", "Удалить", "action"],
  ];
  const columns = () => definitions.map(([key, label, type = "text", options]) => ({
    key, label: key === "decision_payout" ? `${label} (${state.currentCountry === "uz" ? "сум" : "тг"})` : label, type, options,
  }));

  function dependencies() {
    form.elements.claim_date.disabled = form.elements.claim_sent.value !== "true";
    form.elements.hearing_date.disabled = form.elements.lawsuit_exists.value !== "true";
    form.elements.decision_payout.disabled = !form.elements.decision.value;
    for (const key of ["claim_date", "hearing_date", "decision_payout"]) {
      if (form.elements[key].disabled) form.elements[key].value = "";
    }
  }

  function bind() {
    window.CourtDocuments.bind();
    for (const field of ["category", "received_date", "receive_method"]) {
      const input = form.elements[field];
      input.closest("label").classList.add("hidden");
      input.disabled = true;
    }
    form.querySelector(".authority-toggle-group").classList.add("hidden");
    claimOnlyBlock.classList.add("hidden");
    claimOnlyBlock.querySelectorAll("input, select, textarea").forEach(input => { input.disabled = true; });
    categoryHint.classList.add("hidden");
    lookupButton.classList.remove("hidden");
    for (const node of [
      form.elements.contract_number.closest("label"), form.elements.client_name.closest("label"),
      companySelect.closest("label"), form.elements.city.closest("label"),
      form.elements.notification_date.closest("label"), form.elements.contract_date.closest("label"), courtBlock,
      ...["claim_sent", "claim_date", "lawsuit_exists", "hearing_date", "decision", "decision_payout", "case_number", "case_court"]
        .map(key => form.elements[key].closest("label")), otherOnlyBlock,
    ]) detailsBlock.appendChild(node);
    for (const key of [...booleanFields, "decision"]) form.elements[key].addEventListener("change", dependencies);
    tbody.addEventListener("change", async event => {
      const input = event.target;
      const key = input.dataset.caseField;
      if (!key) return;
      const record = state.records.find(item => item.id === Number(input.dataset.id));
      if (!record) return;
      let value = input.value;
      if (booleanFields.includes(key)) value = value === "true";
      if (dates.includes(key)) {
        value = parseDisplayDateValue(value);
        if (input.value.trim() && !value) { alert("Укажите корректную дату."); return; }
      }
      if (key === "decision_payout") value = Number(value || 0);
      const payload = { [key]: value };
      input.disabled = true;
      if (await save(payload, record.id)) { await loadRecords(); renderTable(); }
      else { input.disabled = false; }
    });
  }

  function open(mode, id) {
    state.modalMode = mode;
    state.editingId = id;
    form.reset();
    crmStatus.classList.add("hidden");
    renderCompanyOptions();
    courtSearchInput.value = "";
    renderCourtOptions();
    setAuthorityKind(AUTHORITY_COURT);
    const record = state.records.find(item => item.id === id);
    for (const key of textFields) {
      const input = form.elements[key === "comment" ? "generic_comment" : key];
      if (record && record[key] && input.tagName === "SELECT" && ![...input.options].some(o => o.value === record[key])) {
        input.add(new Option(record[key], record[key]));
      }
      input.value = record?.[key] ?? "";
    }
    for (const key of dates) form.elements[key].value = formatDisplayDate(record?.[key + "_iso"]) || "";
    for (const key of booleanFields) form.elements[key].value = String(Boolean(record?.[key]));
    form.elements.decision.value = record?.decision || "";
    form.elements.decision_payout.value = record?.decision_payout ?? 0;
    document.getElementById("court-case-courts").innerHTML = (state.referenceData?.courts ?? [])
      .map(court => `<option value="${escapeHtmlAttribute(court)}"></option>`).join("");
    detailsBlock.classList.remove("hidden");
    otherOnlyBlock.classList.remove("hidden");
    modalElement.classList.add("is-expanded");
    dependencies();
    modalBackdrop.classList.remove("hidden");
  }

  function prefill(data) {
    form.elements.city.value = data.city || "";
    const iso = String(data.contract_date || "").slice(0, 10);
    if (iso) form.elements.contract_date.value = formatDisplayDate(iso) || "";
    if (data.company) {
      if (![...companySelect.options].some(o => o.value === data.company)) companySelect.add(new Option(data.company, data.company));
      companySelect.value = data.company;
    }
  }

  async function save(payload, id) {
    try {
      const response = await fetch(id ? `${RECORDS_ENDPOINT}/${id}` : RECORDS_ENDPOINT, {
        method: id ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        const message = Array.isArray(error.detail) ? error.detail.map(item => `${item.loc.at(-1)}: ${item.msg}`).join("\n") : error.detail;
        throw new Error(message || "Не удалось сохранить запись.");
      }
      return true;
    } catch (error) { alert(error.message || "Ошибка соединения."); return false; }
  }

  async function saveForm() {
    const payload = { country: state.currentCountry };
    for (const key of textFields) payload[key] = form.elements[key === "comment" ? "generic_comment" : key].value.trim();
    for (const key of dates) {
      const input = form.elements[key];
      const iso = getDateInputIsoValue(input);
      if (!input.disabled && input.value.trim() && !iso) { alert("Укажите корректную дату."); input.focus(); return; }
      payload[key] = input.disabled ? null : iso;
    }
    for (const key of booleanFields) payload[key] = form.elements[key].value === "true";
    payload.decision = form.elements.decision.value || null;
    payload.decision_payout = Number(form.elements.decision_payout.value || 0);
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      if (await save(payload, state.editingId)) { closeModal(); await loadRecords(); renderTable(); }
    } finally { submit.disabled = false; }
  }

  function cell(record, column) {
    const key = column.key;
    if (key === "client_name") return `<td><button class="court-client-documents" type="button" data-case-documents="${record.id}" aria-label="${escapeHtmlAttribute('Документы: ' + record.client_name)}">${escapeHtml(record.client_name)}</button></td>`;
    if (key === "response_file") return `<td>${record.response_file_url
      ? `<a class="secondary-button compact-button" href="${escapeHtmlAttribute(record.response_file_url)}" download>Скачать</a>` : "—"}</td>`;
    const common = `class="cell-editor ${dates.includes(key) ? "date-input" : ""}" data-case-field="${key}" data-id="${record.id}"`;
    if (booleanFields.includes(key) || key === "decision") {
      const choices = booleanFields.includes(key) ? [[false, "Нет"], [true, "Да"]] : [["", "—"], ...decisions.map(value => [value, value])];
      return `<td><select ${common}>${choices.map(([value, label]) => `<option value="${value}" ${String(record[key] ?? "") === String(value) ? "selected" : ""}>${label}</option>`).join("")}</select></td>`;
    }
    if (["notification_date", "claim_date", "hearing_date"].includes(key)) {
      const disabled = key === "claim_date" && !record.claim_sent || key === "hearing_date" && !record.lawsuit_exists;
      return `<td><input ${common} data-date-input="true" placeholder="дд.мм.гггг" value="${escapeHtmlAttribute(record[key] || "")}" ${disabled ? "disabled" : ""} /></td>`;
    }
    if (key === "decision_payout") return `<td><input ${common} type="number" min="0" step="0.01" value="${record[key] || 0}" ${record.decision ? "" : "disabled"} /></td>`;
    if (key === "comment") return `<td><textarea ${common} rows="2">${escapeHtml(record[key] || "")}</textarea></td>`;
    if (["case_number", "case_court"].includes(key)) return `<td><input ${common} value="${escapeHtmlAttribute(record[key] || "")}" /></td>`;
    return null;
  }
  return { columns, bind, open, prefill, saveForm, cell };
})();
