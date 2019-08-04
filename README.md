# GCD Web Application

This file last updated: *Aug 2019*

This is the current implementation of the Grand Comics Database, hosted at
http://www.comics.org/ (production) and http://beta.comics.org/ (public beta
for new features).

See the [Technical section on docs.comics.org](http://docs.comics.org/wiki/Main_Page#Technical_Details)
and the [Wiki](https://github.com/GrandComicsDatabase/gcd-django/wiki) for more detailed information about how we work and what has been done to date.
This file just covers the essentials of branches and code reviews.

Please join the [gcd-tech list](http://groups.google.com/group/gcd-tech/) for
help and to find out where we could use your contributions:

http://groups.google.com/group/gcd-tech/

## Setting up a Development Environment

Our Vagrant-setup needs updating ! We used recommend that you use [our Vagrant-based development environment](https://github.com/GrandComicsDatabase/gcd-django-vagrant-install).

You can find manual instructions for various platforms in the docs directory
[GCD Docs](https://github.com/GrandComicsDatabase/gcd-django/tree/beta/docs) but they aren't
necessarily up to date.  As of Aug 2019 they should work.

## Workflow

Our primary collaboration space is the
[gcd-tech](http://groups.google.com/group/gcd-tech/) mailing list.
We use the GitHub code review system for discussing code changes.

Pull requests are welcome, but you might want to poke the mailing list if
no one seems to be paying attention.

## Branches

### `master`

This is (generally) the production deployment.  For the most part, work
should not be done here directly.

Contact: gcd-tech-team
via [gcd-tech](http://groups.google.com/group/gcd-tech/)

### `beta`

This is the general-purpose development branch.  It is often deployed to
[the beta site](http://beta.comics.org/), and most work should be done here.
Special-purpose development branches are based from `beta` unless otherwise
noted.

Contact: gcd-tech-team
via [gcd-tech](http://groups.google.com/group/gcd-tech/)

### `experimental`

This branch is for experimental work to refactor the system in
several stages.  

There will probably be some modernization and code clean-up along the way.

Contact: [handrews](https://github.com/handrews)
via [gcd-tech](http://groups.google.com/group/gcd-tech/)

### api_experimental

This is an experimental branch for developing the REST API. We expect that
proceeding here will also involve some code clean-up to move the web UI onto
the REST API.  It is not yet determined how often this branch will merge
to `beta`.

Contact: gcd-tech-team
via [gcd-tech](http://groups.google.com/group/gcd-tech/)

## History of the Code

This version of the GCD web application was initially written in Python using
Django 0.96, and rushed into deployment in late 2009 when the prior system's
host crashed after many years of service.  Due to both of these facts, there
remain some oddities and things that you would not see in a modern Django system.

The current production code runs on Django 1.11.

## Reporting or Examining Bugs

Bugs and feature requests are currently recorded in GitHub's issue tracking system. We previously
used an instance of Bugzilla but all bugs/requests from that system have been moved to GitHub. 

If you are unfamiliar with the code, please contact the
[gcd-tech](http://groups.google.com/group/gcd-tech/) list before starting
to submit fixes.


## Acknowledgements

In addition to the contributors you see within the git log, we'd like to
thank Jon Løvstadt for his work developing and running the previous iteration
of the GCD web application.
