# GCD Web Application

This file last updated: *May 2015*

This is the current implementation of the Grand Comics Database, hosted at
http://www.comics.org/ (production) and http://beta.comics.org/ (public beta
for new features).

See the [Technical section on docs.comics.org](http://docs.comics.org/wiki/Main_Page#Technical_Details)
for more detailed information about how we work and what has been done to date.
This file just covers the essentials of branches and code reviews.

Please join the [gcd-tech list](http://groups.google.com/group/gcd-tech/) for
help and to find out where we could use your contributions:

http://groups.google.com/group/gcd-tech/

## Setting up a Development Environment

We recommend that you use [our Vagrant-based development environment](https://github.com/GrandComicsDatabase/gcd-django-vagrant-install).

You can find manual instructions for various platforms in the Technical section
of the [GCD Docs wiki](http://docs.comics.org/wiki/Main_Page) but they aren't
necessarily up to date.  As of May 2015 they should work.

## Workflow

Our primary collaboration space is the
[gcd-tech](http://groups.google.com/group/gcd-tech/) mailing list.
Partially due to GitHub pull requests and reviews not working well with mailing
lists, we use a Review Board installation at http://reviews.comics.org/ for
discussing code changes.

Pull requests are welcome, but you might want to poke the mailing list if
no one seems to be paying attention.

## Branches

### `master`

This is (generally) the production deployment.  For the most part, work
should not be done here directly.

Contact: [jochengcd](https://github.com/jochengcd)
via [gcd-tech](http://groups.google.com/group/gcd-tech/)

### `devel`

This is the general-purpose development branch.  It is often deployed to
[the beta site](http://beta.comics.org/), and most work should be done here.
Special-purpose development branches are based from `devel` unless otherwise
noted.

Contact: [jochengcd](https://github.com/jochengcd)
via [gcd-tech](http://groups.google.com/group/gcd-tech/)

### `mycomics`

The `mycomics` branch is where the forthcoming http://my.comics.org/
collection management site is being added to the system.  It is sometimes
deployed to [the beta site](http://beta.comics.org/)

`mycomics` predates regular use of the `devel` branch so it is based off of
`master`, which is merged to `mycomics` periodically.

Contact: [wkarpeta](https://github.com/wkarpeta)
via [gcd-tech](http://groups.google.com/group/gcd-tech/)

### `django18`

This branch is for work to migrate the system from Django 1.4 to 1.8, in
several stages.  While this is moving from one LTS release of Django to the
next, it is our intention to keep up with each Django major release as much
as possible going forwards.  This will `merge` to devel once we are caught up.
Hopefully before Django 1.9 comes out.

There will probably be some modernization and code clean-up along the way.

Contact: [handrews](https://github.com/handrews)
via [gcd-tech](http://groups.google.com/group/gcd-tech/)

### Future branch `rest`

This will be for developing the REST API, after the project has been moved
to the current version of Django (1.8 at the time of this writing).
This will likely also involve some code clean-up to move the web UI onto
the REST API.  It is not yet determined how often this branch will merge
to `devel`.

Contact: [handrews](https://github.com/handrews)
via [gcd-tech](http://groups.google.com/group/gcd-tech/)

### Closed branches
The `newsearch` branch is dead- it was used to add Elasticsearch to the system.

## History of the Code

This version of the GCD web application was initially written in Python using
Django 0.96, and rushed into deployment in late 2009 when the prior system's
host crashed after many years of service.  Due to both of these facts, there
remain some oddities and things that you would not see in a modern Django system.

The current production code runs on Django 1.4, although there is a project
underway to bring it up to Django 1.8, which will likely involve a fair amount
of modernization and cleanup of the code.

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
