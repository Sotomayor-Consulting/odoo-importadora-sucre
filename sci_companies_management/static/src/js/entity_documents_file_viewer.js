/** @odoo-module */

import { createFileViewer } from "@web/core/file_viewer/file_viewer_hook";

const fileViewer = createFileViewer();

function isTextMime(mimetype) {
    return [
        "application/javascript",
        "application/json",
        "text/css",
        "text/html",
        "text/plain",
    ].includes(mimetype);
}

function isVideoMime(mimetype) {
    return ["audio/mpeg", "video/x-matroska", "video/mp4", "video/webm"].includes(mimetype);
}

function buildFileFromElement(el) {
    const mimetype = el.dataset.mimetype || "";
    const name = el.dataset.filename || "Documento";
    const url = el.dataset.url || "";
    const downloadUrl = el.dataset.downloadUrl || url;

    const isImage = mimetype.startsWith("image/");
    const isPdf = mimetype.startsWith("application/pdf");
    const isText = isTextMime(mimetype);
    const isVideo = isVideoMime(mimetype);
    const isViewable = isImage || isPdf || isText || isVideo;

    let defaultSource = url;
    if (isPdf) {
        const encoded = encodeURIComponent(url);
        defaultSource = `/web/static/lib/pdfjs/web/viewer.html?file=${encoded}#pagemode=none`;
    }

    return {
        name,
        mimetype,
        isImage,
        isPdf,
        isText,
        isVideo,
        isViewable,
        defaultSource,
        downloadUrl,
    };
}

function openFileViewer(target) {
    const container = target.closest(".o_entity_documents_kanban") || document;
    const elements = Array.from(container.querySelectorAll(".o_entity_document_preview"));
    const files = elements.map(buildFileFromElement);
    const index = elements.indexOf(target);
    const file = files[index] || buildFileFromElement(target);

    if (!file.isViewable) {
        if (file.downloadUrl) {
            window.open(file.downloadUrl, "_blank");
        }
        return;
    }

    fileViewer.open(file, files);
}

document.addEventListener("click", (ev) => {
    const target = ev.target.closest(".o_entity_document_preview");
    if (!target) {
        return;
    }
    ev.preventDefault();
    ev.stopPropagation();
    openFileViewer(target);
});
