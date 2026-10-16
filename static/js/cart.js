/* =========================================================
   ALZOR COUTURE
   CART SYSTEM
========================================================= */

(() => {

    "use strict";


    /* =====================================================
       ELEMENTS
    ===================================================== */

    const cartItems = document.querySelectorAll("[data-cart-item]");

    const clearCartButton =
        document.getElementById("clearCartButton");

    const summaryItemCount =
        document.getElementById("summaryItemCount");

    const summarySubtotal =
        document.getElementById("summarySubtotal");

    const summaryTotal =
        document.getElementById("summaryTotal");

    const checkoutButton =
        document.getElementById("checkoutButton");


    /* =====================================================
       HELPERS
    ===================================================== */

    function money(value) {

        const number = Number(value);

        if (!Number.isFinite(number)) {
            return "₹0";
        }

        return "₹" + new Intl.NumberFormat("en-IN").format(number);

    }


    function updateHeaderCount(count) {

        document
            .querySelectorAll(".cart-count")
            .forEach((element) => {

                element.textContent = count;

            });

    }


    function updateSummary(subtotal, cartCount) {

        if (summaryItemCount) {
            summaryItemCount.textContent = cartCount;
        }

        if (summarySubtotal) {
            summarySubtotal.textContent = money(subtotal);
        }

        if (summaryTotal) {
            summaryTotal.textContent = money(subtotal);
        }

        updateHeaderCount(cartCount);

    }


    function showMessage(message, type = "normal") {

        const existing =
            document.querySelector(".cart-floating-message");

        if (existing) {
            existing.remove();
        }


        const notice =
            document.createElement("div");

        notice.className =
            "cart-floating-message " + type;

        notice.textContent = message;


        document.body.appendChild(notice);


        window.setTimeout(() => {

            notice.classList.add("show");

        }, 20);


        window.setTimeout(() => {

            notice.classList.remove("show");

        }, 2200);


        window.setTimeout(() => {

            notice.remove();

        }, 2700);

    }


    async function postJSON(url, data = {}) {

        const response =
            await fetch(url, {

                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json"
                },

                body: JSON.stringify(data)

            });


        let result = null;

        try {

            result = await response.json();

        } catch (error) {

            throw new Error(
                "The server returned an invalid response."
            );

        }


        if (!response.ok || !result.success) {

            throw new Error(
                result.message ||
                "The request could not be completed."
            );

        }


        return result;

    }


    /* =====================================================
       QUANTITY
    ===================================================== */

    async function changeQuantity(item, direction) {

        const slug =
            item.dataset.slug;

        const size =
            item.dataset.size;

        const quantityElement =
            item.querySelector(".quantity-value");

        const itemTotalElement =
            item.querySelector(".cart-item-total");

        const buttons =
            item.querySelectorAll(".quantity-button");


        if (
            !slug ||
            !size ||
            !quantityElement
        ) {
            return;
        }


        const currentQuantity =
            Number(quantityElement.textContent);


        if (!Number.isFinite(currentQuantity)) {
            return;
        }


        let newQuantity =
            currentQuantity + direction;


        if (newQuantity < 1) {
            newQuantity = 1;
        }


        if (newQuantity > 20) {
            newQuantity = 20;
        }


        if (newQuantity === currentQuantity) {

            if (newQuantity === 20) {
                showMessage("Maximum quantity is 20.");
            }

            return;

        }


        buttons.forEach((button) => {

            button.disabled = true;

        });


        item.classList.add("is-updating");


        try {

            const result =
                await postJSON(
                    "/update-cart",
                    {
                        slug: slug,
                        size: size,
                        quantity: newQuantity
                    }
                );


            quantityElement.textContent =
                result.quantity;


            if (itemTotalElement) {

                itemTotalElement.textContent =
                    money(result.item_total);

            }


            updateSummary(
                result.subtotal,
                result.cart_count
            );


            showMessage("Bag updated.");

        } catch (error) {

            showMessage(
                error.message ||
                "Unable to update your bag.",
                "error"
            );

        } finally {

            item.classList.remove("is-updating");

            buttons.forEach((button) => {

                button.disabled = false;

            });

        }

    }


    /* =====================================================
       REMOVE ITEM
    ===================================================== */

    async function removeItem(item) {

        const slug =
            item.dataset.slug;

        const size =
            item.dataset.size;


        if (!slug || !size) {
            return;
        }


        const removeButton =
            item.querySelector(
                '[data-action="remove"]'
            );


        if (removeButton) {
            removeButton.disabled = true;
        }


        item.classList.add("is-removing");


        try {

            const result =
                await postJSON(
                    "/remove-from-cart",
                    {
                        slug: slug,
                        size: size
                    }
                );


            updateSummary(
                result.subtotal,
                result.cart_count
            );


            await new Promise((resolve) => {

                window.setTimeout(
                    resolve,
                    350
                );

            });


            item.remove();


            const remaining =
                document.querySelectorAll(
                    "[data-cart-item]"
                );


            if (!remaining.length) {

                window.location.reload();

                return;

            }


            showMessage(
                "Piece removed from your bag."
            );

        } catch (error) {

            item.classList.remove("is-removing");


            if (removeButton) {
                removeButton.disabled = false;
            }


            showMessage(
                error.message ||
                "Unable to remove this piece.",
                "error"
            );

        }

    }


    /* =====================================================
       CLEAR CART
    ===================================================== */

    async function clearCart() {

        if (!clearCartButton) {
            return;
        }


        const confirmed =
            window.confirm(
                "Remove all pieces from your shopping bag?"
            );


        if (!confirmed) {
            return;
        }


        clearCartButton.disabled = true;

        clearCartButton.textContent =
            "CLEARING…";


        try {

            await postJSON(
                "/clear-cart",
                {}
            );


            showMessage(
                "Your bag has been cleared."
            );


            window.setTimeout(() => {

                window.location.reload();

            }, 350);


        } catch (error) {

            clearCartButton.disabled = false;

            clearCartButton.textContent =
                "CLEAR BAG";


            showMessage(
                error.message ||
                "Unable to clear your bag.",
                "error"
            );

        }

    }


    /* =====================================================
       EVENT HANDLERS
    ===================================================== */

    cartItems.forEach((item) => {

        const buttons =
            item.querySelectorAll(
                "[data-action]"
            );


        buttons.forEach((button) => {

            button.addEventListener(
                "click",
                () => {

                    const action =
                        button.dataset.action;


                    if (action === "increase") {

                        changeQuantity(
                            item,
                            1
                        );

                    }


                    if (action === "decrease") {

                        changeQuantity(
                            item,
                            -1
                        );

                    }


                    if (action === "remove") {

                        removeItem(item);

                    }

                }
            );

        });

    });


    if (clearCartButton) {

        clearCartButton.addEventListener(
            "click",
            clearCart
        );

    }


    /* =====================================================
       CHECKOUT GUARD
    ===================================================== */

    if (checkoutButton) {

        checkoutButton.addEventListener(
            "click",
            (event) => {

                const items =
                    document.querySelectorAll(
                        "[data-cart-item]"
                    );


                if (!items.length) {

                    event.preventDefault();

                    showMessage(
                        "Your shopping bag is empty.",
                        "error"
                    );

                }

            }
        );

    }


    /* =====================================================
       SMALL DYNAMIC STYLES
    ===================================================== */

    const dynamicStyle =
        document.createElement("style");


    dynamicStyle.textContent = `

        .cart-floating-message {
            position: fixed;
            left: 50%;
            bottom: 28px;
            z-index: 100000;

            min-width: 230px;
            max-width: 90vw;

            padding: 14px 20px;

            background: #181818;
            color: #ffffff;

            border: 1px solid rgba(173,138,81,.55);

            box-shadow:
                0 18px 50px rgba(0,0,0,.18);

            font-family:
                Arial,
                Helvetica,
                sans-serif;

            font-size: 9px;
            font-weight: 500;

            letter-spacing: 1.5px;

            text-align: center;

            opacity: 0;

            transform:
                translate(-50%, 15px);

            pointer-events: none;

            transition:
                opacity .3s ease,
                transform .3s ease;
        }


        .cart-floating-message.show {
            opacity: 1;

            transform:
                translate(-50%, 0);
        }


        .cart-floating-message.error {
            border-color:
                rgba(164,93,82,.75);
        }


        .cart-item {
            transition:
                opacity .35s ease,
                transform .35s ease;
        }


        .cart-item.is-updating {
            opacity: .55;
        }


        .cart-item.is-removing {
            opacity: 0;
            transform:
                translateX(25px);
        }


        .quantity-button:disabled {
            cursor: wait;
            opacity: .45;
        }


        .clear-cart-button:disabled {
            cursor: wait;
            opacity: .55;
        }

    `;


    document.head.appendChild(
        dynamicStyle
    );


})();