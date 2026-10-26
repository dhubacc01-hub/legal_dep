const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function pageContext(filename) {
  const element = { value: "", querySelector: () => null, querySelectorAll: () => [], addEventListener() {} };
  element.elements = new Proxy({}, { get: () => element });
  const document = { getElementById: () => element, querySelector: () => element, querySelectorAll: () => [], addEventListener() {} };
  const window = { __APP_CONTEXT__: {}, localStorage: { getItem: () => null } };
  const context = vm.createContext({ document, window, localStorage: window.localStorage, console });
  const source = fs.readFileSync(path.join(__dirname, "..", "app", "static", filename), "utf8");
  vm.runInContext(filename === "incoming_correspondence.js" ? source.slice(0, source.lastIndexOf("init().catch")) : source, context);
  return context;
}

test("debtor export uses all filtered branches, including matches in a child", () => {
  const context = pageContext("app.js");
  vm.runInContext(`
    state.debtors = Array.from({ length: 70 }, (_, index) => ({ id: index + 1, category: "Новый", client_name: "Client " + index }));
    state.debtors.push({ id: 99, parent_debtor_id: 1, category: "Клиент частично оплачивает" });
    var filters = readFilters();
    var all = filteredDebtorBranches(filters);
    filters.category = ["Клиент частично оплачивает"];
    var filtered = filteredDebtorBranches(filters);
  `, context);
  assert.equal(vm.runInContext("all.roots.length", context), 70);
  assert.equal(vm.runInContext("filtered.roots.length", context), 1);
  assert.equal(vm.runInContext("filtered.roots[0].id", context), 1);
  assert.equal(vm.runInContext("filtered.childrenByParent.get(1).id", context), 99);
});

test("date sorting is chronological, stable and keeps empty dates last in both directions", () => {
  const context = pageContext("app.js");
  vm.runInContext(`
    state.debtors = [
      { id: 1, claim_sent_date_iso: "2026-01-02", hearing_date_iso: "2026-12-01" },
      { id: 2, claim_sent_date_iso: "2025-12-30", hearing_date_iso: "2026-01-01" },
      { id: 3, claim_sent_date_iso: null },
      { id: 4, claim_sent_date_iso: "2026-01-02", hearing_date_iso: "2026-02-01" },
      { id: 5, claim_sent_date_iso: "" },
      { id: 6, claim_sent_date_iso: "2026-10-01", hearing_date_iso: "2025-12-31" }
    ];
    state.sortField = "claim_sent_date_iso";
  `, context);
  const orderedIds = () => vm.runInContext("filteredDebtorBranches(readFilters()).roots.map(r => r.id).join(',')", context);
  assert.equal(orderedIds(), "2,1,4,6,3,5");
  vm.runInContext('state.sortDirection = "desc";', context);
  assert.equal(orderedIds(), "6,1,4,2,3,5");
  vm.runInContext('state.sortField = "hearing_date_iso"; state.sortDirection = "asc";', context);
  assert.equal(orderedIds(), "6,2,4,1,3,5");
  vm.runInContext('state.sortDirection = "desc";', context);
  assert.equal(orderedIds(), "1,4,2,6,3,5");
  assert.equal(vm.runInContext("state.debtors.map(r => r.id).join(',')", context), "1,2,3,4,5,6");
});

test("sorted export includes all pages and preserves parent-child branches for each country and page", () => {
  const context = pageContext("app.js");
  vm.runInContext(`
    state.debtors = Array.from({ length: 70 }, (_, index) => ({
      id: index + 1, category: "Новый",
      claim_sent_date_iso: new Date(Date.UTC(2026, 0, 71 - index)).toISOString().slice(0, 10)
    }));
    state.debtors.push({ id: 99, parent_debtor_id: 70, claim_sent_date_iso: "2027-01-01" });
    state.sortField = "claim_sent_date_iso";
    state.currentPage = 2;
  `, context);
  for (const country of ["kz", "uz"]) {
    for (const page of ["debtors", "csi"]) {
      vm.runInContext(`
        state.currentCountry = ${JSON.stringify(country)};
        state.appPage = ${JSON.stringify(page)};
        var result = filteredDebtorBranches(readFilters());
        var exportIds = result.roots.flatMap(parent => {
          const child = result.childrenByParent.get(parent.id);
          return child ? [parent.id, child.id] : [parent.id];
        });
      `, context);
      assert.equal(vm.runInContext("result.roots.length", context), 70);
      assert.equal(vm.runInContext("exportIds.slice(0, 4).join(',')", context), "70,99,69,68");
      assert.equal(vm.runInContext("exportIds.length", context), 71);
      assert.equal(vm.runInContext("result.roots.slice(PAGE_SIZE)[0].id", context), 20);
    }
  }
});

