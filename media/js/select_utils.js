$(function () {
    // Handle "Select all" button
    $('#select_all').click(function (e) {
        e.preventDefault();
        $(this).hide();
        $('#select_none').show();
        $('input:checkbox').prop('checked', true);
    });

    // Handle "Select none" button
    $('#select_none').show().click(function (e) {
        e.preventDefault();
        $(this).hide();
        $('#select_all').show();
        $('input:checkbox').prop('checked', false);
    }).siblings('span').hide();

    // Toggle ranges by clicking on begin, shift-clicking on end
    var lastClickedCheckbox;
    $('input:checkbox').click(function (e) {
        var target = $(e.target);
        if (e.shiftKey && lastClickedCheckbox) {
            var checkboxes = $('input:checkbox');
            var begin = checkboxes.index(lastClickedCheckbox);
            var end = checkboxes.index(target);
            // swap begin and and if clicked in reverse order
            if (end < begin) {
                var tmp = end;
                end = begin;
                begin = tmp;
            }
            checkboxes.slice(begin + 1, end).each(function () {
                this.checked = !this.checked;
            });
        }
        lastClickedCheckbox = target;
    });
});
