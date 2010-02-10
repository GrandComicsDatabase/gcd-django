from decimal import Decimal, InvalidOperation

from django.http import HttpResponseRedirect
from django.utils.html import conditional_escape as esc
from django.contrib.auth.decorators import permission_required
from django.shortcuts import render_to_response, get_object_or_404

from apps.gcd.views import render_error
from apps.gcd.views.details import KEY_DATE_REGEXP
from apps.oi.models import *
from apps.oi.forms import *

ISSUE_FIELDS = 11
SEQUENCE_FIELDS = 16

NUMBER = 0
VOLUME = 1
INDICIA_PUBLISHER = 2
BRAND = 3
PUBLICATION_DATE = 4
KEY_DATE = 5
INDICIA_FREQUENCY = 6
PRICE = 7
ISSUE_PAGE_COUNT = 8
ISSUE_EDITING = 9
ISSUE_NOTES = 10

TITLE = 0
TYPE = 1
FEATURE = 2
STORY_PAGE_COUNT = 3
SCRIPT = 4
PENCILS = 5
INKS = 6
COLORIST = 7
LETTERER = 8
STORY_EDITING = 9
GENRE = 10
CHARACTER_APPEARANCE = 11
JOB_NUMBER = 12
REPRINT_INFO = 13
SYNOPSIS = 14
STORY_NOTES = 15

# order of the fields in line with the OI, but not
# all fields (i.e. no_...) are present explicitly
# relevant documentation and order is here:
# http://docs.comics.org/wiki/Indexing_Offline
def _check_for_none(value):
    if value.strip().lower() == 'none':
        return '', True
    else:
        return value.strip(), False


def _check_page_count(page_count):
    if page_count.find('?') >= 0:
        page_count_uncertain = True
        page_count = page_count[:page_count.find('?')]
    else:
        page_count_uncertain = False
    try:
        page_count = Decimal(page_count)
    except InvalidOperation:
        page_count = None
        page_count_uncertain = True
    return page_count, page_count_uncertain


def _parse_volume(volume):
    if not volume:
        volume = None
        no_volume = True
    else:
        try:
            volume = int(volume)
            no_volume = False
        except ValueError:
            volume = None
            no_volume = False
    return volume, no_volume


def _import_sequences(request, issue_id, changeset, lines, running_number):
    """
    Processing of story lines happens here. 
    lines is a list of lists. 
    This routine is independent of a particular format of the file,
    as long as the order of the fields in lines matches.
    """

    for fields in lines:
        try:
            story_type = StoryType.objects.get(name=fields[TYPE].strip().lower)
        except StoryType.DoesNotExist:
            return render_error(request,
              'Story type "%s" in line %s does not exist.' 
              ' Back to the <a href="%s">editing page</a>.' \
              % (esc(fields[TYPE]), esc(fields), urlresolvers.reverse('edit', 
                 kwargs={'id': changeset.id})), is_safe=True)
        title = fields[TITLE].strip()
        if title.startswith('[') and title.endswith(']'):
            title = title[1:-1]
            title_inferred = True        
        else:
            title_inferred = False
        feature = fields[FEATURE].strip()
        page_count, page_count_uncertain = \
          _check_page_count(fields[STORY_PAGE_COUNT])
        script, no_script = _check_for_none(fields[SCRIPT])
        if story_type == StoryType.objects.get(name='cover'):
            if not script:
                no_script = True
        pencils, no_pencils = _check_for_none(fields[PENCILS])
        inks, no_inks = _check_for_none(fields[INKS])
        colors, no_colors = _check_for_none(fields[COLORIST])
        letters, no_letters = _check_for_none(fields[LETTERER])
        editing, no_editing = _check_for_none(fields[STORY_EDITING])
        genre = fields[GENRE].strip()
        characters = fields[CHARACTER_APPEARANCE].strip()
        job_number = fields[JOB_NUMBER].strip()
        reprint_notes = fields[REPRINT_INFO].strip()
        synopsis = fields[SYNOPSIS].strip()
        notes = fields[STORY_NOTES].strip()

        story_revision = StoryRevision(changeset=changeset,
                                       title=title, 
                                       title_inferred=title_inferred,
                                       feature=feature,
                                       type=story_type,
                                       sequence_number=running_number,
                                       page_count=page_count,
                                       page_count_uncertain = page_count_uncertain,
                                       script = script,
                                       pencils = pencils,
                                       inks = inks,
                                       colors = colors,
                                       letters = letters,
                                       editing = editing,
                                       no_script = no_script,
                                       no_pencils = no_pencils,
                                       no_inks = no_inks,
                                       no_colors = no_colors,
                                       no_letters = no_letters,
                                       no_editing = no_editing,
                                       job_number = job_number,
                                       genre = genre,
                                       characters = characters,
                                       synopsis = synopsis,
                                       reprint_notes = reprint_notes,
                                       notes = notes,
                                       issue = Issue.objects.get(id=issue_id)
                                       )
        story_revision.save()
        running_number += 1
    return HttpResponseRedirect(urlresolvers.reverse('edit',
      kwargs={ 'id': changeset.id }))


