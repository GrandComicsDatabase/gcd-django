from apps.oi.models import OngoingReservation
from django.contrib import admin

class OngoingReservationAdmin(admin.ModelAdmin):
    fields = ('indexer', 'series')
    raw_id_fields = ('indexer', 'series')

admin.site.register(OngoingReservation, OngoingReservationAdmin)

