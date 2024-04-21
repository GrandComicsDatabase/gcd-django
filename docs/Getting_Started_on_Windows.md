# Getting Started on Windows

This is the implementation of the Grand Comics Database in Python using the
Django framework.

For basic information, see the [README file](../README.md) in the project's root directory.

This file explains the specifics of setting up a development environment on
Windows. There are some differences between x32 and x64 installs at this
time.

# Python

You'll need Python.  We are currently using Python 3.8.
http://www.python.org/download/
python.org distribution is preferred as ActiveState Python has some purchase
'enforcing' on x64 (see Note 1). ActiveState seems OK for x32 though.

In order to use precompiled libraries with Python, you **must** get Python 3.8
as the **precompiled binaries must match the version of Python or they will not
install**.

These instructions have been tested with 64-bit Python 3.8.10 for Windows
as of February 2023.

[Direct link to 64-bit Python 3.8.10 for Windows](https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe)

After installing Python, add these directories to the front of your `PATH` to ensure
that they are found first:

```
%LOCALAPPDATA%\Programs\Python\Python38
%LOCALAPPDATA%\Programs\Python\Python38\Scripts
```

# Git and GitHub

* Install git, which may be found through http://github.com/

* Clone the repository.  The GitHub web page is:
https://github.com/GrandComicsDatabase/gcd-django
See the GitHub help documentation for options, and contact the gcd-tech
mailing list if you need assistance.

# Applications and non-Python libraries

## MySQL

Install MySQL (version 5.5.x is currently in production)
http://dev.mysql.com/downloads/

Put the following lines in your configuration (my.cnf) if not already there,
these are nowadays the default on Windows installations.

```
default-character-set = utf8
default-storage-engine = InnoDB
```

These settings will save you from accidentally not using foreign keys or
transactions, or from trying to stuff unicode into an 8-bit character set.
None of those are fun to debug or recover from.

It can be useful to install the GUI MySQL Workbench.

## CSSTidy

CSSTidy is an executable required by django-compressor. If DEBUG=True, the
default setting, django-compressor is not active, therefore CSSTidy is not
needed if you are only working with DEBUG=True.

http://csstidy.sourceforge.net/

It just needs to be somewhere in the PATH. Using 32bit executable for 64bit
seems fine.

# Python and bootstrapping the library install.

## EASY-INSTALL

Get it from http://pypi.python.org/pypi/setuptools#windows

32-bit version of Python
    Install setuptools using the provided .exe installer.

64-bit versions of Python: download ez_setup.py and run it; it will download
the appropriate .egg file and install it for you.
Currently, the provided .exe installer does not support 64-bit versions of
Python for Windows, due to a distutils installer compatibility issue

## Virtualenv / Pip

We recommend using virtualenv, but it is optional.  It will allow you to isolate
the libraries you need for the GCD, and not contaminate your system python.

For more on installing and using virtualenv, see
http://www.virtualenv.org/en/latest/index.html

The recommended way to use pip is within virtualenv, since every virtualenv
has pip installed in it automatically. So do
`easy_install.exe virtualenv`

If you do not want to use virtualenv install pip using
`easy_install.exe pip`.

Use pip to install virtualenv, and then create a virtualenv for use with the
GCD.  For this example, we will create one called "gcd" in a directory called
"virtualenvs".

Now create a virtualenv
```
virtualenv.exe \path\to\env\gcd
```
and activate the virtualenv
```
\path\to\env\gcd\Scripts\activate
```

Note that "(gcd)" at the beginning of the prompt.  Now all Python execution
and installation will occur inside of the "gcd" virtual env, i.e.
\path\to\env\gcd\.

# Python libraries

Inside the git-shell installed by github do
`\path\to\env\gcd\Scripts\activate`
Or make sure git is in your path if using a different shell and activate
the virtualenv. We assume nothing is installed in it.

Now go the the directory with the cloned git repo "gcd-django".

We use pip and our checked-in `requirements.txt` file to install all necessary Python
packages. You either downloaded the pre-compiled packages or compile them yourself.
Compiling them yourself is an advanced topic and not necessary; it is recommended
that you simply use the precompiled versions available.

You could also just run pip without the virtualenv to install everything into
your system python's site-packages tree, but we recommend to use virtualenv.

## Packages Requiring Compilation

Two of the python packages need compiling. This typically additional installs
and on x64 does not work out of the box. The easy way is to use the
[Unofficial Windows Binaries for Python Extension Packages](http://www.lfd.uci.edu/~gohlke/pythonlibs).

That page contains "wheel" packages for various Python libraries that require compilation.
A wheel package can be installed into your virtual environment using `pip`:
```
C:> \path\to\env\gcd\Scripts\activate
(gcd) C:\path\to\env\gcd> pip install package.whl
```

You must obtain a wheel package that is compiled for the specific version of Python
installed on your system.  As directed above this is "C Python 3.8" so choose the wheel
packages with `cp38` in their name as given below.

### Pillow

Download the Pillow wheel package [Pillow-8.4.0-cp38-cp38-win_amd64](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pillow).
Install the wheel package with `pip`.

### PyICU

Download the PyICU wheel package [PyICU-2.4.3-cp38-cp38-win_amd64](http://www.lfd.uci.edu/~gohlke/pythonlibs/#pyicu).
Install the wheel package with `pip`.

## Installing Remaining Packages

Now that you've satisifed the requirements for the two packages that require compilation,
you can install the remaining packages from the requirements file:

```
pip install -r requirements.txt
# You can also just open up the requirements.txt and install each line separately.
# It is safe to re-run pip, since if everything installed properly, it will just
# check each library and skip it as already installed.
```

This should install Django and every other python package you need to
run the site and post code reviews for the project.

# The GCD project and apps

Now go to the generic [Getting Started](Getting_Started.md) instructions for information on
how to setup the environment using a dump from the GCD project.

# Additional Notes

## Note 1 ActivePython

Ex:
pypm install setuptools
The following packages will be installed into "%APPDATA%Python" (2.7):
 distribute-0.6.27
error: Can't install distribute-0.6.27: requires Business Edition subscription
*** If you have purchased ActivePython Business Edition, please login to
*** your account at:
***   https://account.activestate.com/
*** and download and run the license installer for your platform.
***
*** Please visit  to learn more
*** about the ActivePython Business Edition offering.

## Note 2 CSStidy

One needs to install scons 1.3.1 (later versions didn't work for me)
http://www.scons.org/
Download zip, run setup.py install.
Download CSStidy source distribution from:
http://csstidy.sourceforge.net/
VC9 won't build it properly
Fix is not too difficult though.
Solution comes from:
http://stackoverflow.com/questions/3075697/non-existent-member-function-specified-as-friend
Edit umap.hpp
Move class iterator definition block toward the first line of public: (of class umap)
s