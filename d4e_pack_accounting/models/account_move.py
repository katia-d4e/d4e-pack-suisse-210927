# -*- coding: utf-8 -*-
from odoo import api, models, fields, http, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import pdf
from datetime import datetime
from copy import deepcopy

SEQUENCE = 999999999


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['base.order', 'account.move']

    internal_reference = fields.Char(string='Internal Reference')
    new_section_number = fields.Integer(default=1)
    sections_sum_total = fields.Float(compute='_inv_compute_sections_total')
    print_date = fields.Datetime(string='Print Date')
    printed = fields.Boolean(string='Printed')
    sent = fields.Boolean(string='Sent')
    discount_num = fields.Float(string='Discount')
    amount_discount = fields.Monetary(string='Total Discount',
                                      store=True,
                                      readonly=True,
                                      compute='_compute_amount_disc',
                                      tracking=4)
    amount_untaxed_with_disc = fields.Monetary(string='Total untaxed',
                                               store=True,
                                               readonly=True,
                                               compute='_compute_amount_disc',
                                               tracking=4)
    is_stop_total = fields.Boolean(string='Stop Total')
    stop_at = fields.Float(string='Stop amount at')
    stop = fields.Selection(selection=[('ttc', 'TTC'), ('ht', 'HT')],
                            default='ttc',
                            string='Total to stop')
    payment_mode = fields.Char(string='Payment Mode', compute='_compute_payment_mode')
    is_correct_bvr = fields.Boolean('Correct')
    bank_details = fields.Boolean(string='Bank Details', compute='_compute_bank_details')

    @api.onchange('payment_reference')
    def _check_invoice_payment_ref(self):
        reports = [0, 9, 4, 6, 8, 2, 7, 1, 3, 5]
        report = 0
        if self.payment_reference:
            self.payment_reference = self.payment_reference.replace(" ", "")
            if len(self.payment_reference) == 16 or len(self.payment_reference) == 27:
                for i in range(0,8):
                    digits = int(self.payment_reference[i]) - int('0')
                    report = reports[(digits + 10 - report) % 10]
                if int(self.payment_reference[8]) == reports[report]:
                    self.is_correct_bvr = True
                else:
                    self.is_correct_bvr = False
            else:
                self.is_correct_bvr = False
        else:
            self.is_correct_bvr = False

        if self.payment_reference and len(self.payment_reference) > 1:
            new = self.payment_reference[0] + self.payment_reference[1]
            i = 2
            while i < len(self.payment_reference):
                new += " " + self.payment_reference[i:i + 5]
                i += 5
            self.payment_reference = new

    @api.depends('currency_id.name')
    def _compute_payment_mode(self):
        for record in self:
            payment_mode = ''
            if record.move_type == 'in_invoice' and record.partner_bank_id:
                if record.partner_bank_id.acc_type == 'postal':
                    payment_mode = "BVR " + record.currency_id.name
                else:
                    payment_mode = "SEPA " + record.currency_id.name
            record.payment_mode = payment_mode

    @api.onchange('partner_id')
    def _compute_bank_details(self):
        if len(self.partner_id.bank_ids) >= 1:
            bankid = self.partner_id.bank_ids[0]
            if bankid.acc_type == "postal":
                self.bank_details = True
            elif bankid.acc_type == "iban":
                if bankid.bank_id is not False and bankid.bank_id.bic is not False:
                    self.bank_details = True
                else:
                    self.bank_details = False
            else:
                self.bank_details = False
        elif len(self.partner_id.parent_id.bank_ids) >= 1:
            bankid1 = self.partner_id.parent_id.bank_ids[0]
            if bankid1.acc_type == "postal":
                self.bank_details = True
            elif bankid1.acc_type == "iban":
                if bankid1.bank_id is not False and bankid1.bank_id.bic is not False:
                    self.bank_details = True
                else:
                    self.bank_details = False
            else:
                self.bank_details = False
        else:
            self.bank_details = False

    def read_specific_product(self):
        if self.is_stop_total:
            if self.stop == 'ttc':
                return self.env.ref('d4e_pack_accounting.discount_ttc')
            elif self.stop == 'ht':
                return self.env.ref('d4e_pack_accounting.discount_ht')
        return self.env['product.product'].sudo()

    def create_discount_vals(self, product_discount, adjustment_value=0.0, sequence=SEQUENCE):
        if not product_discount:
            raise ValidationError(_('Add discount product'))
        if self.stop == 'ht' and product_discount.taxes_id.filtered(lambda t: t.price_include):
            raise ValidationError(_('The disount product HT must not contain included taxes'))
        elif self.stop == 'ttc' and product_discount.taxes_id.filtered(lambda t: not t.price_include):
            raise ValidationError(_('The disount product HT must contain included taxes'))
        line_discount = self.invoice_line_ids.filtered(lambda l: not l.display_type and l.is_discount_line)
        add_sequence = 2 if line_discount else 1
        line_vals = {
            'product_id': product_discount.id,
            'name': _('Stop Amount'),
            'price_unit': adjustment_value,
            'is_discount_line': False,
            'is_discount_section': False,
            'is_stop_line': True,
            'product_uom_id': product_discount.uom_id.id,
            'account_id': self.journal_id.default_account_id.id,
            'quantity': 1,
            'sequence': sequence + add_sequence,
        }
        if product_discount.taxes_id:
            line_vals['tax_ids'] = [(5, 0, 0)] + [(4, tax_id.id) for tax_id in product_discount.taxes_id]
        return line_vals

    def discount_line_values(self, discount_line, product_discount, new_amount, amount):
        line_section = self.invoice_line_ids.filtered(lambda l: l.is_discount_section is True)
        if new_amount != amount:
            compute_amount = new_amount - amount
            if discount_line:
                discount_line.unlink()
            order_line_vals = []
            sequence = SEQUENCE
            if not line_section:
                order_line_vals.append((0, 0, {
                    'name': _('Discount'),
                    'display_type': 'line_section',
                    'is_discount_section': True,
                    'sequence': SEQUENCE,
                }))
            else:
                sequence = line_section.sequence
            new_vals = self.create_discount_vals(product_discount, compute_amount, sequence)
            new_vals['name'] = ': '.join([_('Stop Amount'), '%.2f' % new_amount])
            order_line_vals.append((0, 0, new_vals))
            self.write({
                'invoice_line_ids': order_line_vals,
            })
        elif new_amount == amount and discount_line:
            discount_line.unlink()
            if line_section and not self.invoice_line_ids.filtered(lambda line: line.is_discount_line):
                line_section.unlink()

    def inv_compute_by_tax_type(self, line_id, tax_type):
        if tax_type == 'tax_included':
            return line_id.price_total
        elif tax_type == 'tax_excluded':
            return line_id.price_subtotal
        return 0.0

    def inv_compute_sections(self):
        section_lines = {'_': self.env['account.move.line'].sudo()}
        line_ids = self.invoice_line_ids.sorted_by_order()
        for section_id in line_ids.filtered(lambda l_id: l_id.display_type == 'line_section'):
            section_lines[section_id] = self.env['account.move.line'].sudo()
            section_sub_total_line_id = line_ids.filtered(lambda l_id: l_id.section_number == section_id.section_number and l_id.display_type == 'line_section_sub_total')
            if section_sub_total_line_id:
                start_sequence = section_id.sequence
                end_sequence = section_sub_total_line_id.sequence
                if start_sequence < end_sequence:
                    section_lines[section_id] |= line_ids.filtered(lambda l_id: start_sequence < l_id.sequence < end_sequence and l_id.display_type != 'line_sub_total')
        all_section_lines = self.env['account.move.line'].sudo()
        for section_id in section_lines.keys():
            if section_id != '_':
                all_section_lines |= section_lines[section_id]
        section_lines['_'] |= line_ids.filtered(lambda l_id: l_id not in all_section_lines and l_id.display_type != 'line_section_sub_total')
        return section_lines

    def inv_compute_sub_total_lines(self):
        sub_total_lines = {}
        start_from_sequence = None
        line_ids = self.invoice_line_ids.sorted_by_order()
        for line_sub_total_id in line_ids.filtered(lambda l_id: l_id.display_type == 'line_sub_total'):
            sub_total_lines[line_sub_total_id] = self.env['account.move.line'].sudo()
            start_adding = False
            for line_id in line_ids:
                if not start_from_sequence or line_id == start_from_sequence:
                    start_adding = True
                if line_id == line_sub_total_id:
                    break
                if start_adding:
                    if line_id.display_type == 'line_section_sub_total':
                        sub_total_lines[line_sub_total_id] = self.env['account.move.line'].sudo()
                    else:
                        sub_total_lines[line_sub_total_id] |= line_id
            start_from_sequence = line_sub_total_id
        return sub_total_lines

    def inv_compute_line_section_sub_total(self, sub_total_line_id):
        line_tax_type = self.show_line_subtotals_tax_selection()
        section_lines = self.inv_compute_sections()
        current_section_number = sub_total_line_id.section_number or -1
        for key_id in section_lines.keys():
            section_number = key_id != '_' and key_id.section_number or -1
            if section_number == current_section_number:
                line_ids = section_lines[key_id].filtered(lambda l_id: not l_id.display_type)
                return sum(self.inv_compute_by_tax_type(line_id, line_tax_type) or 0.0 for line_id in line_ids)
        return 0.0

    def inv_compute_line_sub_total(self, sub_total_line_id):
        line_tax_type = self.show_line_subtotals_tax_selection()
        invoice_line_ids = self.inv_compute_sub_total_lines()
        invoice_line_ids = invoice_line_ids[sub_total_line_id].filtered(lambda l_id: not l_id.display_type) if sub_total_line_id in invoice_line_ids else []
        return sum(self.inv_compute_by_tax_type(line_id, line_tax_type) or 0.0 for line_id in invoice_line_ids)

    @api.depends('invoice_line_ids')
    def _inv_compute_sections_total(self):
        for invoice_id in self.with_context(disable_inv_line_order=True):
            sections_sum_total = 0.0
            for line_id in invoice_id.invoice_line_ids.sorted_by_order():
                sub_total_value = 0
                totals_below_sections = line_id.totals_below_sections
                if totals_below_sections and line_id.display_type in ['line_section_sub_total']:
                    sub_total_value = invoice_id.inv_compute_line_section_sub_total(sub_total_line_id=line_id)
                elif line_id.display_type in ['line_sub_total']:
                    sub_total_value = invoice_id.inv_compute_line_sub_total(sub_total_line_id=line_id)
                if (totals_below_sections and line_id.display_type == 'line_section_sub_total') or line_id.display_type == 'line_sub_total':
                    if line_id.section_total != sub_total_value:
                        line_id.section_total = sub_total_value
                else:
                    if line_id.section_total != 0.0:
                        line_id.section_total = 0.0
                sections_sum_total += sub_total_value
            if invoice_id.sections_sum_total != sections_sum_total:
                invoice_id.sections_sum_total = sections_sum_total

    def create_section_sub_total_line_vals(self, line_id, sequence, number):
        return {
            'name': '%s, %s' % (line_id.name, _('Sub-total')),
            'display_type': 'line_section_sub_total',
            'quantity': 0,
            'price_unit': 0.0,
            'tax_ids': [(5, 0, 0)],
            'exclude_from_invoice_tab': False,
            'section_number': number,
            'move_id': line_id.move_id.id,
            'sequence': sequence,
            'is_discount_line': line_id.is_discount_section,
            'is_stop_line': line_id.is_stop_line,
        }

    def update_move_lines(self):
        sequence = 1
        line_ids_vals = []
        write_vals = {}
        new_section_number = self.new_section_number
        line_ids = self.invoice_line_ids.sorted_by_order()
        for line_id in line_ids:
            line_vals = {'sequence': sequence}
            if line_id.display_type == 'line_section':
                section_number = line_id.section_number or 0
                if section_number == 0:
                    line_vals['section_number'] = new_section_number
                    new_section_number += 1
                elif new_section_number <= section_number:
                    new_section_number = section_number + 1
            elif line_id.display_type != 'line_section_sub_total':
                line_vals['section_number'] = 0
            line_ids_vals.append((1, line_id.id, line_vals))
            sequence += 1
            if line_id.totals_below_sections and line_id.display_type == 'line_section':
                original_number_value = line_id.section_number or 0
                section_number = line_vals.get('section_number', original_number_value)
                section_sub_total_line_id = line_ids.filtered(lambda l_id: l_id.section_number == section_number and l_id.display_type == 'line_section_sub_total')
                if original_number_value == 0 or (section_number != 0 and not section_sub_total_line_id):
                    line_ids_vals.append((0, 0, self.create_section_sub_total_line_vals(line_id=line_id, sequence=sequence, number=section_number)))
                    sequence += 1
        if len(line_ids_vals) > 0:
            list_vals = self._update_move_lines(line_ids_vals)
            write_vals.update({
                'invoice_line_ids': list_vals,
                'line_ids': list_vals,
            })
        if new_section_number != self.new_section_number:
            write_vals.update({
                'new_section_number': new_section_number,
            })
        if write_vals:
            super(AccountMove, self).write(write_vals)
        return write_vals

    def _update_move_lines(self, list_vals):
        browse = self.env['account.move.line'].sudo().browse
        if any(x[0] == 0 for x in list_vals):
            write_vals = []
            start_sequence_at = 1
            current_section = None
            for line_vals in list_vals:
                if line_vals[0] != 0:
                    new_vals = deepcopy(line_vals)
                    if browse(line_vals[1]).display_type == 'line_section':
                        if current_section:
                            # Update section "line_section_sub_total" line sequence
                            section_st_vals = [x for x in list_vals if x[0] == 0 and x[2].get('section_number', None) == current_section]
                            if section_st_vals:
                                new_section_line_vals = deepcopy(section_st_vals[0])
                                new_section_line_vals[2].update({'sequence': start_sequence_at})
                                write_vals.append(new_section_line_vals)
                                start_sequence_at += 1
                        current_section = line_vals[2].get('section_number', None)
                    new_vals[2].update({'sequence': start_sequence_at})
                    write_vals.append(new_vals)
                    start_sequence_at += 1
            if current_section:
                # Update last section "line_section_sub_total" line sequence
                section_st_vals = [x for x in list_vals if x[0] == 0 and x[2].get('section_number', None) == current_section]
                if section_st_vals:
                    new_section_line_vals = deepcopy(section_st_vals[0])
                    new_section_line_vals[2].update({'sequence': start_sequence_at})
                    write_vals.append(new_section_line_vals)
            return write_vals
        return list_vals

    @api.model_create_multi
    def create(self, vals_list):
        context = {'disable_inv_line_order': True, 'bypass_discount_inv': True, 'bypass_stop_inv': True, 'check_move_validity': True}
        move_ids = super(AccountMove, self.with_context(**context)).create(vals_list)
        disable_inv_line_order = self.env.context.get('disable_inv_line_order', False)
        bypass_discount_inv = self.env.context.get('bypass_discount_inv', False)
        bypass_stop_inv = self.env.context.get('bypass_stop_inv', False)
        for record_id in move_ids.with_context(**context):
            if not bypass_discount_inv and record_id.state == 'draft':
                product_discount = self.env.ref('d4e_pack_accounting.product_discount')
                if record_id.move_type == 'out_invoice' and record_id.discount_num > 0 and not record_id.invoice_line_ids.filtered(lambda l: l.is_discount_section or l.is_discount_line):
                    invoice_line_ids = [(0, 0, {
                        'name': _('Discount'),
                        'display_type': 'line_section',
                        'is_discount_section': True,
                        'sequence': SEQUENCE,
                    })]
                    line_name = '{n} {v}%'.format(n=_('Discount'), v=record_id.discount_num)
                    line_vals = {
                        'product_id': product_discount.id,
                        'name': line_name,
                        'price_unit': - record_id.sum_untaxed_value() * (record_id.discount_num / 100),
                        'product_uom_id': product_discount.uom_id.id,
                        'quantity': 1,
                        'is_discount_line': True,
                        'sequence': SEQUENCE + 1,
                    }
                    if product_discount.taxes_id:
                        line_vals['tax_ids'] = [(5, 0, 0)] + [(4, tax_id.id) for tax_id in product_discount.taxes_id]
                    invoice_line_ids.append((0, 0, line_vals))
                    record_id.write({'invoice_line_ids': invoice_line_ids})
            if not bypass_stop_inv and record_id.move_type == 'out_invoice' and record_id.state == 'draft' and record_id.is_stop_total and record_id.stop_at and record_id.stop:
                amount_untaxed = record_id.amount_untaxed
                amount_total = record_id.amount_total
                product_discount = record_id.read_specific_product()
                if record_id.stop == 'ht':
                    record_id.discount_line_values(None, product_discount, record_id.stop_at, amount_untaxed)
                elif record_id.stop == 'ttc':
                    record_id.discount_line_values(None, product_discount, record_id.stop_at, amount_total)
            if not disable_inv_line_order:
                record_id.update_move_lines()
        return move_ids

    def write(self, vals):
        res = True
        context = {'disable_inv_line_order': True, 'bypass_discount_inv': True, 'bypass_stop_inv': True, 'check_move_validity': False}
        ttc = self.env.ref('d4e_pack_accounting.discount_ttc')
        ht = self.env.ref('d4e_pack_accounting.discount_ht')
        product_discount = self.env.ref('d4e_pack_accounting.product_discount')
        disable_inv_line_order = self.env.context.get('disable_inv_line_order', False)
        bypass_discount_inv = self.env.context.get('bypass_discount_inv', False)
        bypass_stop_inv = self.env.context.get('bypass_stop_inv', False)
        for record_id in self.with_context(**context):
            force_update = False
            is_stop_total = record_id.is_stop_total
            stop = record_id.stop
            res = super(AccountMove, record_id).write(vals) and res
            if not bypass_discount_inv:
                force_update = True
                invoice_vals = {}
                if record_id.move_type == 'out_invoice':
                    line_discount = record_id.invoice_line_ids.filtered(lambda l: not l.display_type and l.is_discount_line)
                    line_discount_section = record_id.invoice_line_ids.filtered(lambda l: l.display_type == 'line_section' and l.is_discount_section)
                    if not line_discount and 'discount_num' in vals and vals.get('discount_num') != 0:
                        sequence = SEQUENCE
                        if not vals.get('invoice_line_ids'):
                            invoice_vals['invoice_line_ids'] = []
                        if not line_discount_section:
                            invoice_vals['invoice_line_ids'].append((0, 0, {
                                'name': _('Discount'),
                                'display_type': 'line_section',
                                'is_discount_section': True,
                                'sequence': SEQUENCE,
                            }))
                        else:
                            sequence = line_discount_section.sequence + 1
                        discount_num = vals.get('discount_num')
                        line_name = '{n} {v}%'.format(n=_('Discount'), v=discount_num)
                        line_vals = {
                            'product_id': product_discount.id,
                            'name': line_name,
                            'price_unit': - record_id.sum_untaxed_value() * (discount_num / 100),
                            'product_uom_id': product_discount.uom_id.id,
                            'quantity': 1,
                            'is_discount_line': True,
                            'account_id': record_id.journal_id.default_account_id.id,
                            'sequence': sequence,
                        }
                        if product_discount.taxes_id:
                            line_vals['tax_ids'] = [(5, 0, 0)] + [(4, tax_id.id) for tax_id in product_discount.taxes_id]
                        invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
                        if invoice_vals:
                            res = super(AccountMove, record_id).write(invoice_vals) and res
                    elif line_discount and 'discount_num' in vals and vals.get('discount_num') == 0:
                        if record_id.state == 'draft':
                            super(AccountMove, record_id).write({'invoice_line_ids': [(2, line_discount.id), (2, line_discount_section.id)]})
                        else:
                            line_discount.quantity = 0
                    if line_discount and 'discount_num' in vals and vals.get('discount_num') != 0:
                        super(AccountMove, record_id).write({'invoice_line_ids': [(1, line_discount.id, {
                            'name': '{n} {v}%'.format(n=_('Discount'), v=vals['discount_num']),
                            'price_unit': - record_id.sum_untaxed_value() * (vals['discount_num'] / 100),
                        })]})
                    if line_discount and ('invoice_line_ids' in vals or 'line_ids' in vals):
                        super(AccountMove, record_id).write({
                            'invoice_line_ids': [(1, line_discount.id, {
                                'price_unit': - record_id.sum_untaxed_value() * (record_id.discount_num / 100),
                            })]
                        })
            if not bypass_stop_inv and record_id.move_type == 'out_invoice' and record_id.state == 'draft' and ('is_stop_total' in vals or 'stop_at' in vals or 'stop' in vals or 'invoice_line_ids' in vals):
                force_update = True
                discount_line = None
                if is_stop_total:
                    if stop == 'ttc':
                        discount_line = record_id.invoice_line_ids.filtered(lambda l: l.product_id == ttc and l.is_stop_line)
                    elif stop == 'ht':
                        discount_line = record_id.invoice_line_ids.filtered(lambda l: l.product_id == ht and l.is_stop_line)
                amount_untaxed = record_id.amount_untaxed
                amount_total = record_id.amount_total
                if record_id.is_stop_total and record_id.stop_at and record_id.stop:
                    if discount_line:
                        amount_untaxed -= discount_line.price_subtotal
                        amount_total -= discount_line.price_total
                    # Update lines
                    product_discount = record_id.read_specific_product()
                    if record_id.stop == 'ht':
                        record_id.discount_line_values(discount_line, product_discount, record_id.stop_at, amount_untaxed)
                    elif record_id.stop == 'ttc':
                        record_id.discount_line_values(discount_line, product_discount, record_id.stop_at, amount_total)
                elif discount_line and (not record_id.is_stop_total or not record_id.stop_at):
                    discount_line.unlink()
                    line_section = record_id.invoice_line_ids.filtered(lambda l: l.display_type == 'line_section' and l.is_discount_section)
                    if line_section and not record_id.invoice_line_ids.filtered(lambda line: not line.display_type and line.is_discount_line):
                        line_section.unlink()
            if force_update or 'invoice_line_ids' in vals or 'line_ids' in vals:
                unlink_ids = []
                for line_id in record_id.invoice_line_ids.filtered(lambda l: l.section_number and l.display_type == 'line_section_sub_total'):
                    if not record_id.invoice_line_ids.filtered(lambda l: l.section_number == line_id.section_number and l.display_type == 'line_section'):
                        unlink_ids.append((2, line_id.id))
                if len(unlink_ids) > 0:
                    res = super(AccountMove, record_id).write({'invoice_line_ids': unlink_ids}) and res
                if not disable_inv_line_order:
                    # Recompute fields values
                    record_fields = list(self.sudo().fields_get().keys())
                    record_id.read(fields=record_fields)
                    # Update move lines
                    record_id.update_move_lines()
        return res

    def compute_discount_untaxed_value(self):
        return self.invoice_line_ids.filtered(lambda l: not l.display_type and not l.is_discount_section and not l.is_discount_line and not l.is_stop_line)

    def sum_untaxed_value(self):
        return sum(self.compute_discount_untaxed_value().mapped('price_subtotal') or [])

    def update_print_date(self):
        for record_id in self:
            if record_id.state != 'draft':
                record_id.write({
                    'print_date': datetime.now(),
                    'printed': True,
                })

    def print_ch_qr_bill(self):
        res = super(AccountMove, self).print_ch_qr_bill()
        self.update_print_date()
        return res

    def isr_print(self):
        res = super(AccountMove, self).isr_print()
        self.update_print_date()
        return res

    def action_invoice_print(self):
        res = super(AccountMove, self).action_invoice_print()
        self.update_print_date()
        return res

    def copy(self, default=None):
        default = dict(default or {})
        default['print_date'] = None
        default['printed'] = None
        return super(AccountMove, self).copy(default=default)

    def _pdf_invoices_with_isr(self, invoice_ids):
        pdf_docs = []
        ai_render_qweb_pdf = self.env.ref('account.account_invoices')._render_qweb_pdf
        isr_render_qweb_pdf = self.env.ref('l10n_ch.l10n_ch_isr_report')._render_qweb_pdf
        for invoice_id in self.browse(invoice_ids):
            pdf_data = ai_render_qweb_pdf(invoice_id.id)[0]
            pdf_docs.append(pdf_data)
            if invoice_id.l10n_ch_isr_valid:
                invoice_id.l10n_ch_isr_sent = True
                isr_data = isr_render_qweb_pdf(invoice_id.id)[0]
                pdf_docs.append(isr_data)
            invoice_id.update_print_date()
        pdf_merge = pdf.merge_pdf(pdf_docs)
        return pdf_merge

    def _pdf_invoices_with_qr(self, invoice_ids):
        pdf_docs = []
        ai_render_qweb_pdf = self.env.ref('account.account_invoices')._render_qweb_pdf
        qr_render_qweb_pdf = self.env.ref('l10n_ch.l10n_ch_qr_report')._render_qweb_pdf
        for invoice_id in self.browse(invoice_ids):
            pdf_data = ai_render_qweb_pdf(invoice_id.id)[0]
            pdf_docs.append(pdf_data)
            invoice_id.l10n_ch_isr_sent = True
            qr_data = qr_render_qweb_pdf(invoice_id.id)[0]
            pdf_docs.append(qr_data)
            invoice_id.update_print_date()
        pdf_merge = pdf.merge_pdf(pdf_docs)
        return pdf_merge

    def run_inv_onchanges(self):
        try:
            self._onchange_partner_id()
            self._onchange_invoice_date()
            self._onchange_currency()
            self._onchange_recompute_dynamic_lines()
            self._onchange_invoice_line_ids()
            self._onchange_journal()
            self._onchange_invoice_payment_ref()
            self._onchange_invoice_vendor_bill()
            self._onchange_type()
        except Exception as e:
            print(str(e))
        return True

    @api.depends('invoice_line_ids')
    def _compute_amount_disc(self):
        for move in self:
            amount_untaxed = amount_discount = 0
            for line in move.invoice_line_ids:
                amount_untaxed += line.price_subtotal if not line.display_type else 0.0
                amount_discount += line.price_subtotal if not line.display_type and (line.is_discount_line or line.is_stop_line) else 0.0
            move.update({
                'amount_discount': amount_discount,
                'amount_untaxed_with_disc': amount_untaxed - amount_discount
            })

    def update_sequence_except(self):
        return self.invoice_line_ids.filtered(lambda l: l.is_discount_line or l.is_discount_section or l.is_stop_line)

    def _reorder_lines_action(self):
        context = {'disable_inv_line_order': True, 'bypass_discount_inv': True, 'bypass_stop_inv': True, 'check_move_validity': False}
        record_ids = self.with_context(**context)
        for record_id in record_ids:
            line_idx = 1
            invoice_line_vals = []
            for line_id in record_id.invoice_line_ids.sorted_by_order().filtered(lambda l: not l.is_discount_section and not l.is_discount_line and not l.is_stop_line):
                invoice_line_vals.append((1, line_id.id, {
                    'sequence': line_idx,
                }))
                line_idx += 1
            for line_id in record_id.update_sequence_except().sorted_by_order():
                if line_id.is_discount_section:
                    invoice_line_vals.append((1, line_id.id, {
                        'sequence': line_idx,
                    }))
                    section_sub_total_line = record_id.invoice_line_ids.filtered(lambda l: l.display_type == 'line_section_sub_total' and l.section_number == line_id.section_number)
                    if section_sub_total_line:
                        invoice_line_vals.append((1, section_sub_total_line.id, {
                            'sequence': line_idx + 3,
                        }))
                elif line_id.is_discount_line:
                    invoice_line_vals.append((1, line_id.id, {
                        'sequence': line_idx + 1,
                    }))
                elif line_id.is_stop_line:
                    invoice_line_vals.append((1, line_id.id, {
                        'sequence': line_idx + 2,
                    }))
            if invoice_line_vals:
                record_id.write({'invoice_line_ids': invoice_line_vals})
        return record_ids

    def reorder_lines_action(self):
        self._reorder_lines_action()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        context = {'disable_inv_line_order': True, 'bypass_discount_inv': True, 'bypass_stop_inv': True}
        return super(AccountMove, self.with_context(**context)).copy(default=default)