test("header clicks toggle direction, reset pagination and start a new column ascending", () => {
  const context = pageContext("app.js");
  vm.runInContext(`
    var renders = [];
    renderDebtors = (resetPage) => {
      if (resetPage) state.currentPage = 1;
      renders.push([state.sortField, state.sortDirection, state.currentPage]);
    };
    var clickColumn = (field) => handleFilterClick({ target: {
      closest: selector => selector === "[data-sort-field]" ? { dataset: { sortField: field } } : null
    } });
    state.currentPage = 3;
    clickColumn("claim_sent_date_iso");
    clickColumn("claim_sent_date_iso");
    clickColumn("hearing_date_iso");
    clickColumn("hearing_date_iso");
  `, context);
  assert.deepEqual(JSON.parse(vm.runInContext("JSON.stringify(renders)", context)), [
    ["claim_sent_date_iso", "asc", 1], ["claim_sent_date_iso", "desc", 1],
    ["hearing_date_iso", "asc", 1], ["hearing_date_iso", "desc", 1],
  ]);
});

test("sorting is persisted per country and invalid or missing preferences restore the default", () => {
  const context = pageContext("app.js");
  vm.runInContext(`
    var storage = new Map();
    window.localStorage.setItem = (key, value) => storage.set(key, value);
    window.localStorage.getItem = key => storage.get(key);
    state.sortField = "hearing_date_iso";
    state.sortDirection = "desc";
    saveViewState();
    state.sortField = null;
    restoreViewState();
  `, context);
  assert.equal(vm.runInContext("state.sortField", context), "hearing_date_iso");
  assert.equal(vm.runInContext("state.sortDirection", context), "desc");
  vm.runInContext('state.currentCountry = "uz"; restoreViewState();', context);
  assert.equal(vm.runInContext("state.sortField", context), null);
  assert.equal(vm.runInContext("state.sortDirection", context), "asc");
  vm.runInContext(`
    storage.set(getViewStateStorageKey(), JSON.stringify({ sort: { field: "debt_amount", direction: "desc" } }));
    restoreViewState();
  `, context);
  assert.equal(vm.runInContext("state.sortField", context), null);
});

test("sort headers expose active direction and reset the inactive indicator", () => {
  const context = pageContext("app.js");
  vm.runInContext(`
    var buttons = ["claim_sent_date_iso", "hearing_date_iso"].map(field => ({
      dataset: { sortField: field }, indicator: {}, attributes: {},
      classList: { toggle() {} },
      closest() { return { setAttribute: (key, value) => { this.attributes[key] = value; } }; },
      querySelector() { return this.indicator; }
    }));
    thead.querySelectorAll = selector => selector === "[data-sort-field]" ? buttons : [];
    state.sortField = "claim_sent_date_iso";
    state.sortDirection = "desc";
    updateTableSortHeaders();
  `, context);
  assert.equal(vm.runInContext('buttons[0].attributes["aria-sort"]', context), "descending");
  assert.equal(vm.runInContext("buttons[0].indicator.textContent", context), "\u2193");
  assert.equal(vm.runInContext('buttons[1].attributes["aria-sort"]', context), "none");
  assert.equal(vm.runInContext("buttons[1].indicator.textContent", context), "\u2195");
});

test("incoming export respects active tab, multi-select empty values, text and dates", () => {
  const context = pageContext("incoming_correspondence.js");
  vm.runInContext(`
    state.filters = buildDefaultFilters();
    state.records = [
      { id: 1, category: "Претензия", company: "A", receive_method: "Почта", response_text: "", client_name: "Alice", received_date_iso: "2026-03-01" },
      { id: 2, category: "Претензия", company: "A", receive_method: "Telegram", response_text: "Отказ", client_name: "Bob", received_date_iso: "2026-03-02" },
      { id: 3, category: "Иск", company: "A", receive_method: "Почта", response_text: "", client_name: "Alice", received_date_iso: "2026-03-01" }
    ];
    state.filters.response_text = ["__EMPTY__"];
    state.filters.company = ["A"];
    state.filters.receive_method = ["Почта", "Telegram"];
    state.filters.received_date = { from: "2026-03-01", to: "2026-03-01" };
    state.filters.client_name = "ali";
  `, context);
  assert.equal(vm.runInContext("filteredRecords().map(r => r.id).join(',')", context), "1");
  vm.runInContext('state.currentTab = "other"; state.filters = buildDefaultFilters();', context);
  assert.equal(vm.runInContext("filteredRecords().map(r => r.id).join(',')", context), "3");
});

