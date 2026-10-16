(function () {
    "use strict";

    const overlay = document.getElementById("alzorQuickAddOverlay");
    if (!overlay) return;

    const nameEl = document.getElementById("alzorQuickAddName");
    const sizeWrap = document.getElementById("alzorQuickAddSizes");
    const messageEl = document.getElementById("alzorQuickAddMessage");
    const confirmButton = document.getElementById("alzorQuickAddConfirm");
    const viewButton = document.getElementById("alzorQuickAddView");
    const closeButton = document.getElementById("alzorQuickAddClose");

    // GLOBAL SIZES FOR ALL PRODUCTS
    const sizes = ["S", "M", "L", "XL", "XXL"];

    let activeSlug = "";
    let activeName = "";
    let activeSize = "";

    // =====================================================
    // OPEN QUICK-ADD MODAL
    // =====================================================

    function openModal(button) {
        activeSlug = button.dataset.quickAddSlug || "";
        activeName = button.dataset.quickAddName || "";
        activeSize = "";

        nameEl.textContent = activeName;
        messageEl.textContent = "";
        sizeWrap.innerHTML = "";

        // Create size buttons
        sizes.forEach(function (size) {
            const sizeButton = document.createElement("button");

            sizeButton.type = "button";
            sizeButton.className = "alzor-quick-add-size";
            sizeButton.textContent = size;

            sizeButton.addEventListener("click", function () {

                sizeWrap
                    .querySelectorAll(".alzor-quick-add-size")
                    .forEach(function (item) {
                        item.classList.remove("is-selected");
                    });

                sizeButton.classList.add("is-selected");

                activeSize = size;

                messageEl.textContent = "";
            });

            sizeWrap.appendChild(sizeButton);
        });

        overlay.classList.add("is-open");
        overlay.setAttribute("aria-hidden", "false");

        document.body.classList.add("alzor-quick-add-lock");

        const firstSize = sizeWrap.querySelector("button");

        if (firstSize) {
            firstSize.focus();
        }
    }


    // =====================================================
    // CLOSE MODAL
    // =====================================================

    function closeModal() {
        overlay.classList.remove("is-open");
        overlay.setAttribute("aria-hidden", "true");

        document.body.classList.remove("alzor-quick-add-lock");

        activeSlug = "";
        activeName = "";
        activeSize = "";
    }


    // =====================================================
    // QUICK-ADD BUTTONS
    // =====================================================

    document
        .querySelectorAll("[data-quick-add-slug]")
        .forEach(function (button) {

            button.addEventListener("click", function (event) {

                event.preventDefault();
                event.stopPropagation();

                openModal(button);
            });

        });


    // =====================================================
    // CLOSE EVENTS
    // =====================================================

    overlay
        .querySelectorAll("[data-quick-add-close]")
        .forEach(function (element) {

            element.addEventListener("click", closeModal);

        });


    closeButton.addEventListener("click", closeModal);


    // =====================================================
    // ESCAPE KEY
    // =====================================================

    document.addEventListener("keydown", function (event) {

        if (
            event.key === "Escape" &&
            overlay.classList.contains("is-open")
        ) {
            closeModal();
        }

    });


    // =====================================================
    // ADD TO BAG
    // =====================================================

    confirmButton.addEventListener("click", async function () {

        if (!activeSlug) {
            return;
        }

        // Make sure customer selected a size
        if (!activeSize) {

            messageEl.textContent =
                "Please select a size first.";

            return;
        }


        confirmButton.disabled = true;

        messageEl.textContent =
            "ADDING TO BAG…";


        try {

            const response = await fetch(
                "/add-to-cart",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        slug: activeSlug,
                        size: activeSize
                    })
                }
            );


            const data =
                await response.json();


            if (
                !response.ok ||
                !data.success
            ) {

                messageEl.textContent =
                    data.message ||
                    "Unable to add this piece.";

                return;
            }


            // Update cart count everywhere
            document
                .querySelectorAll(".cart-count")
                .forEach(function (count) {

                    count.textContent =
                        data.cart_count;

                });


            messageEl.textContent =
                "ADDED TO YOUR BAG.";

        }


        catch (error) {

            messageEl.textContent =
                "Something went wrong. Please try again.";

        }


        finally {

            confirmButton.disabled = false;

        }

    });


    // =====================================================
    // VIEW PRODUCT
    // =====================================================

    viewButton.addEventListener("click", function () {

        if (!activeSlug) {
            return;
        }

        window.location.href =
            "/product/" +
            encodeURIComponent(activeSlug);

    });

})();