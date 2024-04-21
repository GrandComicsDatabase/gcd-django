# -*- coding: utf-8 -*-


import re
import django
from django.db import transaction
from apps.gcd.models import Issue
from apps.legacy.tools import migrate_reserve, do_auto_approve

monthRegExp = [re.compile(x) for x in (
    r'(jan|gen|ene|ιαν|ocak|tammikuu|styczeń|o(dd|đđ)ajag)',
    r'(feb|f[eé]v|φεβ|şubat|helmikuu|luty|guovva)',
    r'(m[aä]r|maart|márc|μ[αά]ρ|maaliskuu|njukča)',
    r'(a[pvb]r|ápr|απρ|nisan|huhtikuu|kwiecień|cuoŋo|spring|vår|påsk)',
    r'(ma[yigj]|mei|máj|μάι|μαΐ|toukokuu|miesse)',
    r'(j[uú]n|giu|juin|ιο[υύ]ν|haziran|kesäkuu|czerwiec|geasse)',
    r'(j[uú]l|lug|juil|ιο[υύ]λ|heinäkuu|temmuz|lipiec|suoidne|summer|sommar)',
    r'(aug|ago|aoû|α[υύ]γ|ağustos|elokuu|sierpień|borge)',
    r'(se[pt]|szept|σεπ|eylül)|syyskuu|wrzesień|čakča',
    r'(o[ckt]t|out|οκτ|ekim|lokakuu|październik|golggot|fall|h[öø]st)',
    r'(nov|νο[εέ]|kasım|marraskuu|listopad|skábma)',
    r'(de[czs]|d[éi]c|δεκ|aralık|joulukuu|grudzień|juovla)')]

# Check if str matches one of the regexps in the array above
# Returns corresponding month or 0 if none match
def checkMonth(str):
    global monthRegExp
    if str == 'julen' or str == 'jula':
        return 12 # Christmas in sv/da/no
    for month, regexp in enumerate(monthRegExp, start=1):
        if regexp.match(str):
            return month;
    return 0;


def formatKeyDate(year, month, day):
    return '%04d-%02d-%02d' % (year, month, day)


# Try to parse a publication date string
# Return a key date string or empty if parsing failed
def parsePubDate(pubDate):
    # Leave keydate blank to check manually for the following:
    # Winter means month = 01 or 12, 'vecka' means 'week'
    if re.match(r'\b(winter|vinter|vecka)\b', pubDate):
        return ''
    year = month = day = 0
    m = re.match(r'(\d{1,2})/(\d{4})', pubDate)
    if m:
        return formatKeyDate(int(m.group(2)), int(m.group(1)), 0)
    parts = [x.lower() for x in re.split(r"(\s|[[/{}(),?'\"]|]|-|\.)+", pubDate)]
    for part in parts:
        yearMatch = re.match(r'(\d{4})', part)
        monthMatch = checkMonth(part)
        dayMatch = re.match(r'(\d{1,2})(?!\d)', part)
        if yearMatch and not year and part > '18' and part < '21':
            year = int(yearMatch.group(0))
        elif monthMatch and not month:
            month = monthMatch
        elif dayMatch and not day:
            day = int(dayMatch.group(0))
            if day > 31:
                day = 0
    # Return a formatted key date if at least the year was found
    if year:
        return formatKeyDate(year, month, day)
    else:
        return ''


def keydate_migration(issues):
    changes = []
    for i in issues:
        keydate = parsePubDate(i.publication_date)
        if keydate:
            with transaction.commit_on_success():
                c = migrate_reserve(i, 'issue',
                        'to autofill keydates from publication dates')
                if c:
                    ir = c.issuerevisions.all()[0]
                    ir.key_date = keydate
                    ir.save()
                    changes.append((c, True))
                else:
                    print("%s is reserved" % i)
        if len(changes) > 25:
            with transaction.commit_on_success():
                do_auto_approve(changes,
                                'publication date to keydate conversion')
            changes = []
    with transaction.commit_on_success():
        do_auto_approve(changes,
                        'publication date to keydate conversion')


def main():
    issues = Issue.objects.filter(deleted=False, key_date='').exclude(publication_date='').distinct()
    print(issues.count())
    keydate_migration(issues)

if __name__ == '__main__':
    django.setup()
    main()
