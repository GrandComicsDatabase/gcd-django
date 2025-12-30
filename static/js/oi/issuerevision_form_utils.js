$.fn.textWidth = function(text, font) {
    if (!$.fn.textWidth.fakeEl) $.fn.textWidth.fakeEl = $('<span>').hide().appendTo(document.body);
    $.fn.textWidth.fakeEl.text(text || this.text()).css('font', font || this.css('font'));
    return $.fn.textWidth.fakeEl.width();
};
$.fn.optionAndImageWidth = function(){
    var val = $(this).attr('image-width');
    if (val != undefined){
        val = parseInt(val, 10);
        val = val + $(this).textWidth();
        return val;
    }
    return $(this).textWidth();
};
$.fn.addToOptionWidth = function(){
    // we add a value to an outerWidth, so that is the base
    var max_length = $(this).outerWidth();
    $('option', $(this)).each(function(){
        max_length = Math.max(max_length, $(this).optionAndImageWidth());
    });
    return Math.max(max_length - $(this).outerWidth(), 30);
}

var monthRegExp = [
    /^(jan|gen|ene|ιαν|ocak|tammikuu|styczeń|o(dd|đđ)ajag)/,
    /^(feb|f[eé]v|φεβ|şubat|helmikuu|luty|guovva)/,
    /^(m[aä]r|márc|maart|μ[αά]ρ|maaliskuu|njukča)/,
    /^(a[pvb]r|ápr|απρ|nisan|huhtikuu|kwiecień|cuoŋo|spring|vår|påsk)/,
    /^(ma[yigj]|máj|mei|μάι|μαΐ|toukokuu|miesse)/,
    /^(j[uú]n|giu|juin|ιο[υύ]ν|haziran|kesäkuu|czerwiec|geasse)/,
    /^(j[uú]l|lug|juil|ιο[υύ]λ|heinäkuu|temmuz|lipiec|suoidne|summer|sommar)/,
    /^(aug|ago|aoû|α[υύ]γ|ağustos|elokuu|sierpień|borge)/,
    /^(se[pt]|szept|σεπ|eylül)|syyskuu|wrzesień|čakča/,
    /^(o[ckt]t|out|οκτ|ekim|lokakuu|październik|golggot|fall|h[öø]st)/,
    /^(nov|νο[εέ]|kasım|marraskuu|listopad|skábma)/,
    /^(de[czs]|d[éi]c|δεκ|aralık|joulukuu|grudzień|juovla)/];

// Check if str matches one of the regexps in the array above
// Returns corresponding month or 0 if none match
function checkMonth(str) {
    var month;
    if (str == 'julen' || str == 'jula') {
        return 12; // Christmas in sv/da/no
    }
    for (month = 1; month <= 12; month++) {
        if (str.match(monthRegExp[month - 1])) {
            return month;
        }
    }
    return 0;
}

// Try to parse a Japanese date in the form [reign]YYYY年[MM月[DD日]]
function parseJpDate(str) {
    var re = /(平成|昭和|大正|明治)?\s*(\d{1,4})年\s*(?:(\d{1,2})月\s*(?:(\d{1,2})日)?)?/;
    var match = str.match(re);
    var date = { year: 0, month: 0, day: 0 };
    var reignOffset = {
        '平成': 1988, // Heisei 1989–present
        '昭和': 1925, // Shōwa  1926–1989
        '大正': 1911, // Taishō 1912–1926
        '明治': 1867, // Meiji  1868–1912
    };

    if (match) {
        if (match[2]) {
            // year found
            date.year = parseInt(match[2], 10);
            if (match[1]) {
                // reign found (traditional date)
                date.year += reignOffset[match[1]];
            }
            if (match[3] && match[3] >= 1 && match[3] <= 12) {
                // month found
                date.month = match[3];
                if (match[4]) {
                    // day found
                    date.day = match[4];
                }
            }
        }
    }
    return date;
}

// Zero-pad integers up to four digits long
function pad(n, len) {
    var s = n.toString();
    if (s.length < len) {
        return ('0000' + s).slice(-len);
    } else {
        return s;
    }
}

function formatKeyDate(year, month, day) {
    return pad(year, 4) + '-' + pad(month, 2) + '-' + pad(day, 2);
}

