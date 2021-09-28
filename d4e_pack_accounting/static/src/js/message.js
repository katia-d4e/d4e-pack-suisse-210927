odoo.define('d4e_pack_accounting.Bank_account', function (require){
  "use strict";

var AbstractController = require('web.AbstractController');
var core = require('web.core');
var Dialog = require('web.Dialog');
var FieldManagerMixin = require('web.FieldManagerMixin');
var TranslationDialog = require('web.TranslationDialog');
var _t = core._t;

  //require the module to modify:
var Bank_account = require('web.BasicController');

  //override the method:
Bank_account.include({
      canBeDiscarded : function (recordID) {
        console.log("recordID : " + recordID);
        var self = this;
        console.log("self : " + self);
        if (this.discardingDef) {
            // discard dialog is already open
            return this.discardingDef;
        }
        if (!this.isDirty(recordID)) {
            return Promise.resolve(false);
        }

        var message = _t("The record has been modified, your changes will be discarded. Do you want to proceed?");
        if (recordID.includes('res.partner.bank_')) {
            message = _t("Please complete your bank information or your changes will be discarded.");
        }

        this.discardingDef = new Promise(function (resolve, reject) {
            var dialog = Dialog.confirm(self, message, {
                title: _t("Warning"),
                confirm_callback: () => {
                    resolve(true);
                    self.discardingDef = null;
                },
                cancel_callback: () => {
                    reject();
                    self.discardingDef = null;
                },
            });
            dialog.on('closed', self.discardingDef, reject);
        });
        return this.discardingDef;
    },


});

return Bank_account;

});

