# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import ValidationError


class Report(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, res_ids=None, data=None):
        report_name = self.sudo().report_name
        report_type = self.sudo().report_type
        if report_type == 'qweb-pdf' and report_name in ['d4e_pack_accounting.account_invoices_with_isr', 'd4e_pack_accounting.account_invoices_with_qr']:
            if not data:
                data = {}
            data.setdefault('report_type', 'html')
            data = self._get_rendering_context(res_ids, data)
            if report_name == 'd4e_pack_accounting.account_invoices_with_isr':
                doc_ids = data.get('doc_ids', [])
                if doc_ids:
                    pdf_content = self.env['account.move'].sudo()._pdf_invoices_with_isr(doc_ids)
                    return pdf_content, 'pdf'
                raise ValidationError('Select a document')
            elif report_name == 'd4e_pack_accounting.account_invoices_with_qr':
                doc_ids = data.get('doc_ids', [])
                if doc_ids:
                    pdf_content = self.env['account.move'].sudo()._pdf_invoices_with_qr(doc_ids)
                    return pdf_content, 'pdf'
                raise ValidationError('Select a document')
        return super(Report, self)._render_qweb_pdf(res_ids=res_ids, data=data)

    def report_action(self, docids, data=None, config=True):
        res = super(Report, self).report_action(docids=docids, data=data, config=config)
        if self == self.env.ref('account.account_invoices'):
            active_ids = self.env['account.move'].sudo()
            if docids:
                if isinstance(docids, models.Model):
                    active_ids = docids
                elif isinstance(docids, int):
                    active_ids = active_ids.browse([docids])
                elif isinstance(docids, list):
                    active_ids = active_ids.browse(docids)
            active_ids.update_print_date()
        return res
