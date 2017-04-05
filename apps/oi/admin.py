from apps.oi.models import *
from django.contrib import admin

class OngoingReservationAdmin(admin.ModelAdmin):
    fields = ('indexer', 'series')
    raw_id_fields = ('indexer', 'series')


class CreatorSchoolDetailRevisonInline(admin.TabularInline):
    model = CreatorSchoolDetailRevision
    extra = 1


class CreatorDegreeDetailRevisonInline(admin.TabularInline):
    model = CreatorDegreeDetailRevision
    extra = 1


admin.site.register(OngoingReservation, OngoingReservationAdmin)


#register creator revison models to admin panel
admin.site.register(CreatorNameDetailRevision)
admin.site.register(CreatorRevision)
admin.site.register(NameRelationRevision)
admin.site.register(BirthYearSourceRevision)
admin.site.register(BirthMonthSourceRevision)
admin.site.register(BirthDateSourceRevision)
admin.site.register(DeathYearSourceRevision)
admin.site.register(DeathMonthSourceRevision)
admin.site.register(DeathDateSourceRevision)
admin.site.register(BirthCountrySourceRevision)
admin.site.register(BirthProvinceSourceRevision)
admin.site.register(BirthCitySourceRevision)
admin.site.register(DeathCountrySourceRevision)
admin.site.register(DeathProvinceSourceRevision)
admin.site.register(DeathCitySourceRevision)
admin.site.register(PortraitSourceRevision)
admin.site.register(BioSourceRevision)
admin.site.register(CreatorSchoolDetailRevision)
admin.site.register(CreatorDegreeDetailRevision)
admin.site.register(Changeset)
admin.site.register(PublisherRevision)
admin.site.register(CreatorMembershipRevision)
admin.site.register(CreatorAwardRevision)
admin.site.register(CreatorArtInfluenceRevision)
admin.site.register(CreatorNonComicWorkRevision)
admin.site.register(NonComicWorkYearRevision)
admin.site.register(NonComicWorkLinkRevision)







