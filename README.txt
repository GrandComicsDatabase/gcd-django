This is a new implementation of the Grand Comics Database in Python
using the Django framework.

Setup:
======
The short form of how to set this up is:
   * Install Python 2.4 (http://www.python.org)
   * Install MySQL 5.0 (http://www.mysql.com)
   * Install MySQLdb (http://sourceforge.net/projects/mysql-python)
   * Install Django from Subversion circa revision 7835
     (http://www.djangoproject.com)
   * Go nuts :-)

For detailed documentation about setting up a development environment
on varioius OSes, see the Getting_Started_on_*.txt files in the docs/
directory.  The MacOS file explains why we're using Python 2.4.
In theory, you should be able to use Python 2.5 as long as you do
not do anything that breaks 2.4 compatibility.

A Guide to the Project Structure:
=================================
Note that the project root directory is placed in the Python include
path.  This means that files and directories here can serve as Python modules.

Directories
    apps/
        * Python package for the Django application
    docs/
        * Setup guides
        * Coding standards
        * Test documentation (someday)
    locale/
        * Internationalization stuff
    media/
        * CSS and Images for the Django application
    templates/
        * HTML templates for the Django application

Files:
    manage.py
        * A Django module that runs the test web server and provides
          other utility services.  Not generally modified.
    settings.py
        * The settings for the Django application.  You may need to modify
          this depending on your set-up, but please do not check in any
          such local modifications.  In theory, you can create a separate
          local setup file to make modifications.  See the Django docs.
    urls.py
        * Django configuration mapping URLs to view functions.


To run:
    python manage.py runserver
    will launch a test server at http://127.0.0.1:8000/gcd/


To report bugs or find bugs to work on:
    http://dev.comics.org/bugzilla/

    * Bugs in the NEW state are available for work.
    * Bugs in the ASSIGNED state are being worked on.

    Be sure to "Accept" a bug to put it in the ASSIGNED state
    before you start working on it.  Unlike in many Bugzilla installations,
    "Accept"ing a bug will automatically reassign it to you.

    If you are unfamiliar with the code, contact the GCD-Tech list
    before starting to submit fixes.


*******************************************************************************

A quick guide to the code:
[For the most up-to-date-docs, visit http://docs.comics.org/ ]

gcd.settings, gcd.urls and gcd.manage are all Django artifacts.  gcd.manage
is entirely Django code, with no modifications.  gcd.urls provides the mappings
from URLs to function calls within what Django calls "views", which most
frameworks consider to be "controllers" (Django's templates more closely
correspond to what is traditionally called a "view").

The gcd.models.* files implement classes corresponding to database tables.
The table implementations are fairly straightforward, with the most notable
thing being that the column names, spelling and capitalization have all been
standardized, with most abbreviations spelled out for clarity.

The gcd.views.* files contain functions that render the templates for display.
They are called by Django's built-in controller layer which uses gcd.urls to
route requests.  gcd.views.search holds functions related to searching and
displaying search results.  gcd.views.details holds functions related to
displaying the details of publishers, series, issues and stories.
The code to display the index page resides in gcd.views.__init__.

