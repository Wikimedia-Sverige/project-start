#! /usr/bin/env python3

import argparse
import csv
import datetime
import logging
from collections import OrderedDict

import yaml

from phab import Phab
from wiki import Wiki


def setup_logging(verbose):
    """Add logging handlers.

    Parameters
    ----------
    verbose : bool
        If True, standard out handler will print every message.
    """
    format_ = "%(asctime)s[%(levelname)s](%(module)s): %(message)s"
    logging.basicConfig(
        level=logging.DEBUG,
        format=format_,
        filename="project-start.log"
    )
    if verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(
        logging.Formatter(format_)
    )
    logging.getLogger().addHandler(stream_handler)


def read_goals(tsv):
    """Read goal values from tab separated data.

    Parameters
    ----------
    tsv : iterator
        Gives one list per row from tab separated data.

    Returns
    -------
    dict
        Map of project names to dicts that maps goal name to planned
        value.
    dict
        Map of goal names to goal fulfillment texts.
    """
    goals = OrderedDict()
    fulfillments = {}
    for i, row in enumerate(tsv):
        if i == config["goals"]["last_row"]:
            # Stop reading when we all projects have been read.
            break
        elif row[0] == "":
            # Skip rows that have nothing in the first field; they
            # will not contain any goal numbers.
            continue
        description = row[0]
        name = get_goal_name(description)
        fulfillment = row[1]
        if fulfillment:
            fulfillments[name] = fulfillment
        for j, field in enumerate(row):
            if j >= config["goals"]["first_project_column"]:
                if i == config["goals"]["project_row"]:
                    # Add keys for all of the projects. Since we
                    # use an ordered dictionary, this allows us to
                    # find the correct project when we add goal
                    # values.
                    project = field
                    if project == "":
                        # Temporarily add empty columns to maintain
                        # the indices.
                        goals[j] = None
                    else:
                        # Use ordered dictionary here to keep the
                        # order of the goals when they are added to
                        # the template.
                        goals[project] = OrderedDict()
                elif i > config["goals"]["project_row"]:
                    planned_value = field
                    project_index = j - config["goals"]["first_project_column"]
                    project_name = list(goals.keys())[project_index]
                    if planned_value:
                        goals[project_name][name] = planned_value
    # Remove any empty columns.
    goals = {k: v for k, v in goals.items() if v}
    # Make it a normal dictionary, since we don't need to keep track
    # of project indices anymore.
    return dict(goals), fulfillments


def get_goal_name(description):
    """Get goal name from description.

    Parameters
    ----------
    description : string
        Goal description in the format "T.1.1 - Berika projekten med
        25 nya resurser".

    Returns
    -------
    str
        Goal name in the format "T.1.1".
    """
    return description.split(" - ")[0]


def add_wiki_project_pages(project_information, project_columns,
                           phab_id, phab_name):
    """Add a project page to the wiki.

    Also adds relevant subpages.

    Parameters
    ----------
    project_information : dict
    project_columns: dict
    phab_id : int
        Id of the project on Phabricator.
    phab_name : str
        Name of the project on Phabricator
    """
    logging.info("Adding wiki pages.")
    english_name = project_information[project_columns["english_name"]]
    wiki.add_project_page(
        phab_id,
        phab_name,
        project_information,
        goals[english_name],
        goal_fulfillments
    )
    name = project_information[project_columns["swedish_name"]]
    area = project_information[project_columns["area"]]
    wiki.add_project_categories(name, area)


def add_phab_project(project_information, project_columns):
    """Add a project on Phabricator.

    Parameters
    ----------
    project_information : dict
    project_columns: dict
    """
    logging.info("Adding Phabricator project.")
    name = project_information[project_columns["english_name"]]
    description = project_information[project_columns["about_english"]]
    return phab.add_project(name, description)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--year",
        "-y",
        help="Year for the projects created. If not given, the current year will be used."  # noqa: E501
    )
    parser.add_argument(
        "--dry-run",
        "-d",
        help="Don't write anything to the target platforms.",
        action="store_true"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        help="Print all logging messages.",
        action="store_true"
    )
    parser.add_argument(
        "--overwrite-wiki",
        "-w",
        help="Write to wiki even if pages exist.",
        action="store_true"
    )
    parser.add_argument(
        "--config",
        "-c",
        help="Config file.",
        default="config.yaml"
    )
    parser.add_argument(
        "project_file",
        help="Path to a file containing project information. The data should be tab separated values.",  # noqa: E501
        nargs=1
    )
    parser.add_argument(
        "goal_file",
        help="Path to a file containing information about project goals. The data should be tab separated values.",  # noqa: E501
        nargs=1
    )
    args = parser.parse_args()
    setup_logging(args.verbose)
    logging.info("Creating projects.")
    config_path = args.config
    with open(config_path) as config_file:
        config = yaml.safe_load(config_file)
    logging.info("Loaded config from '{}'".format(config_path))
    with open(args.goal_file[0]) as file_:
        goals_reader = csv.reader(file_, delimiter="\t")
        goals, goal_fulfillments = read_goals(goals_reader)
    if args.year:
        year = args.year
    else:
        year = datetime.date.today().year
    project_columns = config["project_columns"]
    wiki = Wiki(config["wiki"], project_columns, args.dry_run,
                args.overwrite_wiki, year)
    phab = Phab(config["phab"], args.dry_run)
    with open(args.project_file[0]) as file_:
        projects_reader = csv.DictReader(file_, delimiter="\t")
        for project_information in projects_reader:
            if project_information[project_columns["skip"]]:
                logging.info(
                    "Skipping '{}', marked as inactive.".format(
                        project_information[project_columns["english_name"]]))
                continue
            superproject = project_information[
                project_columns["super_project"]]
            project_name = project_information[
                project_columns["english_name"]]
            if superproject:
                # Don't add anything for subprojects.
                continue
            if project_name not in goals:
                logging.warn(
                    "Project name '{}' found in projects file, but not in goals file. It will not be created.".format(project_name)  # noqa: E501
                )
                continue
            logging.info(
                "Processing project '{}'.".format(
                    project_information[project_columns["swedish_name"]]
                )
            )
            phab_id, phab_name = add_phab_project(project_information,
                                                  project_columns)
            add_wiki_project_pages(project_information, project_columns,
                                   phab_id, phab_name)
            goals[project_name]["added"] = True
            wiki.add_project(
                project_information[project_columns["project_id"]],
                project_information[project_columns["swedish_name"]]
            )
    wiki.parse_programs()
    for project, parameters in goals.items():
        if "added" not in parameters:
            logging.warn(
                "Project name '{}' found in goals file, but not in projects file. It will not be created.".format(project)  # noqa: E501
            )
    wiki.add_year_pages()
