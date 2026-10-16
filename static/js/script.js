/* =========================================================
   ALZOR COUTURE JAVASCRIPT
========================================================= */


/* =========================================================
   MOBILE MENU
========================================================= */

const mobileMenuButton =
    document.querySelector(".mobile-menu-button");

const mobileMenu =
    document.querySelector(".mobile-menu");


if (mobileMenuButton && mobileMenu) {

    mobileMenuButton.addEventListener(
        "click",
        () => {

            const isOpen =
                mobileMenu.classList.toggle("open");


            mobileMenuButton.classList.toggle(
                "open",
                isOpen
            );


            mobileMenuButton.setAttribute(
                "aria-expanded",
                isOpen ? "true" : "false"
            );

        }
    );


    const mobileLinks =
        mobileMenu.querySelectorAll("a");


    mobileLinks.forEach(link => {

        link.addEventListener(
            "click",
            () => {

                mobileMenu.classList.remove(
                    "open"
                );


                mobileMenuButton.classList.remove(
                    "open"
                );


                mobileMenuButton.setAttribute(
                    "aria-expanded",
                    "false"
                );

            }
        );

    });

}


/* =========================================================
   INFINITE MARQUEE
========================================================= */

const marquee =
    document.getElementById("alzorMarquee");


if (marquee) {

    const groups =
        marquee.querySelectorAll(".marquee-group");


    if (groups.length >= 2) {

        let groupWidth = 0;

        let position = 0;

        let lastTime = null;


        function measureMarquee() {

            groupWidth =
                groups[0].getBoundingClientRect().width;

        }


        function animateMarquee(timestamp) {

            if (lastTime === null) {

                lastTime = timestamp;

            }


            const delta =
                timestamp - lastTime;


            lastTime =
                timestamp;


            const speed =
                45;


            position -=
                (speed * delta) / 1000;


            if (
                groupWidth > 0 &&
                Math.abs(position) >= groupWidth
            ) {

                position +=
                    groupWidth;

            }


            marquee.style.transform =
                `translate3d(${position}px, 0, 0)`;


            requestAnimationFrame(
                animateMarquee
            );

        }


        measureMarquee();


        window.addEventListener(
            "resize",
            measureMarquee
        );


        requestAnimationFrame(
            animateMarquee
        );

    }

}


/* =========================================================
   PRODUCT GALLERY
========================================================= */

const thumbnails =
    document.querySelectorAll(".thumbnail");

const mainProductImage =
    document.getElementById("mainProductImage");


if (
    thumbnails.length &&
    mainProductImage
) {

    thumbnails.forEach(thumbnail => {

        thumbnail.addEventListener(
            "click",
            function () {

                const image =
                    this.dataset.image;


                if (!image) {
                    return;
                }


                mainProductImage.src =
                    image;


                thumbnails.forEach(item => {

                    item.classList.remove(
                        "selected"
                    );

                });


                this.classList.add(
                    "selected"
                );

            }
        );

    });

}


/* =========================================================
   SIZE SELECTION
========================================================= */

const sizeButtons =
    document.querySelectorAll(
        ".size-option"
    );


let selectedSize = null;


sizeButtons.forEach(button => {

    button.addEventListener(
        "click",
        function () {

            sizeButtons.forEach(item => {

                item.classList.remove(
                    "selected"
                );

            });


            this.classList.add(
                "selected"
            );


            selectedSize =
                this.dataset.size;

        }
    );

});


/* =========================================================
   CART COUNT
========================================================= */

function updateCartCount(count) {

    const counters =
        document.querySelectorAll(
            ".cart-count"
        );


    counters.forEach(counter => {

        counter.textContent =
            count;

    });

}


/* =========================================================
   ADD TO CART
========================================================= */

