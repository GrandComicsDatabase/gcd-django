from django.contrib import admin

from apps.stddata.models import Country, Language, Currency


class CountryAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code')
    list_display = ('code', 'name')
    list_display_links = ('code', 'name')


class CurrencyAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code')
    list_display = ('code', 'name', 'is_decimal')
    list_display_links = ('code', 'name')


class LanguageAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code')
    list_display = ('code', 'name')
    list_display_links = ('code', 'name')


admin.site.register(Country, CountryAdmin)
admin.site.register(Currency, CurrencyAdmin)
admin.site.register(Language, LanguageAdmin)
