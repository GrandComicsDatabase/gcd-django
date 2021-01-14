$(function() {
    // Running character count for synopsis
    $('#id_synopsis')
        .after('<br><span id="id_synopsis_length"></span>')
        .bind('input', function () {
            var len = $(this).val().length;
            var legend = $('#id_synopsis_length');
            legend.text('Characters: ' + len + ' / ' + limitSynopsisLength);
            if (len > limitSynopsisLength) {
                legend.addClass('errorlist');
            } else {
                legend.removeClass('errorlist');
            }
        }).trigger('input');
});

$(document).on('change', 'input[type=checkbox]', function () {
    var id = $(this).attr('id'),
        match = id.match(/story_credit_revisions-(\d+)-(is_signed|is_credited)/)

    if (match) {
    var inputRow = $('#id_story_credit_revisions-' + match[1] +
		(match[2] == 'is_signed'? '-signed_as': '-credited_as'))
                .parent().parent();
        if ($(this).is(':checked')) {
            inputRow.show()
        } else {
            inputRow.hide()
        }
        if (match[2] == 'is_signed') {
        var inputRow = $('#id_story_credit_revisions-' + match[1] + '-signature')
                    .parent().parent();
            if ($(this).is(':checked')) {
                inputRow.show()
            } else {
                inputRow.hide()
            }
        }
    }
})

$('input[type=checkbox]').change()
