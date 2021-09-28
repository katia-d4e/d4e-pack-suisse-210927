odoo.define('d4e_pack_accounting.sidebar', function (require) {
"use strict";

var core = require("web.core");
var Sidebar = require("web.Sidebar");
var _t = core._t;

Sidebar.include({
    currentRecords: [],
    labels: [],
    start: function () {
        return Promise.resolve(this._readRecord()).then(this._super.bind(this));
    },
    _readRecord: function() {
        var self = this;
        return self._rpc({
            context: self.env.context,
            model: 'ir.actions.server.menu',
            method: 'search_read',
            args: [[['id', '!=', -1]]],
        }).then(function (r) {
            if (!_.isEmpty(r)) {
                _.each(r, function (record) {
                    self.labels.push(new ActionServerMenuCdt(record));
                });
            }
        });
    },
    _addRecords: function (model, resID) {
        var self = this;
        if (!resID) {
            return Promise.resolve();
        }
        return self._rpc({
            context: self.env.context,
            model: model,
            method: 'search_read',
            args: [[['id', 'in', resID]]],
        }).then(function (r) {
            self.currentRecords = r;
        });
    },
    _showItem: function (item) {
        var tab = [];
        if (item.classname) {
            tab = item.classname.split(' ');
        }
        tab.splice(tab.indexOf('d-none'), 1);
        item.classname = tab.join(' ');
    },
    _hideItem: function (item) {
        var tab = [];
        if (item.classname) {
            tab = item.classname.split(' ');
        }
        tab.push('d-none');
        item.classname = tab.join(' ');
    },
    _manageItemBefore: function () {
        var self = this, model = self.env.model;
        for (var i = 0; i < self.items.other.length; i++) {
            var item = self.items.other[i];
            if (item.action) {
                for (var l = 0; l < self.labels.length; l++) {
                    var label = self.labels[l];
                    if (label.equalsAction(item.action)) {
                        var valid = true;
                        for (var j = 0; j < self.currentRecords.length; j++) {
                            var record = self.currentRecords[j];
                            valid = valid && label.validate(model, record);
                        }
                        if (!valid) {
                            self._hideItem(item);
                        } else {
                            self._showItem(item);
                        }
                        break;
                    }
                }
            }
        }
    },
    _redraw: function () {
        var self = this, def = self._addRecords(self.env.model, self.env.activeIds).then(function () {
            self._manageItemBefore();
        });
        return Promise.resolve(def).then(self._super.bind(self));
    },
});

class ActionServerMenuCdt {
    constructor(record) {
        this.action = record.action_id;
        this.condition = record.js_condition;
    }

    equalsAction(action) {
        return this.action[0] === action.id;
    }

    validate(model, record) {
        return eval(this.condition);
    }
}

});
