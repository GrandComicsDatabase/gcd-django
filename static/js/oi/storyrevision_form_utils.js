$(function() {
    // Running character count for synopsis
    $('#id_synopsis')
        .after('<br><span id="id_synopsis_length"></span>')
        .bind('input', function () {
            var len = $(this).val().length;
            var legend = $('#id_synopsis_length');
            legend.text('Characters: ' + len + ' / ' + limitSynopsisLength);
            if (len > limitSynopsisLength) {
                legend.addClass('text-red-400 font-bold');
            } else {
                legend.removeClass('text-red-400 font-bold');
            }
        }).trigger('input');
});

$(document).on('change', 'input[type=checkbox]', function () {
    var id = $(this).attr('id'),
        match = id.match(/story_credit_revisions-(\d+)-(is_signed|is_credited|is_sourced)/)

    if (match) {
        if (match[2] == 'is_sourced'){
            var inputRow = $('#id_story_credit_revisions-' + match[1] + '-sourced_by')
                        .parent().parent();
            if ($(this).is(':checked')) {
                inputRow.show()
            } else {
                inputRow.hide()
            }
            return;
        }
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

$(document).on('change', 'input[type=checkbox]', function () {
    var id = $(this).attr('id'),
        match = id.match(/story_character_revisions-(\d+)-(additional_information)/)

    if (match) {
        if (match[2] == 'additional_information'){
            var fields = ['role', 'group_name', 'universe', 'group_universe', 'is_flashback', 'is_origin', 'is_death', 'notes'];
            for (var i=0; i<fields.length; i++){
                var inputRow = $('#id_story_character_revisions-' + match[1] + '-' + fields[i])
                            .parent().parent();
                if ($(this).is(':checked')) {
                    inputRow.show()
                } else {
                    inputRow.hide()
                }
            }
        }
    }
    else {
        var id = $(this).attr('id'),
        match = id.match(/appearing_characters_additional_information/)
        position = '#id_appearing_characters_'
        if (!match){
            match = id.match(/group_members_additional_information/)
            position = '#id_group_members_'
        }
        if (match) {
            var fields = ['role', 'flashback', 'origin', 'death', 'notes'];
            for (var i=0; i<fields.length; i++){
                var inputRow = $(position + fields[i])
                            .parent().parent();
                if ($(this).is(':checked')) {
                    inputRow.show()
                } else {
                    inputRow.hide()
                }
            }
        }
    }
})

$('input[type=checkbox]').change()