def _process_issue_file(request, changeset):
    lines = []
    # process the file into a list of lines and check for length
    for line in request.FILES['flatfile']:
        if not lines: # first line is issue line
            if len(line.split('\t')) != ISSUE_FIELDS:
                response = render_error(request,
                  'issue line %s has %d fields, it must have %d. '
                  'Back to the <a href="%s">editing page</a>.' % \
                    (line.strip('\n').split('\t'),
                     len(line.strip('\n').split('\t')), ISSUE_FIELDS,
                     urlresolvers.reverse('edit', 
                     kwargs={'id': changeset.id})), 
                  is_safe=True)
                return response, True
        else: # others are story lines
            if len(line.split('\t')) != SEQUENCE_FIELDS:
                response = render_error(request,
                  'sequence line %s has %d fields, it must have %d. '
                  'Back to the <a href="%s">editing page</a>.' % \
                    (line.strip('\n').split('\t'),
                     len(line.strip('\n').split('\t')), SEQUENCE_FIELDS,
                     urlresolvers.reverse('edit', 
                     kwargs={'id': changeset.id})), 
                  is_safe=True)
                return response, True
        lines.append(line.strip('\n').split('\t'))
    return lines, False


def _find_publisher_object(request, name, publisher_objects, 
                           object_type, publisher, changeset):
    if not name:
        return None, False

    publisher_objects = publisher_objects.filter(name__iexact=name,
                                                 parent=publisher)
    if publisher_objects.count() == 1:
        return publisher_objects[0], False
    else:
        response = render_error(request,
          '%s "%s" does not exists for publisher '
          '%s. Back to the <a href="%s">editing page</a>.' % \
            (object_type, esc(name), esc(publisher), 
            urlresolvers.reverse('edit', kwargs={'id': changeset.id})), 
          is_safe=True)
        return response, True


@permission_required('gcd.can_reserve')
def import_issue_from_file(request, issue_id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may import issue data.')
    try:
        # Process add form if this is a POST.
        if request.method == 'POST' and 'flatfile' in request.FILES:
            issue_revision = changeset.issuerevisions.get(issue=issue_id)
            if StoryRevision.objects.filter(changeset=changeset).count():
                return render_error(request,
                  'There are already sequences present for %s in this'
                  ' changeset. Back to the <a href="%s">editing page</a>.'\
                   % (esc(issue_revision), urlresolvers.reverse('edit', 
                      kwargs={'id': changeset.id})), is_safe=True)
            lines, failure = _process_issue_file(request, changeset)
            if failure:
                return lines

            # parse the issue line
            issue_fields = lines.pop(0) 
            issue_revision.number = issue_fields[NUMBER].strip()
            issue_revision.volume, issue_revision.no_volume = \
              _parse_volume(issue_fields[VOLUME].strip())

            indicia_publisher, failure = _find_publisher_object(request,
              issue_fields[INDICIA_PUBLISHER].strip(), 
              IndiciaPublisher.objects.all(), 
              "Indicia publisher", issue_revision.issue.series.publisher,
              changeset)
            if failure:
                return indicia_publisher
            else:
                issue_revision.indicia_publisher = indicia_publisher

            brand_name, issue_revision.no_brand = \
              _check_for_none(issue_fields[BRAND])
            brand, failure = _find_publisher_object(request,
              brand_name, Brand.objects.all(), "Brand", 
              issue_revision.issue.series.publisher, changeset)
            if failure:
                return brand
            else:
                issue_revision.brand = brand

            issue_revision.publication_date = issue_fields[PUBLICATION_DATE]\
              .strip()
            issue_revision.key_date = issue_fields[KEY_DATE].strip()
            if not re.search(KEY_DATE_REGEXP, issue_revision.key_date):
                issue_revision.key_date = ''

            issue_revision.indicia_frequency = issue_fields[INDICIA_FREQUENCY]\
              .strip()
            issue_revision.price = issue_fields[PRICE].strip()
            issue_revision.page_count, issue_revision.page_count_uncertain =\
              _check_page_count(issue_fields[ISSUE_PAGE_COUNT])
            issue_revision.editing, issue_revision.no_editing = \
              _check_for_none(issue_fields[ISSUE_EDITING])
            issue_revision.notes = issue_fields[ISSUE_NOTES].strip()
            issue_revision.save()                        
            running_number = 0
            return _import_sequences(request, issue_id, changeset, 
                                     lines, running_number)
        else:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': changeset.id }))

    except (Issue.DoesNotExist, Issue.MultipleObjectsReturned, 
            IssueRevision.DoesNotExist):
        return render_error(request,
          'Could not find issue for id %s and changeset %s' \
            % (issue_id, changeset_id))


@permission_required('gcd.can_reserve')
def import_sequences_from_file(request, issue_id, changeset_id):
    changeset = get_object_or_404(Changeset, id=changeset_id)
    if request.user != changeset.indexer:
        return render_error(request,
          'Only the reservation holder may import stories.')
    try:
        # Process add form if this is a POST.
        if request.method == 'POST' and 'flatfile' in request.FILES:
            issue_revision = changeset.issuerevisions.get(issue=issue_id)
            lines = []
            # check for right number of fields and build list
            for line in request.FILES['flatfile']:
                if len(line.split('\t')) != SEQUENCE_FIELDS:
                    return render_error(request,
                      'The line %s has %d fields, it must have %d.' 
                      ' Back to the <a href="%s">editing page</a>.'% \
                        (esc(line.strip('\n').split('\t')), 
                         len(line.strip('\n').split('\t')), SEQUENCE_FIELDS, 
                         urlresolvers.reverse('edit', 
                         kwargs={'id': changeset.id})), is_safe=True)
                lines.append(line.strip('\n').split('\t'))
            running_number = issue_revision.next_sequence_number()
            return _import_sequences(request, issue_id, changeset, 
                                     lines, running_number)
        else:
            return HttpResponseRedirect(urlresolvers.reverse('edit',
              kwargs={ 'id': changeset.id }))

    except (Issue.DoesNotExist, Issue.MultipleObjectsReturned, 
            IssueRevision.DoesNotExist):
        return render_error(request,
          'Could not find issue for id %s and changeset %s' \
            % (issue_id, changeset_id))

