import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

function showDialog(title, message) {
    const dialog = document.createElement("dialog");
    dialog.style.cssText = "background:var(--comfy-menu-bg,Canvas);color:var(--input-text,CanvasText);border:1px solid var(--border-color,GrayText);border-radius:8px;padding:20px;max-width:650px;width:80vw";
    const heading = document.createElement("h3");
    heading.textContent = title;
    const body = document.createElement("div");
    body.style.whiteSpace = "pre-wrap";
    body.textContent = message;
    const close = document.createElement("button");
    close.textContent = "关闭";
    close.onclick = () => dialog.close();
    dialog.append(heading, body, close);
    dialog.addEventListener("close", () => dialog.remove(), { once: true });
    document.body.append(dialog);
    dialog.showModal();
    return { dialog, body, close };
}

function chooseModel(node, models) {
    const widget = node.widgets.find(w => w.name === "model");
    const { dialog, body, close } = showDialog(`选择模型（${models.length} 个）`, "");
    const filter = document.createElement("input");
    filter.placeholder = "输入关键词筛选模型";
    filter.style.cssText = "width:100%;box-sizing:border-box;margin-bottom:8px";
    const list = document.createElement("select");
    list.size = 12;
    list.style.cssText = "width:100%;margin-bottom:12px";
    const update = () => {
        list.replaceChildren();
        for (const id of models.filter(id => id.toLowerCase().includes(filter.value.toLowerCase()))) {
            const option = document.createElement("option");
            option.value = id;
            option.textContent = id;
            list.append(option);
        }
        if ([...list.options].some(option => option.value === widget.value)) list.value = widget.value;
        else list.selectedIndex = 0;
    };
    const apply = () => {
        if (!list.value) return;
        widget.value = list.value;
        widget.callback?.(list.value);
        node.graph?.change();
        node.setDirtyCanvas(true, true);
        dialog.close();
    };
    const use = document.createElement("button");
    use.textContent = "使用选中模型";
    use.onclick = apply;
    list.ondblclick = apply;
    filter.oninput = update;
    dialog.addEventListener("keydown", event => {
        if (event.key === "Enter") { event.preventDefault(); apply(); }
    });
    body.append(filter, list, use);
    close.textContent = "取消";
    update();
    filter.focus();
}

app.registerExtension({
    name: "SkillPrompt.SimpleLLMConnector",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "SkillLLMServiceConnector") return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = original?.apply(this, arguments);
            const node = this;
            let busy = false;
            const action = async (button, kind) => {
                if (busy) return;
                busy = true;
                const label = button.name;
                button.name = kind === "models" ? "正在获取模型…" : "正在测试连接…";
                node.setDirtyCanvas(true, true);
                try {
                    const values = {};
                    for (const name of ["base_url", "api_key", "model", "timeout"]) {
                        values[name] = node.widgets.find(w => w.name === name)?.value;
                    }
                    const response = await api.fetchApi(`/skill-prompt/${kind}`, {
                        method: "POST", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(values),
                    });
                    const data = await response.json();
                    if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
                    if (kind === "models") chooseModel(node, data.models);
                    else showDialog("连接成功", `模型：${data.model}\n耗时：${data.elapsed_seconds} 秒\n回复：${data.reply}`);
                } catch (error) {
                    showDialog("请求失败", error.message);
                } finally {
                    busy = false;
                    button.name = label;
                    node.setDirtyCanvas(true, true);
                }
            };
            const models = this.addWidget("button", "获取模型", null, () => action(models, "models"), { serialize: false });
            const test = this.addWidget("button", "测试连接（发送短请求）", null, () => action(test, "test"), { serialize: false });
            this.setSize(this.computeSize());
            return result;
        };
    },
});
