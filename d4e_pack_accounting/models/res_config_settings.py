# -*- coding: utf-8 -*-
from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def recompute_disount_values(self):
        model = self.env['account.move']
        invoices = model.search([])
        for inv in invoices:
            if inv.invoice_payment_state != 'paid':
                inv._compute_amount()
