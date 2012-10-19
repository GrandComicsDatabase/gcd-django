
var monthRegExp = [
    /^(jan|gen|ene|ιαν|ocak|tammikuu|styczeń|o(dd|đđ)ajag)/,
    /^(feb|f[eé]v|φεβ|şubat|helmikuu|luty|guovva)/,
    /^(m[aä]r|márc|μ[αά]ρ|maaliskuu|njukča)/,
    /^(a[pvb]r|ápr|απρ|nisan|huhtikuu|kwiecień|cuoŋo|spring|vår|påsk)/,
    /^(ma[yigj]|máj|μάι|μαΐ|toukokuu|miesse)/,
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

// Try to parse a publication date string
// Return a key date string or empty if parsing failed
function parsePubDate (pubDate) {
    var year = 0,
        month = 0,
        day = 0,
        tmpMonth,
        parts = pubDate.split(/(\s|[[{}(),?']|]|-|\.)+/g);

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

    // Return a formatted key date if at least the year was found
    if (year) {
        return formatKeyDate(year, month, day);
    } else {
        return '';
    }
}


$(function() {
    // Set to true if user edits the key date field
    var keyDateEdited = false;
    var keyDateField = $('#id_key_date');
    // Contains message defined in templates/oi/bits/revision_form_utils.html
    var keyDateIndicator = $('#id_key_date_indicator');

    keyDateIndicator.insertAfter(keyDateField).show();

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

    // Auto-update key date field from publication date
    $('#id_publication_date').bind('input', function () {
        if (!keyDateEdited) {
            var newdate = parsePubDate($(this).val());
            if (newdate) {
                keyDateField.val(newdate);
            }
        }
    });

    // Disable form submission with Enter for barcode field
    $('#id_barcode').keypress(function (e) {
        if (e.which == 13) {
            return false;
        }
    });

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
