(() => {
  function formatDate(value) {
    return `${String(value.getDate()).padStart(2, "0")}.${String(value.getMonth() + 1).padStart(2, "0")}.${value.getFullYear()}`;
  }

  function parseDate(value) {
    const match = String(value).trim().match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (!match) return null;
    const [, day, month, year] = match;
    const parsed = new Date(Number(year), Number(month) - 1, Number(day));
    if (parsed.getFullYear() !== Number(year) || parsed.getMonth() !== Number(month) - 1 || parsed.getDate() !== Number(day)) return null;
    return `${year}-${month}-${day}`;
  }

  window.LegalExport = {
    init({ getSelection, closeDatePicker }) {
      const modal = document.getElementById("export-modal-backdrop");
      const button = document.getElementById("open-export-modal");
      if (!modal || !button) return;
      const report = document.getElementById("export-report");
      const paymentsOption = report.querySelector('[value="payments"]');
      const format = document.getElementById("export-format");
      const period = document.getElementById("export-period");
      const periodFields = document.getElementById("export-period-fields");
      const dateFrom = document.getElementById("export-date-from");
      const dateTo = document.getElementById("export-date-to");
      const status = document.getElementById("export-status");
      const submit = document.getElementById("confirm-export-button");
      let selection = null;
      let controller = null;

      function setStatus(message, failed = false) {
        status.textContent = message;
        status.classList.toggle("hidden", !message);
        status.classList.toggle("is-error", failed);
      }

      function setPeriod() {
        if (period.value === "custom") {
          dateFrom.value = "";
          dateTo.value = "";
          dateFrom.focus();
          return;
        }
        const today = new Date();
        const previous = period.value === "previous";
        dateFrom.value = formatDate(new Date(today.getFullYear(), today.getMonth() - (previous ? 1 : 0), 1));
        dateTo.value = formatDate(previous ? new Date(today.getFullYear(), today.getMonth(), 0) : today);
      }

      function close() {
        controller?.abort();
        closeDatePicker();
        modal.classList.add("hidden");
        button.focus();
      }

      button.addEventListener("click", () => {
        selection = getSelection();
        if (selection.payments) {
          if (!report.contains(paymentsOption)) report.appendChild(paymentsOption);
        } else {
          paymentsOption.remove();
        }
        report.value = "table";
        periodFields.classList.add("hidden");
        period.value = "current";
        setPeriod();
        document.getElementById("export-scope").textContent = selection.title;
        document.getElementById("export-selection-summary").textContent = `Записей с учётом фильтров: ${selection.record_ids.length}. Будут выгружены все страницы таблицы.`;
        setStatus("");
        modal.classList.remove("hidden");
        report.focus();
      });
      report.addEventListener("change", () => periodFields.classList.toggle("hidden", report.value !== "payments"));
      period.addEventListener("change", setPeriod);
      [dateFrom, dateTo].forEach((input) => {
        ["input", "change"].forEach((event) => input.addEventListener(event, () => { period.value = "custom"; }));
      });
      ["close-export-modal", "cancel-export-modal"].forEach((id) => document.getElementById(id).addEventListener("click", close));
      modal.addEventListener("click", (event) => { if (event.target === modal) close(); });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.classList.contains("hidden") && !document.querySelector(".date-picker-popover:not(.hidden)")) close();
      });
      submit.addEventListener("click", async () => {
        if (!selection) return;
        const payload = {
          source: selection.source,
          country: selection.country,
          record_ids: selection.record_ids,
          report: report.value,
          format: format.value,
        };
        if (payload.report === "payments") {
          payload.date_from = parseDate(dateFrom.value);
          payload.date_to = parseDate(dateTo.value);
          if (!payload.date_from || !payload.date_to) {
            setStatus("Укажите обе даты периода.", true);
            return;
          }
          if (payload.date_to < payload.date_from) {
            setStatus("Дата окончания не может быть раньше даты начала.", true);
            return;
          }
        }
        controller = new AbortController();
        submit.disabled = true;
        setStatus("Готовим файл...");
        try {
          const response = await fetch("/api/exports", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            signal: controller.signal,
          });
          if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(typeof error.detail === "string" ? error.detail : "Не удалось сформировать файл. Обновите страницу и повторите экспорт.");
          }
          const url = URL.createObjectURL(await response.blob());
          const link = document.createElement("a");
          link.href = url;
          link.download = `${payload.source}_${payload.report}_${payload.country}.${payload.format}`;
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
          controller = null;
          close();
        } catch (error) {
          if (error.name !== "AbortError") setStatus(error.message, true);
        } finally {
          controller = null;
          submit.disabled = false;
        }
      });
    },
  };
})();
