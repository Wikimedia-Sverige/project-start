#! /usr/bin/env python3

import argparse
import csv
import datetime
import logging
from collections import OrderedDict

import yaml

from const import Components
from phab import Phab
from wiki import Wiki


def setup_logging(verbose):
    """Add logging handlers.

    Parameters
    ----------
    verbose : bool
        If True, standard out handler will print every message.
    """
    format_ = "%(asctime)s [%(levelname)s] (%(module)s): %(message)s"
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


def pick_components():
    """Let the user select what components to add.

    Shows a menu with a number for each component. Components are
    main wiki page, Phabricator project, project categories and
    subpages on wiki. Selection is made by entering space
    delimited numbers.

    Returns
    -------
    list
        Seleced numbers.
    """
    error = False
    # These need to match the values in const.Components, starting at
    # 1.
    options = [
        "Project main page",
        "Phabricator project",
        "Categories"
    ]
    subpages = config["wiki"]["subpages"]
    options += [s["title"] for s in subpages]
    for i, option in enumerate(options, start=1):
        print("{}: {}".format(i, option))

    selection_string = input(
        "Select components by entering their numbers, delimited by space:\n"
    )
    if selection_string == "":
        return []

    try:
        selection = [int(i) for i in selection_string.split(" ")]

        for s in selection:
            if s < 1 or s > len(options) + 1:
                error = True
                break
    except ValueError:
        error = True

    if error:
        print("Invalid selection")
        return pick_components()

    return selection


