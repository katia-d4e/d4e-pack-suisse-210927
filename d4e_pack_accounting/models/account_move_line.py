# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    _sql_constraints = [
        (
            'check_credit_debit',
            """CHECK(credit + debit >= 0 AND credit * debit = 0)""",
            """Wrong credit or debit value in accounting entry !"""
        ),
        (
            'check_amount_currency_balance_sign',
            """CHECK(((currency_id != company_currency_id) AND ((debit - credit <= 0 AND amount_currency <= 0) OR (debit - credit >= 0 AND amount_currency >= 0))) OR (currency_id = company_currency_id AND ROUND(debit - credit - amount_currency, 2) = 0))""",
            """The amount expressed in the secondary currency must be positive when account is debited and negative when account is credited. If the currency is the same as the one from the company, this amount must strictly be equal to the balance."""
        ),
        (
            'check_accountable_required_fields',
            """CHECK(COALESCE(display_type IN ('line_section_sub_total', 'line_sub_total', 'line_title', 'line_section', 'line_note'), 'f') OR account_id IS NOT NULL)""",
            """Missing required account on accountable invoice line."""
        ),
        (
            'check_non_accountable_fields_null',
            """CHECK(display_type NOT IN ('line_section_sub_total', 'line_sub_total', 'line_title', 'line_section', 'line_note') OR (amount_currency = 0 AND debit = 0 AND credit = 0 AND account_id IS NULL))""",
            """Forbidden unit price, account and quantity on non-accountable invoice line"""
        ),
    ]

    section_number = fields.Integer(default=0)
    display_type = fields.Selection(selection_add=[('line_section_sub_total', 'Sub-total'),
                                                   ('line_title', 'Title'),
                                                   ('line_sub_total', 'Sub-total')])
    section_total = fields.Monetary(currency_field='currency_id')
    company_id = fields.Many2one(comodel_name='res.company',
                                 related='move_id.company_id')
    totals_below_sections = fields.Boolean(related='company_id.totals_below_sections')
    tax_selection = fields.Char(compute='_compute_tax_selection')
    is_discount_section = fields.Boolean(string='Discount Section',
                                         default=False)
    is_discount_line = fields.Boolean(string='Discount Line',
                                      default=False)
    is_stop_line = fields.Boolean(string='Is Stop Line',
                                  default=False)

    def _get_computed_price_unit(self):
        price_unit = super(AccountMoveLine, self)._get_computed_price_unit()
        if self.is_stop_line:
            return self.price_unit
        return price_unit

    def _compute_tax_selection(self):
        for line_id in self:
            if line_id.move_id:
                line_id.tax_selection = line_id.move_id.show_line_subtotals_tax_selection()
            else:
                line_id.tax_selection = 'tax_excluded'

    def default_get(self, fields_list):
        line_vals = super(AccountMoveLine, self).default_get(fields_list)
        display_type = line_vals.get('display_type', None)
        if display_type:
            if display_type in ['line_sub_total', 'line_title']:
                line_vals['quantity'] = 0
                line_vals['price_unit'] = 0.0
                line_vals['exclude_from_invoice_tab'] = False
                line_vals['tax_ids'] = [(5, 0, 0)]
            if display_type == 'line_sub_total':
                line_vals['name'] = _('Sub-total')
            elif display_type == 'line_title':
                line_vals['name'] = _('New title')
        return line_vals

    def sorted_by_order(self):
        return self.sorted(lambda line_id: (line_id.sequence, line_id.create_date))

    def run_inv_lines_onchanges(self):
        try:
            self._onchange_product_id()
            self._onchange_currency()
            self._onchange_amount_currency()
            self._onchange_credit()
            self._onchange_debit()
            self._onchange_mark_recompute_taxes()
            self._onchange_mark_recompute_taxes_analytic()
            self._onchange_balance()
            self._onchange_price_subtotal()
        except Exception as e:
            _logger.error(str(e))
        return True
