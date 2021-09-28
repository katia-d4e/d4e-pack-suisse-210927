# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ActionServer(models.Model):
    _name = 'ir.actions.server.menu'
    _description = 'IR Actions Server Menu'

    condition = fields.Text()
    action_id = fields.Many2one(comodel_name='ir.actions.server')
    js_condition = fields.Text(compute='update_js_condition', store=True)

    @api.depends('condition')
    def update_js_condition(self):
        for record in self:
            condition = record.condition
            condition = condition.replace(' == ', ' == ')
            condition = condition.replace(' is ', ' === ')
            condition = condition.replace(' and ', ' && ')
            condition = condition.replace(' or ', ' || ')
            condition = condition.replace(' not ', ' ! ')
            condition = condition.replace('(not ', '(! ')
            condition = condition.replace('[not ', '[! ')
            record.js_condition = condition
