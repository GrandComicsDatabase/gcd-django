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
  for (var b=/\d/g,i=0, sum=0; i < 10; i++) {
    sum += ((10-i) * b.exec(a));
  };
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
    // Set to true if user edits the key date field
    var keyDateEdited = false;
    var keyDateField = $('#id_key_date');
    var keyDateIndicator = $('<span>').hide().appendTo(document.body);
    keyDateIndicator.text(' Auto-set from publication date ');
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

    // Auto-update key date field from publication date
    $('#id_publication_date').bind('input', function () {
        if (!keyDateEdited) {
            var newdate = parsePubDate($(this).val());
            if (newdate) {
                keyDateField.val(newdate);
                keyDateIndicator.show();
            }
        }
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

    // Add brand emblem images
    $("#id_brand").msDropDown({addToWidth: $("#id_brand").addToOptionWidth()});
});
