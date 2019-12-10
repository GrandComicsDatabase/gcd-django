from django.db import models

from .character import Character
from .language import Language

class CharacterName(models.Model):
    class Meta:
        db_table = 'inducks_charactername'
        app_label = 'coa'

    class Admin:
        pass

    character = models.ForeignKey(Character, primary_key = True, 
                                  db_column = 'charactercode')
    name = models.CharField(max_length = 20, primary_key = True, 
                            db_column = 'charactername')
    language = models.ForeignKey(Language, primary_key = True, 
                                 db_column = 'languagecode')
    preferred = models.CharField(max_length = 5, db_column = 'preferred')
    
    def __unicode__(self):
        return str(self.character) + str(self.name) + str(self.language)
