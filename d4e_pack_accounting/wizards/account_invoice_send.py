# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import api, fields, models, _


class AccountInvoiceSend(models.TransientModel):
    _inherit = 'account.invoice.send'

    def send_and_print_action(self):
        res = super(AccountInvoiceSend, self).send_and_print_action()
        self.ensure_one()
        if self.composition_mode == 'mass_mail' and self.template_id:
            active_ids = self.env.context.get('active_ids', self.res_id)
            active_records = self.env[self.model].browse(active_ids)
            for rec in active_records:
                rec.print_date = datetime.now()
                rec.sent = True
        else:
            active_id = self.env.context.get('active_id')
            active_record = self.env[self.model].browse(active_id)
            active_record.print_date = datetime.now()
            active_record.sent = True
        return res
