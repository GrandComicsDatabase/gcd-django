// This is the JQuery way to run a function (in this case, an
// anonymous one) after the web page is ready
$(window).load(function(){
    // First get the width and height of the image with id 'cropbox'
    var width = $('#cropbox').width();
    var height = $('#cropbox').height();
    var real_width = parseInt($('#id_real_width').val());
    var ratio = width/real_width
    // Now create a jcrop object with some defaults
    // The onChange and onSelect attributes specify a function to run
    var jcrop = $.Jcrop('#cropbox', {
        onChange: updateForm,
        onSelect: updateForm,
        // we show the image scaled to width, adjust min_width accordingly
        minSize: [400*width/real_width, 0],
        maxSize: [0, height],
        setSelect: [0, 0, width, height]});

    // This function will run when the form fields are updated
    function updateSelection() {
        // Get the field values as integers
        x = parseInt($('#id_left').val());
        w = parseInt($('#id_width').val());
        y = parseInt($('#id_top').val());
        h = parseInt($('#id_height').val());

        x = parseInt(x*ratio);
        w = parseInt(w*ratio);
        y = parseInt(y*ratio);
        h = parseInt(h*ratio);
        // Now move the selection to new coordinates
        jcrop.setSelect([x, y, x+w, y+h]);
    };

    // This runs when the selection is changed, and updates the
    // form fields
    function updateForm(c) {
        $('#id_width').val(parseInt((c.x2 - c.x)/ratio));
        $('#id_left').val(parseInt(c.x/ratio));
        $('#id_height').val(parseInt((c.y2 - c.y)/ratio));
        $('#id_top').val(parseInt(c.y/ratio));
    };

    // This is to make sure that when the user presses enter
    // (keyCode == 13) in the fields, the form isn't submitted,
    // but the selection is updated
    function checkForEnter(event) {
        if (event.keyCode == 13) {
            updateSelection();
            event.preventDefault();
            return false;
        }
    }

    // Attach functions to events on the form fields
    $('#id_width, #id_left, #id_height, #id_top').change(updateSelection).keypress(checkForEnter);
});
