from django.contrib import admin

from apps.gcd.models import StoryType, SeriesBondType

from apps.gcd.models.creator import *

class StoryTypeAdmin(admin.ModelAdmin):
    list_display = ('sort_code', 'name')
    list_display_links = ('name',)
    list_editable = ('sort_code',)


class SeriesBondTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


class ImpGrantAdmin(admin.ModelAdmin):
    raw_id_fields = ('indexer',)

class CreatorSchoolDetailInline(admin.TabularInline):
    model = CreatorSchoolDetail
    extra = 1

class CreatorDegreeDetailInline(admin.TabularInline):
    model = CreatorDegreeDetail
    extra = 1

class CreatorAdmin(admin.ModelAdmin):
    inlines = [CreatorSchoolDetailInline, CreatorDegreeDetailInline]

admin.site.register(StoryType, StoryTypeAdmin)
admin.site.register(SeriesBondType, SeriesBondTypeAdmin)

#register creator models to admin panel
admin.site.register(NameType)
admin.site.register(CreatorNameDetails)
admin.site.register(SourceType)
admin.site.register(RelationType)
admin.site.register(NameRelation)
admin.site.register(MembershipType)
admin.site.register(NonComicWorkType)
admin.site.register(NonComicWorkRole)
admin.site.register(Creator,CreatorAdmin)
admin.site.register(BirthYearSource)
admin.site.register(BirthMonthSource)
admin.site.register(BirthDateSource)
admin.site.register(DeathYearSource)
admin.site.register(DeathMonthSource)
admin.site.register(DeathDateSource)
admin.site.register(BirthCountrySource)
admin.site.register(BirthProvinceSource)
admin.site.register(BirthCitySource)
admin.site.register(DeathCountrySource)
admin.site.register(DeathProvinceSource)
admin.site.register(DeathCitySource)
admin.site.register(PortraitSource)
admin.site.register(BioSource)
admin.site.register(School)
admin.site.register(Degree)
admin.site.register(ArtInfluence)
admin.site.register(Membership)
admin.site.register(Award)
admin.site.register(NonComicWork)
admin.site.register(NonComicWorkYear)
admin.site.register(NonComicWorkLink)
admin.site.register(CreatorSchoolDetail)
admin.site.register(CreatorDegreeDetail)
