from django.db.models import Count
from django.shortcuts import render_to_response
from django.template import RequestContext

from apps.gcd.models import Publisher, Country
from apps.gcd.views import paginate_response
from apps.projects.forms import ImprintsInUseForm


def imprints_in_use(request):
    """
    This project is geared towards clearing out the old imprint field so we can
    either remove it or start over with a new 'imprint' concept with a consistent
    definition.  For this we need a list of imprints in use that can be filtered
    and sorted by a few basic attributes.
    """

    imprints = Publisher.objects.filter(deleted=0, is_master=0)

    qargs = {'deleted': 0, 'is_master': 0}
    qorder = ['series_count', 'parent__name', 'name']

    vars = {
        'heading': 'Imprints',
        'search_item': 'In Use',
        'item_name': 'imprint',
        'plural_suffix': 's',
    }

    if (request.GET):
        form = ImprintsInUseForm(request.GET)
        form.is_valid()
        if form.is_valid():
            data = form.cleaned_data

            # Extra filters
            if data['parent']:
                qargs['parent'] = data['parent']
            if data['parent_country']:
                qargs['parent__country'] = data['parent_country']
            if data['imprint_country']:
                qargs['country'] = data['imprint_country']

            # Override order
            if data['order1'] or data['order2'] or data['order3']:
                qorder = []
                if data['order1']:
                    qorder.append(data['order1'])
                if data['order2']:
                    qorder.append(data['order2'])
                if data['order3']:
                    qorder.append(data['order3'])
    else:
        form = ImprintsInUseForm(auto_id=True,
          initial=dict(zip(('order1', 'order2', 'order3'), qorder)))

    imprints = imprints.filter(**qargs).order_by(*qorder)
    vars['form'] = form

    return paginate_response(request, imprints,
                             'projects/imprints_in_use.html', vars)

