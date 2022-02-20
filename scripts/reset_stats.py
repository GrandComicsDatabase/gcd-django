from apps.stats.models import *

CountStats.objects.all().delete()                                                                                                              
CountStats.objects.init_stats()                                                                                                                

for i in Language.objects.all():  
    if Series.objects.filter(language=i).exists(): 
        CountStats.objects.init_stats(language=i)  

for i in Country.objects.all():
    if Series.objects.filter(country=i).exists():
        CountStats.objects.init_stats(country=i)
