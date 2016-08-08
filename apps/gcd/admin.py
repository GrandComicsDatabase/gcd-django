from django.contrib import admin

from apps.gcd.models import *

class StoryTypeAdmin(admin.ModelAdmin):
    list_display = ('sort_code', 'name')
    list_display_links = ('name',)
    list_editable = ('sort_code',)

class SeriesBondTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)

class IndexerAdmin(admin.ModelAdmin):
    search_fields = ('user__first_name', 'user__last_name',
                     'user__username', 'user__email')
    readonly_fields = ('registration_key',)
    list_display = ('id', 'user', 'registration_expires', 'registration_key')
    list_display_links = ('id', 'user')
    list_filter = ('is_new', 'registration_expires')
    list_editable = ('registration_expires',)
    fieldsets = (
        (None, {
            'fields': ('user', 'is_banned',
                       'registration_key', 'registration_expires'),
        }),
        ('Indexing', {
            'fields': ('mentor', 'is_new', 'max_reservations', 'max_ongoing'),
        }),
        ('Profile', {
            'fields': ('country', 'languages', 'interests', 'deceased'),
        }),
        ('Preferences', {
            'fields': ('notify_on_approve', 'collapse_compare_view'),
        }),
    )
    filter_horizontal = ('languages',)

class ImpGrantAdmin(admin.ModelAdmin):
    raw_id_fields = ('indexer',)

admin.site.register(StoryType, StoryTypeAdmin)
admin.site.register(SeriesBondType, SeriesBondTypeAdmin)
admin.site.register(Indexer, IndexerAdmin)
admin.site.register(ImpGrant, ImpGrantAdmin)

