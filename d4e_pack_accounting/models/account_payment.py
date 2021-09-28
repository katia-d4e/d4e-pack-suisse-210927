# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta


MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'out_receipt': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
    'in_receipt': 'supplier',
}


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.depends('invoice_ids', 'amount', 'payment_date', 'currency_id', 'payment_type')
    def _compute_payment_difference(self):
        draft_payments = self.filtered(lambda p: p.invoice_ids and p.state == 'draft')
        for pay in draft_payments:
            payment_amount = -pay.amount if pay.payment_type == 'outbound' else pay.amount
            pay.payment_difference = pay.with_context(with_escompte = False)._compute_payment_amount(pay.invoice_ids, pay.currency_id, pay.journal_id, pay.payment_date) - payment_amount
        (self - draft_payments).payment_difference = 0

    @api.onchange('journal_id')
    def _onchange_journal(self):
        if self.journal_id:
            if self.journal_id.currency_id:
                self.currency_id = self.journal_id.currency_id
            # Set default payment method (we consider the first to be the default one)
            payment_methods = self.payment_type == 'inbound' and self.journal_id.inbound_payment_method_ids or self.journal_id.outbound_payment_method_ids
            payment_methods_list = payment_methods.ids
            default_payment_method_id = self.env.context.get('default_payment_method_id')
            if default_payment_method_id:
                # Ensure the domain will accept the provided default value
                payment_methods_list.append(default_payment_method_id)
            else:
                self.payment_method_id = payment_methods and payment_methods[0] or False
            # Set payment method domain (restrict to methods enabled for the journal and to selected payment type)
            payment_type = self.payment_type in ('outbound', 'transfer') and 'outbound' or 'inbound'
            domain = {'payment_method_id': [('payment_type', '=', payment_type), ('id', 'in', payment_methods_list)]}
            if self.env.context.get('active_model') == 'account.move':
                active_ids = self._context.get('active_ids')
                invoices = self.env['account.move'].browse(active_ids)
                self.amount = abs(self.with_context(with_escompte = True)._compute_payment_amount(invoices, self.currency_id, self.journal_id, self.payment_date))
            return {'domain': domain}
        return {}

    @api.onchange('currency_id')
    def _onchange_currency(self):
        self.amount = abs(self.with_context(with_escompte = True)._compute_payment_amount(self.invoice_ids, self.currency_id, self.journal_id, self.payment_date))
        if self.journal_id:  # TODO: only return if currency differ?
            return
        # Set by default the first liquidity journal having this currency if exists.
        domain = [('type', 'in', ('bank', 'cash')), ('currency_id', '=', self.currency_id.id)]
        if self.invoice_ids:
            domain.append(('company_id', '=', self.invoice_ids[0].company_id.id))
        journal = self.env['account.journal'].search(domain, limit=1)
        if journal:
            return {'value': {'journal_id': journal.id}}

    @api.model
    def default_get(self, default_fields):
        rec = super(AccountPayment, self).default_get(default_fields)
        active_ids = self._context.get('active_ids') or self._context.get('active_id')
        active_model = self._context.get('active_model')
        if not active_ids or active_model != 'account.move':
            return rec
        invoices = self.env['account.move'].browse(active_ids).filtered(
            lambda move: move.is_invoice(include_receipts=True))
        amt = 0
        for inv in invoices:
            if inv.move_type == 'in_invoice' and inv.invoice_payment_term_id.is_escompte:
                for line in inv.invoice_payment_term_id.line_ids:
                    if line.value == 'percent':
                        next_date = fields.Date.from_string(inv.invoice_date)
                        if line.option == 'day_after_invoice_date':
                            next_date += relativedelta(days=line.days)
                            if line.day_of_the_month > 0:
                                months_delta = (line.day_of_the_month < next_date.day) and 1 or 0
                                next_date += relativedelta(day=line.day_of_the_month, months=months_delta)
                        elif line.option == 'after_invoice_month':
                            next_first_date = next_date + relativedelta(day=1, months=1)
                            next_date = next_first_date + relativedelta(days=line.days - 1)
                        elif line.option == 'day_following_month':
                            next_date += relativedelta(day=line.days, months=1)
                        elif line.option == 'day_current_month':
                            next_date += relativedelta(day=line.days, months=0)
                        if fields.Date.from_string(fields.Date.today()) <= next_date:
                            if len(invoices) == 1:
                                amt = rec['amount'] * (line.value_amount / 100.0)
                            else:
                                amt += inv.amount_residual_signed * (line.value_amount / 100.0)
                            rec.update({
                                'payment_difference_handling': 'reconcile',
                                'writeoff_account_id': inv.invoice_payment_term_id.escompte_account_id.id,
                                'writeoff_label': inv.invoice_payment_term_id.escompte_label,
                                'amount': amt,
                            })
                        else:
                            amt += inv.amount_residual_signed
        return rec

    @api.model
    def _compute_payment_amount(self, invoices, currency, journal, date):
        tot = super(AccountPayment, self)._compute_payment_amount(invoices, currency, journal, date)
        tots = 0
        for inv in invoices:
            if self._context.get('with_escompte', False) and inv.move_type == 'in_invoice' and inv.invoice_payment_term_id.is_escompte:
                for line in inv.invoice_payment_term_id.line_ids:
                    if line.value == 'percent':
                        next_date = fields.Date.from_string(inv.invoice_date)
                        if line.option == 'day_after_invoice_date':
                            next_date += relativedelta(days=line.days)
                            if line.day_of_the_month > 0:
                                months_delta = (line.day_of_the_month < next_date.day) and 1 or 0
                                next_date += relativedelta(day=line.day_of_the_month, months=months_delta)
                        elif line.option == 'after_invoice_month':
                            next_first_date = next_date + relativedelta(day=1, months=1)
                            next_date = next_first_date + relativedelta(days=line.days - 1)
                        elif line.option == 'day_following_month':
                            next_date += relativedelta(day=line.days, months=1)
                        elif line.option == 'day_current_month':
                            next_date += relativedelta(day=line.days, months=0)
                        if fields.Date.from_string(fields.Date.today()) <= next_date:
                            if len(invoices) == 1:
                                tots = tot * (line.value_amount / 100.0)
                            else:
                                tots += inv.amount_residual_signed * (line.value_amount / 100.0)
                        else:
                            tots += inv.amount_residual_signed
        #                 break
        return tots if tots != 0 else tot


