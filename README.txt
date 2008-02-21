This is a new implementation of the Grand Comic-Book Database in Python
using the Django framework.

This project is arranged in three directories:
    * src/ contains all Python source code, including configuration files
      that are themselves Python code.
    * media/ contains support files such as images and CSS.
    * templates/ contains Django templates for web pages.

To run:

0.  You'll need Python.  This code was developed with Python 2.4 in order
to be compatible with the last version of MySQLdb (1.2.1) that was pre-compiled
for MacOS.  Current versions of MySQLdb do not compile on all versions
of MacOS.  More details on this later.


1.  Install Django (http://www.djangoproject.com).  Get the source
from Subversion as of revision 6980 for best results (this number will
move forward as relevant patches to Django are checked in, especially
in regards to bug #2076 about using ORDER BY on joined tables.


2.  Install MySQL (version 5.0.45 has been used with this code).  Load a
data dump of the GCD database into MySQL (ask the tech list for help
if you don't already know how to get such a dump).  Depending on what
queries you run, you may have some trouble with some of the stranger
entries in the database, as some rather important foreign keys are null
for a few entries.  If you hit these problems (and error handling is currently
more or less non-existant), try something along the lines of:

DELETE from stories WHERE IssueID is NULL;
DELETE from issues WHERE SeriesID is NULL;
DELETE from series WHERE PubID is NULL;

Do double-check the above before running it as I have not tested it directly
from this file.


3.  Install the MySQLdb Python module from
http://sourceforge.net/projects/mysql-python

On Linux or Windows, this should not be problematic.

If you are on a Mac, you may need to downgrade to Python 2.4 and use
a slightly older version of MySQLdb due to bug 1768305 (in the SourceForge
bug-tracking system), which applies to Python 2.5 despite saying 2.4 in the
title.  Yes, that's confusing.  There is a page that maintains pre-compiled
Python packages for MacOS that has one for Python 2.4 but not 2.5:
http://pythonmac.org/packages/py24-fat/index.html
This is what I used, and I recommend it- the last release of MySQLdb was
almost a year ago (Feb 2007) so I'm not holding my breath wating for the compile
problem to be fixed.

If you're feeling brave, this page on installing Django:
http://tinyurl.com/2sq4x7
(which is on a Ruby site for some reason) has instructions on how to
get MySQLdb  compiling for Python 2.5.


4.  Put the src/ directory of this project on your Python path.


5.  Open up src/gcd/settings.py and find all of the lines marked TODO.
replace these as necessary for your system.


6.  From the src/gcd/ directory, run

python manage.py runserver

and then take a look at http://127.0.0.1:8000/gcd/

You should see a minimal page with a link to the optimistically named
"advanced search" page.  Also take a look in src/gcd/urls.py for some
explanation about URLs you can type in directly in order to run searches.
For instance, http://127.0.0.1:8000/gcd/series/name/Blue Beetle/sort/chrono
should list the various series including "Blue Beetle" in their titles
in chronological order.

All such searches can be reached through the search forms as well.  The
simple search form just redirects to those URLs, while the advanced form
does things a bit differently.  Searches should mostly yield the same
results as on the GCD, although some elements of the display are not
yet correct, and in a few places the exact details of the matching
algorithm are a bit unclear.  Please note also that there is a lot of
cruft in the database, in particular with regards to the dates used to
sort things chronologically.  Therefore if there are some outliers
at the beginning and/or end of a chronological sort, it is because of
the data in the database (as the code does not re-sort the results).

If you don't get any page at all, check www.djangoproject.com if it
looks like Django isn't configured correctly, or handrews@users.sourceforge.net
if it appears to be a code problem.  The bug tracking system for GCD on
SourceForge will be set up in the near future, but please contact handrews
first if you have not yet gotten the system running.


*******************************************************************************

A quick guide to the code:

gcd.settings, gcd.urls and gcd.manage are all Django artifacts.  gcd.manage
is entirely Django code, with no modifications.  gcd.urls provides the mappings
from URLs to function calls within what Django calls "views", which most
frameworks consider to be "controllers" (Django's templates more closely
correspond to what is traditionally called a "view").

The gcd.models.* files implement classes corresponding to database tables.
The tables relating to indexers aren't yet implemented because the current
code base does not need them.  The remaining table implementations are fairly
straightforward, with the most notable thing being that the column names,
spelling and capitalization have all been standardized, with most abbreviations
spelled out for clarity.

The gcd.views.* files contain functions that render the templates for display.
They are called by Django's built-in controller layer which uses gcd.urls to
route requests.  gcd.views.search holds functions related to searching and
displaying search results.  gcd.views.details holds functions related to
displaying the details of publishers, series, issues and stories.
The code to display the index page resides in gcd.views.__init__.


*******************************************************************************
* Please try to adhere to the following coding standards.
*******************************************************************************

Python Coding Standards:

* Indentation is 4 spaces.  No tabs.  This is critical in Python.

* Stay within 80 columns.  Continued lines should line up with matching
  operands or parameters on the first line if possible, or should be
  indented an extra 2 (not 4) spaces.  Examples:

  * Breaking after an operator:

  * Simple example of 2-space continuation:

    latest_updated_indexes = \
      Issue.objects.all().order_by('-modified', -modification_time')[:MAX]
  * Continuing a line when lining up the parameters would not work.  In this
    case it is better to start the 2nd parameter with a 2-space indent rather
    than line it up with the first and break again inside the dictionary:

    return render_to_response('index.html',
      {'latest_updated_indexes' : latest_updated_indexes})

  * Use extra local variables to avoid complex long lines.  For instance,
    the previous example could be done as:

    vars = {'latest_updated_indexes' : latest_updated_indexes})
    return render_to_response('index.html', vars)


* Place two blank lines in between methods and/or classes.

* Place a blank line between code blocks, especially when there are
  multiple adjacent if blocks that could easily be misinterpreted as
  else-ifs.

* Keep model code arranged as one class per file.

* Group view functions into files based on similar functionality.


*******************************************************************************

HTML / CSS / Template coding standards.

* Generally the same as for Python, although in some cases long lines
  are unavoidable.  For instance, within anchor tags (links) extra
  whitespace of any sort can cause undesired effects.

* Use CSS whenever possible.  If something is being done through HTML
  that could be done through CSS, please fix it.

* If you have extensive HTML/CSS/JavaScript experience, contact handrews
  about expanding this section.