// Build a keydate from the publication and on-sale dates
function keyDate(pubDate, onSaleDate) {
    var year = 0, month = 0, day = 0, usedPubDate = false, usedOnSaleDate = false, unsure = false;

    if (onSaleDate.year.length == 3) {
        onSaleDate.year += '0';
    }

    onSaleDate.year = onSaleDate.year.replace('?', '0');
    onSaleDate.month = onSaleDate.month.replace('?', '0');
    onSaleDate.day = onSaleDate.day.replace('?', '0');

    if (pubDate.year) {
        year = pubDate.year;
        usedPubDate = true;
    } else if (onSaleDate.year) {
        year = onSaleDate.year;
        usedOnSaleDate = true;
    }

    if (year) {
        if (pubDate.month) {
            month = pubDate.month;
            usedPubDate = true;
            if (!pubDate.year) {
                unsure = true; // Got month from pubDate and year from onSaleDate
            }
        } else if ((year == onSaleDate.year || !onSaleDate.year) && onSaleDate.month) {
            month = onSaleDate.month;
            usedOnSaleDate = true;
            if (!onSaleDate.year) {
                unsure = true; // Got month from onSaleDate and year from pubDate
            }
        }
    }

    if (month) {
        if (pubDate.day) {
            day = pubDate.day;
            usedPubDate = true;
        } else if (month == onSaleDate.month && onSaleDate.day) {
            day = onSaleDate.day;
            usedOnSaleDate = true;
        }
    }

    if (unsure) {
        return { string: '',
                 indicator: ' Possible keydate: ' + formatKeyDate(year, month, day) + ' - please verify and copy in field manually' };
    }

    // Return a formatted key date if at least the year was found
    if (year) {
        var indicator = ' Auto-set from ';
        if (usedPubDate && usedOnSaleDate) {
            indicator += 'publication and on-sale dates';
        } else if (usedPubDate) {
            indicator += 'publication date';
        } else if (usedOnSaleDate) {
            indicator += 'on-sale date';
        }

        return { string: formatKeyDate(year, month, day),
                 indicator: indicator };
    } else {
        return { string: '' };
    }
}

