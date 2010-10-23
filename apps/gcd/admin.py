from django.contrib import admin

from apps.gcd.models import *

class CountryAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code')
    list_display = ('code', 'name')
    list_display_links = ('code', 'name')

class LanguageAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code')
    list_display = ('code', 'name')
    list_display_links = ('code', 'name')

class StoryTypeAdmin(admin.ModelAdmin):
    list_display = ('sort_code', 'name')
    list_display_links = ('name',)
    list_editable = ('sort_code',)

class ClassificationAdmin(admin.ModelAdmin):
    list_display = ('sort_code', 'name', 'is_singular', 'is_book_like')
    list_display_links = ('name',)
    list_editable = ('sort_code', 'is_singular', 'is_book_like')

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

admin.site.register(Country, CountryAdmin)
admin.site.register(Language, LanguageAdmin)
admin.site.register(StoryType, StoryTypeAdmin)
admin.site.register(Classification, ClassificationAdmin)
admin.site.register(Indexer, IndexerAdmin)
admin.site.register(ImpGrant, ImpGrantAdmin)