async function addProductToCart() {

    const productActions =
        document.querySelector(
            ".product-actions"
        );


    const message =
        document.getElementById(
            "cartMessage"
        );


    if (!productActions) {

        return false;

    }


    const slug =
        productActions.dataset.productSlug;


    if (!selectedSize) {

        if (message) {

            message.textContent =
                "Please select S, M or L.";

        }

        return false;

    }


    try {

        const response =
            await fetch(
                "/add-to-cart",
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({

                            slug:
                                slug,

                            size:
                                selectedSize

                        })

                }
            );


        const data =
            await response.json();


        if (!data.success) {

            if (message) {

                message.textContent =
                    data.message;

            }

            return false;

        }


        updateCartCount(
            data.cart_count
        );


        if (message) {

            message.textContent =
                `${selectedSize} added to your bag.`;

        }


        return true;

    }
    catch (error) {

        console.error(error);


        if (message) {

            message.textContent =
                "Something went wrong. Please try again.";

        }


        return false;

    }

}


/* =========================================================
   ADD TO BAG
========================================================= */

const addToBagButton =
    document.getElementById(
        "addToBagButton"
    );


if (addToBagButton) {

    addToBagButton.addEventListener(
        "click",
        async () => {

            await addProductToCart();

        }
    );

}


/* =========================================================
   BUY NOW
========================================================= */

const buyNowButton =
    document.getElementById(
        "buyNowButton"
    );


if (buyNowButton) {

    buyNowButton.addEventListener(
        "click",
        async () => {

            const success =
                await addProductToCart();


            if (success) {

                const message =
                    document.getElementById(
                        "cartMessage"
                    );


                if (message) {

                    message.textContent =
                        "Added to your bag.";

                }

            }

        }
    );

}


/* =========================================================
   CART PAGE
========================================================= */

const cartItems =
    document.querySelectorAll(".cart-item");


function formatPrice(value) {

    return "₹" +
        Number(value).toLocaleString("en-IN");

}


function updateCartItem(
    item,
    quantity
) {

    const slug =
        item.dataset.slug;


    const size =
        item.dataset.size;


    fetch(
        "/update-cart",
        {
            method:
                "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body:
                JSON.stringify({

                    slug:
                        slug,

                    size:
                        size,

                    quantity:
                        quantity

                })

        }
    )
    .then(response => response.json())
    .then(data => {

        if (!data.success) {

            return;

        }


        const quantityValue =
            item.querySelector(
                ".quantity-value"
            );


        const itemTotal =
            item.querySelector(
                ".cart-item-total"
            );


        if (quantityValue) {

            quantityValue.textContent =
                data.quantity;

        }


        if (itemTotal) {

            if (data.item_total > 0) {

                itemTotal.textContent =
                    formatPrice(
                        data.item_total
                    );

            }
            else {

                itemTotal.textContent =
                    "—";

            }

        }


        updateCartCount(
            data.cart_count
        );


        updateSummary(
            data.subtotal,
            data.cart_count
        );

    })
    .catch(error => {

        console.error(error);

    });

}


function updateSummary(
    subtotal,
    cartCount
) {

    const subtotalElement =
        document.getElementById(
            "cartSubtotal"
        );


    const countElement =
        document.getElementById(
            "summaryItemCount"
        );


    if (countElement) {

        countElement.textContent =
            cartCount;

    }


    if (subtotalElement) {

        if (subtotal > 0) {

            subtotalElement.textContent =
                formatPrice(subtotal);

        }
        else {

            subtotalElement.textContent =
                "PRICE ON REQUEST";

        }

    }

}


