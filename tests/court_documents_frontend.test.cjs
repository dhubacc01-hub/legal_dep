const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function documentUi(documents = []) {
  const nodes = new Map();
  const documentEvents = {};
  const document = {
    body: { style: { overflow: "auto" } }, activeElement: null,
    getElementById: element, querySelector: () => element("shell"),
    addEventListener: (key, handler) => { documentEvents[key] = handler; },
  };
  function element(id) {
    if (!nodes.has(id)) {
      const classes = new Set(id.includes("backdrop") ? ["hidden"] : []);
      const node = {
        inert: false, isConnected: true, textContent: "", innerHTML: "", handlers: {},
        classList: { add: value => classes.add(value), remove: value => classes.delete(value), contains: value => classes.has(value) },
        addEventListener(key, handler) { this.handlers[key] = handler; },
        focus() { document.activeElement = this; }, querySelectorAll: () => [], reset() {},
      };
      nodes.set(id, node);
    }
    return nodes.get(id);
  }
  element("court-document-form").elements = { title: element("title") };
  const window = {};
  const trigger = element("trigger");
  trigger.dataset = { caseDocuments: "7" };
  const context = vm.createContext({
    window, document, tbody: element("tbody"), closeDatePicker() {},
    state: { records: [{ id: 7, client_name: "Client", contract_number: "contract", company: "Company" }] },
    fetch: async () => ({ ok: true, json: async () => documents }),
    escapeHtml: value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;"),
    escapeHtmlAttribute: value => String(value).replaceAll('"', "&quot;"),
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../app/static/court_documents.js"), "utf8"), context);
  window.CourtDocuments.bind();
  return { element, documentEvents, trigger, document };
}

test("upload modal blocks the drawer backdrop and cannot close both layers", () => {
  const ui = documentUi();
  const drawer = ui.element("court-documents-backdrop");
  const modal = ui.element("court-document-modal-backdrop");
  ui.element("tbody").handlers.click({ target: { closest: () => ui.trigger } });
  ui.element("add-court-document").handlers.click();
  assert.equal(drawer.inert, true);
  assert.equal(modal.classList.contains("hidden"), false);
  drawer.handlers.click({ target: drawer });
  assert.equal(modal.classList.contains("hidden"), false);
  assert.equal(drawer.classList.contains("hidden"), false);
  ui.documentEvents.keydown({ key: "Escape", preventDefault() {} });
  assert.equal(modal.classList.contains("hidden"), true);
  assert.equal(drawer.classList.contains("hidden"), false);
  assert.equal(drawer.inert, false);
  assert.equal(ui.document.activeElement, ui.element("add-court-document"));
  ui.documentEvents.keydown({ key: "Escape", preventDefault() {} });
  assert.equal(drawer.classList.contains("hidden"), true);
  assert.equal(ui.document.body.style.overflow, "auto");
  assert.equal(ui.document.activeElement, ui.trigger);
});

test("document modal layer overrides the later generic backdrop rule", () => {
  const css = fs.readFileSync(path.join(__dirname, "../app/static/styles.css"), "utf8");
  const modal = css.match(/\.modal-backdrop\.court-document-modal\s*\{[^}]*z-index:\s*(\d+)/);
  const drawer = css.match(/\.court-documents-backdrop\s*\{[^}]*z-index:\s*(\d+)/);
  assert.ok(modal && drawer);
  assert.ok(Number(modal[1]) > Number(drawer[1]));
  assert.match(css, /\.court-documents-panel\s+\.modal-inline-status\s*\{[^}]*margin:\s*0/);
});

test("document card opens in a separate tab without a download button", async () => {
  const ui = documentUi([{
    id: "upload-1", source: "upload", title: "<Document>", filename: "document.pdf",
    description: "Description", created_at: "2026-11-25T12:00:00", size_bytes: 100,
    download_url: "/api/court-cases/7/documents/1/file",
  }]);
  ui.element("tbody").handlers.click({ target: { closest: () => ui.trigger } });
  await new Promise(resolve => setImmediate(resolve));
  const html = ui.element("court-documents-list").innerHTML;
  assert.match(html, /<a class="court-document-card"[^>]*target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.match(html, /href="\/api\/court-cases\/7\/documents\/1\/file"/);
  assert.doesNotMatch(html, /Скачать|\sdownload(?:\s|=|>)/);
});
