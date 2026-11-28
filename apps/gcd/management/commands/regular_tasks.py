"""Run the clean-ups the site needs at regular times, one after another."""

import argparse
from io import StringIO

from django.core.management import BaseCommand, CommandError, call_command


def remove_orphaned_tags():
    """Delete the keywords that no record uses any more."""
    output = StringIO()
    call_command('remove_orphaned_tags', stdout=output)
    return output.getvalue().strip()


# Each task is a name and a function that returns one line of report.
TASKS = (
    ('remove_orphaned_tags', remove_orphaned_tags),
)


class Command(BaseCommand):
    """Run every task of TASKS, also when an earlier one fails."""

    help = (
        'Run the regular clean-ups one after another: one line per task on\n'
        'stdout; a task that fails writes its error on stderr, the next\n'
        'tasks still run, and the command ends with an error naming the\n'
        'failed ones. For cron, once a night; with stdout thrown away,\n'
        'cron mails only the failures:\n'
        '\n'
        '15 4 * * * cd <site> && python manage.py regular_tasks > /dev/null'
    )

    def create_parser(self, prog_name, subcommand, **kwargs):
        """Print the help as written, so the cron line stays whole."""
        kwargs.setdefault(
            'formatter_class', argparse.RawDescriptionHelpFormatter)
        return super().create_parser(prog_name, subcommand, **kwargs)

    def handle(self, *args, **options):
        """Run the tasks; raise CommandError naming the ones that failed."""
        failed = []
        for name, task in TASKS:
            try:
                report = task()
            except Exception as error:
                failed.append(name)
                self.stderr.write(
                    f'{name}: failed: {type(error).__name__}: {error}')
                continue
            self.stdout.write(f'{name}: {report}')
        if failed:
            raise CommandError('Failed tasks: ' + ', '.join(failed))
