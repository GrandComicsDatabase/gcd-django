// Convert argument to integer and return value as string
function intString(num) {
    return Math.round(num).toString();
}

// This is the JQuery way to run a function (in this case, an
// anonymous one) after the web page is ready
$(window).load(function() {
    // First get the width and height of the image with id 'cropbox'
    var width = $('#cropbox').width();
    var height = $('#cropbox').height();
    var preview_width = $('#preview_box').width();
    var preview_height = $('#preview_box').height();
    var real_width = parseInt($('#id_real_width').val(), 10);
    var ratio = width/real_width;

    // This runs when the selection is changed, and updates the
    // form fields
    var updateForm = function(coords) {
        $('#id_width').val(intString(coords.w / ratio));
        $('#id_left').val(intString(coords.x / ratio));
        $('#id_height').val(intString(coords.h / ratio));
        $('#id_top').val(intString(coords.y / ratio));
        showPreview(coords);
    };

    // Update preview thumbnail
    function showPreview(coords) {
        var rx = preview_width / coords.w;
        var preview_height = preview_width * coords.h / coords.w;
        var ry = preview_height / coords.h;

        $('#preview_box').css({ height: Math.round(preview_height) + 'px' });

        $('#preview').css({
                width: Math.round(rx * width) + 'px',
                height: Math.round(ry * height) + 'px',
                marginLeft: '-' + Math.round(rx * coords.x) + 'px',
                marginTop: '-' + Math.round(ry * coords.y) + 'px'
        });
    }

    // This is to make sure that when the user presses enter
    // (keyCode == 13) in the fields, the form isn't submitted,
    // but the selection is updated
    var checkForEnter = function(event) {
        if (event.keyCode == 13) {
            updateSelection();
            event.preventDefault();
            return false;
        }
    };

    // This function will run when the form fields are updated
    var updateSelection = function() {
        // Get the field values as integers
        x = parseInt($('#id_left').val(), 10);
        w = parseInt($('#id_width').val(), 10);
        y = parseInt($('#id_top').val(), 10);
        h = parseInt($('#id_height').val(), 10);

        x = Math.round(x * ratio);
        w = Math.round(w * ratio);
        y = Math.round(y * ratio);
        h = Math.round(h * ratio);
        // Now move the selection to new coordinates
        jcrop.setSelect([x, y, x+w, y+h]);
    };


    // Put the preview image in the box set aside for it
    $('#preview_box').html('<img src="' + $('img#cropbox').attr('src') + '" id="preview">');

    // Now create a jcrop object with some defaults
    // The onChange and onSelect attributes specify a function to run
    var jcrop = $.Jcrop('#cropbox', {
        onChange: updateForm,
        onSelect: updateForm,
        // we show the image scaled to width, adjust min_width accordingly
        minSize: [400*width/real_width, 0],
        maxSize: [0, height],
        setSelect: [0, 0, width, height]
    });

    // Attach functions to events on the form fields
    $('#id_width, #id_left, #id_height, #id_top').change(updateSelection).keypress(checkForEnter);
});
