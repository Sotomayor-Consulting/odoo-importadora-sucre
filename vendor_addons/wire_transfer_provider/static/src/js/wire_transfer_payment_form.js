/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PaymentForm } from "@payment/interactions/payment_form";

const ROOT_SELECTOR = '[data-wire-inline-root="1"]';
const FILE_SELECTOR = '[data-wire-receipt-file="1"]';
const REF_SELECTOR = '[data-wire-reference="1"]';
const DROPZONE_SELECTOR = '[data-wire-dropzone="1"]';
const FILE_TRIGGER_SELECTOR = '[data-wire-file-trigger="1"]';
const SELECTED_FILE_SELECTOR = '[data-wire-selected-file="1"]';
const SELECTED_NAME_SELECTOR = '[data-wire-selected-name="1"]';
const SELECTED_IMAGE_SELECTOR = '[data-wire-selected-image="1"]';
const LOCAL_PREVIEW_SELECTOR = '[data-wire-local-preview="1"]';
const CLEAR_FILE_SELECTOR = '[data-wire-clear-file="1"]';
const ALLOWED_EXTENSIONS = ["pdf", "png", "jpg", "jpeg"];

function ensureToastContainer() {
    let container = document.getElementById("wire-transfer-toast-container");
    if (container) {
        return container;
    }
    container = document.createElement("div");
    container.id = "wire-transfer-toast-container";
    container.className = "toast-container position-fixed top-0 end-0 p-3";
    container.style.zIndex = "1085";
    document.body.appendChild(container);
    return container;
}

function showToast(message, level = "error") {
    if (!message) {
        return;
    }
    const container = ensureToastContainer();
    const toastEl = document.createElement("div");
    const isError = level === "error";
    toastEl.className = `toast align-items-center text-bg-${isError ? "danger" : "success"} border-0`;
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body"></div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    toastEl.querySelector(".toast-body").textContent = message;
    container.appendChild(toastEl);
    if (window.bootstrap && window.bootstrap.Toast) {
        const toast = new window.bootstrap.Toast(toastEl, { delay: 5000 });
        toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
        toast.show();
    } else {
        window.setTimeout(() => toastEl.remove(), 5000);
    }
}

function extensionOf(file) {
    const parts = (file?.name || "").toLowerCase().split(".");
    return parts.length > 1 ? parts.pop() : "";
}

function toBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const result = String(reader.result || "");
            resolve(result.includes(",") ? result.split(",")[1] : result);
        };
        reader.onerror = () => reject(new Error("file_read_error"));
        reader.readAsDataURL(file);
    });
}

function mimetypeFromFile(file) {
    const extension = extensionOf(file);
    if (extension === "pdf") return "application/pdf";
    if (extension === "png") return "image/png";
    if (extension === "jpg" || extension === "jpeg") return "image/jpeg";
    return file?.type || "application/octet-stream";
}

function renderSelectedFile(root) {
    if (!root) {
        return;
    }
    const fileInput = root.querySelector(FILE_SELECTOR);
    const dropzone = root.querySelector(DROPZONE_SELECTOR);
    const card = root.querySelector(SELECTED_FILE_SELECTOR);
    const nameNode = root.querySelector(SELECTED_NAME_SELECTOR);
    const imageNode = root.querySelector(SELECTED_IMAGE_SELECTOR);
    const previewLink = root.querySelector(LOCAL_PREVIEW_SELECTOR);
    const file = fileInput?.files?.[0];
    const previousUrl = root.dataset.wireObjectUrl;

    if (previousUrl) {
        URL.revokeObjectURL(previousUrl);
        delete root.dataset.wireObjectUrl;
    }

    if (!file || !card) {
        card?.classList.add("d-none");
        dropzone?.classList.remove("d-none");
        if (previewLink) {
            previewLink.removeAttribute("href");
        }
        return;
    }

    const objectUrl = URL.createObjectURL(file);
    root.dataset.wireObjectUrl = objectUrl;
    const mimetype = mimetypeFromFile(file);

    if (imageNode) {
        imageNode.dataset.mimetype = mimetype;
        imageNode.title = file.name;
    }
    if (nameNode) {
        nameNode.textContent = file.name;
    }
    if (previewLink) {
        previewLink.setAttribute("href", objectUrl);
    }
    card.classList.remove("d-none");
    dropzone?.classList.add("d-none");
}

function attachDropzoneBehavior(root) {
    if (!root || root.dataset.wireDropzoneReady === "1") {
        return;
    }
    root.dataset.wireDropzoneReady = "1";

    const dropzone = root.querySelector(DROPZONE_SELECTOR);
    const fileInput = root.querySelector(FILE_SELECTOR);
    const trigger = root.querySelector(FILE_TRIGGER_SELECTOR);
    const clearBtn = root.querySelector(CLEAR_FILE_SELECTOR);
    if (!dropzone || !fileInput) {
        return;
    }

    const setDragged = (dragged) => {
        dropzone.classList.toggle("border-primary", dragged);
        dropzone.classList.toggle("bg-primary-subtle", dragged);
    };

    dropzone.addEventListener("click", (ev) => {
        if (ev.target.closest(FILE_TRIGGER_SELECTOR) || ev.target.closest(CLEAR_FILE_SELECTOR)) {
            return;
        }
        fileInput.click();
    });
    trigger?.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        fileInput.click();
    });

    ["dragenter", "dragover"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (ev) => {
            ev.preventDefault();
            setDragged(true);
        });
    });
    ["dragleave", "drop"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (ev) => {
            ev.preventDefault();
            setDragged(false);
        });
    });
    dropzone.addEventListener("drop", (ev) => {
        const file = ev.dataTransfer?.files?.[0];
        if (!file) {
            return;
        }
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
        renderSelectedFile(root);
    });

    fileInput.addEventListener("change", () => renderSelectedFile(root));
    clearBtn?.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        fileInput.value = "";
        renderSelectedFile(root);
        fileInput.classList.remove("is-invalid");
    });
}

