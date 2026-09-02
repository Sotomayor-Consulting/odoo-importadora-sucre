/** @odoo-module **/

import { Many2ManyBinaryField, many2ManyBinaryField } from "@web/views/fields/many2many_binary/many2many_binary_field";
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";

export class ConfirmMany2ManyBinaryField extends Many2ManyBinaryField {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    onFileRemove(file) {
        this.dialog.add(ConfirmationDialog, {
            body: "¿Estás seguro de que deseas eliminar este documento?",
            title: "Confirmación de eliminación",
            confirm: () => {
                super.onFileRemove(file);
            },
            cancel: () => {},
        });
    }
}

export const confirmMany2ManyBinaryField = {
    ...many2ManyBinaryField,
    component: ConfirmMany2ManyBinaryField,
    displayName: "Many2Many Binary (con confirmación)",
};

registry.category("fields").add("many2many_binary_confirm", confirmMany2ManyBinaryField);
