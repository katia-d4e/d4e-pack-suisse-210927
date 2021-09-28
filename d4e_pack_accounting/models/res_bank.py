# -*- coding: utf-8 -*-
from odoo.osv import expression
from odoo import api, fields, models, _
import requests


class ResBank(models.Model):
    _inherit = "res.bank"

    clearing = fields.Char(string="Clearing")
    swissbank_id = fields.Char()

    def name_get(self):
        res = super(ResBank, self).name_get()
        result = []
        for bank in self:
            name = bank.name + (bank.clearing and (' - ' + bank.clearing) or '') + (bank.city and (' - ' + bank.city) or '') + (bank.bic and (' - ' + bank.bic) or '')
            result.append((bank.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', '|', ('bic', '=ilike', name + '%'), ('name', operator, name), ('clearing', '=ilike', name + '%'), ('city', '=ilike', name + '%')]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&'] + domain
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)

    @api.model
    def create_bank_with_api(self):
        url = "https://api.six-group.com/api/epcd/bankmaster/v2/public"
        reponse = requests.get(url).json()
        for rec in reponse['entries']:
            swissbank_id = str(rec.get('group') or '') + str(rec.get('iid') or '') + str(rec.get('branchId') or '') + str(rec.get('sicIid') or '') + str(rec.get('headOffice') or '')
            idd = ''
            if rec.get('newIid'):
                idd = str(rec.get('newIid'))
            else:
                idd = str(rec.get('iid'))
            bank_vals = {
                'name': rec.get('bankOrInstitutionName') or '',
                'phone': rec.get('phone') or '',
                'zip': rec.get('zipCode') or '',
                'street': rec.get('domicileAddress') or '',
                'city': rec.get('place') or '',
                'bic': rec.get('bic') or '',
                'clearing': idd or '',
                'swissbank_id': swissbank_id,
            }
            bank = self.env["res.bank"].search([('swissbank_id', '=', bank_vals['swissbank_id'])])
            if bank:
                bank.write(bank_vals)
            else:
                self.env["res.bank"].create(bank_vals)


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    @api.onchange('bank_id')
    def on_change_bank_id(self):
        if self.bank_id.bic == '':
            title = _("Warning for %s", self.bank_id.name)
            message = _(
                "The selected bank does not contain BIC / SWIFT, please choose another bank or change the bank information.")
            warning = {
                'title': title,
                'message': message
            }
            return {'warning': warning}
