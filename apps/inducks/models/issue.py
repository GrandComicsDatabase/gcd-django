from django.db import models

from .series import Series

class Issue(models.Model):
    """ issue from inducks database"""

    class Meta:
        db_table = 'inducks_issue'
        app_label = 'coa'

    class Admin:
        pass

    id = models.CharField(primary_key = True, max_length = 20,
                          db_column = 'issuecode')

    # Core issue attributes.
    number = models.CharField(max_length = 100, db_column = 'issuenumber',
                              null = True)
    notes = models.TextField(db_column = 'issuecomment', null = True)
                              
    publication_date = models.CharField(max_length = 10,
                                        db_column = 'oldestdate',
                                        null = True)
    price = models.CharField(max_length = 100, db_column = 'price', null = True)
    fully_indexed = models.BooleanField(default = False, db_column = 'fullyindexed')
    error_message = models.TextField(db_column = 'errormessage', null = True)
    page_count = models.CharField(max_length = 100, db_column = 'pages', 
                                    null = True)
    series = models.ForeignKey(Series,
                               db_column = 'publicationcode')

    def __unicode__(self):
        return str(self.series.name) + " #" + self.number
