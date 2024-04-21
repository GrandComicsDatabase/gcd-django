# Getting Started on macOS or Linux

This is the implementation of the Grand Comics Database in Python
using the Django framework.

For basic information, see the [README file](../README.md) in the project's root directory.

This documentation is always somewhat outdated, in particular in view of 
version numbers. See aso the Docker setup.

After following the steps here go to [Getting Started file](Getting_Started.md) for information on
how to setup the environment using a dump from GCD project.

This file explains the specifics of setting up a development environment
on MacOS X or Linux.  Note that your Linux distribution's package management
system may be able to handle much of the installation work for you.

This file assumes that you're cloning the "master" branch from github.
If you want to run the current production branch, please inquire
as to which branch is current at http://groups.google.com/group/gcd-tech/

# Python

To run you'll need Python.  We are currently using Python 3.

# Git and GitHub

* Install git, which may be found through http://github.com/

* Clone the repository.  The GitHub web page is:
https://github.com/GrandComicsDatabase/gcd-django
See the GitHub help documentation for options, and contact the gcd-tech
mailing list if you need assistance.

# Applications and non-Python libraries

## MySQL

Install MySQL, we are currently using 5.7.  

Put the following lines in your `/etc/my.cnf`
```
default-character-set = utf8
default-storage-engine = InnoDB
```
These settings will save you from accidentally not using foreign keys or
transactions, or from trying to stuff unicode into an 8-bit character set.
None of those are fun to debug or recover from.

Note that these options are not needed for mysql 8 (>=8.0.1), there these 
are the defaults and default-character-set is replaced character_set_server
anyway.

Note that MySQL may not create an `/etc/my.cnf` during installation
(for instance on Mac OS X Mountain Lion).  Just create one yourself with these
two lines in it.

If installing using Linux packages of some sort and also using pip/virtualenv
for Python libraries as described below, you will also need the devel-packages, 
e.g.
- RPM: `mysqlclient-devel`
- Debian package: `libmysqlclient-dev`

## ICU library

Install the ICU library, which is C/C++ and may require compilation.
You will need this before you install the Python modules, as one of them
depends on it.  This is specifically icu4c, not the Java icu4j.

libicu builds fine on Mac OS X, and pre-built packages should exist for most
linux distributions:

http://site.icu-project.org/
- RPM: `libicu`
- Debian package: `libicu48`

If using pip/virtualenv to build Python libraries, you will also need
the icu-devel RPM or the libicu48-dev Debian package (libicu-dev on newest
Ubuntu).

If you do compile libicu yourself, the instructions on their readme.html
are absurdly complex.  Just do this (which worked on Mac OS X Snow Leopard):

```
bash:~$ tar xzvf icu-whatever.tgz # version 49 at the time of writing
bash:~$ cd icu/source
bash:~/icu/source$ ./configure
bash:~/icu/source$ gnumake
bash:~/icu/source$ sudo gnumake install
```

## Image libraries for Pillow

For the image library python-pillow some libraries can be installed.
Needed are libjpeg-dev and zlib by default.

You will need some additional libraries for Pillow to be able to support some
of the other common image formats.  If you are not doing any image editing, 
this is not required.

See
https://pillow.readthedocs.io/en/stable/installation.html#external-libraries
for further information.

TODO: Document specifics.

## CSSTidy

Install CSSTidy, which should exist as a package for most Linux distributions
(and possibly for MacPorts as well):
http://csstidy.sourceforge.net/
- RPM: csstidy
- Debian package: csstidy

# Python and bootstrapping the library install.

## Python

Install Python if it did not come with your system.  Python 3 is recommended.
http://www.python.org/downloads/

If installing from packages you'll also need development package for python
(if it's separated, like python-dev on Ubuntu).

## virtualenv

We recommend using virtualenv.  It will you to isolate the libraries you 
need for the GCD, and not contaminate your system python.

Install the package `python-virtualenv`.

Create a virtualenv for use with the GCD.  For this example, we will
create one called "gcd" in a directory called "virtualenvs".  

```
bash:~$ mkdir virtualenvs
bash:~$ cd virtualenvs
bash:~/virtualenvs$ virtualenv gcd
New python executable in gcd/bin/python
Installing setuptools............done.
Installing pip...............done.
bash:virtualenvs$ ls
gcd
bash:virtualenvs$ source gcd/bin/activate
(gcd)bash:virtualenvs$
```

Note that "(gcd)" at the beginning of the prompt.  Now all Python execution
and installation will occur inside of the "gcd" virtual env, i.e. `~/virtualenvs/gcd`.

For more on installing and using virtualenv, see
http://www.virtualenv.org/en/latest/index.html

# Python libraries

Assuming you've already activated the virtualenv (but not installed anything
further in it), and cloned the git repo to ~/git/gcd-django, use pip and
our checked-in requirements file to install all necessary Python libraries.
Make certain that you have any C/C++ libraries already compiled and installed
(such as libicu, and optionally some supplemental libraries for PIL depending
on how much of the image editing you want to be able to do).

Debian packages, RPMs and MacPorts packages are available for many of the
Python libraries, and if you prefer to use those, please remember to
make a copy of requirements.txt and remove the libraries that you
installed through other means.  If the OS packages were of older Python
library verions, you may need to add versions to your requirements.txt
or adjust the versions to match.  See the pip documentation for the
`requirements.txt` format. 

This file tries to install versions matching our production environment.
Depending on your installation, you might need more updated version.

PLEASE NOTE:  If the latest version of PyICU does not match the version of
libicu that you installed, you may need to try an older version of PyICU,
which should generally work fine with the GCD.  For instance PyICU 1.0
was known to work with libicu 4.4 as of October 2012.

```
(gcd)bash:~/git/gcd-django$ pip install -r requirements.txt
# A ton of output happens here, especially for PIL compilation.
# You can also just open up the requirements. text and install each line separately.
# It is safe to re-run pip, since if everything installed properly, it will just
# check each library and skip it as already installed.
```

This should install Django and every other python package you need to
run the site and post code reviews for the project.

# The GCD project and apps

Now go to [Getting Started file](Getting_Started.md) for information on how to setup the environment
using a dump from the GCD project.
