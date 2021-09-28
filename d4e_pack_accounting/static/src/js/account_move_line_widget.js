odoo.define('d4e_pack_accounting.aml_section_and_note_backend', function (require) {
"use strict";

const FieldChar = require('web.basic_fields').FieldChar;
const FieldOne2Many = require('web.relational_fields').FieldOne2Many;
const fieldRegistry = require('web.field_registry');
const ListFieldText = require('web.basic_fields').ListFieldText;
const ListRenderer = require('web.ListRenderer');

const AMLSectionAndNoteListRenderer = ListRenderer.extend({
    _renderBodyCell: function (record, node, index, options) {
        var $cell = this._super.apply(this, arguments);
        var displayType = record.data.display_type;
        if (displayType && node.attrs.name === "name") {
            $cell.addClass(`o_aml_${displayType}`);
        }
        return $cell;
    },
    _renderRow: function (record, index) {
        var $row = this._super.apply(this, arguments);
        if (record.data.display_type) {
            $row.addClass('o_aml_is_' + record.data.display_type);
        }
        var isSectionSubTotal = record.data.display_type === 'line_section_sub_total';
        var isSubTotal = record.data.display_type === 'line_sub_total';
        var isTitle = record.data.display_type === 'line_title';
        if (isSectionSubTotal || isSubTotal || isTitle) {
            $row.addClass('o_hidden');
        }
        return $row;
    },
});

const AMLSectionAndNoteFieldOne2Many = FieldOne2Many.extend({
    _getRenderer: function () {
        if (this.view.arch.tag === 'tree') {
            return AMLSectionAndNoteListRenderer;
        }
        return this._super.apply(this, arguments);
    },
});

const AMLSectionAndNoteFieldText = function (parent, name, record, options) {
    var isSection = record.data.display_type === 'line_section';
    var Constructor = isSection ? FieldChar : ListFieldText;
    return new Constructor(parent, name, record, options);
};

fieldRegistry.add('pack_aml_section_and_note_one2many', AMLSectionAndNoteFieldOne2Many);
fieldRegistry.add('pack_aml_section_and_note_text', AMLSectionAndNoteFieldText);

return AMLSectionAndNoteListRenderer;

});
