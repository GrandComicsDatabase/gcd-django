from django.contrib import admin

from apps.gcd.models import StoryType, SeriesBondType

from apps.gcd.models.creator import *

class StoryTypeAdmin(admin.ModelAdmin):
    list_display = ('sort_code', 'name')
    list_display_links = ('name',)
    list_editable = ('sort_code',)


class SeriesBondTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


class ImpGrantAdmin(admin.ModelAdmin):
    raw_id_fields = ('indexer',)

admin.site.register(StoryType, StoryTypeAdmin)
admin.site.register(SeriesBondType, SeriesBondTypeAdmin)

#register creator models to admin panel
admin.site.register(NameType)
admin.site.register(SourceType)
admin.site.register(RelationType)
admin.site.register(MembershipType)
admin.site.register(NonComicWorkType)
admin.site.register(NonComicWorkRole)
admin.site.register(School)
admin.site.register(Degree)
admin.site.register(AwardType)
