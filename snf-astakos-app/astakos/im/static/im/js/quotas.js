function group_form_show_resources(el){
	
	el.addClass('selected');
	var id = el.attr('id');
	$('.quotas-form .group').each(function() {
		if( $(this).hasClass(id) ) {
			 
			//$(this).appendTo('.visible');
			$(this).show('slow');		 
			$(this).find('input').first().focus();
 
		 
		}
	});
	 
	 
	if ($('.quotas-form .with-info .with-errors input[type="text"]')){
		$('.quotas-form .with-info .with-errors input[type="text"]').first().focus();	
	}
	
	
	 
	
	//setTimeout(function() { document.getElementById("city").focus(); }, 100);

}


function group_form_toggle_resources(el){
	

	var id = el.attr('id');
	$('.quotas-form .group').each(function() {
		if( $(this).hasClass(id) ) {
			 
			//$(this).appendTo('.visible');
			$(this).toggle('slow');		  
		}
	});
}


function bytesToSize2(bytes) {
    var sizes = [ 'n/a', 'bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    var i = +Math.floor(Math.log(bytes) / Math.log(1024));
    if (!isFinite(i)) { return 0 + 'KB'}
    return  (bytes / Math.pow(1024, i)).toFixed( 0 ) + sizes[ isNaN( bytes ) ? 0 : i+1 ];
}


function goToByScroll(id){
	$('html,body').animate({scrollTop: $("#"+id).offset().top},'slow');
}
	
$(document).ready(function() {

	
	 
	// ugly fix to transfer data easily 
	$('.with-info input[name^="is_selected_"]').each(function() {
		$(this).closest('.form-row').hide();
	});
    
	$('.quotas-form ul li a').click(function(e){
		
		// check the hidden input field
		$(this).siblings('input[type="hidden"]').val("1");
		
		// get the hidden input field without the proxy
		// and check the python form field
        var name = $(this).siblings('input[type="hidden"]').attr('name');
        if (!name) { return }
	 	var hidden_name = name.replace("proxy_","");
	 	$("input[name='"+hidden_name+"']").val("1");  
		
 		// prevent extra actions if it is checked		 
		if ( $(this).hasClass('selected')){
			 e.preventDefault();
			//group_form_toggle_resources($(this));
		} else {
			
			// show the relevant fieldsets
			group_form_show_resources($(this));
		}   
	});
	
	 
	
	
	 
	
	$('.quotas-form .group .delete').click(function(e){
		
		e.preventDefault(); 
		
		// clear form fields
		$(this).siblings('fieldset').find('input').val('');
		
		// clear errors
		$(this).siblings('fieldset').find('.form-row').removeClass('with-errors');
		 
		// hide relevant fieldset 
		$(this).parents('.group').hide('slow', function() {
		    //$(this).appendTo('.not-visible');
		    $(this).hide();	
		});
		
		group_class = $(this).parents('.group').attr('class').replace('group ', '');
		
		// unselect group icon
		$('.quotas-form ul li a').each(function() {
			if($(this).attr('id')==group_class) {
				$(this).removeClass('selected');
				$(this).siblings('input[type="hidden"]').val('0');
				
				// get the hidden input field without the proxy
				// and check the python form field
			 	hidden_name = $(this).siblings('input[type="hidden"]').attr('name').replace("proxy_","");
			 	$("input[name='"+hidden_name+"']").val('0');  
				
			}
		}); 
		
		// clear hidden fields
		$(this).siblings('fieldset').find('input[type="text"]').each(function() {
			hidden_name = $(this).attr('name').replace("_proxy","");
	 		hidden_input = $("input[name='"+hidden_name+"']");
	 		hidden_input.val('');
		});
		 
		 
	});
	  
	 	 
	// if you fill _proxy fields do stuff 
	$('.quotas-form .quota input[type="text"]').keyup(function () {
	 	
	 	if ( $('#icons span.info').hasClass('error-msg')){
			$('#icons span.info').find('span').html('Here you add resources to your Project. Each resource you specify here, will be granted to *EACH* user of this Project. So the total resources will be: &lt;Total number of members&gt; * &lt;amount_of_resource&gt; for each resource.');
	 	}
	 	 
	 	// get value from input
	 	var value = $(this).val();
	 	 
	 	//get input name without _proxy
	 	hidden_name = $(this).attr('name').replace("_proxy","");
	 	var hidden_input = $("input[name='"+hidden_name+"']");
	 	
        if (value.match(/^(inf|unlimited)/i)) { 
            $(this).closest('.form-row').removeClass('with-errors');
            hidden_input.val("Unlimited");
            return;
        }
	 	if (value) {
		 	// actions for humanize fields
		 	if ($(this).hasClass('dehumanize')){
		 		
		 		var flag = 0;

				// check if the value is not float
		 		var num_float = parseFloat(value);
		 		num_float= String(num_float);

		 		if (num_float.indexOf(".") == 1){
		 			flag = 1 ; 
		 			msg="Please enter an integer";
		 		} else {
		 			var num = parseInt(value);
					if ( num == '0' ) {
					} else {
						if ( value && !num ) { flag = 1 ; msg="Invalid format. Try something like 10GB, 2MB etc"}
				 	
					 	var bytes = num;
				 		
						// remove any numbers and get suffix		 		
				 		var suffix = value.replace( num, '');
		
				 		 // validate suffix. 'i' renders it case insensitive
					 	var suf = suffix.match( new RegExp('^(GB|KB|MB|TB|bytes|G|K|M|T|byte)$', 'i'));
					 	if (suf){
					 		
					 		suf = suf[0].toLowerCase(); 
					 		suf = suf.substr(0,1);
					 	
						 	// transform to bytes
						 	switch (suf){
						 		case 'b': 
						 		  bytes = num*Math.pow(1024,0);
						 		  break;
						 		case 'k':
						 		  bytes = num*Math.pow(1024,1);
						 		  break;
						 		case 'm':
						 		  bytes = num*Math.pow(1024,2);
						 		  break;
						 		case 'g':
						 		  bytes = num*Math.pow(1024,3);
						 		  break;
						 		case 't':
						 		  bytes = num*Math.pow(1024,4);
						 		  break;    
						 		default:
						 		  bytes = num; 
					 		}
					 	} else {
					 		if (num) {
					 		 	flag = 1;
					 		 	msg ="You must specify correct units. Try something like 10GB, 2MB etc" 
					 		}  
					 		 
					 	}
					}		 			
		 		} 
			 	
			 	if ( flag == '1' ){ 
			 		$(this).closest('.form-row').addClass('with-errors');
			 		$(this).closest('.form-row').find('.error-msg').html(msg);
			 		bytes = value;
			 		$(this).focus();
          $(this).data("not-valid", true);
			 	} else {
          $(this).data("not-valid", false);
			 		$(this).closest('.form-row').removeClass('with-errors');
			 	}
			 	
			 	hidden_input.val(bytes);
			 	
			 	
		 	}
		 	 
		 	// validation actions for int fields
		 	else {
		 		var is_int = value.match (new RegExp('^[0-9][0-9]*$'));
		 		if ( !is_int ){ 
		 			$(this).closest('.form-row').find('.error-msg').html('Enter a positive integer');
			 		$(this).closest('.form-row').addClass('with-errors');
          $(this).data("not-valid", true);
			 	} else {
          $(this).data("not-valid", false);
          $(this).closest('.form-row').removeClass('with-errors');
			 	}
			 	hidden_input.val(value);
	
		 	}
	 	
	 	} else {
	 		$(this).closest('.with-errors').removeClass('with-errors');
	 		hidden_input.removeAttr('value');
	 	}
	 	$('#icons span.info').removeClass('error-msg');
	 	
	 });
	 
	
	// if hidden checkboxes are checked, the right group is selected 
	$('.with-info input[name^="is_selected_"]').each(function() {
		if ( ($(this).val()) == 1 ){
			
			// get hidden input name
			hidden_name = $(this).attr('name');
			$("input[name='proxy_"+hidden_name+"']").val("1"); 
			
			// pretend to check the ul li a
			// show the relevant fieldsets
			var mock_a = $("input[name='proxy_"+hidden_name+"']").siblings('a');
			group_form_show_resources(mock_a);
			 
		}
	}); 
	
 
	 
	$('.group input[name$="_m_uplimit_proxy"], .group input[name$="_p_uplimit_proxy"]').each(function() {
		if ($(this).val()){
			// get value from input
	 		var value = $(this).val();
			
			// get hidden input name
			hidden_name = $(this).attr('name');
			hidden_field_name = hidden_name.replace("_proxy", "");
			$("input[name='"+hidden_field_name+"']").val(value);
			var field = $(this); 
			
			if ( (field.hasClass('dehumanize')) && !($(this).closest('.form-row').hasClass('with-errors'))) {
				// for dehumanize fields transform bytes to KB, MB, etc
				// unless there is an error
                if (value.match(/^(inf|unlimited)/i)) { 
                    field.val("Unlimited");
                    field.data("value", "Unlimited");
                } else {
                    field.val(bytesToSize2(value) || 0);
                    field.data("value", bytesToSize2(value) || 0);
                }
			} else {
				// else just return the value
				field.val(value);	
                field.data("value", value);
			}
			var group_class = field.closest('div[class^="group"]').attr('class').replace('group ', '');
            
			// select group icon
			$('.quotas-form ul li a').each(function() {
				
				if($(this).attr('id') == group_class) {
					$(this).addClass('selected');
					$(this).siblings('input[type="hidden"]').val("1");
					
					// get the hidden input field without the proxy
					// and check the python form field
				 	hidden_name = $(this).siblings('input[type="hidden"]').attr('name').replace("proxy_","");
				 	$("input[name='"+hidden_name+"']").val("1");  
				 	
				 	group_form_show_resources($(this));
				}
			}); 
			
			// if the field has class error, transfer error to the proxy fields
			if ( $(this).closest('.form-row').hasClass('with-errors') ) {
				field.closest('.form-row').addClass('with-errors');
			}
		}
	});  
	
	
	$('#group_create_form').submit(function(){
		var flag = 0;		 
		$('.quotas-form .group input[type="text"]').each(function() {
	 		var value = $(this).val();
			if (value){
				flag = 1;
			}
		});
		
		if (flag =='0') {
			$('#icons').focus();
			$('#icons span.info').addClass('error-msg');
			$('#icons span.info').find('span').html('You must fill in at least one resource');
			goToByScroll("icons");

			return false;
			
		}
		 
		
		if ($('.not-visible .group .with-errors').length > 0 ){
			//$('.not-visible .group .with-errors').first().find('input[type="text"]').focus();
			return false;
		}
	});

	//goToByScroll("top");
	$('.quotas-form .form-row.with-errors input[type="text"]').first().focus();
	
	// change error colors in quotas forms
	$('.quotas-form .quota input[type="text"]').focusout(function() {
	  $(this).closest('.with-errors').addClass('strong-error');
	   
	});
	$('.quotas-form .quota input[type="text"]').focusin(function() {
	  $(this).closest('.with-errors').removeClass('strong-error');
	   
	});
	  
    // enforce uplimit updates
  //$('.quotas-form .quota input[type="text"]').trigger("keyup");


    $('.resource-col input').each(function() {
        if (!$(this).attr("name").indexOf("proxy")) { return }
        if ($(this).hasClass("dehumanize") && $(this).closest(".form-row").hasClass("with-errors")) {
            var value = $(this).data("value");
            $(this).data("value", bytesToSize2(value) || 0);
            $(this).val(bytesToSize2(value));
        }
    });

    $('.resource-col input').bind("blur", function() {
        var name = $(this).attr("name");
        var initial_value = $(this).data("value");
        var value = $(this).val();
        var changed_value = $(this).data("changed-value");

        if ((!changed_value && initial_value != value) || 
                                                changed_value != value) {
            $(this).data("changed", true);
        } else {
            $(this).data("changed", false);
        }
        
        var get_el = function(id) {
            return $("input[name='"+name.replace(replace_str, id)+"']");
        }
        var replace_str = "m_uplimit_proxy";
        var other = get_el("p_uplimit_proxy");
        if (name.indexOf("p_uplimit_proxy") >= 0) {
            replace_str = "p_uplimit_proxy";
            other = get_el("m_uplimit_proxy");
        }

        window.setTimeout((function() { 
            return function() {

                var member_proxy_el = get_el("m_uplimit_proxy");
                var member_value_el = get_el("m_uplimit");
                var project_proxy_el = get_el("p_uplimit_proxy");
                var project_value_el = get_el("p_uplimit");
                var members_el = $("input[name='limit_on_members_number']");

                if (member_proxy_el.is(":focus") || 
                                            project_proxy_el.is(":focus")) {
                    return
                }
                
                if (!member_proxy_el.val() && !project_proxy_el.val()) {
                    return
                }
                
                if (!member_proxy_el.val()) {
                    if (project_proxy_el.data("not-valid")) {
                        return
                    }
                    member_proxy_el.val(project_proxy_el.val());
                    member_value_el.val(project_proxy_el.val());
                    member_proxy_el.trigger("keyup");
                    member_proxy_el.data("changed-value", 
                                         project_proxy_el.val());
                }

                if (other.closest(".form-row").hasClass("with-errors")) {
                  if (initial_value != value) {
                    other.val(other.val()).trigger("keyup");
                  }
                }

        }})(replace_str), 0);

    });
});
