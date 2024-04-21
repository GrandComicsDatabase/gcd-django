from django.db import models

from .gcddata import GcdData, GcdLink

class SourceType(models.Model):
    """
    The data source type for each data source record should be recorded.
    """

    class Meta:
        db_table = 'gcd_source_type'
        app_label = 'gcd'
        ordering = ('type',)
        verbose_name_plural = 'Source Types'

    type = models.CharField(max_length=50)

    def __str__(self):
        return str(self.type)


class DataSource(GcdData):
    """
    Indicates the various sources of data
    """

    class Meta:
        db_table = 'gcd_data_source'
        app_label = 'gcd'
        ordering = ('source_description',)
        verbose_name_plural = 'Creator Data Source'

    source_type = models.ForeignKey(SourceType, on_delete=models.CASCADE)
    source_description = models.TextField()
    field = models.CharField(max_length=256)

    def __str__(self):
        return '%s - %s' % (str(self.field),
                            str(self.source_type.type))


class ExternalSite(models.Model):
    """
    Pre-approved external sites that can be linked to.
    """

    class Meta:
        db_table = 'gcd_external_site'
        app_label = 'gcd'
        ordering = ('site',)
        verbose_name_plural = 'External Sites'

    site = models.CharField(max_length=255)
    matching = models.CharField(max_length=50)

    def __str__(self):
        return str(self.site)


class ExternalLink(GcdLink):
    """
    Records the links for a data record.
    """

    class Meta:
        db_table = 'gcd_external_link'
        app_label = 'gcd'
        verbose_name_plural = 'External Links'
        ordering = ('site__site',)

    site = models.ForeignKey(ExternalSite, on_delete=models.CASCADE)
    link = models.URLField(max_length=2000)

    def __str__(self):
        return '%s - %s' % (str(self.site),
                            self.link)
