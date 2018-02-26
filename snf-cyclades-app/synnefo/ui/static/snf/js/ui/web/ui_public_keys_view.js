// Copyright (C) 2010-2014 GRNET S.A.
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.
// 

;(function(root){
    
    // root
    var root = root;
    
    // setup namepsaces
    var snf = root.synnefo = root.synnefo || {};
    var models = snf.models = snf.models || {}
    var storage = snf.storage = snf.storage || {};
    var ui = snf.ui = snf.ui || {};
    var util = snf.util || {};
    var views = snf.views = snf.views || {}

    // shortcuts
    var bb = root.Backbone;
    
    // logging
    var logger = new snf.logging.logger("SNF-VIEWS");
    var debug = _.bind(logger.debug, logger);
      
    views.PublicKeyCreateView = views.Overlay.extend({
        view_id: "public_key_create_view",
        
        content_selector: "#public-key-create-content",
        css_class: 'overlay-public-key-create overlay-info',
        overlay_id: "public_key_create_view",

        subtitle: "",
        title: "Create new keypair",
        
        initialize: function() {
            views.PublicKeyCreateView.__super__.initialize.apply(this, arguments);
            this.form = this.$("form.model-form");
            this.submit = this.$(".form-actions .submit");
            this.cancel = this.$(".form-actions .cancel");
            this.close = this.$(".form-actions .close");
            this.error = this.$(".error-msg");
            this.model_actions = this.$(".model-actions");
            this.form_actions_cont = this.$(".form-actions");
            this.form_actions = this.$(".form-actions .form-action");
            this.form_file = this.$(".public-key .fromfile-field");

            this.input_name = this.form.find(".input-name");
            this.input_key = this.form.find("textarea");
            this.input_file = this.form.find(".content-input-file");
            
            this.generate_action = this.$(".model-action.generate");
            this.generate_msg = this.$(".generate-msg");
            this.generate_download = this.generate_msg.find(".download");
            this.generate_success = this.generate_msg.find(".success");

            this.generating = false;
            this.in_progress = false;
            this.init_handlers();
        },

        _init_reader: function() {
          var opts = {
            dragClass: "drag",
            accept: false,
            readAsDefault: 'BinaryString',
            on: {
              loadend: _.bind(function(e, file) {
                this.input_key.val(e.target.result);
                this.validate_form();
              }, this),
              error: function() {}
            }
          }
          FileReaderJS.setupInput(this.input_file.get(0), opts);
        },
        
        validate_form: function() {
          this.form.find(".error").removeClass("error");
          this.form.find(".errors").empty();

          var name = _.trim(this.input_name.val());
          var key = _.trim(this.input_key.val());
          var error = false;

          if (!name) {
            this.input_name.parent().find(".errors").append("<span class='error'>Key name cannot be blank.</span>");
            error = true;
          }

          var key_exists = !!snf.storage.keys.matching_keys(name).length
          if (key_exists) {
              this.input_name.parent().find(".errors").append("<span class='error'>Key name already in use.</span>");
              error = true;
          }

          if (!key) {
            this.input_key.parent().find(".errors").append("<span class='error'>Key content cannot be blank.</span>");
            error = true;
          } else {
            try {
              key = snf.util.validatePublicKey(key);
            } catch (err) {
              this.input_key.parent().find(".errors").append("<span class='error'>"+err+"</span>");
              error = true;
            }
          }

          if (error) { return false }
          return { key: key, name: name }
        },

        _reset_form: function() {
          this.input_name.val("");
          this.input_key.val("");
          this.input_file.val("");
          this.form.find(".error").removeClass("error");
          this.form.find(".errors").empty();
          this.form.show();
          this.generate_msg.hide();
          this.form_actions.show();
          this.form_file.show();
          this.input_file.show();
          this.close.hide();
          this.error.hide();
          this.model_actions.show();
        },

        beforeOpen: function() {
          this.private_key = undefined;
          this._reset_form();
          this._init_reader();
          this.unset_in_progress();
        },

        onOpen: function() {
          views.PublicKeyCreateView.__super__.onOpen.apply(this, arguments);
          this.input_name.focus();
        },
        
        init_handlers: function() {
          this.cancel.click(_.bind(function() { this.hide(); }, this));
          this.close.click(_.bind(function() { this.hide(); }, this));
          this.generate_action.click(_.bind(this.generate, this));
          this.generate_download.click(_.bind(this.download_key, this));
          this.form.submit(_.bind(function(e){
            e.preventDefault();
            this.submit_key(_.bind(function() {
              this.hide();
            }, this))
          }, this));
          this.submit.click(_.bind(function() {
            this.form.submit();
          }, this));
        },
        
        set_in_progress: function() {
          this.in_progress = true;
          this.submit.addClass("in-progress");
        },

        unset_in_progress: function() {
          this.in_progress = false;
          this.submit.removeClass("in-progress");
        },

        submit_key: function(cb) {
          var data = this.validate_form();
          if (!data) {
              return false;
          }

          this.set_in_progress();
          var params = {
            complete: _.bind(function() {
              synnefo.storage.keys.fetch();
              this.unset_in_progress();
              cb && cb();
            }, this)
          };

          return synnefo.storage.keys.create({
            content: data.key,
            name: data.name
          }, params);
        },

        download_key: function() {
          try {
            var blob = new Blob([this.private_key], {
              type: "application/x-perm-key;charset=utf-8"
            });
            saveAs(blob, "id_rsa");
          } catch (err) {
            alert(this.private_key);
          }
        },
        
        _generated_key_name: function() {
          if (this.input_name.val()) {
            return this.input_name.val();
          }
          var name_tpl = "Generated ssh key name";
          var name = name_tpl;
          var exists = function() {
            return synnefo.storage.keys.filter(function(key){
              return key.get("name") == name;
            }).length > 0;
          }

          var count = 1;
          while(exists()) {
            name = name_tpl + " {0}".format(++count);
          }
          return name;
        },

        generate: function() {
          this.error.hide();
          this.generate_msg.hide();

          if (this.generating) { return }
          
          this.generating = true;
          this.generate_action.addClass("in-progress");
          
          var success = _.bind(function(key) {
            this.input_name.val(this._generated_key_name());
            this.input_key.val(key.public);
            this.private_key = key.private;

            this.form_file.hide();
            this.generating = false;
            this.generate_action.removeClass("in-progress");
            this.generate_msg.show();

            var submitWasSuccessful = !!this.submit_key();
            if (submitWasSuccessful) {
                this.form.hide();
                this.form_actions.hide();
                this.close.show();
                this.model_actions.hide();
            }
          }, this);
          var error = _.bind(function() {
            this.generating = false;
            this.generate_action.removeClass("in-progress");
            this.private_key = undefined;
            this.show_error();
          }, this);
          var key = storage.keys.generate_new(success, error);
        },

        show_error: function(msg) {
          msg = msg === undefined ? "Something went wrong. Please try again later." : msg;
          if (msg) { this.error.find("p").html(msg) }
          this.error.show();
        }
    });

    views.PublicKeyView = views.ext.ModelView.extend({
      tpl: '#public-key-view-tpl',
      post_init_element: function() {
        this.content = this.$(".content-cont");
        this.content.hide();
        this.content_toggler = this.$(".cont-toggler");
        this.content_toggler.click(this.toggle_content);
        this.content_visible = false;
      },

      toggle_content: function() {
        if (!this.content_visible) {
          this.content.slideDown(function() {
            $(window).trigger("resize");
          });
          this.content_visible = true;
          this.content_toggler.addClass("open");
        } else {
          this.content.slideUp(function() {
            $(window).trigger("resize");
          });
          this.content_visible = false;
          this.content_toggler.removeClass("open");
        }
      },

      remove_key: function() {
        this.model.do_remove();
      },

      post_hide: function() {
        views.PublicKeyView.__super__.post_hide.apply(this);
        if (this.content_visible) {
          this.toggle_content();
          this.content.hide();
        }
      }
    });
    
    views.PublicKeysCollectionView = views.ext.CollectionView.extend({
      collection: storage.keys,
      collection_name: 'keys',
      model_view_cls: views.PublicKeyView,
      create_view_cls: views.PublicKeyCreateView,
      initialize: function() {
        views.PublicKeysCollectionView.__super__.initialize.apply(this, arguments);
        this.collection.bind("add", _.bind(this.update_quota, this));
        this.collection.bind("remove", _.bind(this.update_quota, this));
        this.collection.bind("reset", _.bind(this.update_quota, this));
      },

      update_quota: function() {
        var quota = synnefo.config.userdata_keys_limit;
        var available = quota - this.collection.length;
        if (!available) {
          var msg = snf.config.limit_reached_msg;
          snf.util.set_tooltip(this.create_button, this.quota_limit_message || msg, {tipClass: 'warning tooltip'});
          this.create_button.addClass("disabled");
        } else {
          snf.util.unset_tooltip(this.create_button);
          this.create_button.removeClass("disabled");
        }
      }
    });

    views.PublicKeysPaneView = views.ext.PaneView.extend({
      id: "pane",
      el: '#public-keys-pane',
      collection_view_cls: views.PublicKeysCollectionView,
      collection_view_selector: '#public-keys-list-view'
    });

})(this);

