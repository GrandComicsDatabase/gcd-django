from django.contrib import admin

from apps.gcd.models import StoryType, SeriesBondType


class StoryTypeAdmin(admin.ModelAdmin):
    list_display = ('sort_code', 'name')
    list_display_links = ('name',)
    list_editable = ('sort_code',)


class SeriesBondTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


admin.site.register(StoryType, StoryTypeAdmin)
admin.site.register(SeriesBondType, SeriesBondTypeAdmin)