function exportUi(selection) {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) {
      const classes = new Set(id === "export-modal-backdrop" ? ["hidden"] : []);
      const listeners = {};
      const result = {
        value: "", textContent: "", disabled: false, listeners,
        classList: { add: (x) => classes.add(x), remove: (x) => classes.delete(x), contains: (x) => classes.has(x), toggle: (x, on) => on ? classes.add(x) : classes.delete(x) },
        addEventListener: (event, callback) => { (listeners[event] ??= []).push(callback); },
        querySelector: () => element("payments-option"), focus() {}, click() {},
        contains: (child) => !child.removed,
        appendChild: (child) => { child.removed = false; },
        remove() { this.removed = true; },
        async emit(event, extra = {}) { for (const callback of listeners[event] ?? []) await callback({ target: result, ...extra }); },
      };
      elements.set(id, result);
    }
    return elements.get(id);
  }
  const events = {};
  const requests = [];
  const downloads = [];
  const document = {
    getElementById: element, querySelector: () => null,
    addEventListener: (event, callback) => { (events[event] ??= []).push(callback); },
    createElement: () => { const link = { click() { downloads.push(this.download); }, remove() {} }; return link; },
    body: { appendChild() {} },
  };
  class FixedDate extends Date { constructor(...args) { super(...(args.length ? args : [2026, 0, 15])); } }
  const window = { setTimeout() {} };
  const context = vm.createContext({
    document, window, Date: FixedDate, AbortController,
    URL: { createObjectURL: () => "blob:test", revokeObjectURL() {} },
    fetch: async (url, options) => { requests.push({ url, body: JSON.parse(options.body) }); return { ok: true, blob: async () => ({}) }; },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "app", "static", "exports.js"), "utf8"), context);
  window.LegalExport.init({ getSelection: () => selection, closeDatePicker() {} });
  return { element, requests, downloads, events };
}

test("single export control sends the filtered IDs, country and chosen file format", async () => {
  const ui = exportUi({ source: "csi", country: "uz", title: "ЧСИ", payments: true, record_ids: [5, 9] });
  await ui.element("open-export-modal").emit("click");
  assert.equal(ui.element("export-modal-backdrop").classList.contains("hidden"), false);
  ui.element("export-format").value = "pdf";
  await ui.element("confirm-export-button").emit("click");
  assert.deepEqual(ui.requests[0], { url: "/api/exports", body: { source: "csi", country: "uz", record_ids: [5, 9], report: "table", format: "pdf" } });
  assert.deepEqual(ui.downloads, ["csi_table_uz.pdf"]);
});

test("payment preset handles previous month across a year boundary", async () => {
  const ui = exportUi({ source: "debtors", country: "kz", title: "Должники", payments: true, record_ids: [1] });
  await ui.element("open-export-modal").emit("click");
  ui.element("export-format").value = "xlsx";
  ui.element("export-report").value = "payments";
  ui.element("export-period").value = "previous";
  await ui.element("export-period").emit("change");
  await ui.element("confirm-export-button").emit("click");
  assert.equal(ui.requests[0].body.date_from, "2025-12-01");
  assert.equal(ui.requests[0].body.date_to, "2025-12-31");
});

test("invalid custom date blocks download and correspondence has no payment option", async () => {
  const ui = exportUi({ source: "incoming_other", country: "uz", title: "Прочее", payments: false, record_ids: [] });
  await ui.element("open-export-modal").emit("click");
  assert.equal(ui.element("payments-option").removed, true);
  ui.element("export-report").value = "payments";
  ui.element("export-date-from").value = "31.02.2026";
  ui.element("export-date-to").value = "01.03.2026";
  await ui.element("confirm-export-button").emit("click");
  assert.equal(ui.requests.length, 0);
  assert.equal(ui.element("export-status").textContent, "Укажите обе даты периода.");
});