function getWireRoot(form, radio) {
    if (!form || !radio) {
        return null;
    }
    const providerId = radio.dataset.providerId || radio.getAttribute("data-provider-id") || "";
    if (!providerId) {
        return null;
    }
    return form.querySelector(`${ROOT_SELECTOR}[data-wire-provider-id="${providerId}"]`);
}

function validateWireRoot(root) {
    if (!root) {
        return { ok: true };
    }
    const isRequired = root.dataset.wireReceiptRequired === "1";
    const maxSizeMb = parseInt(root.dataset.wireMaxSizeMb || "2", 10) || 2;
    const maxBytes = maxSizeMb * 1024 * 1024;

    const refInput = root.querySelector(REF_SELECTOR);
    const fileInput = root.querySelector(FILE_SELECTOR);
    const file = fileInput?.files?.[0];

    refInput?.classList.remove("is-invalid");
    fileInput?.classList.remove("is-invalid");

    if (isRequired && !(refInput?.value || "").trim()) {
        refInput?.classList.add("is-invalid");
        return { ok: false, message: _t("La referencia del comprobante es obligatoria.") };
    }
    if (isRequired && !file) {
        fileInput?.classList.add("is-invalid");
        return { ok: false, message: _t("Debes adjuntar un comprobante para continuar.") };
    }
    if (!file) {
        return { ok: true };
    }
    if (file.size > maxBytes) {
        fileInput?.classList.add("is-invalid");
        return { ok: false, message: _t("El archivo supera el tamano maximo de %s MB.", maxSizeMb) };
    }
    if (!ALLOWED_EXTENSIONS.includes(extensionOf(file))) {
        fileInput?.classList.add("is-invalid");
        return { ok: false, message: _t("Solo se permiten archivos PDF, PNG, JPG o JPEG.") };
    }
    return { ok: true };
}

patch(PaymentForm.prototype, {
    setup() {
        super.setup(...arguments);
        this._wireDropzoneObserver = null;
    },

    start() {
        const result = super.start(...arguments);
        const initDropzones = () => {
            this.el.querySelectorAll(ROOT_SELECTOR).forEach((root) => attachDropzoneBehavior(root));
        };
        initDropzones();
        this._wireDropzoneObserver = new MutationObserver(() => initDropzones());
        this._wireDropzoneObserver.observe(this.el, { childList: true, subtree: true });
        return result;
    },

    destroy() {
        this._wireDropzoneObserver?.disconnect();
        this.el.querySelectorAll(ROOT_SELECTOR).forEach((root) => {
            const objectUrl = root.dataset.wireObjectUrl;
            if (objectUrl) {
                URL.revokeObjectURL(objectUrl);
                delete root.dataset.wireObjectUrl;
            }
        });
        return super.destroy(...arguments);
    },

    async _initiatePaymentFlow(providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== "wire_transfer_provider") {
            return super._initiatePaymentFlow(providerCode, paymentOptionId, paymentMethodCode, flow);
        }
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        const root = getWireRoot(this.el, checkedRadio);
        attachDropzoneBehavior(root);
        const validation = validateWireRoot(root);
        if (!validation.ok) {
            showToast(validation.message, "error");
            this._enableButton();
            return;
        }
        this._wirePayload = null;
        if (root) {
            const fileInput = root.querySelector(FILE_SELECTOR);
            const refInput = root.querySelector(REF_SELECTOR);
            const file = fileInput?.files?.[0];
            this._wirePayload = {
                reference: (refInput?.value || "").trim(),
                filename: file?.name || "",
                mimetype: file?.type || "application/octet-stream",
                content: file ? await toBase64(file) : "",
            };
        }
        return super._initiatePaymentFlow(providerCode, paymentOptionId, paymentMethodCode, flow);
    },

    _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== "wire_transfer_provider") {
            return super._processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues);
        }
        const div = document.createElement("div");
        div.innerHTML = processingValues.redirect_form_html;
        const redirectForm = div.querySelector("form");
        const payload = this._wirePayload || {};
        const hiddenFields = {
            wire_reference: payload.reference || "",
            wire_receipt_filename: payload.filename || "",
            wire_receipt_mimetype: payload.mimetype || "",
            wire_receipt_content: payload.content || "",
        };
        for (const [name, value] of Object.entries(hiddenFields)) {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = name;
            input.value = value;
            redirectForm.appendChild(input);
        }
        redirectForm.setAttribute("id", "o_payment_redirect_form");
        redirectForm.setAttribute("target", "_top");
        document.body.appendChild(redirectForm);
        redirectForm.submit();
    },
});
