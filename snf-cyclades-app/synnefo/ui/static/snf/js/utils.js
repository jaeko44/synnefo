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
    
    var root = root;
    var snf = root.synnefo = root.synnefo || {};
    
    snf.i18n = {};

    // Logging namespace
    var logging = snf.logging = snf.logging || {};

    // logger object
    var logger = logging.logger = function(ns, level){
        var levels = ["debug", "info", "error"];
        var con = window.console;
        
        this.level = level || synnefo.logging.level;
        this.ns = ns || "";

        this._log = function(lvl) {
            if (lvl >= this.level && con) {
                var args = Array.prototype.slice.call(arguments[1]);
                var level_name = levels[lvl];
                    
                if (this.ns) {
                    args = ["["+this.ns+"] "].concat(args);
                }

                log = con.log
                if (con[level_name])
                    log = con[level_name]

                try {
                    con && log.apply(con, Array.prototype.slice.call(args));
                } catch (err) {}
            }
        }

        this.debug = function() {
            var args = [0]; args.push.call(args, arguments);
            this._log.apply(this, args);
        }

        this.info = function() {
            var args = [1]; args.push.call(args, arguments);
            this._log.apply(this, args);
        }

        this.error = function() {
            var args = [2]; args.push.call(args, arguments);
            this._log.apply(this, args);
        }

    };
    
    synnefo.collect_user_data = function() {
        var data = {}
        
        try {
            data.client = {'browser': $.browser, 'screen': $.extend({}, screen), 'client': $.client}
        } catch (err) { data.client = err }
        try {
            data.calls = synnefo.api.requests;
        } catch (err) { data.calls = err }
        try {
            data.errors = synnefo.api.errors;
        } catch (err) { data.errors = err }
        try {
            data.data = {};
        } catch (err) { data.data = err }
        try {
            data.data.vms = synnefo.storage.vms.toJSON();
        } catch (err) { data.data.vms = err }
        try {
            data.data.networks = synnefo.storage.networks.toJSON();
        } catch (err) { data.data.networks = err }
        //try {
            //data.data.images = synnefo.storage.images.toJSON();
        //} catch (err) { data.data.images = err }
        //try {
            //data.data.flavors = synnefo.storage.flavors.toJSON();
        //} catch (err) { data.data.flavors = err }
        try {
            data.date = new Date;
        } catch (err) { data.date = err }

        return data;
    }

    // default logger level (debug)
    synnefo.logging.level = 0;

    // generic logger
    synnefo.log = new logger({'ns':'SNF'});

    // synnefo config options
    synnefo.config = synnefo.config || {};
    synnefo.config.api_url = "/api/v1.1";
    
    // Util namespace
    synnefo.util = synnefo.util || {};
    
    synnefo.util.FormatDigits = function(num, length) {
        var r = "" + num;
        while (r.length < length) {
            r = "0" + r;
        }
        return r;
    }

    synnefo.util.formatDate = function(d) {
        var dt = synnefo.util.FormatDigits(d.getDate()) + '/';
        dt += synnefo.util.FormatDigits(d.getMonth() + 1, 2);
        dt += '/' + d.getFullYear();
        dt += ' ' + synnefo.util.FormatDigits(d.getHours(), 2) + ':';
        dt += synnefo.util.FormatDigits(d.getMinutes(), 2) + ':';
        dt += synnefo.util.FormatDigits(d.getSeconds(), 2);
        return dt;
    },

    // Extensions and Utility functions
    synnefo.util.ISODateString = function(d){
        function pad(n){
            return n<10 ? '0'+n : n
        }
         return d.getUTCFullYear()+'-'
         + pad(d.getUTCMonth()+1)+'-'
         + pad(d.getUTCDate())+'T'
         + pad(d.getUTCHours())+':'
         + pad(d.getUTCMinutes())+':'
         + pad(d.getUTCSeconds())+'Z'
    }

    
    synnefo.util.parseHeaders = function(headers) {
        var res = {};
        _.each(headers.split("\n"), function(h) {
            var tuple = h.split(/:(.+)?/);
            if (!tuple.length > 1 || !(tuple[0] && tuple[1])) {
                return;
            }
            res[tuple[0]] = tuple[1]
        })

        return res;
    }

    synnefo.util.parseUri = function(sourceUri) {
        var uriPartNames = ["source","protocol","authority","domain","port","path","directoryPath","fileName","query","anchor"];
        var uriParts = new RegExp("^(?:([^:/?#.]+):)?(?://)?(([^:/?#]*)(?::(\\d*))?)?((/(?:[^?#](?![^?#/]*\\.[^?#/.]+(?:[\\?#]|$)))*/?)?([^?#/]*))?(?:\\?([^#]*))?(?:#(.*))?").exec(sourceUri);
        var uri = {};
        
        for(var i = 0; i < 10; i++){
            uri[uriPartNames[i]] = (uriParts[i] ? uriParts[i] : "");
        }
    
        // Always end directoryPath with a trailing backslash if a path was present in the source URI
        // Note that a trailing backslash is NOT automatically inserted within or appended to the "path" key
        if(uri.directoryPath.length > 0){
            uri.directoryPath = uri.directoryPath.replace(/\/?$/, "/");
        }
        
        return uri;
    }

    synnefo.util.equalHeights = function() {
        var max_height = 0;
        var selectors = _.toArray(arguments);
    }

    synnefo.util.ClipHelper = function(wrapper, text, settings) {
        settings = settings || {};
        this.el = $('<div class="clip-copy"></div>');
        wrapper.append(this.el);
        this.clip = $(this.el).zclip(_.extend({
            path: synnefo.config.js_url + "lib/ZeroClipboard.swf",
            copy: text
        }, settings));
    }

    synnefo.util.truncate = function(string, size, append, words) {
        if (string === undefined) { return "" };
        if (string.length <= size) {
            return string;
        }

        if (append === undefined) {
            append = "...";
        }
        
        if (!append) { append = "" };
        // TODO: implement word truncate
        if (words === undefined) {
            words = false;
        }
        
        len = size - append.length;
        return string.substring(0, len) + append;
    }

    synnefo.util.PRACTICALLY_INFINITE = 9223372036854776000;

    synnefo.util.readablizeBytes = function(bytes, fix) {
        if (parseInt(bytes) == 0) { return '0 bytes' }
        if (fix === undefined) { fix = 2; }
        bytes = parseInt(bytes);
        if (bytes >= synnefo.util.PRACTICALLY_INFINITE) {
            return 'Infinite';
        }
        var s = ['bytes', 'kb', 'MB', 'GB', 'TB', 'PB'];
        var e = Math.floor(Math.log(bytes)/Math.log(1024));
        if (e > s.length) {
            e = s.length - 1;
        }
        ret = (bytes/Math.pow(1024, Math.floor(e))).toFixed(fix)+" "+s[e];
        return ret;
    }
    

    synnefo.util.SUBNET_REGEX = /(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/([0-9]|[1-2][0-9]|3[0-2]?)$/;
    synnefo.util.IP_REGEX = /(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;

    synnefo.i18n.API_ERROR_MESSAGES = {
        '403': {
            'non_critical': true,
            'allow_report': false,
            'allow_reload': false,
            'allow_details': false,
            'details': false,
            'title': 'API error'
        },
        'timeout': {
            'title': 'API error',
            'message': 'TIMEOUT', 
            'allow_report': false,
            'type': 'Network'
        },
        'limit_error': {
            'title': 'API error',
            'message': 'Not enough quota available to perform this action.'
        },
        'error': {
            'title': 'API error',
            'message': null
        }, 

        'abort': {},
        'parserror': {},
        '413': {
            'title': "Account warning"
        }
    }
    
    synnefo.util.array_diff = function(arr1, arr2) {
        var removed = [];
        var added = [];

        _.each(arr1, function(v) {
            if (arr2.indexOf(v) == -1) {
                removed[removed.length] = v;
            }
        })


        _.each(arr2, function(v) {
            if (arr1.indexOf(v) == -1) {
                added[added.length] = v;
            }
        })

        return {del: removed, add: added};
    }
    
    synnefo.util.set_tooltip = function(el, title, custom_params) {
        if ($(el).data.tooltip) { return }
        var base_params = {
            'tipClass': 'tooltip',
            'position': 'top center',
            'offset': [-5, 0]
        }
        if (!custom_params) { custom_params = {}; }
        var params = _.extend({}, base_params, custom_params);

        if (title !== undefined)  {
            $(el).attr("title", title);
        }
        
        $(el).tooltip(params);
    }

    synnefo.util.unset_tooltip = function(el) {
        $(el).attr("title", "");
        $(el).tooltip("remove");
    }

    synnefo.util.open_window = function(url, name, opts) {
        // default specs
        opts = _.extend({
            menubar: 'no',
            toolbar: 'no',
            status: 'no',
            height: screen.height,
            width: screen.width,
            fullscreen: 'yes',
            channelmode: 'yes',
            directories: 'no',
            left: 0,
            location: 'no',
            top: 0
        }, opts)
        
        var specs = _.map(opts, function(v,k) {return k + "=" + v}).join(",");
        window.open(url, name, specs);
    }
    
    synnefo.util.readFileContents = function(f, cb) {
        var reader = new FileReader();
        var start = 0;
        var stop = f.size - 1;

        reader.onloadend = function(e) {
            return cb(e.target.result);
        }
        
        var data = reader.readAsText(f);
    },
    
    synnefo.util.generateKey = function(passphrase, length) {
        var passphrase = passphrase || "";
        var length = length || 1024;
        var key = cryptico.generateRSAKey(passphrase, length);

        _.extend(key.prototype, {
            download: function() {
            }
        });

        return key;
    }
    
    synnefo.util.publicKeyTypesMap = {
        "ecdsa-sha2-nistp256": "ecdsa",
        "ssh-dss" : "dsa",
        "ssh-rsa": "rsa",
        "ssh-ed25519": "eddsa",
        "ecdsa-sha2-nistp384": "ecdsa",
        "ecdsa-sha2-nistp521": "ecdsa",
    }

    /*
    * This function implements client side validation of the user provided key.
    * The process is as follows:
    * 0) Split the input to extract the first two parts, which represent
    *    the key-type and the key-content as a base64 formatted string.
    * 1) base64 decode the key contents
    * 2) From the key header extract the key type
    * 3) Validated the type of the key
    * 4) Return the verified key
    *
    * In case the key is invalid an exception will be raised
    */
    synnefo.util.validatePublicKey = function(key) {

        ERR_INVALID_CONTENT = "Invalid key content";
        ERR_INVALID_TYPE = "Invalid or unknown key type"

        var parts = key.split(/[\r\n]/).join("").split(/\s+/);

        var key_type = parts[0];
        var key_content = parts[1];

        if (!key_type && !key_content) {
            throw ERR_INVALID_CONTENT;
        } else if (!key_content) {
            key_content = parts[0];
        }

        var header = {
            type: {
                SIZE: 4,
                length: null,
                content: null
            },
        }

        var checksum;
        try {
            checksum = $.base64.decode(key_content);
        } catch (err) {
            throw ERR_INVALID_CONTENT;
        }

        // Public Key header
        //
        // +------------------+-------------+-------------------------+----------+----------------------+
        // | Type Length (tl) | Type string | Length of exponent (el) | Exponent | Checksum length (cl) |
        // +------------------+-------------+-------------------------+----------+----------------------+
        // |      4 Bytes     |  tl Bytes   |         4 Bytes         | el Bytes |       4 Bytes        |
        // +------------------+-------------+-------------------------+----------+----------------------+
        //

        // Construct the length of key type based on the bytes of the respective
        // header field
        header.type.length = Array.from(checksum.slice(0, header.type.SIZE)).reduce(function(acc, v, i) {
            return acc + v.charCodeAt(0) << 8 * (header.type.SIZE - i - 1);
        }, 0)

        header.type.content = checksum.slice(header.type.SIZE,
                                             header.type.SIZE + header.type.length);

        if (synnefo.util.publicKeyTypesMap[header.type.content]
           && (header.type.content == key_type || !key_type)) {
            return [header.type.content, key_content].join(" ");
        } else {
            throw ERR_INVALID_TYPE;
        }

    }
    
    // detect flash `like a boss`
    // http://stackoverflow.com/questions/998245/how-can-i-detect-if-flash-is-installed-and-if-not-display-a-hidden-div-that-inf/3336320#3336320 
    synnefo.util.hasFlash = function() {
        var hasFlash = false;
        try {
            var fo = new ActiveXObject('ShockwaveFlash.ShockwaveFlash');
            if (fo) hasFlash = true;
        } catch(e) {
          if(navigator.mimeTypes ["application/x-shockwave-flash"] != undefined) hasFlash = true;
        }
        return hasFlash;
    }

    synnefo.util.promptSaveFile = function(selector, filename, data, options) {
        if (!synnefo.util.hasFlash()) { return };
        try {
            return $(selector).downloadify(_.extend({
                filename: function(){ return filename },
                data: function(){ return data },
                onComplete: function(){},
                onCancel: function(){},
                onError: function(){
                    console.log("ERROR", arguments);
                },
                swf: synnefo.config.media_url + 'js/lib/media/downloadify.swf',
                downloadImage: synnefo.config.images_url + 'download.png',
                transparent: true,
                append: false,
                height:20,
                width: 20,
                dataType: 'string'
          }, options));
        } catch (err) {
            return false;
        }
    }

    synnefo.util.canReadFile = function() {
        if ($.browser.msie) { return false };
        if (window.FileReader && window.File) {
            var f = File.prototype.__proto__;
            if (f.slice || f.webkitSlice || f.mozSlice) {
                return true
            }
        }
        return false;
    }

    synnefo.util.errorList = function() {
        
        this.initialize = function() {
            this.errors = {};
        }

        this.add = function(key, msg) {
            this.errors[key] = this.errors[key] || [];
            this.errors[key].push(msg);
        }

        this.get = function(key) {
            return this.errors[key];
        }

        this.empty = function() {
            return _.isEmpty(this.errors);
        }

        this.initialize();
    }

    synnefo.util.stacktrace = function() {
        try {
            var obj = {};
            if (window.Error && Error.captureStackTrace) {
                Error.captureStackTrace(obj, synnefo.util.stacktrace);
                return obj.stack;
            } else {
                return printStackTrace().join("<br /><br />");
            }
        } catch (err) {}
        return "";
    },
    
    synnefo.util.array_combinations = function(arr) {
        if (arr.length == 1) {
            return arr[0];
        } else {
            var result = [];

            // recur with the rest of array
            var allCasesOfRest = synnefo.util.array_combinations(arr.slice(1));  
            for (var i = 0; i < allCasesOfRest.length; i++) {
                for (var j = 0; j < arr[0].length; j++) {
                    result.push(arr[0][j] + "-" + allCasesOfRest[i]);
                }
            }
            return result;
        }
    }

    synnefo.util.parse_api_error = function() {
        if (arguments.length == 1) { arguments = arguments[0] };

        var xhr = arguments[0];
        var error_message = arguments[1];
        var error_thrown = arguments[2];
        var ajax_settings = _.last(arguments) || {};
        var call_settings = ajax_settings.error_params || {};
        var json_data = undefined;

        var critical = ajax_settings.critical === undefined ? true : ajax_settings.critical;

        if (xhr.responseText) {
            try {
                json_data = JSON.parse(xhr.responseText)
            } catch (err) {
                json_data = 'Raw error response contnent (could not parse as JSON):\n\n' + xhr.responseText;
            }
        }
        
        module = "API"

        try {
            path = synnefo.util.parseUri(ajax_settings.url).path.split("/");
            path.splice(0,3)
            module = path.join("/");
        } catch (err) {
            console.error("cannot identify api error module");
        }
        
        defaults = {
            'message': 'Api error',
            'type': 'API',
            'allow_report': true,
            'fatal_error': ajax_settings.critical || false,
            'non_critical': !critical
        }

        var code = -1;
        try {
            code = xhr.status || "undefined";
        } catch (err) {console.error(err);}
        var details = "";
        
        if ([413].indexOf(code) > -1) {
            defaults.non_critical = true;
            defaults.allow_report = false;
            defaults.allow_reload = false;
            error_message = "limit_error";
        }

        if (critical) {
            defaults.allow_report = true;
        }
        
        if (json_data) {
            if (_.isObject(json_data)) {
                $.each(json_data, function(key, obj) {
                    code = obj.code;
                    details = obj.details;
                    error_message = obj.message ? obj.message : error_message;
                })
            } else {
                details = json_data;
            }
        }

        extra = {'URL': ajax_settings.url};
        options = {};
        options = _.extend(options, {'details': details, 'message': error_message, 'ns': module, 'extra_details': extra});
        options = _.extend(options, call_settings);
        options = _.extend(options, synnefo.i18n.API_ERROR_MESSAGES[error_message] || {});
        options = _.extend(options, synnefo.i18n.API_ERROR_MESSAGES[code] || {});
        
        options.api_message = options.message;

        if (window.ERROR_OVERRIDES && window.ERROR_OVERRIDES[options.message]) {
            options.message = window.ERROR_OVERRIDES[options.message];
            options.api_message = '';
        }
        
        if (code && window.ERROR_OVERRIDES && window.ERROR_OVERRIDES[code]) {
            options.message = window.ERROR_OVERRIDES[code];
        }
        
        if (options.api_message == options.message) {
          options.api_message = '';
        }
        options = _.extend(defaults, options);
        options.code = code;

        return options;
    }


    // Backbone extensions
    //
    // super method
    Backbone.Model.prototype._super = Backbone.Collection.prototype._super = Backbone.View.prototype._super = function(funcName){
        return this.constructor.__super__[funcName].apply(this, _.rest(arguments));
    }

    // simple string format helper 
    // http://stackoverflow.com/questions/610406/javascript-equivalent-to-printf-string-format
    String.prototype.format = function() {
        var formatted = this;
        for (var i = 0; i < arguments.length; i++) {
            var regexp = new RegExp('\\{'+i+'\\}', 'gi');
            formatted = formatted.replace(regexp, arguments[i]);
        }
        return formatted;
    };


    $.fn.setCursorPosition = function(pos) {
        $(this).selectRange(pos, pos);
    }

    $.fn.selectRange = function(from, to) {
        try {
            if (to == undefined) {
                to = $(this).val().length;
            }
            if ($(this).get(0).setSelectionRange) {
              $(this).get(0).setSelectionRange(from, to);
            } else if ($(this).get(0).createTextRange) {
              var range = $(this).get(0).createTextRange();
              range.collapse(true);
              range.moveEnd('character', to);
              range.moveStart('character', from);
              range.select();
            }
        } catch(err) {}
    }

    // trim prototype for IE
    if(typeof String.prototype.trim !== 'function') {
        String.prototype.trim = function() {
            return this.replace(/^\s+|\s+$/g, '');
        }
    }

    // indexOf prototype for IE
    if (!Array.prototype.indexOf) {
      Array.prototype.indexOf = function(elt /*, from*/) {
        var len = this.length;
        var from = Number(arguments[1]) || 0;
        from = (from < 0)
             ? Math.ceil(from)
             : Math.floor(from);
        if (from < 0)
          from += len;

        for (; from < len; from++) {
          if (from in this &&
              this[from] === elt)
            return from;
        }
        return -1;
      };
    }

    $.fn.insertAt = function(elements, index){
        var children = this.children();
        if(index >= children.size()){
            this.append(elements);
            return this;
        }
        var before = children.eq(index);
        $(elements).insertBefore(before);
        return this;
    };
    
    // https://gist.github.com/gid79/854708
    var tooltip = $.fn.tooltip,
        slice = Array.prototype.slice;
 
    function removeTooltip($elements){
        $elements.each(function(){
            if (!$(this).data("tooltip")) { return }
            var $element = $(this),
                api = $element.data("tooltip"),
                tip = api.getTip(),
                trigger = api.getTrigger();
            api.hide();
            if( tip ){
                tip.remove();
            }
            trigger.unbind('mouseenter mouseleave');
            $element.removeData("tooltip");
        });
    }
 
    $.fn.tooltip = function(p){
        if( p === 'remove'){
            removeTooltip(this);
            return this;
        } else {
            return tooltip.apply(this, slice.call(arguments,0));
        }
    }

})(this);
