(function () {
    "use strict";

    const form = document.getElementById("checkoutForm");
    const button = document.getElementById("placeOrderButton");
    const message = document.getElementById("checkoutFormMessage");

    if (!form || !button) return;

    const fields = [
        "full_name", "last_name", "email", "phone",
        "address", "city", "state", "pincode"
    ];

    function getField(id) {
        return document.getElementById(id);
    }

    function getErrorBox(id) {
        return document.querySelector('[data-error-for="' + id + '"]');
    }

    function setMessage(text, type) {
        if (!message) return;
        message.textContent = text || "";
        message.className = "form-message full-width";
        if (type) message.classList.add(type);
    }

    function isValid(id, value) {
        const cleanValue = value.trim();
        if (!cleanValue) return false;

        if (id === "full_name" || id === "last_name") {
            return cleanValue.length >= 2;
        }
        if (id === "email") {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanValue);
        }
        if (id === "phone") {
            return /^[6-9]\d{9}$/.test(cleanValue);
        }
        if (id === "address") {
            return cleanValue.length >= 8;
        }
        if (id === "pincode") {
            return /^\d{6}$/.test(cleanValue);
        }
        return cleanValue.length >= 2;
    }

    const errorMessages = {
        full_name: "Enter your first name.",
        last_name: "Enter your last name.",
        email: "Enter a valid email address.",
        phone: "Enter a valid 10-digit Indian mobile number.",
        address: "Enter your complete delivery address.",
        city: "Enter your city.",
        state: "Enter your state.",
        pincode: "Enter a valid 6-digit PIN code."
    };

    function validateField(id, showError) {
        const input = getField(id);
        if (!input) return false;

        const value = input.value.trim();
        const valid = isValid(id, value);
        const wrapper = input.closest(".input-wrap");
        const tick = wrapper ? wrapper.querySelector(".valid-tick") : null;
        const error = getErrorBox(id);

        input.classList.toggle("field-valid", valid);
        input.classList.toggle("field-invalid", !valid && value.length > 0);
        if (tick) tick.classList.toggle("show", valid);

        if (error) {
            error.textContent = showError && !valid ? errorMessages[id] : "";
        }
        return valid;
    }

    fields.forEach(function (id) {
        const input = getField(id);
        if (!input) return;

        input.addEventListener("input", function () {
            if (id === "phone" || id === "pincode") {
                input.value = input.value.replace(/\D/g, "");
            }
            validateField(id, false);
        });

        input.addEventListener("blur", function () {
            validateField(id, true);
        });
    });

    const termsEl = document.getElementById("terms");
    if (termsEl) {
        termsEl.addEventListener("change", function () {
            if (termsEl.checked) {
                const wrap = termsEl.closest(".terms");
                if (wrap) wrap.classList.remove("terms-highlight");
                const err = document.getElementById("termsError");
                if (err) err.textContent = "";
                if (message && message.textContent.toLowerCase().includes("terms")) {
                    setMessage("", "");
                }
            }
        });
    }

    function setLoading(isLoading, text) {
        button.disabled = isLoading;
        button.classList.toggle("is-loading", isLoading);
        const buttonText = button.querySelector(".button-text");
        if (buttonText) {
            buttonText.textContent = text || (isLoading ? "PLEASE WAIT…" : "PAY SECURELY");
        }
    }

    async function postJSON(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify(payload)
        });

        let data;
        try {
            data = await response.json();
        } catch (error) {
            throw new Error("The server returned an unexpected response. Please restart Flask and try again.");
        }

        if (!response.ok || !data.success) {
            throw new Error(data.message || "Unable to process checkout.");
        }
        return data;
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        setMessage("", "");

        let valid = true;
        let firstInvalid = null;

        fields.forEach(function (id) {
            const fieldValid = validateField(id, true);
            if (!fieldValid) {
                valid = false;
                if (!firstInvalid) firstInvalid = getField(id);
            }
        });

        const terms = document.getElementById("terms");
        const termsWrap = terms ? terms.closest(".terms") : null;
        const termsError = document.getElementById("termsError");

        if (!terms || !terms.checked) {
            valid = false;
            const termsMsg = "Please accept the ALZOR COUTURE terms and conditions before continuing.";
            setMessage(termsMsg, "error");
            if (termsError) {
                termsError.textContent = "Please select this box to accept terms and conditions.";
            }
            if (termsWrap) {
                termsWrap.classList.remove("terms-highlight");
                void termsWrap.offsetWidth;
                termsWrap.classList.add("terms-highlight");
            }
            if (window.AlzorToast && typeof window.AlzorToast.warning === "function") {
                window.AlzorToast.warning(termsMsg);
            }
            if (!firstInvalid && terms) {
                firstInvalid = terms;
                terms.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }

        if (!valid) {
            if (firstInvalid) firstInvalid.focus();
            return;
        }

        if (typeof window.Razorpay !== "function") {
            setMessage("Razorpay Checkout did not load. Check your internet connection and refresh the page.", "error");
            return;
        }

        const payload = {
            first_name: getField("full_name").value.trim(),
            last_name: getField("last_name").value.trim(),
            email: getField("email").value.trim(),
            phone: getField("phone").value.trim(),
            address: getField("address").value.trim(),
            city: getField("city").value.trim(),
            state: getField("state").value.trim(),
            pincode: getField("pincode").value.trim()
        };

        setLoading(true, "STARTING PAYMENT…");
        setMessage("Preparing your secure payment…", "loading");

        try {
            const orderData = await postJSON("/create-razorpay-order", payload);
            if (!orderData.key_id || !orderData.razorpay_order_id) {
                throw new Error("Razorpay did not return the required order details. Please verify your payment configuration.");
            }

            const options = {
                key: orderData.key_id,
                amount: orderData.amount,
                currency: orderData.currency || "INR",
                name: orderData.brand || "ALZOR COUTURE",
                description: "Alzor Couture Order",
                image: window.location.origin + "/static/images/logo.png",
                order_id: orderData.razorpay_order_id,
                prefill: orderData.customer || {},
                theme: { color: "#ad8a51" },
                handler: async function (paymentResponse) {
                    setLoading(true, "VERIFYING PAYMENT…");
                    setMessage("Payment received. Verifying it securely…", "loading");

                    try {
                        const verified = await postJSON("/verify-razorpay-payment", {
                            razorpay_order_id: paymentResponse.razorpay_order_id,
                            razorpay_payment_id: paymentResponse.razorpay_payment_id,
                            razorpay_signature: paymentResponse.razorpay_signature
                        });

                        setMessage("Payment verified. Redirecting to your order…", "success");
                        window.location.href = verified.redirect_url;
                    } catch (error) {
                        setMessage(error.message || "We could not verify the payment. If money was deducted, check your Razorpay dashboard before trying to pay again.", "error");
                        setLoading(false);
                    }
                },
                modal: {
                    ondismiss: function () {
                        setLoading(false);
                        setMessage("Payment window closed. Your bag is still saved; you can try again when ready.", "error");
                    }
                }
            };

            const razorpay = new window.Razorpay(options);
            razorpay.on("payment.failed", function (response) {
                const description = response && response.error && response.error.description;
                setLoading(false);
                setMessage(description || "Payment failed. Your bag is still saved—please try again.", "error");
            });
            razorpay.open();
            setMessage("Complete your payment in the secure Razorpay window.", "loading");
        } catch (error) {
            setMessage(error.message || "Something went wrong. Please try again.", "error");
            setLoading(false);
        }
    });
})();
