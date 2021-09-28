# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_is_zero
from copy import deepcopy

SEQUENCE = 999999999


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['base.order', 'sale.order']

    new_section_number = fields.Integer(default=1)
    sections_sum_total = fields.Float(compute='_order_compute_sections_total')
    discount_num = fields.Float(string='Discount (%)')
    amount_discount = fields.Monetary(string='Total Discount',
                                      store=True,
                                      readonly=True,
                                      compute='_amount_all',
                                      tracking=4)
    amount_untaxed_with_disc = fields.Monetary(string='Total untaxed',
                                               store=True,
                                               readonly=True,
                                               compute='_amount_all',
                                               tracking=4)
    is_stop_total = fields.Boolean(string='Stop Total',
                                   default=False)
    stop_at = fields.Float(string='Stop amount at')
    stop = fields.Selection(selection=[('ttc', 'TTC'), ('ht', 'HT')],
                            default='ttc',
                            string='Total to stop')

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
        line_discount = self.order_line.filtered(lambda l: not l.display_type and l.is_discount_line)
        add_sequence = 2 if line_discount else 1
        line_vals = {
            'product_id': product_discount.id,
            'name': _('Stop Amount'),
            'price_unit': adjustment_value,
            'product_uom': product_discount.uom_id.id,
            'is_discount_line': False,
            'is_discount_section': False,
            'is_stop_line': True,
            'product_uom_qty': 1,
            'sequence': sequence + add_sequence,
        }
        if product_discount.taxes_id:
            line_vals['tax_id'] = [(5, 0, 0)] + [(4, tax_id.id) for tax_id in product_discount.taxes_id]
        return line_vals

    def compute_amounts(self):
        amount_untaxed = amount_tax = 0.0
        for line in self.order_line.filtered(lambda r: not r.is_stop_line):
            amount_tax += line.price_tax
            amount_untaxed += line.price_subtotal
        return {
            'amount_untaxed': amount_untaxed,
            'amount_total': amount_untaxed + amount_tax,
        }

    def update_discount_line_values(self, discount_line, product_discount, new_amount, amount):
        line_section = self.order_line.filtered(lambda l: l.display_type == 'line_section' and l.is_discount_section)
        if new_amount != amount:
            compute_amount = new_amount - amount
            if discount_line:
                discount_line_vals = {}
                if discount_line.product_id != product_discount:
                    discount_line_vals['product_id'] = product_discount.id
                    discount_line_vals['tax_id'] = [(5, 0, 0)] + [(4, tax_id.id) for tax_id in product_discount.taxes_id]
                if discount_line.price_unit != compute_amount:
                    discount_line_vals['price_unit'] = compute_amount
                discount_line_vals['name'] = ': '.join([_('Stop Amount'), '%.2f' % new_amount])
                self.write({'order_line': [(1, discount_line.id, discount_line_vals)]})
            else:
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
                self.write({'order_line': order_line_vals})
        elif new_amount == amount and discount_line:
            if self.state == 'draft':
                order_line = [(2, discount_line.id)]
                if line_section and not self.order_line.filtered(lambda line: line.is_discount_line):
                    order_line.append((2, line_section.id))
                self.write({'order_line': order_line})
            else:
                discount_line.product_uom_qty = 0

    def order_compute_by_tax_type(self, line_id, tax_type):
        if tax_type == 'tax_included':
            return line_id.price_total
        elif tax_type == 'tax_excluded':
            return line_id.price_subtotal
        return 0.0

    def order_compute_sections(self):
        section_lines = {'_': self.env['sale.order.line'].sudo()}
        line_ids = self.order_line.sorted_by_order()
        for section_id in line_ids.filtered(lambda l_id: l_id.display_type == 'line_section'):
            section_lines[section_id] = self.env['sale.order.line'].sudo()
            section_sub_total_line_id = line_ids.filtered(lambda l_id: l_id.section_number == section_id.section_number and l_id.display_type == 'line_section_sub_total')
            if section_sub_total_line_id:
                start_sequence = section_id.sequence
                end_sequence = section_sub_total_line_id.sequence
                if start_sequence < end_sequence:
                    section_lines[section_id] |= line_ids.filtered(lambda l_id: start_sequence < l_id.sequence < end_sequence and l_id.display_type != 'line_sub_total')
        all_section_lines = self.env['sale.order.line'].sudo()
        for section_id in section_lines.keys():
            if section_id != '_':
                all_section_lines |= section_lines[section_id]
        section_lines['_'] |= line_ids.filtered(lambda l_id: l_id not in all_section_lines and l_id.display_type != 'line_section_sub_total')
        return section_lines

    def order_compute_sub_total_lines(self):
        sub_total_lines = {}
        start_from_sequence = None
        line_ids = self.order_line.sorted_by_order()
        for line_sub_total_id in line_ids.filtered(lambda l_id: l_id.display_type == 'line_sub_total'):
            sub_total_lines[line_sub_total_id] = self.env['sale.order.line'].sudo()
            start_adding = False
            for line_id in line_ids:
                if not start_from_sequence or line_id == start_from_sequence:
                    start_adding = True
                if line_id == line_sub_total_id:
                    break
                if start_adding:
                    if line_id.display_type == 'line_section_sub_total':
                        sub_total_lines[line_sub_total_id] = self.env['sale.order.line'].sudo()
                    else:
                        sub_total_lines[line_sub_total_id] |= line_id
            start_from_sequence = line_sub_total_id
        return sub_total_lines

    def order_compute_line_section_sub_total(self, sub_total_line_id):
        line_tax_type = self.show_line_subtotals_tax_selection()
        section_lines = self.order_compute_sections()
        current_section_id = sub_total_line_id.section_number or -1
        for key_id in section_lines.keys():
            key_key = key_id != '_' and key_id.section_number or -1
            if key_key == current_section_id:
                line_ids = section_lines[key_id].filtered(lambda l_id: not l_id.display_type)
                return sum(self.order_compute_by_tax_type(line_id, line_tax_type) or 0.0 for line_id in line_ids)
        return 0.0

    def order_compute_line_sub_total(self, sub_total_line_id):
        line_tax_type = self.show_line_subtotals_tax_selection()
        line_ids = self.order_compute_sub_total_lines()
        line_ids = line_ids[sub_total_line_id].filtered(lambda l_id: not l_id.display_type) if sub_total_line_id in line_ids else []
        return sum(self.order_compute_by_tax_type(line_id, line_tax_type) or 0.0 for line_id in line_ids)

    @api.depends('order_line')
    def _order_compute_sections_total(self):
        for order_id in self.with_context(disable_so_line_order=True):
            sections_sum_total = 0.0
            for line_id in order_id.order_line.sorted_by_order():
                sub_total_value = 0
                totals_below_sections = line_id.totals_below_sections
                if totals_below_sections and line_id.display_type in ['line_section_sub_total']:
                    sub_total_value = order_id.order_compute_line_section_sub_total(sub_total_line_id=line_id)
                elif line_id.display_type in ['line_sub_total']:
                    sub_total_value = order_id.order_compute_line_sub_total(sub_total_line_id=line_id)
                if (totals_below_sections and line_id.display_type == 'line_section_sub_total') or line_id.display_type == 'line_sub_total':
                    if line_id.section_total != sub_total_value:
                        line_id.section_total = sub_total_value
                else:
                    if line_id.section_total != 0.0:
                        line_id.section_total = 0.0
                sections_sum_total += sub_total_value
            if order_id.sections_sum_total != sections_sum_total:
                order_id.sections_sum_total = sections_sum_total

    def _get_invoiceable_lines(self, final=False):
        down_payment_line_ids = []
        invoiceable_line_ids = []
        pending_section = None
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self.order_line.sorted_by_order():
            if line.display_type == 'line_section':
                pending_section = line
                continue
            if line.display_type in ['line_section_sub_total', 'line_sub_total', 'line_title']:
                invoiceable_line_ids.append(line.id)
                continue
            if line.display_type != 'line_note' and float_is_zero(line.qty_to_invoice, precision_digits=precision):
                continue
            if line.qty_to_invoice > 0 or (line.qty_to_invoice < 0 and final) or line.display_type == 'line_note':
                if line.is_downpayment:
                    down_payment_line_ids.append(line.id)
                    continue
                if pending_section:
                    invoiceable_line_ids.append(pending_section.id)
                    pending_section = None
                invoiceable_line_ids.append(line.id)
        return self.env['sale.order.line'].browse(invoiceable_line_ids + down_payment_line_ids)

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals.update({
            'new_section_number': self.new_section_number,
        })
        return invoice_vals

    def _create_invoices(self, grouped=False, final=False, date=None):
        order_with_context = self.with_context(disable_inv_line_order=True)
        return super(SaleOrder, order_with_context)._create_invoices(grouped=grouped, final=final, date=date)

    def create_section_sub_total_line_vals(self, line_id, sequence, number):
        return {
            'name': '%s, %s' % (line_id.name, _('Sub-total')),
            'display_type': 'line_section_sub_total',
            'product_uom_qty': 0,
            'price_unit': 0.0,
            'tax_id': [(5, 0, 0)],
            'section_number': number,
            'order_id': line_id.order_id.id,
            'sequence': sequence,
            'is_discount_line': line_id.is_discount_section,
            'is_stop_line': line_id.is_stop_line,
        }

    def update_order_lines(self):
        sequence = 1
        line_ids_vals = []
        write_vals = {}
        new_section_number = self.new_section_number
        line_ids = self.order_line.sorted_by_order()
        for line_id in line_ids:
            line_vals = {'sequence': sequence}
            if line_id.display_type == 'line_section':
                section_number = line_id.section_number or 0
                if section_number == 0:
                    line_vals['section_number'] = new_section_number
                    new_section_number += 1
                elif new_section_number <= section_number:
                    new_section_number = section_number + 1
                line_ids_vals.append((1, line_id.id, line_vals))
                sequence += 1
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
            write_vals.update({
                'order_line': self._update_order_lines(line_ids_vals),
            })
        if new_section_number != self.new_section_number:
            write_vals.update({
                'new_section_number': new_section_number,
            })
        if write_vals:
            self.write(write_vals)
        return write_vals

    def _update_order_lines(self, list_vals):
        browse = self.env['sale.order.line'].sudo().browse
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

    @api.model
    def create(self, vals):
        context = {'disable_so_line_order': True, 'bypass_discount_so': True, 'bypass_stop_so': True}
        order_id = super(SaleOrder, self.with_context(**context)).create(vals)
        disable_so_line_order = self.env.context.get('disable_so_line_order', False)
        bypass_discount_so = self.env.context.get('bypass_discount_so', False)
        bypass_stop_so = self.env.context.get('bypass_stop_so', False)
        if not bypass_discount_so:
            product_discount = self.env.ref('d4e_pack_accounting.product_discount')
            if order_id.discount_num > 0 and not order_id.order_line.filtered(lambda l: l.is_discount_section or l.is_discount_line):
                sale_order_line = [(0, 0, {
                    'name': _('Discount'),
                    'display_type': 'line_section',
                    'is_discount_section': True,
                    'sequence': SEQUENCE,
                })]
                line_name = '{n} {v}%'.format(n=_('Discount'), v=order_id.discount_num)
                line_vals = {
                    'product_id': product_discount.id,
                    'name': line_name,
                    'price_unit': - (order_id.amount_untaxed - order_id.amount_discount) * order_id.discount_num / 100,
                    'product_uom_qty': 1,
                    'is_discount_line': True,
                    'sequence': SEQUENCE + 1,
                }
                if product_discount.taxes_id:
                    line_vals['tax_id'] = [(5, 0, 0)] + [(4, tax_id.id) for tax_id in product_discount.taxes_id]
                sale_order_line.append((0, 0, line_vals))
                order_id.write({'order_line': sale_order_line})
        if not bypass_stop_so and order_id.is_stop_total and order_id.stop_at and order_id.stop:
            amount_untaxed = order_id.amount_untaxed
            amount_total = order_id.amount_total
            product_discount = order_id.read_specific_product()
            if order_id.stop == 'ht':
                order_id.update_discount_line_values(None, product_discount, order_id.stop_at, amount_untaxed)
            elif order_id.stop == 'ttc':
                order_id.update_discount_line_values(None, product_discount, order_id.stop_at, amount_total)
        if not disable_so_line_order:
            order_id.update_order_lines()
        return order_id

    def write(self, vals):
        res = True
        ttc = self.env.ref('d4e_pack_accounting.discount_ttc')
        ht = self.env.ref('d4e_pack_accounting.discount_ht')
        context = {'disable_so_line_order': True, 'bypass_discount_so': True, 'bypass_stop_so': True}
        product_discount = self.env.ref('d4e_pack_accounting.product_discount')
        disable_so_line_order = self.env.context.get('disable_so_line_order', False)
        bypass_discount_so = self.env.context.get('bypass_discount_so', False)
        bypass_stop_so = self.env.context.get('bypass_stop_so', False)
        for order_id in self.with_context(**context):
            force_update = False
            is_stop_total = order_id.is_stop_total
            stop = order_id.stop
            res = super(SaleOrder, order_id).write(vals) and res
            if not bypass_discount_so:
                force_update = True
                sale_vals = {}
                line_discount = order_id.order_line.filtered(lambda l: not l.display_type and l.is_discount_line)
                line_discount_section = order_id.order_line.filtered(lambda l: l.display_type == 'line_section' and l.is_discount_section)
                if not line_discount and 'discount_num' in vals and vals.get('discount_num') != 0:
                    if not vals.get('order_line'):
                        sale_vals['order_line'] = []
                    if not line_discount_section:
                        sale_vals['order_line'].append((0, 0, {
                            'name': _('Discount'),
                            'display_type': 'line_section',
                            'is_discount_section': True,
                            'sequence': SEQUENCE,
                        }))
                    price = - order_id.sum_untaxed_value() * (vals.get('discount_num') / 100)
                    line_name = '{n} {v}%'.format(n=_('Discount'), v=vals.get('discount_num'))
                    line_vals = {
                        'product_id': product_discount.id,
                        'name': line_name,
                        'price_unit': price,
                        'product_uom_qty': 1,
                        'is_discount_line': True,
                        'sequence': SEQUENCE + 1,
                    }
                    if product_discount.taxes_id:
                        line_vals['tax_id'] = [(5, 0, 0)] + [(4, tax_id.id) for tax_id in product_discount.taxes_id]
                    sale_vals['order_line'].append((0, 0, line_vals))
                elif line_discount and 'discount_num' in vals and vals.get('discount_num') == 0:
                    if order_id.state == 'draft':
                        line_discount.unlink()
                        line_discount_section.unlink()
                    else:
                        line_discount.product_uom_qty = 0
                if sale_vals:
                    res = super(SaleOrder, order_id).write(sale_vals) and res
                if line_discount and ('order_line' in vals or order_id.discount_num != 0):
                    super(SaleOrder, order_id).write({'order_line': [(1, line_discount.id, {
                        'name': '{n} {v}%'.format(n=_('Discount'), v=order_id.discount_num),
                        'price_unit': - order_id.sum_untaxed_value() * (order_id.discount_num / 100),
                    })]})
            if not bypass_stop_so:
                force_update = True
                discount_line = None
                if is_stop_total:
                    if stop == 'ttc':
                        discount_line = order_id.order_line.filtered(lambda l: l.product_id == ttc and l.is_stop_line)
                    elif stop == 'ht':
                        discount_line = order_id.order_line.filtered(lambda l: l.product_id == ht and l.is_stop_line)
                if discount_line and len(discount_line) > 1:
                    discount_line = discount_line[0]
                amount_untaxed = order_id.amount_untaxed
                amount_total = order_id.amount_total
                if order_id.is_stop_total and order_id.stop_at and order_id.stop:
                    if discount_line:
                        amount_untaxed -= discount_line.price_subtotal
                        amount_total -= discount_line.price_total
                    product_discount = order_id.read_specific_product()
                    if order_id.stop == 'ht':
                        order_id.update_discount_line_values(discount_line, product_discount, order_id.stop_at, amount_untaxed)
                    elif order_id.stop == 'ttc':
                        order_id.update_discount_line_values(discount_line, product_discount, order_id.stop_at, amount_total)
                elif discount_line and (not order_id.is_stop_total or not order_id.stop_at):
                    if order_id.state == 'draft':
                        super(SaleOrder, order_id).write({'order_line': [(2, discount_line.id)]})
                    else:
                        discount_line.product_uom_qty = 0
                    line_section = order_id.order_line.filtered(lambda l: l.is_discount_section is True)
                    if order_id.state == 'draft' and line_section and not order_id.order_line.filtered(lambda line: line.is_discount_line):
                        super(SaleOrder, order_id).write({'order_line': [(2, line_section.id)]})
            if force_update or 'order_line' in vals:
                unlink_ids = []
                for line_id in order_id.order_line.filtered(lambda l_id: l_id.section_number and l_id.display_type == 'line_section_sub_total'):
                    if not order_id.order_line.filtered(lambda l_id: l_id.section_number == line_id.section_number and l_id.display_type == 'line_section'):
                        unlink_ids.append((2, line_id.id))
                if len(unlink_ids) > 0:
                    res = super(SaleOrder, order_id).write({'order_line': unlink_ids}) and res
                if not disable_so_line_order:
                    # Recompute fields values
                    record_fields = list(self.sudo().fields_get().keys())
                    order_id.read(fields=record_fields)
                    # Update order lines
                    order_id.update_order_lines()
        return res

    def compute_discount(self):
        discount_num = self.discount_num
        self.write({'discount_num': 0})
        self.write({'discount_num': discount_num})

    @api.depends('order_line.price_total', 'order_line.is_discount_line')
    def _amount_all(self):
        for order in self:
            super(SaleOrder, order)._amount_all()
            amount_untaxed = amount_discount = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_discount += line.price_subtotal if not line.display_type and (line.is_discount_line or line.is_stop_line) else 0.0
            order.update({
                'amount_discount': amount_discount,
                'amount_untaxed_with_disc': amount_untaxed - amount_discount
            })

    def update_sequence_except(self):
        return self.order_line.filtered(lambda l: l.is_discount_line or l.is_discount_section or l.is_stop_line)

    def compute_discount_untaxed_value(self):
        return self.order_line.filtered(lambda l: not l.display_type and not l.is_discount_section and not l.is_discount_line and not l.is_stop_line)

    def sum_untaxed_value(self):
        return sum(self.compute_discount_untaxed_value().mapped('price_subtotal') or [])

    def _prepare_invoice(self, **kwargs):
        res = super(SaleOrder, self)._prepare_invoice(**kwargs)
        res.update({
            'discount_num': self.discount_num,
            'is_stop_total': self.is_stop_total,
            'stop_at': self.stop_at,
            'stop': self.stop,
        })
        return res

    def _reorder_lines_action(self):
        context = {'disable_so_line_order': True, 'bypass_discount_so': True, 'bypass_stop_so': True}
        record_ids = self.with_context(**context)
        for record_id in record_ids:
            line_idx = 1
            order_line_vals = []
            excpet_lines = record_id.update_sequence_except()
            for line_id in record_id.order_line.filtered(lambda l: l not in excpet_lines).sorted_by_order():
                order_line_vals.append((1, line_id.id, {
                    'sequence': line_idx,
                }))
                line_idx += 1
            for line_id in excpet_lines.sorted_by_order():
                if line_id.is_discount_section:
                    order_line_vals.append((1, line_id.id, {
                        'sequence': line_idx,
                    }))
                    section_sub_total_line = record_id.order_line.filtered(lambda l: l.display_type == 'line_section_sub_total' and l.section_number == line_id.section_number)
                    if section_sub_total_line:
                        order_line_vals.append((1, section_sub_total_line.id, {
                            'sequence': line_idx + 3,
                        }))
                elif line_id.is_discount_line:
                    order_line_vals.append((1, line_id.id, {
                        'sequence': line_idx + 1,
                    }))
                elif line_id.is_stop_line:
                    order_line_vals.append((1, line_id.id, {
                        'sequence': line_idx + 2,
                    }))
            if order_line_vals:
                record_id.write({'order_line': order_line_vals})
        return record_ids

    def reorder_lines_action(self):
        self._reorder_lines_action()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        context = {'disable_so_line_order': True, 'bypass_discount_so': True, 'bypass_stop_so': True}
        return super(SaleOrder, self.with_context(**context)).copy(default=default)
