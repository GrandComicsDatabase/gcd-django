from datetime import date
from django.conf import settings
from django.core import mail
from django.contrib.auth.models import *

new_users = User.objects.filter(date_joined__gt=date(2009, 10, 5), is_active=True)
old_users = User.objects.filter(date_joined__lt=date(2009, 10, 6),
                                email__contains='@',
                                indexer__is_banned=False,
                                indexer__deceased=False,
                                is_active=True)

# This is just to get the connection.  The non-method "get_connection" function
# shown in the documentation does not actually exist in the module.
email = mail.EmailMessage('Starting...', from_email='sysadmin@comics.org',
                          to=['hha1@cornell.edu'],
                          headers={'Reply-To': 'contact@comics.org'})
email.send()

new_message="""
Hello from the Grand Comic-Book Database!

We're proud to announce that our Online Indexing data entry system is finally
available for use!  Please visit http://www.comics.org/ to see a list of features
and get started entering data and making corrections.

Once you log in to the site, you can edit anything from its display page, or
add series, brands or indicia publishers from the parent publisher page,
or add issues from the issue's series page.

To add a publisher or see the list of changes you have saved but not yet submitted,
go to your profile (using the "Profile" link in the search bar, or by clicking
your own name in the login box on the front page) and you will see a gray bar
under the normal blue search bar.  This has links for adding and editing, as well
as "pending", which shows submitted changes while they are being reviewed by our
Editors.

If you haven't already, please consider joining the main GCD mailing list at 
http://groups.google.com/group/gcd-main

We look forward to your contributions!

thanks,
-The Grand Comic-Book Database Team
"""

old_message="""
Hello from the Grand Comic-Book Database!

We're proud to announce our new and improved Online Indexing system!  If you've
been waiting for this moment, you need wait no longer.

If you opened an account with us some time ago but stopped using it, this is a
one-time email to encourage you to give us another try (we won't be pestering you
with more mass emails in the future :-)

Here's why you should come back:

* You can do a lot more!  No more asking an editor to add or correct something
  for you.  You can add or edit publishers, series and issues, and you can edit
  issues that have already been indexed.

* The site is on a faster server!  We are no longer experiencing the frequent
  extremely slow responses that became common as our former server got older.

* You can use more languages!  Languages with non-Roman writing systems are
  now accepted in the database.

* We've added new fields to capture more data, and we've cleaned up some of our
  more confusing fields.  This is an ongoing project, and you can expect to see
  more progress in the months ahead.

* We have an active technical team supporting the system with bug fixes and
  new features.  The site does still have a few rough edges as we tried to
  build it as quickly as we could.  Please bear with us and you will see that
  the site will steadily get better.  We do still need a web designer and/or
  an HTML/CSS/JavaScript expert, as well as other technical help, so if you
  can help us out please let us know at contact@comics.org !

Once you log in to the site, you can edit anything from its display page, or
add series, brands or indicia publishers from the parent publisher page,
or add issues from the issue's series page.

To add a publisher or see the list of changes you have saved but not yet submitted,
go to your profile (using the "Profile" link in the search bar, or by clicking
your own name in the login box on the front page) and you will see a gray bar
under the normal blue search bar.  This has links for adding and editing, as well
as "pending", which shows submitted changes while they are being reviewed by our
Editors.

If you've been away for a while, please consider joining the main GCD mailing
list at http://groups.google.com/group/gcd-main

We look forward to your continued or renewed contributions!

thanks,
-The Grand Comic-Book Database Team

"""

for new_user in new_users:
    email = mail.EmailMessage('GCD Online Indexing is available!',
                              new_message,
                              settings.EMAIL_INDEXING,
                              [new_user.email],
                              headers={'Reply-To': settings.EMAIL_CONTACT})
    email.send()

for old_user in old_users:
    email = mail.EmailMessage('All-New GCD Online Indexing is available!',
                              old_message,
                              settings.EMAIL_INDEXING,
                              [old_user.email],
                              headers={'Reply-To': settings.EMAIL_CONTACT})
    email.send()


