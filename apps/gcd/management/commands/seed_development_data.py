"""Create the small, deterministic dataset used for local development."""

import base64

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.management import BaseCommand, call_command
from django.db import transaction

from apps.gcd.models import (
    Character,
    CharacterNameDetail,
    CharacterRole,
    Cover,
    Creator,
    CreatorNameDetail,
    CreditType,
    Feature,
    FeatureNameDetail,
    FeatureType,
    Group,
    GroupNameDetail,
    Image,
    ImageType,
    Issue,
    Publisher,
    Reprint,
    Series,
    Story,
    StoryCharacter,
    StoryCredit,
    StoryType,
    Universe,
)
from apps.oi import states
from apps.oi.models import CTYPES, Changeset, ChangesetComment
from apps.stddata.models import Country, Language, Script
from apps.stats.models import CountStats


SAMPLE_PREFIX = '[GCD DEV]'
SAMPLE_COMMENT = (
    '[GCD DEV] Seeded sample change history for local development. ✅'
)
SAMPLE_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk'
    'YAAAAAYAAjCB0C8AAAAASUVORK5CYII='
)


class Command(BaseCommand):
    """Load local accounts, sample catalog data, and edit-workflow state."""

    help = (
        'Load deterministic development accounts, sample catalog data, and '
        'global catalog statistics.'
    )

    def handle(self, *args, **options):
        """Seed data safely on a new database or refresh it on an existing one."""
        with transaction.atomic():
            call_command('loaddata', 'users', verbosity=options['verbosity'])
            self._seed_catalog()
            self._seed_change_history()
            CountStats.objects.init_stats()

        self.stdout.write(
            self.style.SUCCESS(
                'Development accounts, sample catalog data, and statistics are ready.'
            )
        )

    def _seed_catalog(self):
        """Create a compact, relationship-rich catalog sample idempotently."""
        country = Country.objects.filter(code='us').first() or Country.objects.first()
        language = (Language.objects.filter(code='en').first()
                    or Language.objects.first())
        if country is None or language is None:
            raise RuntimeError('Country and language reference data are required.')

        publisher, _ = Publisher.objects.get_or_create(
            name=f'{SAMPLE_PREFIX} Example Comics',
            defaults={'notes': 'Deterministic publisher for local development.',
                      'country': country},
        )
        series, _ = Series.objects.get_or_create(
            publisher=publisher,
            name=f'{SAMPLE_PREFIX} Adventures',
            defaults={
                'sort_name': f'{SAMPLE_PREFIX} Adventures',
                'notes': 'Deterministic series for local development.',
                'year_began': 2024,
                'publication_dates': '2024-present',
                'tracking_notes': '',
                'country': country,
                'language': language,
                'is_comics_publication': True,
                'is_current': True,
            },
        )
        issue, _ = Issue.objects.get_or_create(
            series=series,
            sort_code=1,
            defaults={
                'number': '1',
                'title': f'{SAMPLE_PREFIX} First Flight',
                'volume': '1',
                'isbn': '',
                'valid_isbn': '',
                'variant_name': '',
                'barcode': '',
                'publication_date': '2024',
                'key_date': '2024-01-01',
                'on_sale_date': '2024-01-01',
                'indicia_frequency': 'monthly',
                'price': '$3.99',
                'editing': '',
                'notes': 'Deterministic issue for local development.',
                'indicia_printer_sourced_by': '',
                'is_indexed': 10,
            },
        )
        variant, _ = Issue.objects.get_or_create(
            series=series,
            sort_code=2,
            defaults={
                'number': '1',
                'title': f'{SAMPLE_PREFIX} First Flight',
                'volume': '1',
                'isbn': '',
                'valid_isbn': '',
                'variant_name': 'Direct Market Variant',
                'barcode': '',
                'publication_date': '2024',
                'key_date': '2024-01-01',
                'on_sale_date': '2024-01-01',
                'indicia_frequency': 'monthly',
                'price': '$3.99',
                'editing': '',
                'notes': 'Deterministic variant for local development.',
                'indicia_printer_sourced_by': '',
                'is_indexed': 10,
                'variant_of': issue,
                'variant_cover_status': 3,
            },
        )

        feature_type, _ = FeatureType.objects.get_or_create(name='story')
        feature, _ = Feature.objects.get_or_create(
            name=f'{SAMPLE_PREFIX} Feature',
            language=language,
            defaults={
                'sort_name': f'{SAMPLE_PREFIX} Feature',
                'genre': 'superhero',
                'feature_type': feature_type,
                'description': 'Deterministic feature for local development.',
                'notes': '',
            },
        )
        feature_name, _ = FeatureNameDetail.objects.get_or_create(
            feature=feature,
            name=f'{SAMPLE_PREFIX} Feature',
            defaults={'is_official_name': True},
        )
        story_type, _ = StoryType.objects.get_or_create(
            name='cartoon', defaults={'sort_code': 7}
        )
        story, story_created = Story.objects.get_or_create(
            issue=issue,
            sequence_number=0,
            defaults={
                'title': f'{SAMPLE_PREFIX} First Flight Story',
                'feature': feature.name,
                'type': story_type,
                'script': '',
                'pencils': '',
                'inks': '',
                'colors': '',
                'letters': '',
                'editing': '',
                'job_number': '',
                'genre': '',
                'characters': '',
                'synopsis': 'Deterministic story for local development.',
                'reprint_notes': '',
                'notes': '',
            },
        )
        if not story_created and (story.type_id != story_type.id or
                                  story.title != f'{SAMPLE_PREFIX} First Flight Story'):
            story.type = story_type
            story.title = f'{SAMPLE_PREFIX} First Flight Story'
            story.save(update_fields=['type', 'title'])
        story.feature_object.add(feature)
        story.feature_name.add(feature_name)

        creator, _ = Creator.objects.get_or_create(
            gcd_official_name=f'{SAMPLE_PREFIX} Alex Example',
            defaults={
                'bio': 'Deterministic creator for local development.',
                'notes': '',
                'sort_name': f'{SAMPLE_PREFIX} Alex Example',
                'birth_province': '',
                'birth_city': '',
                'death_province': '',
                'death_city': '',
            },
        )
        script = Script.objects.filter(number=37).first()
        if script is None:
            script = Script.objects.filter(code='latn').first()
        if script is None:
            script = Script.objects.create(number=37, code='latn', name='Latin')
        creator_name, _ = CreatorNameDetail.objects.get_or_create(
            creator=creator,
            name=f'{SAMPLE_PREFIX} Alex Example',
            defaults={'is_official_name': True, 'in_script': script},
        )
        credit_type, _ = CreditType.objects.get_or_create(
            name='script', defaults={'sort_code': 1}
        )
        StoryCredit.objects.get_or_create(
            story=story,
            creator=creator_name,
            credit_type=credit_type,
            defaults={
                'signed_as': '',
                'credited_as': creator_name.name,
                'sourced_by': '',
                'credit_name': '',
                'is_credited': True,
            },
        )

        universe, _ = Universe.objects.get_or_create(
            multiverse=f'{SAMPLE_PREFIX} Multiverse',
            name=f'{SAMPLE_PREFIX} Main Universe',
            designation='Earth-DEV',
            defaults={
                'description': 'Deterministic universe for local development.',
                'notes': '',
                'year_first_published': 2024,
            },
        )
        character, _ = Character.objects.get_or_create(
            name=f'{SAMPLE_PREFIX} Captain Example',
            defaults={
                'sort_name': f'{SAMPLE_PREFIX} Captain Example',
                'disambiguation': 'development sample',
                'universe': universe,
                'language': language,
                'description': 'Deterministic character for local development.',
                'notes': '',
            },
        )
        character_name, _ = CharacterNameDetail.objects.get_or_create(
            character=character,
            name=f'{SAMPLE_PREFIX} Captain Example',
            defaults={'is_official_name': True},
        )
        group, _ = Group.objects.get_or_create(
            name=f'{SAMPLE_PREFIX} Example League',
            defaults={
                'sort_name': f'{SAMPLE_PREFIX} Example League',
                'disambiguation': 'development sample',
                'universe': universe,
                'language': language,
                'description': 'Deterministic group for local development.',
                'notes': '',
            },
        )
        group_name, _ = GroupNameDetail.objects.get_or_create(
            group=group,
            name=f'{SAMPLE_PREFIX} Example League',
            defaults={'is_official_name': True},
        )
        role, _ = CharacterRole.objects.get_or_create(
            name='featured', defaults={'sort_code': 3}
        )
        appearance, _ = StoryCharacter.objects.get_or_create(
            story=story,
            character=character_name,
            defaults={'universe': universe, 'role': role, 'notes': ''},
        )
        appearance.group.add(group)
        appearance.group_name.add(group_name)
        story.universe.add(universe)
        Reprint.objects.get_or_create(
            origin=story,
            target=None,
            origin_issue=issue,
            target_issue=variant,
            defaults={'notes': 'Deterministic issue reprint for local development.'},
        )

        image_type, _ = ImageType.objects.get_or_create(
            name=f'{SAMPLE_PREFIX} Cover Image',
            defaults={
                'description': 'Deterministic cover image for local development.'
            },
        )
        issue_content_type = ContentType.objects.get_for_model(Issue)
        for covered_issue in (issue, variant):
            Cover.objects.get_or_create(issue=covered_issue)
            image, _ = Image.objects.get_or_create(
                content_type=issue_content_type,
                object_id=covered_issue.id,
                type=image_type,
            )
            if not image.image_file:
                image.image_file.save(
                    f'gcd-dev-cover-{covered_issue.sort_code}.png',
                    ContentFile(SAMPLE_PNG),
                    save=True,
                )

        series.set_first_last_issues()
        series.issue_count = series.active_issues().count()
        series.save(update_fields=['issue_count'])
        publisher.issue_count = Issue.objects.filter(series__publisher=publisher,
                                                      deleted=False).count()
        publisher.series_count = publisher.active_series().count()
        publisher.save(update_fields=['issue_count', 'series_count'])

    def _seed_change_history(self):
        """Create one approved changeset and emoji-bearing comment sample."""
        admin = User.objects.get(username='admin')
        comment = ChangesetComment.objects.filter(text=SAMPLE_COMMENT).first()
        if comment:
            return
        changeset = Changeset.objects.create(
            state=states.APPROVED,
            indexer=admin,
            change_type=CTYPES['series'],
        )
        ChangesetComment.objects.create(
            commenter=admin,
            changeset=changeset,
            text=SAMPLE_COMMENT,
            old_state=states.PENDING,
            new_state=states.APPROVED,
        )