class payment_register(models.TransientModel):
    _inherit = 'account.payment.register'

    def _get_payment_group_key(self, invoice):
        return (invoice.commercial_partner_id, invoice.currency_id, invoice.invoice_partner_bank_id, invoice.invoice_payment_term_id, MAP_INVOICE_TYPE_PARTNER_TYPE[invoice.move_type])

    def _prepare_payment_vals(self, invoices):
        amount = self.env['account.payment'].with_context(with_escompte = True)._compute_payment_amount(invoices, invoices[0].currency_id, self.journal_id, self.payment_date)
        values = {
            'journal_id': self.journal_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_date': self.payment_date,
            'communication': self._prepare_communication(invoices),
            'invoice_ids': [(6, 0, invoices.ids)],
            'payment_type': ('inbound' if amount > 0 else 'outbound'),
            'amount': abs(amount),
            'currency_id': invoices[0].currency_id.id,
            'partner_id': invoices[0].commercial_partner_id.id,
            'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].move_type],
            'partner_bank_account_id': invoices[0].invoice_partner_bank_id.id,
        }
        if invoices[0].invoice_payment_term_id.is_escompte:
            values.update({'payment_difference_handling': 'reconcile',
                           'writeoff_account_id': invoices[0].invoice_payment_term_id.escompte_account_id.id,
                           'writeoff_label': invoices[0].invoice_payment_term_id.escompte_label,
                          })
        return values