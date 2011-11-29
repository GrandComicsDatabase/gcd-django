from django.contrib import admin

from apps.voting.models import *

class OptionInline(admin.StackedInline):
    model = Option
    extra = 0

class TopicAdmin(admin.ModelAdmin):
    inlines = (OptionInline,)
    raw_id_fields = ('author', 'second')
    list_filter = ('agenda', 'open')
    list_display = ('name', 'agenda', 'open', 'deadline')

class AgendaMailingListInline(admin.StackedInline):
    model = AgendaMailingList
    extra = 0

class AgendaAdmin(admin.ModelAdmin):
    inlines = (AgendaMailingListInline,)

class AgendaItemAdmin(admin.ModelAdmin):
    raw_id_fields = ('owner',)
    search_fields = ('owner__username', 'owner__first_name', 'owner__last_name')
    list_display = ('name', 'state', 'owner')
    list_filter = ('agenda', 'state')

class ExpectedVoterAdmin(admin.ModelAdmin):
    raw_id_fields = ('voter',)
    list_display = ('voter_name', 'agenda', 'tenure_began', 'tenure_ended')

admin.site.register(Agenda, AgendaAdmin)
admin.site.register(AgendaItem, AgendaItemAdmin)
admin.site.register(MailingList)
admin.site.register(Topic, TopicAdmin)
admin.site.register(VoteType)
admin.site.register(ExpectedVoter, ExpectedVoterAdmin)

