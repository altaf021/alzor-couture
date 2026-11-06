/* =========================================================
   ALZOR COUTURE - LUXURY CART TOAST CONTROLLER
   ========================================================= */

(function () {
    "use strict";

    let container = null;

    function getContainer() {
        if (!container || !document.body.contains(container)) {
            container = document.createElement("div");
            container.className = "alzor-toast-container";
            container.setAttribute("role", "region");
            container.setAttribute("aria-label", "Shopping Bag Notifications");
            document.body.appendChild(container);
        }
        return container;
    }

    function formatCurrency(val) {
        const num = Number(val);
        if (!Number.isFinite(num)) return "";
        return "₹" + new Intl.NumberFormat("en-IN").format(num);
    }

    function createToastElement(options) {
        const isError = options.type === "error";
        const isWarning = options.type === "warning";

        const toast = document.createElement("div");
        toast.className = "alzor-toast" +
            (isError ? " alzor-toast-error" : "") +
            (isWarning ? " alzor-toast-warning" : "");
        toast.setAttribute("role", "alert");
        toast.setAttribute("aria-live", "polite");

        const iconSvg = isError
            ? '<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>'
            : isWarning
            ? '<svg viewBox="0 0 24 24"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>'
            : '<svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>';

        const badgeText = isError
            ? "NOTICE"
            : isWarning
            ? "ATTENTION"
            : "ADDED TO BAG";

        const titleText = options.title || (isError ? "Notification" : options.productName || "Piece Added");
        const priceFormatted = options.price ? formatCurrency(options.price) : "";
        const metaParts = [];
        if (options.size) metaParts.push("SIZE: " + options.size);
        if (priceFormatted) metaParts.push(priceFormatted);
        const metaText = metaParts.join(" • ");

        let messageText = options.message;
        if (!messageText) {
            if (options.productName) {
                messageText = options.productName + (options.size ? " (Size " + options.size + ")" : "") + " added to your cart successfully.";
            } else {
                messageText = "Your piece has been added to your bag.";
            }
        }

        let imageHtml = "";
        if (options.image) {
            let imgSource = options.image;
            if (!imgSource.startsWith("http") && !imgSource.startsWith("/")) {
                imgSource = "/static/images/" + imgSource;
            }
            imageHtml = `
                <div class="alzor-toast-image">
                    <img src="${imgSource}" alt="${titleText}" loading="eager" />
                </div>
            `;
        }

        const actionsHtml = !isError && !isWarning
            ? `
                <div class="alzor-toast-actions">
                    <a href="/cart" class="alzor-toast-btn-view">VIEW BAG</a>
                    <button type="button" class="alzor-toast-btn-continue" data-toast-dismiss>CONTINUE SHOPPING</button>
                </div>
            `
            : "";

        toast.innerHTML = `
            <div class="alzor-toast-header">
                <span class="alzor-toast-badge">
                    ${iconSvg}
                    <span>${badgeText}</span>
                </span>
                <button type="button" class="alzor-toast-close" aria-label="Close notification" data-toast-dismiss>&times;</button>
            </div>
            <div class="alzor-toast-body">
                ${imageHtml}
                <div class="alzor-toast-details">
                    <h4 class="alzor-toast-title">${titleText}</h4>
                    ${metaText ? `<p class="alzor-toast-meta">${metaText}</p>` : ""}
                    <p class="alzor-toast-message">${messageText}</p>
                </div>
            </div>
            ${actionsHtml}
            <div class="alzor-toast-progress"></div>
        `;

        return toast;
    }

    function show(options) {
        options = options || {};
        const duration = typeof options.duration === "number" ? options.duration : 6500;
        const parent = getContainer();

        // Dismiss existing toasts
        const existingToasts = parent.querySelectorAll(".alzor-toast");
        existingToasts.forEach(function (el) {
            el.classList.add("alzor-toast-hiding");
            setTimeout(function () {
                if (el.parentNode) el.remove();
            }, 250);
        });

        const toast = createToastElement(options);
        parent.appendChild(toast);

        // Update cart counters everywhere
        if (typeof options.cartCount !== "undefined" && options.cartCount !== null) {
            document.querySelectorAll(".cart-count").forEach(function (countEl) {
                countEl.textContent = options.cartCount;
                countEl.classList.add("cart-count-bump");
                setTimeout(function () {
                    countEl.classList.remove("cart-count-bump");
                }, 300);
            });
        }

        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                toast.classList.add("alzor-toast-visible");
            });
        });

        const progressBar = toast.querySelector(".alzor-toast-progress");
        let startTime = Date.now();
        let remaining = duration;
        let timer = null;
        let isPaused = false;

        function startTimer() {
            if (progressBar) {
                progressBar.style.transition = "transform " + remaining + "ms linear";
                progressBar.style.transform = "scaleX(0)";
            }
            timer = setTimeout(dismiss, remaining);
        }

        function pauseTimer() {
            if (isPaused) return;
            isPaused = true;
            clearTimeout(timer);
            remaining -= (Date.now() - startTime);
            if (remaining < 600) remaining = 600;
            if (progressBar) {
                const computed = window.getComputedStyle(progressBar);
                const transform = computed.transform;
                progressBar.style.transition = "none";
                progressBar.style.transform = transform;
            }
        }

        function resumeTimer() {
            if (!isPaused) return;
            isPaused = false;
            startTime = Date.now();
            startTimer();
        }

        function dismiss() {
            clearTimeout(timer);
            toast.classList.remove("alzor-toast-visible");
            toast.classList.add("alzor-toast-hiding");
            setTimeout(function () {
                if (toast.parentNode) toast.remove();
            }, 350);
        }

        toast.querySelectorAll("[data-toast-dismiss]").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                dismiss();
            });
        });

        toast.addEventListener("mouseenter", pauseTimer);
        toast.addEventListener("mouseleave", resumeTimer);

        startTimer();

        return { dismiss: dismiss };
    }

    window.AlzorToast = {
        show: show,
        success: function (data) {
            data = data || {};
            return show({
                type: "success",
                productName: data.product_name || data.name,
                size: data.size,
                price: data.price,
                image: data.image,
                cartCount: (typeof data.cart_count !== "undefined") ? data.cart_count : data.cartCount,
                message: data.message
            });
        },
        error: function (message) {
            return show({
                type: "error",
                title: "Error",
                message: message || "Something went wrong. Please try again.",
                duration: 4500
            });
        },
        warning: function (message) {
            return show({
                type: "warning",
                title: "Attention",
                message: message,
                duration: 4500
            });
        }
    };
})();
