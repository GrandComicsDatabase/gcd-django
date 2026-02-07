# GCD Web Application

This file last updated: *Jan 2026*

This is the current implementation of the Grand Comics Database, hosted at
https://www.comics.org/ (production) and https://beta.comics.org/ (public beta
for new features).

See the [Technical section on docs.comics.org](https://docs.comics.org/wiki/Main_Page#Technical_Details)
and the [Wiki](https://github.com/GrandComicsDatabase/gcd-django/wiki) for more detailed information about how we work and what has been done to date.
This file just covers the essentials of branches and code reviews.

We have a first version of a REST API, see the [documentation](https://github.com/GrandComicsDatabase/gcd-django/wiki/API).

Please join the [gcd-tech list](http://groups.google.com/group/gcd-tech/) for
help and to find out where we could use your contributions:

http://groups.google.com/group/gcd-tech/

## Setting up a Development Environment

We recommend that you use [our Docker-based development environment](https://github.com/GrandComicsDatabase/gcd-django-docker).

You can find manual instructions for various platforms using virtual environments for python in the docs directory
[GCD Docs](https://github.com/GrandComicsDatabase/gcd-django/tree/beta/docs) but they aren't
necessarily up to date.  As of September 2023 they should work.

## Workflow

Our primary collaboration space is the
[gcd-tech](https://groups.google.com/group/gcd-tech/) mailing list.
We use the GitHub code review system for discussing code changes.

Pull requests are welcome, but you might want to poke the mailing list if
no one seems to be paying attention.

## Branches

### `master`

This is (generally) the production deployment.  For the most part, work
should not be done here directly.

Contact: gcd-tech-team
via [gcd-tech](https://groups.google.com/group/gcd-tech/)

### `beta`

This is the general-purpose development branch.  It is often deployed to
[the beta site](http://beta.comics.org/), and most work should be done here.
Special-purpose development branches are based from `beta` unless otherwise
noted.

Contact: gcd-tech-team
via [gcd-tech](https://groups.google.com/group/gcd-tech/)

### `experimental`

This branch was for experimental work to refactor the system in
several stages.

Most of the refactoring work was moved over to the main branch, some double checking needs to be performed if there are remaining ideas.

Contact: gcd-tech-team via [gcd-tech](https://groups.google.com/group/gcd-tech/)

## History of the Code

The current production code runs on Django 5.2.

This version of the GCD web application was initially written in Python using
Django 0.96, and rushed into deployment in late 2009 when the prior system's
host crashed after many years of service.  Due to both of these facts, there
remain some oddities and things that you would not see in a modern Django system.

## Reporting or Examining Bugs

Bugs and feature requests are recorded in GitHub's issue tracking system.

If you are unfamiliar with the code, please contact the
[gcd-tech](https://groups.google.com/group/gcd-tech/) list before starting
to submit fixes.


## Acknowledgements

In addition to the contributors you see within the git log, we'd like to
thank Jon Løvstadt for his work developing and running the previous iteration
of the GCD web application.
