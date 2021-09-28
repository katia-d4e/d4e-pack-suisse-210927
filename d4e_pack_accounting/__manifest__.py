# -*- coding: utf-8 -*-
{
    'name': "Pack Accounting",
    'description': """Digital4Efficiency - Pack Accounting""",
    'author': "D4E",
    'website': "https://www.d4e.cool",
    'category': 'Tools',
    'version': '14.0.1.0',
    'depends': [
        'contacts',
        'sale_management',
        'account_accountant',
        'l10n_ch',
        'account_reports',
        'hr',
        'web',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Data
        'data/product_discount.xml',
        # Views
        'views/assets.xml',
        'views/account.xml',
        'views/sale_order.xml',
        'views/res_partner.xml',
        'views/template.xml',
        'views/res_bank.xml',
        'views/postal_number.xml',
        'views/res_config_settings_views.xml',
        # Reports
        'reports/report_invoice.xml',
        'reports/sale_report_templates.xml',
    ],
    'demo': [],
    'qweb': [],
    'application': True,
    'auto_install': False,
}
