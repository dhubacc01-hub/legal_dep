const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function setup() {
  const handlers = {};
  function element(id) {
    return { textContent: "", value: "", disabled: false, focused: false,
      addEventListener(event, handler) { handlers[`${id}:${event}`] = handler; },
      focus() { this.focused = true; },
    };
  }
  const elements = Object.fromEntries(["csi-writ-modal", "csi-writ-form", "csi-writ-status", "debtors-tbody", "csi-writ-client", "csi-writ-title", "csi-writ-judge-field"].map(id => [id, element(id)]));
  const judgeField = elements["csi-writ-judge-field"];
  judgeField.classList = { toggle(name, hidden) { judgeField.hidden = hidden; } };
  const form = elements["csi-writ-form"], modal = elements["csi-writ-modal"];
  form.elements = { judge_name: element("judge"), lawyer_email: element("email") };
  form.reset = () => { form.elements.judge_name.value = ""; form.elements.lawyer_email.value = "mikhail.inozemtsev.dp@gmail.com"; };
  form.reportValidity = () => true;
  const submit = element("submit"), cancel = element("cancel");
  form.querySelector = () => submit;
  modal.querySelectorAll = selector => selector === "[data-close-writ]" ? [cancel] : [cancel, form.elements.judge_name, form.elements.lawyer_email, submit];
  modal.hidden = true;
  modal.classList = { add() { modal.hidden = true; }, remove() { modal.hidden = false; } };
  const state = { appPage: "csi", currentCountry: "kz", debtors: [{ id: 7, client_name: "Test client", contract_number: "123" }] };
  const preview = { closed: false, location: {}, close() { this.closed = true; } };
  const requests = [];
  let response = { ok: true, blob: async () => "PDF" };
  const document = { getElementById: id => elements[id], createElement: () => ({ click() {} }) };
  const context = vm.createContext({ state, document, window: { open: () => preview, setTimeout() {} },
    URL: { createObjectURL: () => "blob:pdf", revokeObjectURL() {} },
    fetch: async (url, options) => { requests.push({ url, options }); return response; },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "app", "static", "csi_documents.js"), "utf8"), context);
  const opener = { ...element("opener"), dataset: { id: "7" } };
  function open(mode = "writ") {
    opener.dataset.csiDocument = mode;
    handlers["debtors-tbody:click"]({ target: { closest: () => opener } });
  }
  function submitForm() { return handlers["csi-writ-form:submit"]({ preventDefault() {} }); }
  return { elements, modal, form, state, preview, requests, handlers, opener, open, submitForm, setResponse(value) { response = value; } };
}

test("writ form opens with editable default email and restores focus on Escape", () => {
  const ui = setup();
  ui.open();
  assert.equal(ui.modal.hidden, false);
  assert.equal(ui.form.elements.judge_name.focused, true);
  assert.equal(ui.form.elements.lawyer_email.value, "mikhail.inozemtsev.dp@gmail.com");
  assert.match(ui.elements["csi-writ-client"].textContent, /Test client/);
  ui.handlers["csi-writ-modal:keydown"]({ key: "Escape", preventDefault() {} });
  assert.equal(ui.modal.hidden, true);
  assert.equal(ui.opener.focused, true);
});

test("writ form submits the judge and edited email and opens the generated PDF", async () => {
  const ui = setup(); ui.open();
  ui.form.elements.judge_name.value = "  Test Judge  ";
  ui.form.elements.lawyer_email.value = " another@example.com ";
  await ui.submitForm();
  assert.equal(ui.requests.length, 1);
  assert.equal(ui.requests[0].url, "/api/debtors/7/csi-writ-pdf");
  assert.deepEqual(JSON.parse(ui.requests[0].options.body), { judge_name: "Test Judge", lawyer_email: "another@example.com" });
  assert.equal(ui.preview.location.href, "blob:pdf");
  assert.equal(ui.modal.hidden, true);
});

test("writ API errors stay in the form rather than losing input or showing Object Object", async () => {
  const ui = setup(); ui.open();
  ui.form.elements.judge_name.value = "Test Judge";
  ui.setResponse({ ok: false, json: async () => ({ detail: [{ msg: "Missing field" }] }) });
  await ui.submitForm();
  assert.equal(ui.elements["csi-writ-status"].textContent, "Missing field");
  assert.equal(ui.modal.hidden, false);
  assert.equal(ui.preview.closed, true);
  assert.equal(ui.form.elements.judge_name.value, "Test Judge");
});

test("unsupported country and debtors page cannot open the CSI template", () => {
  const ui = setup();
  ui.state.currentCountry = "uz"; ui.open();
  assert.equal(ui.modal.hidden, true);
  ui.state.currentCountry = "kz"; ui.state.appPage = "debtors"; ui.open();
  assert.equal(ui.modal.hidden, true);
});

test("dispatch form hides the judge and submits only the lawyer email to its own endpoint", async () => {
  const ui = setup(); ui.open("dispatch");
  assert.equal(ui.elements["csi-writ-title"].textContent, "Направление исполнительного листа");
  assert.equal(ui.elements["csi-writ-judge-field"].hidden, true);
  assert.equal(ui.form.elements.judge_name.disabled, true);
  assert.equal(ui.form.elements.lawyer_email.focused, true);
  ui.form.elements.lawyer_email.value = "dispatch@example.com";
  await ui.submitForm();
  assert.equal(ui.requests[0].url, "/api/debtors/7/csi-dispatch-pdf");
  assert.deepEqual(JSON.parse(ui.requests[0].options.body), { lawyer_email: "dispatch@example.com" });
  assert.equal(ui.preview.location.href, "blob:pdf");
  ui.open("writ");
  assert.equal(ui.form.elements.judge_name.disabled, false);
  assert.equal(ui.elements["csi-writ-judge-field"].hidden, false);
  assert.equal(ui.elements["csi-writ-title"].textContent, "Выдача исполнительного листа");
});