def read_goals(tsv, settings):
    """Read goal values from tab separated data.

    Parameters
    ----------
    tsv : iterator
        Gives one list per row from tab separated data.
    settings: dict
        Goals settings from the config

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
    for i, unsanitized_row in enumerate(tsv):
        row = sanitize(unsanitized_row)
        if i == settings["last_row"]:
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
        # Convert alphabetic label of column to numeric one where A = 0
        first_project_column = ord(settings["first_project_column"]) - 65
        for j, field in enumerate(row):
            if j >= first_project_column:
                if i == settings["project_row"]:
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
                elif i > settings["project_row"]:
                    planned_value = field
                    project_index = j - first_project_column
                    project_name = list(goals.keys())[project_index]
                    if planned_value:
                        goals[project_name][name] = planned_value
    # Remove any empty columns.
    goals = {k: v for k, v in goals.items() if v}
    # Make it a normal dictionary, since we don't need to keep track
    # of project indices anymore.
    return dict(goals), fulfillments


def sanitize(unsanitized):
    """Sanitize a dict or list containing strings.

    Parameters
    ----------
    unsanitized : iterator
        Dictionary or list to sanitize

    Returns
    -------
    iterator
        Copy of input with sanitized strings
    """
    sanitized = None
    if isinstance(unsanitized, dict):
        sanitized = {
            sanitize_string(k): sanitize_string(v) for
            k, v in unsanitized.items()
        }
    elif isinstance(unsanitized, list):
        sanitized = [sanitize_string(i) for i in unsanitized]
    return sanitized


def sanitize_string(unsanitized_string):
    """Sanitize a strings.

    * Strips leading and trailing whitespaces

    Parameters
    ----------
    unsanitized_string : string
        String to sanitize

    Returns
    -------
    string
        Sanitized string
    """
    sanitized_sring = unsanitized_string.strip()
    return sanitized_sring


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


def is_active(project_information, project_columns):
    return project_information.get(project_columns.get("active")) == "1"


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
    wiki.add_project_page(
        project_information,
        phab_id,
        phab_name
    )


def add_phab_project(project_information, project_columns):
    """Add a project on Phabricator.

    Parameters
    ----------
    project_information : dict
    project_columns: dict
    """
    logging.info("Adding Phabricator project.")
    name_en = project_information[project_columns["english_name"]]
    name_sv = project_information[project_columns["swedish_name"]]
    description = project_information[project_columns["about_english"]]
    return phab.add_project(name_en, name_sv, description)


def process_project(project_information, project_columns):
    """Process a single project.

    Parameters
    ----------
    project_information : dict
    project_columns : dict
    """
    superproject = project_information[project_columns["super_project"]]
    project_name = project_information[project_columns["english_name"]]
    if superproject:
        # Don't add anything for subprojects.
        return
    if goals and project_name not in goals:
        logging.warning(
            "Project name '{}' found in projects file, but not in goals file. "
            "It will not be created. If you tried to add components that "
            "don't require goal information, run without the goal "
            "file.".format(project_name)
        )
        return
    logging.info(
        "Processing project '{}'.".format(
            project_information[project_columns["swedish_name"]]
        )
    )
    if components is None or Components.PHABRICATOR.value in components:
        phab_id, phab_name = add_phab_project(
            project_information,
            project_columns
        )
    else:
        phab_id = phab_name = ""
    add_wiki_project_pages(project_information, project_columns,
                           phab_id, phab_name)
    if goals:
        goals[project_name]["added"] = True
    wiki.add_project(
        project_information[project_columns["project_number"]],
        project_information[project_columns["swedish_name"]],
        project_information[project_columns["english_name"]],
        project_information[project_columns["program"]]
    )


def load_args():
    """Load and process command line arguments.

    Returns
    -------
    argparse.ArgumentParser
        All encountered arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--year",
        "-y",
        help=("Year for the projects created. "
              "If not given, the current year will be used.")
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
        "--project",
        "-p",
        help=("Single project (English or Swedish name) to create. "
              "If not given, all projects will be processed.")
    )
    parser.add_argument(
        "--components",
        "-o",
        action="store_true",
        help=("Shows a menu to select components for each "
              "project. Enter the corresponding numbers delimited by space.")
    )
    parser.add_argument(
        "--prompt-add-pages",
        "-r",
        action="store_true",
        help="Prompt before adding each general (non-project specific) page."
    )
    parser.add_argument(
        "project_file",
        help=("Path to a file containing project information. "
              "The data should be tab separated values."),
        nargs=1
    )
    parser.add_argument(
        "goal_file",
        help=("Path to a file containing information about project goals. "
              "The data should be tab separated values. This parameter is "
              "only needed if a subpage has the `add_goals_parameters` set "
              "in the config."),
        nargs="?"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = load_args()
    setup_logging(args.verbose)
    logging.info("Creating projects.")
    config_path = args.config
    with open(config_path) as config_file:
        config = yaml.safe_load(config_file)
    logging.debug("Loaded config from '{}'".format(config_path))

    if args.components:
        components = pick_components()
    else:
        components = None

    if args.goal_file:
        with open(args.goal_file, newline="") as file_:
            goals_reader = csv.reader(file_, delimiter="\t")
            goals, goal_fulfillments = read_goals(
                goals_reader,
                config["goals"]
            )
    else:
        goals = goal_fulfillments = None

    if args.year:
        year = args.year
    else:
        year = datetime.date.today().year
    project_columns = config["project_columns"]
    wiki = Wiki(
        config["wiki"],
        project_columns,
        args.dry_run,
        args.overwrite_wiki,
        year,
        goals,
        goal_fulfillments,
        components,
        args.prompt_add_pages
    )
    phab = Phab(config, args.dry_run)

    with open(args.project_file[0], newline="") as file_:
        projects_reader = csv.DictReader(file_, delimiter="\t")
        single_project_found = False
        for unsanitized_project_information in projects_reader:
            project_information = sanitize(unsanitized_project_information)
            if not project_information[project_columns["swedish_name"]]:
                # Check if there is a name and skip if not. This is
                # likely a row that has some text, but not actually
                # project information.
                continue

            if args.project:
                if args.project not in (
                        project_information[project_columns["swedish_name"]],
                        project_information[project_columns["english_name"]]):
                    continue
                else:
                    single_project_found = True
                    wiki.single_project_info(
                        project_information[project_columns["project_number"]],
                        project_information[project_columns["swedish_name"]]
                    )
            elif not is_active(project_information, project_columns):
                # handle skip outside of process_project to allow specifying a
                # single project to override the skip value.
                logging.info(
                    "Skipping '{}', marked as inactive.".format(
                        project_information[
                            project_columns["english_name"]]))
                continue
            process_project(project_information, project_columns)

    if not args.project:
        # don't create these pages or run the checks unless it's a full run
        if goals:
            for project, parameters in goals.items():
                if "added" not in parameters:
                    logging.warning(
                        "Project name '{}' found in goals file, but "
                        "not in projects file. It will not be "
                        "created.".format(project)
                    )
        wiki.add_year_pages()
    elif not single_project_found:
        logging.warning(
            "Project name '{}' could not be found in projects file. "
            "It will not be created.".format(args.project)
        )

    wiki.update_project_name_templates()
    wiki.log_report()
