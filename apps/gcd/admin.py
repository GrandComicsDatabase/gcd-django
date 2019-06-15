from django.contrib import admin

from .models import (MembershipType, NameType, NonComicWorkRole,
                     NonComicWorkType, RelationType, School, SeriesBondType,
                     SourceType, FeatureType, StoryType, Degree)

class StoryTypeAdmin(admin.ModelAdmin):
    list_display = ('sort_code', 'name')
    list_display_links = ('name',)
    list_editable = ('sort_code',)


class SeriesBondTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


class ImpGrantAdmin(admin.ModelAdmin):
    raw_id_fields = ('indexer',)


#register models without editing to admin panel
admin.site.register(StoryType, StoryTypeAdmin)
admin.site.register(SeriesBondType, SeriesBondTypeAdmin)
admin.site.register(NameType)
admin.site.register(SourceType)
admin.site.register(FeatureType)
admin.site.register(RelationType)
admin.site.register(MembershipType)
admin.site.register(NonComicWorkType)
admin.site.register(NonComicWorkRole)
admin.site.register(School)
admin.site.register(Degree)
