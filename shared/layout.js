// Единый шаблон шапки для всех страниц (light DOM — применяется shared/theme.css).
// Использование: <app-header title="…" subtitle="…" badge="📝" logo="logo.jpg" back="/portal/"></app-header>
// back="none" — скрыть кнопку «В меню» (для главной портала).
class AppHeader extends HTMLElement {
    connectedCallback() {
        const title = this.getAttribute("title") || "";
        const subtitle = this.getAttribute("subtitle") || "";
        const badge = this.getAttribute("badge") || "";
        const logo = this.getAttribute("logo") || "";
        const back = this.getAttribute("back");
        const backHref = back === null ? "/portal/" : back;
        const showBack = backHref && backHref !== "none";

        this.innerHTML =
            (showBack ? `<a class="app-back" href="${backHref}">← В меню</a>` : "") +
            `<a class="app-logout" href="#">Выйти</a>` +
            `<div class="app-header-bar">` +
                (logo ? `<img class="app-logo" src="${logo}" alt="" onerror="this.style.display='none'">` : "") +
                (badge ? `<div class="app-badge">${badge}</div>` : "") +
                `<h1>${title}</h1>` +
                (subtitle ? `<p class="app-sub">${subtitle}</p>` : "") +
            `</div>`;

        const logout = this.querySelector(".app-logout");
        if (logout) {
            logout.addEventListener("click", async (e) => {
                e.preventDefault();
                try { await fetch("/api/auth/logout", { method: "POST" }); } catch (err) {}
                window.location.href = "/login/";
            });
        }
    }
}
customElements.define("app-header", AppHeader);