cartItems.forEach(item => {


    const decreaseButton =
        item.querySelector(
            ".decrease-quantity"
        );


    const increaseButton =
        item.querySelector(
            ".increase-quantity"
        );


    const removeButton =
        item.querySelector(
            ".remove-item"
        );


    const quantityElement =
        item.querySelector(
            ".quantity-value"
        );


    if (
        decreaseButton &&
        quantityElement
    ) {

        decreaseButton.addEventListener(
            "click",
            () => {

                let quantity =
                    parseInt(
                        quantityElement.textContent,
                        10
                    );


                if (quantity > 1) {

                    quantity -= 1;

                    updateCartItem(
                        item,
                        quantity
                    );

                }

            }
        );

    }


    if (
        increaseButton &&
        quantityElement
    ) {

        increaseButton.addEventListener(
            "click",
            () => {

                let quantity =
                    parseInt(
                        quantityElement.textContent,
                        10
                    );


                if (quantity < 20) {

                    quantity += 1;

                    updateCartItem(
                        item,
                        quantity
                    );

                }

            }
        );

    }


    if (removeButton) {

        removeButton.addEventListener(
            "click",
            async () => {

                const slug =
                    item.dataset.slug;


                const size =
                    item.dataset.size;


                try {

                    const response =
                        await fetch(
                            "/remove-from-cart",
                            {
                                method:
                                    "POST",

                                headers: {
                                    "Content-Type":
                                        "application/json"
                                },

                                body:
                                    JSON.stringify({

                                        slug:
                                            slug,

                                        size:
                                            size

                                    })

                            }
                        );


                    const data =
                        await response.json();


                    if (!data.success) {

                        return;

                    }


                    item.remove();


                    updateCartCount(
                        data.cart_count
                    );


                    updateSummary(
                        data.subtotal,
                        data.cart_count
                    );


                    if (
                        data.cart_count === 0
                    ) {

                        window.location.reload();

                    }

                }
                catch (error) {

                    console.error(error);

                }

            }
        );

    }

});


/* =========================================================
   CLEAR BAG
========================================================= */

const clearCartButton =
    document.getElementById(
        "clearCartButton"
    );


if (clearCartButton) {

    clearCartButton.addEventListener(
        "click",
        async () => {

            try {

                const response =
                    await fetch(
                        "/clear-cart",
                        {
                            method:
                                "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            }

                        }
                    );


                const data =
                    await response.json();


                if (data.success) {

                    updateCartCount(0);

                    window.location.reload();

                }

            }
            catch (error) {

                console.error(error);

            }

        }
    );

}


/* =========================================================
   CHECKOUT
========================================================= */

const checkoutButton =
    document.getElementById(
        "checkoutButton"
    );


if (checkoutButton) {

    checkoutButton.addEventListener(
        "click",
        () => {

            alert(
                "Checkout will be connected next."
            );

        }
    );

}


/* =========================================================
   WISHLIST
========================================================= */

const wishlistButtons =
    document.querySelectorAll(
        ".wishlist-button"
    );


wishlistButtons.forEach(button => {

    button.addEventListener(
        "click",
        function () {

            if (
                this.textContent.trim() === "♡"
            ) {

                this.textContent =
                    "♥";

            }
            else {

                this.textContent =
                    "♡";

            }

        }
    );

});


/* =========================================================
   SEARCH
========================================================= */

<button
    type="button"
    class="header-action search-button alzor-icon-button"
    id="alzorSearchButton"
    aria-label="Open search"
    aria-controls="alzorSearchOverlay"
>
    <svg
        class="alzor-header-icon alzor-search-header-icon"
        viewBox="0 0 32 32"
        aria-hidden="true"
    >
        <circle
            cx="13.5"
            cy="13.5"
            r="8.2"
        ></circle>

        <path
            d="M19.5 19.5 L27 27"
        ></path>
    </svg>
</button>


/* =========================================================
   NEWSLETTER
========================================================= */

const newsletterForms =
    document.querySelectorAll(
        ".newsletter-form"
    );


newsletterForms.forEach(form => {

    form.addEventListener(
        "submit",
        event => {

            event.preventDefault();


            const input =
                form.querySelector(
                    "input"
                );


            if (
                !input ||
                !input.value.trim()
            ) {

                return;

            }


            alert(
                "Welcome to Alzor World."
            );


            form.reset();

        }
    );

});