(() => {
  const modal = document.getElementById("csi-writ-modal");
  const form = document.getElementById("csi-writ-form");
  if (!modal || !form) return;
  const status = document.getElementById("csi-writ-status");
  let targetId = null;
  let mode = "writ";
  let opener = null;
  let busy = false;

  function close() {
    if (busy) return;
    modal.classList.add("hidden");
    targetId = null;
    opener?.focus();
  }

  document.getElementById("debtors-tbody").addEventListener("click", (event) => {
    const button = event.target.closest("[data-csi-writ-button]");
    if (busy || !button || button.disabled || state.appPage !== "csi" || state.currentCountry !== "kz") return;
    const debtor = state.debtors.find(item => item.id === Number(button.dataset.id));
    if (!debtor) return;
    targetId = debtor.id;
    opener = button;
    form.reset();
    mode = button.dataset.csiDocument === "dispatch" ? "dispatch" : "writ";
    const dispatch = mode === "dispatch";
    form.elements.judge_name.disabled = dispatch;
    document.getElementById("csi-writ-judge-field").classList.toggle("hidden", dispatch);
    document.getElementById("csi-writ-title").textContent = dispatch
      ? "Направление исполнительного листа" : "Выдача исполнительного листа";
    status.textContent = "";
    document.getElementById("csi-writ-client").textContent = `${debtor.client_name} · ${debtor.contract_number}`;
    modal.classList.remove("hidden");
    (dispatch ? form.elements.lawyer_email : form.elements.judge_name).focus();
  });
  modal.querySelectorAll("[data-close-writ]").forEach(button => button.addEventListener("click", close));
  modal.addEventListener("click", event => { if (event.target === modal) close(); });
  modal.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
    if (event.key === "Tab") {
      const controls = [...modal.querySelectorAll("button:not(:disabled), input:not(:disabled)")];
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first?.focus();
      }
    }
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || targetId === null || !form.reportValidity()) return;
    const payload = {
      lawyer_email: form.elements.lawyer_email.value.trim(),
    };
    if (mode === "writ") payload.judge_name = form.elements.judge_name.value.trim();
    if (mode === "writ" && payload.judge_name.length < 3) {
      status.textContent = "Укажите ФИО судьи.";
      form.elements.judge_name.focus();
      return;
    }
    busy = true;
    status.textContent = "Формирование PDF...";
    form.querySelector('button[type="submit"]').disabled = true;
    // Open synchronously so a delayed CRM response does not trigger popup blocking.
    const preview = window.open("", "_blank");
    try {
      const response = await fetch(`/api/debtors/${targetId}/csi-${mode}-pdf`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        const detail = Array.isArray(error.detail) ? error.detail.map(item => item.msg).join("; ") : error.detail;
        throw new Error(typeof detail === "string" ? detail : "Не удалось сформировать заявление.");
      }
      const url = URL.createObjectURL(await response.blob());
      if (preview && !preview.closed) preview.location.href = url;
      else {
        const link = document.createElement("a");
        link.href = url; link.download = `csi_${mode}_${targetId}.pdf`; link.click();
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      busy = false;
      close();
    } catch (error) {
      preview?.close();
      status.textContent = error.message || "Не удалось сформировать заявление.";
    } finally {
      busy = false;
      form.querySelector('button[type="submit"]').disabled = false;
    }
  });
})();
