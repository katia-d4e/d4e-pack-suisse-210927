# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    is_escompte = fields.Boolean("est un Escompte ")
    escompte_account_id = fields.Many2one('account.account', string="Comptabiliser l'escompte dans", copy=False)
    escompte_label = fields.Char("Libellé Escompte ")
