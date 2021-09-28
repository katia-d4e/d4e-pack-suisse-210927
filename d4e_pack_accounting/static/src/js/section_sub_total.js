odoo.define('d4e_pack_accounting.section_and_note_subtotal_backend', function (require) {
"use strict";

const SectionAndNoteListRenderer = require('account.section_and_note_backend');
const { format } = require('web.field_utils');

SectionAndNoteListRenderer.include({
    _renderBodyCell: function (record, node, index, options) {
        var $cell = this._super.apply(this, arguments);
        var displayType = record.data.display_type;
        var isSection = displayType === 'line_section';
        var isNote = displayType === 'line_note';
        var isSectionSubTotal = displayType === 'line_section_sub_total';
        var isSubTotal = displayType === 'line_sub_total';
        var isTitle = displayType === 'line_title';
        if (isSection || isNote || isTitle) {
            if (node.attrs.widget === "handle") {
                return $cell;
            } else if (node.attrs.name === "name") {
                var nbrColumns = this._getNumberOfCols();
                if (this.handleField) {
                    nbrColumns--;
                }
                if (this.addTrashIcon) {
                    nbrColumns--;
                }
                $cell.attr('colspan', nbrColumns);
            } else {
                $cell.removeClass('o_invisible_modifier');
                return $cell.addClass('o_hidden');
            }
        } else if (isSectionSubTotal || isSubTotal) {
            var fieldName = (record.data.tax_selection === 'tax_included') ? 'price_total' : 'price_subtotal';
            if (node.attrs.widget === "handle") {
                return $cell;
            } else if (node.attrs.name === "name") {
                var nbrColumns = this._getNumberOfCols() - 1;
                if (this.handleField) {
                    nbrColumns--;
                }
                if (this.addTrashIcon) {
                    nbrColumns--;
                }
                $cell.attr('colspan', nbrColumns);
            } else if (node.attrs.name !== fieldName) {
                $cell.removeClass('o_invisible_modifier');
                $cell.addClass('o_hidden');
            } else if (node.attrs.name === fieldName) {
                var currency_id = record.data.currency_id;
                var display_name = currency_id.data.display_name;
                var value = format.monetary(record.data.section_total, {}, {currency_id: currency_id});
                $cell.text(`${value} ${display_name}`);
            }
            return $cell;
        }
        return $cell;
    },
});

});
