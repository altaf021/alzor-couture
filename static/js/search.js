(() => {
    const overlay = document.getElementById("alzorSearchOverlay");
    const openButton = document.getElementById("alzorSearchButton");
    const closeButton = document.getElementById("alzorSearchClose");
    const input = document.getElementById("alzorSearchInput");
    const form = document.getElementById("alzorSearchForm");
    const status = document.getElementById("alzorSearchStatus");
    const results = document.getElementById("alzorSearchResults");

    if (
        !overlay ||
        !openButton ||
        !closeButton ||
        !input ||
        !form ||
        !status ||
        !results
    ) {
        return;
    }

    let debounceTimer = null;
    let requestController = null;

    /* =====================================================
       OPEN SEARCH
    ===================================================== */

    function openSearch() {
        overlay.classList.add("is-open");
        overlay.setAttribute("aria-hidden", "false");

        document.body.classList.add("alzor-search-open");

        window.setTimeout(() => {
            input.focus();
            input.select();
        }, 80);

        if (!input.value.trim()) {
            status.textContent = "Search the Alzor collection";

            renderEmptyState(
                "Find your piece",
                "Search by product name, category, colour, fabric or design detail."
            );
        }
    }


    /* =====================================================
       CLOSE SEARCH
    ===================================================== */

    function closeSearch() {
        overlay.classList.remove("is-open");
        overlay.setAttribute("aria-hidden", "true");

        document.body.classList.remove("alzor-search-open");
    }


    /* =====================================================
       EMPTY STATE
    ===================================================== */

    function renderEmptyState(title, message) {
        results.innerHTML = `
            <div
                class="alzor-search-empty"
                style="grid-column: 1 / -1;"
            >
                <p>ALZOR COUTURE</p>

                <h3>
                    ${escapeHtml(title)}
                </h3>

                <p>
                    ${escapeHtml(message)}
                </p>
            </div>
        `;
    }


    /* =====================================================
       SHOW SEARCH RESULTS
    ===================================================== */

    function renderResults(items) {

        if (!items.length) {

            renderEmptyState(
                "Nothing found",
                "Try another product name, category, colour or fabric."
            );

            return;
        }


        results.innerHTML = items.map((item, index) => {

            const original =
                item.original_price != null
                    ? `
                        <span class="alzor-search-original">
                            ₹${formatPrice(item.original_price)}
                        </span>
                    `
                    : "";


            const current =
                item.price != null
                    ? `
                        <span class="alzor-search-current">
                            ₹${formatPrice(item.price)}
                        </span>
                    `
                    : `
                        <span class="alzor-search-current">
                            PRICE ON REQUEST
                        </span>
                    `;


            return `
                <a
                    class="alzor-search-result"
                    href="/product/${encodeURIComponent(item.slug)}"
                    style="
                        animation-delay:
                        ${Math.min(index, 11) * 35}ms
                    "
                >

                    <div class="alzor-search-result-image">

                        <img
                            src="${escapeAttribute(item.image)}"
                            alt="${escapeAttribute(item.name)}"
                            loading="lazy"
                        >

                    </div>


                    <div class="alzor-search-result-info">

                        <p class="alzor-search-result-category">
                            ${escapeHtml(item.category || "")}
                        </p>


                        <h3 class="alzor-search-result-name">
                            ${escapeHtml(item.name || "")}
                        </h3>


                        <div class="alzor-search-result-price">
                            ${original}
                            ${current}
                        </div>

                    </div>

                </a>
            `;

        }).join("");
    }


    /* =====================================================
       SEARCH API
    ===================================================== */

    async function performSearch(query) {

        if (requestController) {
            requestController.abort();
        }


        const controller = new AbortController();

        requestController = controller;


        status.textContent =
            `Searching for "${query}"…`;


        try {

            const response = await fetch(
                `/api/search?q=${encodeURIComponent(query)}`,
                {
                    signal: controller.signal,

                    headers: {
                        "Accept": "application/json"
                    }
                }
            );


            if (!response.ok) {
                throw new Error(
                    `Search request failed: ${response.status}`
                );
            }


            const data = await response.json();


            if (input.value.trim() !== query) {
                return;
            }


            status.textContent =
                `${data.results.length} result${
                    data.results.length === 1 ? "" : "s"
                } for "${query}"`;


            renderResults(data.results);

        }

        catch (error) {

            if (error.name === "AbortError") {
                return;
            }


            status.textContent =
                "Search unavailable";


            renderEmptyState(
                "Something went wrong",
                "Please try again in a moment."
            );
        }
    }


    /* =====================================================
       DELAY SEARCH
    ===================================================== */

    function scheduleSearch() {

        const query =
            input.value.trim();


        window.clearTimeout(
            debounceTimer
        );


        if (!query) {

            status.textContent =
                "Search the Alzor collection";


            renderEmptyState(
                "Find your piece",
                "Search by product name, category, colour, fabric or design detail."
            );

            return;
        }


        debounceTimer =
            window.setTimeout(() => {

                performSearch(query);

            }, 180);
    }


    /* =====================================================
       FORMAT PRICE
    ===================================================== */

    function formatPrice(value) {

        const number =
            Number(value);


        if (!Number.isFinite(number)) {
            return "";
        }


        return new Intl.NumberFormat(
            "en-IN"
        ).format(number);
    }


    /* =====================================================
       SECURITY HELPERS
    ===================================================== */

    function escapeHtml(value) {

        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }


    function escapeAttribute(value) {

        return escapeHtml(value);
    }


    /* =====================================================
       BUTTON EVENTS
    ===================================================== */

    openButton.addEventListener(
        "click",
        openSearch
    );


    closeButton.addEventListener(
        "click",
        closeSearch
    );


    /* =====================================================
       FORM SUBMIT
    ===================================================== */

    form.addEventListener(
        "submit",
        (event) => {

            event.preventDefault();

            scheduleSearch();
        }
    );


    /* =====================================================
       LIVE TYPING
    ===================================================== */

    input.addEventListener(
        "input",
        scheduleSearch
    );


    /* =====================================================
       CLICK OUTSIDE PANEL
    ===================================================== */

    overlay.addEventListener(
        "click",
        (event) => {

            if (event.target === overlay) {

                closeSearch();
            }
        }
    );


    /* =====================================================
       ESC KEY + "/" SHORTCUT
    ===================================================== */

    document.addEventListener(
        "keydown",
        (event) => {

            /* ESC closes search */

            if (
                event.key === "Escape" &&
                overlay.classList.contains("is-open")
            ) {

                closeSearch();
            }


            /* "/" opens search */

            if (
                event.key === "/" &&
                !event.ctrlKey &&
                !event.metaKey &&
                !event.altKey &&
                document.activeElement !== input
            ) {

                event.preventDefault();

                openSearch();
            }

        }
    );

})();