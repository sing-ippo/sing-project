const form = document.getElementById("login-form");
const errEl = document.getElementById("login-err");
const btn = document.getElementById("login-btn");

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errEl.textContent = "";
    btn.disabled = true;
    const data = new FormData();
    data.append("username", document.getElementById("username").value);
    data.append("password", document.getElementById("password").value);
    try {
        const resp = await fetch("/api/auth/login", { method: "POST", body: data });
        if (resp.ok) {
            window.location.href = "/portal/";
            return;
        }
        let msg = "Неверный логин или пароль";
        try { msg = (await resp.json()).error || msg; } catch (e) {}
        errEl.textContent = msg;
    } catch (e) {
        errEl.textContent = "Сервис входа недоступен. Попробуйте ещё раз.";
    } finally {
        btn.disabled = false;
    }
});
