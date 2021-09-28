# -*- coding: utf-8 -*-
from odoo import models


class BaseOrder(models.AbstractModel):
    _name = 'base.order'

    def get_config_param(self, value: str) -> str:
        return self.env['ir.config_parameter'].sudo().get_param(value)

    def show_line_subtotals_tax_selection(self) -> str:
        return self.get_config_param('account.show_line_subtotals_tax_selection') or 'tax_excluded'
