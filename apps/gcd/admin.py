from django.contrib import admin

from apps.gcd.models import Indexer

class IndexerAdmin(admin.ModelAdmin):
    search_fields = ('user__first_name', 'user__last_name',
                     'user__username', 'user__email')
    list_filter = ('is_new', 'registration_expires')

admin.site.register(Indexer, IndexerAdmin)

