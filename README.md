This bot adds initial information at the start of year for Wikimedia Sverige. It adds projects and year pages to our wiki (https://se.wikimedia.org) and to the Mediawiki Phabricator (https://phabricator.wikimedia.org). It runs with Python 3.8 or later.

# Installation
Install required libraries with pip:

`$ pip install -r requirements.txt`

# Configuration
A configuration file, `config.yaml` by default, is needed to run. `config.yaml.sample` has comments documenting the various parameters and can be used as a template.

Configure Pywikibot, following the instructions on https://www.mediawiki.org/wiki/Manual:Pywikibot/user-config.py.

To edit Phabricator, a Conduit API token is required. This can be generated in the user settings: `Settings` -> `Conduit API Tokens`.

# Input Data
## Files
Two files are required to run the bot: one containing project information and one containing goal information. Both of these should be in tab separated values. The assumed structure of the input is quite strict and is based off of two spreadsheets for [projects](https://docs.google.com/spreadsheets/d/1iuhi661upWWRVCUhdLW6GZnnP8_B5v5Y6sdNEFlq2UU/edit?usp=sharing) and [project goals](https://docs.google.com/spreadsheets/d/1j7u3623U2gtmXYVUJBuHKdXg_GJWBhHbT5ayxOeN3RY/edit?usp=sharing). Some variables, such as what columns contains what data, can be changed in the config, but bigger changes would require adapting the code. Note that some relevant information is in hidden columns.

## Wiki Pages
Information about programs, strategies and goals are fetched from a table on a wikipage, such as [this one from 2019](https://se.wikimedia.org/w/index.php?title=Verksamhetsplan_2019/Tabell_%C3%B6ver_program,_strategi_och_m%C3%A5l&oldid=75471). The code for this is specific for this particular table and would need to be adapted if the same information is represented in another way. Note that some information is stored in HTML comments.

# Running
The bot is run with the command

    $ ./project_start.py project-file goal-file

For flags, see command line help (`$ ./project_start.py --help`).

## Logging
The most important log messages are written to standard out. If you want more detailed logging, see the log file *project-start.log*.
