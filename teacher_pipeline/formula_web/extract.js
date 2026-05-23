// Адрес сервиса формул (formulas). Менять только здесь.
const BACKEND_URL = "http://localhost:8001";

const fileInput = document.getElementById("file-input");
const fileName = document.getElementById("file-name");
const progressEl = document.getElementById("progress");
const statusEl = document.getElementById("status");
const debugLog = document.getElementById("debug-log");
const resultsEl = document.getElementById("results");
const downloadBtn = document.getElementById("download-btn");

let lastFormulas = [];
let lastTitle = "";

function dbg(msg, cls) {
    const now = new Date();
    const ts = now.toLocaleTimeString("ru-RU", { hour12: false }) +
        "." + String(now.getMilliseconds()).padStart(3, "0");
    const line = document.createElement("div");
    if (cls) line.className = cls;
    line.textContent = `[${ts}] ${msg}`;
    debugLog.appendChild(line);
    debugLog.scrollTop = debugLog.scrollHeight;
}

fileInput.addEventListener("change", () => {
    if (fileInput.files.length) extract(fileInput.files[0]);
});

downloadBtn.addEventListener("click", async () => {
    if (!lastFormulas.length) return;
    downloadBtn.disabled = true;
    dbg(`→ POST ${BACKEND_URL}/export/docx | формул: ${lastFormulas.length}`);
    try {
        const resp = await fetch(`${BACKEND_URL}/export/docx`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                title: lastTitle,
                formulas: lastFormulas.map((f) => ({ name: f.name || "", latex: f.latex || "" })),
            }),
        });
        if (!resp.ok) {
            let detail = `HTTP ${resp.status}`;
            try { detail = (await resp.json()).detail || detail; } catch (e) {}
            throw new Error(detail);
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "formulas.docx";
        a.click();
        URL.revokeObjectURL(url);
        dbg("← .docx скачан", "dbg-ok");
    } catch (err) {
        dbg(`← ошибка экспорта: ${err.message}`, "dbg-err");
    } finally {
        downloadBtn.disabled = false;
    }
});

async function extract(file) {
    fileName.textContent = file.name;
    resultsEl.innerHTML = "";
    downloadBtn.hidden = true;
    progressEl.hidden = false;
    dbg(`→ POST ${BACKEND_URL}/analyze | "${file.name}" ${file.size} байт`);

    const t0 = performance.now();
    let ticks = 0;
    statusEl.textContent = "Извлекаю и называю формулы… 0.0с";
    const timer = setInterval(() => {
        ticks += 0.1;
        statusEl.textContent = `Извлекаю и называю формулы… ${ticks.toFixed(1)}с`;
    }, 100);

    try {
        const form = new FormData();
        form.append("file", file, file.name);
        const resp = await fetch(`${BACKEND_URL}/analyze`, { method: "POST", body: form });
        if (!resp.ok) {
            let detail = `HTTP ${resp.status}`;
            try { detail = (await resp.json()).detail || detail; } catch (e) {}
            throw new Error(detail);
        }
        const data = await resp.json();
        const formulas = data.formulas || [];
        const ms = Math.round(performance.now() - t0);
        dbg(`← 200 OK за ${ms} мс | формул: ${formulas.length}`, "dbg-ok");
        lastFormulas = formulas;
        lastTitle = file.name;
        renderFormulas(formulas);
        if (formulas.length) downloadBtn.hidden = false;
    } catch (err) {
        const ms = Math.round(performance.now() - t0);
        dbg(`← ОШИБКА за ${ms} мс: ${err.message}`, "dbg-err");
        statusEl.textContent = "Ошибка: " + err.message;
    } finally {
        clearInterval(timer);
        progressEl.hidden = true;
    }
}

function renderFormulas(formulas) {
    if (!formulas.length) {
        resultsEl.innerHTML = "<p>Формулы не найдены.</p>";
        return;
    }
    formulas.forEach((f) => {
        const card = document.createElement("div");
        card.className = "f-card";

        if (f.name) {
            const name = document.createElement("div");
            name.className = "f-name";
            name.textContent = f.name;
            card.appendChild(name);
        }

        const render = document.createElement("div");
        render.className = "f-render";
        try {
            katex.render(f.latex, render, { throwOnError: false, displayMode: true });
        } catch (e) {
            render.textContent = f.latex;
        }
        card.appendChild(render);

        if (f.description) {
            const desc = document.createElement("div");
            desc.className = "f-desc";
            desc.textContent = f.description;
            card.appendChild(desc);
        }

        const latex = document.createElement("code");
        latex.className = "f-latex";
        latex.textContent = f.latex;
        card.appendChild(latex);

        const meta = document.createElement("div");
        meta.className = "f-meta";
        const parts = [`#${f.formula_id}`, `метод: ${f.method}`];
        if (f.page != null) parts.push(`стр. ${f.page}`);
        if (f.confidence != null) parts.push(`уверенность ${(f.confidence * 100).toFixed(1)}%`);
        meta.textContent = parts.join(" · ");
        card.appendChild(meta);

        if (f.context) {
            const ctx = document.createElement("div");
            ctx.className = "f-ctx";
            ctx.textContent = "контекст: " + f.context;
            card.appendChild(ctx);
        }

        resultsEl.appendChild(card);
    });
}
