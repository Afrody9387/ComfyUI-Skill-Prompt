import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

class Element {
    constructor(tag) {
        this.tag = tag;
        this.children = [];
        this.style = {};
        this.events = {};
        this.selectedIndex = -1;
        this._value = "";
    }
    append(...items) { this.children.push(...items); }
    replaceChildren() { this.children = []; this.selectedIndex = -1; }
    get options() { return this.children; }
    get value() { return this.tag === "select" ? this.children[this.selectedIndex]?.value || "" : this._value; }
    set value(value) {
        this._value = value;
        if (this.tag === "select") this.selectedIndex = this.children.findIndex(item => item.value === value);
    }
    addEventListener(name, callback) { this.events[name] = callback; }
    showModal() { this.open = true; }
    close() { this.open = false; this.events.close?.(); }
    remove() {}
    focus() {}
}

const document = { body: new Element("body"), createElement: tag => new Element(tag) };
let extension;
const calls = [];
let failure = false;
const api = {
    async fetchApi(path, options) {
        const values = JSON.parse(options.body);
        calls.push({ path, values });
        if (failure) return { ok: false, status: 401, json: async () => ({ ok: false, error: "HTTP 401：密钥无效" }) };
        const data = path.endsWith("/models")
            ? { ok: true, models: ["chat", "vision-model"] }
            : { ok: true, model: values.model, reply: "OK", elapsed_seconds: 0.1 };
        return { ok: true, json: async () => data };
    },
};
const source = readFileSync(new URL("../web/llm_connector.js", import.meta.url), "utf8")
    .replace(/^import .+;\r?$/gm, "");
vm.runInNewContext(source, { app: { registerExtension: value => { extension = value; } }, api, document });

class Node {
    constructor() {
        this.widgets = [
            { name: "base_url", value: "https://provider.test/v1" },
            { name: "api_key", value: "first-key" },
            { name: "model", value: "" },
            { name: "timeout", value: 120 },
        ];
        this.graph = { change() {} };
    }
    onNodeCreated() { this.originalCalled = true; }
    addWidget(type, name, value, callback, options) {
        const widget = { type, name, value, callback, options };
        this.widgets.push(widget);
        return widget;
    }
    computeSize() { return [400, 250]; }
    setSize() {}
    setDirtyCanvas() {}
}
extension.beforeRegisterNodeDef(Node, { name: "SkillLLMServiceConnector" });
const node = new Node();
node.onNodeCreated();
assert.ok(node.originalCalled);
const buttons = node.widgets.filter(widget => widget.type === "button");
assert.equal(buttons.length, 2);
assert.ok(buttons.every(button => button.options.serialize === false));
await buttons[0].callback();
assert.equal(calls[0].path, "/skill-prompt/models");
const dialog = document.body.children.at(-1);
const [filter, list, use] = dialog.children[1].children;
assert.equal(list.children.length, 2);
filter.value = "vision";
filter.oninput();
assert.equal(list.children.length, 1);
use.onclick();
assert.equal(node.widgets.find(widget => widget.name === "model").value, "vision-model");
assert.equal(dialog.open, false);
node.widgets.find(widget => widget.name === "api_key").value = "updated-key";
await buttons[1].callback();
assert.equal(calls.at(-1).path, "/skill-prompt/test");
assert.equal(calls.at(-1).values.api_key, "updated-key");
assert.equal(calls.at(-1).values.model, "vision-model");
assert.match(document.body.children.at(-1).children[1].textContent, /OK/);
failure = true;
await buttons[0].callback();
assert.match(document.body.children.at(-1).children[1].textContent, /HTTP 401/);
assert.equal(buttons[0].name, "获取模型");
console.log("Connector UI passed: model filtering/selection, current form values, connection result, error recovery.");
