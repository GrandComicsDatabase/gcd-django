# creates the counts, could be made by SQL if one knows how

from apps.gcd.models import CountStats, Cover, Series, Issue, Publisher, Story

CountStats.objects.create(name='publishers', count=Publisher.objects.count())
CountStats.objects.create(name='series', count=Series.objects.count())
CountStats.objects.create(name='issues', count=Issue.objects.count())
# this isn't fully correct, we have indexed and approved issues without stories, 
# but then these shouldn't be in the db anyway, should they ? 
# 'indexed issues' instead of 'issue indexes' would be too long and fill two 
# lines in standard settings. Other name suggestions ?
CountStats.objects.create(name='issue indexes', count=Issue.objects.filter(story_type_count__gt=0).count())
CountStats.objects.create(name='covers', count=Cover.objects.filter(has_image=True).count())
# this counts sequences not sequences of type=story, what do we want ?
# if type=story we need to change the updating in the OI commit as well
CountStats.objects.create(name='stories', count=Story.objects.count())

