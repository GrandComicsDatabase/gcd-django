from django.db import models

from .gcddata import GcdData

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

    def __unicode__(self):
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

    source_type = models.ForeignKey(SourceType)
    source_description = models.TextField()
    field = models.CharField(max_length=256)

    def __unicode__(self):
        return '%s - %s' % (str(self.field),
                            str(self.source_type.type))


