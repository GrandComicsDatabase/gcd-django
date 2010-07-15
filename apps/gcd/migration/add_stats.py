from apps.gcd.models import *

def add_stats(code):
    lang = Language.objects.get(code=code)
    CountStats.objects.create(name='series',language=lang,count=Series.objects.filter(language=lang).count())
    CountStats.objects.create(name='issues',language=lang,count=Issue.objects.filter(series__language=lang).count())
    CountStats.objects.create(name='issue indexes',language=lang,count=Issue.objects.filter(series__language=lang, story_type_count__gt=0).count())
#    CountStats.objects.create(name='issues',language=lang,count=Issue.objects.filter(series__language=lang, deleted=False).count())
#    CountStats.objects.create(name='issues',language=lang,count=Issue.objects.filter(series__language=lang, deleted=False, story_type_count__gt=0).count())

    CountStats.objects.create(name='stories', language=lang,count=Story.objects.filter(issue__series__language=lang, deleted=False).count())
    CountStats.objects.create(name='covers', language=lang,count=Cover.objects.filter(issue__series__language=lang, deleted=False).count())


