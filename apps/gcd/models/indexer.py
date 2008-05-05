from django.db import models


class Indexer(models.Model):
    """ indexer from gcd database"""

    class Meta:
        db_table = 'Indexers'
        app_label = 'gcd'

    class Admin:
        pass

    id = models.AutoField(primary_key = True, db_column = 'ID')

    first_name = models.CharField(max_length = 255, db_column = 'FirstName',
                                  null = True)
    last_name = models.CharField(max_length = 255, db_column = 'LastName',
                                 null = True)
    name = models.CharField(max_length = 255, db_column = 'Name', null = True)

    # This is not quite the country code from other fields, but is clearly
    # supposed to use two-letter codes even though not all entries do.
    country_code = models.CharField(max_length = 255, db_column = 'Country',
                                    null = True)