// Try to parse a publication date string and
// return the year, month and day
function parsePubDate(pubDate) {
    var year = 0,
        month = 0,
        day = 0,
        tmpMonth,
        parts = pubDate.split(/(\s|[[{}(),?']|]|-|\.)+/g);

    // Check for Japanese date
    var jpDate = parseJpDate(pubDate);
    if (jpDate.year) {
        return jpDate;
    }

    // Check each part for the presense of a year, day or month
    $.each(parts, function () {
        var m, x = this.toLowerCase();
        if ((m = x.match(/^(\d{4})/)) && !year && x > '18' && x < '21') {
            year = m[0];
        } else if (x.match(/^\d{1,2}/) && !day) {
            day = parseInt(x, 10);
            if (day > 31) {
                day = 0;
            }
        } else if ((tmpMonth = checkMonth(x)) && !month) {
            month = tmpMonth;
        }
    });
    return { year: year, month: month, day: day };
}

function isvalidISBN13(a, len){
    if (len){
        e = len*2 -1;
    }
    else{
        e = 25;
    }
    for(var b=/\d/g,c=0,d;
        d=b.exec(a);
        e-=2)
    c+=e%4*d;
    return!(~e|c%10)
}

function isvalidISBN10(a){
  for (var b=/\d/g,i=0, sum=0; i < 9; i++) {
    sum += ((10-i) * b.exec(a));
  };
  var check = a[9];
  if (a[9] === 'X'){
      check = 10;
  }
  sum += parseInt(check);
  return ((sum % 11) == 0);
}

function validISBN(val){
    val = val.replace(/[ -]/g,'');
    var len = val.length;
    if (len === 13){
        return isvalidISBN13(val);
    }
    else if (len === 10) {
        return isvalidISBN10(val);
    }
    return false;
}

function validISBNs(vals){
    var valid = true;
    vals = vals.split(';');
    for (i=0; i<vals.length; i++){
        valid = valid && validISBN(vals[i]);
    }
    return valid;
}

function showISBNStatus(isbnField){
    if (!showISBNStatus.indicator){
        showISBNStatus.indicator = $('<span>').appendTo(document.body);
        showISBNStatus.indicator.insertAfter(isbnField);
    }
    showISBNStatus.indicator.text("");
    if (isbnField.val() != undefined && isbnField.val() != ''){
        if (validISBNs(isbnField.val())) {
            showISBNStatus.indicator.text(" valid ISBN ");
        }
        else{
            showISBNStatus.indicator.text(" invalid ISBN ");
        }
    }
}

function validBarcode(val){
    val = val.replace(/[ -]/g,'');
    var len = val.length;
    if (len > 16){
        val = val.slice(0,len-5);
    }
    else if (len > 13) {
        val = val.slice(0,len-2);
    }
    len = val.length;
    if ($.inArray(len, [13, 12, 8]) != -1){
        return isvalidISBN13(val, len);
    }
    return false;
}

function validBarcodes(vals){
    var valid = true;
    vals = vals.split(';');
    for (i=0; i<vals.length; i++){
        valid = valid && validBarcode(vals[i]);
    }
    return valid;
}

function showBarcodeStatus(barcodeField){
    if (!showBarcodeStatus.indicator){
        showBarcodeStatus.indicator = $('<span>').appendTo(document.body);
        showBarcodeStatus.indicator.insertAfter(barcodeField);
    }
    showBarcodeStatus.indicator.text("");
    if (barcodeField.val() != undefined && barcodeField.val() != ''){
        if (validBarcodes(barcodeField.val())) {
            showBarcodeStatus.indicator.text(" valid UPC/EAN ");
        }
        else{
            showBarcodeStatus.indicator.text(" invalid UPC/EAN or non-standard ");
        }
    }
}

$(function() {
    var pubDate, onSaleDate;

    // Set to true if user edits the key date field to prevent auto-update
    var keyDateEdited = false;
    var keyDateField = $('#id_key_date');
    var keyDateIndicator = $('<span>').hide().appendTo(document.body);
    keyDateIndicator.text(' Default value ');
    keyDateIndicator.insertAfter(keyDateField);

    // Prevent updates to key date field if it's been edited and is not empty
    keyDateField.change(function () {
        if (keyDateField.val() == '') {
            keyDateEdited = false;
            keyDateIndicator.show();
        } else {
            keyDateEdited = true;
            keyDateIndicator.hide();
        }
    });

    function updateKeyDate () {
        if (!keyDateEdited) {
            var keyDateInfo = keyDate(pubDate, onSaleDate);
            if (keyDateInfo.string || keyDateInfo.indicator) {
                keyDateIndicator.text(keyDateInfo.indicator);
                keyDateField.val(keyDateInfo.string);
                keyDateIndicator.show();
            }
        }
    }

    // set initial date fields
    pubDate = parsePubDate($('#id_publication_date').val());
    onSaleDate = {
        year: $('#id_year_on_sale').val(),
        month: $('#id_month_on_sale').val(),
        day: $('#id_day_on_sale').val(),
    };

    // update keydate fields from publication date
    $('#id_publication_date').bind('input', function () {
        pubDate = parsePubDate($(this).val());
        updateKeyDate();
    });

    // update keydate fields from on-sale date
    $('#id_on_sale_date').bind('input', function () {
        var parts = $(this).val().split(/-/g);

        if (parts[0]) {
            onSaleDate.year = parts[0];
        }
        if (parts[1]) {
            onSaleDate.month = parts[1];
        }
        if (parts[2]) {
            onSaleDate.day = parts[2];
        }
        updateKeyDate();
    });

    $('#id_year_on_sale').bind('input', function () {
        onSaleDate.year = $(this).val();
        updateKeyDate();
    });

    $('#id_month_on_sale').bind('input', function () {
        onSaleDate.month = $(this).val();
        updateKeyDate();
    });

    $('#id_day_on_sale').bind('input', function () {
        onSaleDate.day = $(this).val();
        updateKeyDate();
    });

    var isbnField = $('#id_isbn');
    showISBNStatus(isbnField);
    isbnField.bind('input', function () {
        showISBNStatus(isbnField);
    });

    var barcodeField = $('#id_barcode');
    showBarcodeStatus(barcodeField);
    barcodeField.bind('input', function () {
        showBarcodeStatus(barcodeField);
    });

    // Disable form submission with Enter for barcode field
    barcodeField.keypress(function (e) {
        if (e.which == 13) {
            return false;
        }
    });

    var editingField = $('#id_editing');
    editingField.bind('input', function () {
        var migrate_button = $("[name='save_migrate']");
        migrate_button.removeAttr("disabled");
        migrate_button.removeClass('btn-blue-disabled px-2 py-1');
        migrate_button.addClass('btn-blue-editing');
    });

    // Add brand emblem images
    $("#id_brand").msDropDown({addToWidth: $("#id_brand").addToOptionWidth()});
});

$(document).on('change', 'input[type=checkbox]', function () {
    var id = $(this).attr('id'),
        match = id.match(/issue_credit_revisions-(\d+)-(is_credited|is_sourced)/)

    if (match) {
        if (match[2] == 'is_sourced'){
            var inputRow = $('#id_issue_credit_revisions-' + match[1] + '-sourced_by')
                        .parent().parent();
            if ($(this).is(':checked')) {
                inputRow.show()
            } else {
                inputRow.hide()
            }
            return;
        }
        var inputRow = $('#id_issue_credit_revisions-' + match[1] + '-credited_as')
                         .parent().parent();
        if ($(this).is(':checked')) {
            inputRow.show()
        } else {
            inputRow.hide()
        }
    }
    else if (id == 'id_indicia_printer_not_printed') {
        var inputRow = $('#id_indicia_printer_sourced_by').parent().parent();
        if ($(this).is(':checked')) {
            inputRow.show()
        } else {
            inputRow.hide()
        }
    }
})

$('input[type=checkbox]').change()
