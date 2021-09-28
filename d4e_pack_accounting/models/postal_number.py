# -*- coding: utf-8 -*-
from odoo import api, fields, models
import requests


class PostalNumber(models.Model):
    _description = 'Postal Number'
    _name = 'postal.number'
    _rec_name = 'ortbez18'

    onrp = fields.Char(string='Identifiant')
    bfsnr = fields.Char(string='N° OFS')
    plz_typ = fields.Char(string='Type de NPA')
    kanton = fields.Char(string='Canton')
    postleitzahl = fields.Char(string='NPA')
    ortbez18 = fields.Char(string='Localité')
    sprachcode = fields.Selection([('1', 'Allemand'), ('2', 'Français'), ('3', 'Italien')], string="Langue", default='1')

    @api.model
    def create_postal_number_with_api(self):
        pas = 100
        start = 0
        exist_response = True
        while exist_response:
            print("start", start)
            exist_response = False
            params = {
                'rows': pas,
                'start': start,
            }
            start += pas
            url = "https://swisspost.opendatasoft.com/api/records/1.0/search/?dataset={}&facet={}&facet={}&facet={}&facet={}&facet={}&facet={}&facet={}&rows={}&start={}".format(
                str('plz_verzeichnis_v2'), str('onrp'), str('bfsnr'), str('plz_typ'), str('postleitzahl'), str('ortbez18'),
                str('kanton'), str('sprachcode'), str(params['rows']), str(params['start']))
            reponse = requests.get(url).json()
            for rec in reponse['records']:
                exist_response = True
                post_vals = {
                    'onrp': rec['fields']['onrp'],
                    'bfsnr': rec['fields']['bfsnr'],
                    'plz_typ': rec['fields']['plz_typ'],
                    'kanton': rec['fields']['kanton'],
                    'postleitzahl': rec['fields']['postleitzahl'],
                    'ortbez18': rec['fields']['ortbez18'],
                    'sprachcode': str(rec['fields']['sprachcode']),
                }
                npa = self.env["postal.number"].search([('onrp', '=', post_vals['onrp'])])
                if npa:
                    npa.write(post_vals)
                else:
                    self.env["postal.number"].create(post_vals)
