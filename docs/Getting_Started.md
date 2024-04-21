# Getting Started

This is the implementation of the Grand Comics Database in Python
using the [Django framework](https://djangoproject.com).

For basic information, see the [README](README.md) file in the project's root directory.

The specifics of setting up a development environment on MacOS X or Linux is
documented in
[Getting Started on MacOS or Linux](Getting_Started_on_MacOS_or_Linux.md)
The specifics of setting up a development environment on Windows is
documented in
[Getting Started on Windows](Getting_Started_on_Windows.md).

After you went through the steps return to here and follow the instruction to
use a current dump of our database in the dev-environment.

# The GCD project and apps

## 1. `settings.py` and `settings_local.py`

In the top level directory of your repository clone, open up `settings.py` and
take a look at it.  You should create a `settings_local.py` file in the same
directory, and override any values from `settings.py` that need overriding in
that `settings_local.py`.  Do not modify `settings.py` itself, unless you need
to push a change out to all other development and production environments.

Our `.gitignore` settings will prevent git from noticing `settings_local.py`.

The `settings.py` file has numerous comments indicating what needs to be overridden.
The most obvious are the `DATABASES` and `CACHES` group of settings.

By default, we assume that the database is called `gcdonline`. It can be
accessed by a user called `gcdonline` with no password. If you set your
database up differently, look for settings that start with `DATABASE`. Override
them appropriately.

## 2. Creating your test database

Create your database and set up whatever permissions you want.  Django
will create the tables for you, but you need to create the database first.

E.g. from MySQL command line client do (this is without a password):
```
create schema gcdonline;
create user gcdonline;
grant all on gcdonline.* to gcdonline;
```

## 3. Creating the database schema

To create the various tables run the migrations with

```
python manage.py migrate
```

This will create the tables, populate them with some of the required initial data, 
and update your schema if any updates beyond the initial state are required. 

If you get system check errors for `models.E025`, add `models.E025` to the
`SILENCED_SYSTEM_CHECKS` array in your `settings_local.py` to suppress the check:
```
SILENCED_SYSTEM_CHECKS = ['models.E025']
```

## 4. Populating fixture data

Currently it is needed to manually perform `python manage.py loaddata` on all
files in the fixtures folders of the django apps,
e.g. `apps/indexer/fixtures/`, `apps/gcd/fixtures`, etc.

```
python manage.py loaddata users
```

this will add an admin user, an approver, and a basic indexer. The usernames,
email addresses and passwords can be seen in the fixture file, which is
located at `apps/indexer/fixtures/users.yaml`.  Load all the relevant fixture
data for the apps you expect to be using.

## 5. Populating your database with the GCD data

If you want data in your database, and know that the current development master
matches the production schema, you can load a data dump from

http://www.comics.org/download/

Contact the GCD tech team to find out if the development and production
schemas currently match, and what to do if they do not.

With the default user and database-name you need to do
```
mysql -ugcdonline gcdonline < dump.sql
```
(You might want to do `-v` to see something is happening)

Note that we do not distribute the images for covers and other user contributed
uploads of scans.

## 6. Run backend search facility

For haystack search to work one needs to run elasticsearch search backend.
The latest version can be downloaded here: http://www.elasticsearch.org/download/

Either use the provided deb/rpm or unpack it and run `bin/elasticsearch -f` (on Linux and Mac) or `bin\elasticsearch.bat` (on Windows).

If you get an error like "Unsupported major.minor version 51.0" and a stack
trace, it means that you need to update your java runtime.

After that you can run `python manage.py rebuild_index` in `gcd-django` directory to populate your search indexes with data.

## 7. Launching your test web server

At this time you should be able to test your installation and data import using a
read-only mode, or try out editing with read-write mode.

Read-write mode is the default.
For read-only mode, set `READ_ONLY = True` and `NO_OI = True` in `settings_local.py`

Once your settings are chosen, run

```
python manage.py runserver
```

and take a look at http://127.0.0.1:8000/

If you don't get any page at all, check http://www.djangoproject.com/ if it
looks like Django isn't configured correctly, or
http://dev.comics.org/ and/or http://groups.google.com/group/gcd-tech/
if it appears to be a code problem.

# Proposing your first change for review

When you start making changes, go to the wiki at http://docs.comics.org/
for instructions on how to get code reviewed before checkin.  You'll need
to set up an account with our Review Board instance so that we can review
your first pull request before deciding whether to accept it.  If you develop
a good record of contributions, you will be granted direct access to the project.

Submissions to the project-owned repository that do not first go through
code review will be reverted without notice.
