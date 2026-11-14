# -*- coding: utf-8 -*-


from django.contrib import admin
from django.contrib.auth.models import User

from apps.indexer.models import Indexer, ImpGrant


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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Users who may only view the page get no mentor field.
        if 'mentor' in form.base_fields:
            mentors = User.objects.with_perm(
              'indexer.can_mentor', include_superusers=False,
              backend='django.contrib.auth.backends.ModelBackend')
            # The current mentor may no longer be an editor.
            if obj and obj.mentor_id:
                mentors |= User.objects.filter(pk=obj.mentor_id)
            form.base_fields['mentor'].queryset = mentors
        return form


class ImpGrantAdmin(admin.ModelAdmin):
    raw_id_fields = ('indexer',)


admin.site.register(Indexer, IndexerAdmin)
admin.site.register(ImpGrant, ImpGrantAdmin)
