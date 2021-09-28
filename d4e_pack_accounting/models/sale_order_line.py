# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools.float_utils import float_is_zero


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _sql_constraints = [
        (
            'non_accountable_null_fields',
            "CHECK(display_type IS NULL OR display_type IN ['line_title', 'line_section_sub_total', 'line_sub_total'] OR (product_id IS NULL AND price_unit = 0 AND product_uom_qty = 0 AND product_uom IS NULL AND customer_lead = 0))",
            "Forbidden values on non-accountable sale order line"
        ),
    ]

    section_number = fields.Integer(default=0)
    display_type = fields.Selection(selection_add=[('line_section_sub_total', 'Sub-total'),
                                                   ('line_title', 'Title'),
                                                   ('line_sub_total', 'Sub-total')])
    section_total = fields.Monetary(currency_field='currency_id')
    company_id = fields.Many2one(comodel_name='res.company',
                                 related='order_id.company_id')
    totals_below_sections = fields.Boolean(related='company_id.totals_below_sections')
    tax_selection = fields.Char(compute='_compute_tax_selection')
    is_discount_section = fields.Boolean(string='Discount Section',
                                         default=False)
    is_discount_line = fields.Boolean(string='Discount Line',
                                      default=False)
    is_stop_line = fields.Boolean(string='Is Stop Line',
                                  default=False)

    def _compute_tax_selection(self):
        for line_id in self:
            if line_id.order_id:
                line_id.tax_selection = line_id.order_id.show_line_subtotals_tax_selection()
            else:
                line_id.tax_selection = 'tax_excluded'

    def default_get(self, fields_list):
        line_vals = super(SaleOrderLine, self).default_get(fields_list)
        display_type = line_vals.get('display_type', None)
        if display_type:
            if display_type in ['line_sub_total', 'line_title']:
                line_vals['product_uom_qty'] = 0
                line_vals['price_unit'] = 0.0
                line_vals['tax_id'] = [(5, 0, 0)]
            if display_type == 'line_sub_total':
                line_vals['name'] = _('Sub-total')
            elif display_type == 'line_title':
                line_vals['name'] = _('New title')
        return line_vals

    def _prepare_invoice_line(self, **optional_values):
        invoice_line_vals = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
        invoice_line_vals.update({
            'is_discount_line': self.is_discount_line,
            'is_discount_section': self.is_discount_section,
            'is_stop_line': self.is_stop_line,
        })
        if self.display_type in ['line_section_sub_total', 'line_sub_total', 'line_title']:
            invoice_line_vals.update({
                'quantity': 0,
                'price_unit': 0.0,
                'tax_ids': [(5, 0, 0)],
            })
        if self.display_type in ['line_section_sub_total', 'line_section']:
            invoice_line_vals.update({
                'section_number': self.section_number,
            })
        if self.display_type == 'line_section_sub_total':
            invoice_line_vals.update({
                'section_total': self.section_total,
            })
        return invoice_line_vals

    def sorted_by_order(self):
        return self.sorted(lambda line_id: (line_id.sequence, line_id.create_date))
