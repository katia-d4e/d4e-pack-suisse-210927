# -*- coding:utf-8 -*-
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _get_data_account_type_expenses(self):
        return [('user_type_id', '=', self.env.ref('account.data_account_type_expenses').id)]

    default_charge_account_for_capture = fields.Many2one(comodel_name='account.account',
                                                         string="Default charge account for capture",
                                                         domain=_get_data_account_type_expenses)

    def compute_customer_no(self):
        num = self.env['res.partner'].search([])
        maxi = num.mapped('customer_no')
        if not maxi:
            return 1
        return max(maxi) + 1

    customer_no = fields.Integer(string="Customer no.", default=compute_customer_no)
    phone_2 = fields.Char(string="Phone 2")
    postal_number_city_id = fields.Many2one('postal.number', string='City', ondelete='restrict')

    @api.onchange('zip')
    def on_change_zip(self):
        if self.zip:
            return {'domain': {'postal_number_city_id': [('postleitzahl', '=', self.zip)]}}
        else:
            self.postal_number_city_id = {}
            return {'domain': {'postal_number_city_id': []}}

    @api.onchange('postal_number_city_id')
    def on_change_city(self):
        if self.postal_number_city_id:
            self.zip = self.postal_number_city_id.postleitzahl
            self.city = self.postal_number_city_id.ortbez18

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if name:
            # Be sure name_search is symetric to name_get
            name = name.split(' / ')[-1]
            args = ['|', '|', '|', ('city', '=ilike', name + '%'), ('zip', '=ilike', name + '%'), ('name', operator, name), ('customer_no', operator, name)] + args
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)
