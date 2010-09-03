from django.contrib import admin

from apps.voting.models import *

class OptionInline(admin.StackedInline):
    model = Option
    extra = 0

class TopicAdmin(admin.ModelAdmin):
    inlines = (OptionInline,)
    raw_id_fields = ('author', 'second')

class AgendaMailingListInline(admin.StackedInline):
    model = AgendaMailingList
    extra = 0

class AgendaItemInline(admin.StackedInline):
    model = AgendaItem
    extra = 0
    raw_id_fields = ('owner',)

class AgendaAdmin(admin.ModelAdmin):
    inlines = (AgendaMailingListInline, AgendaItemInline)
    
admin.site.register(Agenda, AgendaAdmin)
admin.site.register(MailingList)
admin.site.register(Topic, TopicAdmin)
admin.site.register(VoteType)

