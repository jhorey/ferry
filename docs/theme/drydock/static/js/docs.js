
// This script should be included at the END of the document. 
// For the fastest loading it does not inlude $(document).ready()


$(function(){

    // sidebar accordian-ing
    // don't apply on last object (it should be the FAQ) or the first (it should be introduction)

    // define an array to which all opened items should be added
    var openmenus = [];

    var elements = $('.toctree-l1');
    for (var i = 0; i < elements.length; i += 1) {
        var current = $(elements[i]);

        if (current.hasClass('current')) {
            current.addClass('open');
            currentlink = current.children('a')[0].href;
            openmenus.push(currentlink);

            // do nothing
        } else {
            // collapse children
            current.children('ul').hide();
        }
    }

    // attached handler on click
    // We're removing the first two and last elements. A better way
    // would be to filter out elements that don't have any children.
    // However that requires someone that actually understands Javascript. 
    $('.sidebar > ul > li > a').not(':last').not(':first').not(':first').click(function(){
        var index = $.inArray(this.href, openmenus)
        if (index > -1) {
            console.log(index);
            openmenus.splice(index, 1);

            $(this).parent().children('ul').slideUp(200, function() {
                $(this).parent().removeClass('open'); // toggle after effect
            });
        }
        else {
            openmenus.push(this.href);

            var current = $(this);

            setTimeout(function() {
                // $('.sidebar > ul > li').removeClass('current');
                current.parent().addClass('current').addClass('open'); // toggle before effect
                current.parent().children('ul').hide();
                current.parent().children('ul').slideDown(200);
            }, 100);
        }
        return false;
    });

    // add class to all those which have children
    $('.sidebar > ul > li').not(':last').not(':first').not(':first').addClass('has-children');
});