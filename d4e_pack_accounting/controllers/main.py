# -*- coding: utf-8 -*-
from odoo import http


class Main(http.Controller):

    @http.route('/report/isr/<active_ids>', auth='user')
    def report_isr(self, active_ids):
        invoice_ids = [int(active_id) for active_id in active_ids.split(',')]
        pdf_merge = http.request.env['account.move']._pdf_invoices_with_isr(invoice_ids)
        pdf_http_headers = [('Content-Type', 'application/pdf'), ('Content-Length', len(pdf_merge))]
        return http.request.make_response(pdf_merge, headers=pdf_http_headers)

    @http.route('/report/qr/<active_ids>', auth='user')
    def report_qr(self, active_ids):
        invoice_ids = [int(active_id) for active_id in active_ids.split(',')]
        pdf_merge = http.request.env['account.move']._pdf_invoices_with_qr(invoice_ids)
        pdf_http_headers = [('Content-Type', 'application/pdf'), ('Content-Length', len(pdf_merge))]
        return http.request.make_response(pdf_merge, headers=pdf_http_headers)
