import logging
import re

import mwparserfromhell as mwp
from wikitables.util import ftag

from pywikibot import Page, Site

from const import Components
from template import Template


class Wiki:
    """Handles wiki interaction.

    Uses `pywikibot` to write to the wiki.

    Attributes
    ----------
    _config : dict
        Parameters read from configuration file.
    _site : Site
        `Site` object used by Pywikibot
    _dry_run : bool
        If True, no data is written to the wiki.
    _project_columns: dict
        Mapping of column headers in the projects spreadsheet to canonical
        labels
    """

    def __init__(
            self,
            config,
            project_columns,
            dry_run,
            overwrite,
            year,
            goals,
            goal_fulfillments,
            components,
            prompt_add_pages
    ):
        self._config = config
        self._project_columns = project_columns
        self._dry_run = dry_run
        self._overwrite = overwrite
        self._year = year
        self._goals = goals
        self._goal_fulfillments = goal_fulfillments
        self._components = components
        self._prompt_add_pages = prompt_add_pages
        self._site = Site()
        self._projects = {}
        self._programs = []
        self._touched_pages = []

    def add_project_page(
            self,
            parameters,
            phab_id,
            phab_name
    ):
        """Add pages for a project.

        Adds main page, subpages and categories.

        Parameters
        ----------
        parameters : dict
            Parameters for the project.
        phab_id : int
            Id for the project's Phabricator project.
        phab_name : str
            Name of the project's Phabricator project.
        """
        if (
                self._components is None
                or Components.PROJECT_MAIN_PAGE.value in self._components
        ):
            self._add_project_main_page(parameters, phab_id, phab_name)
        if self._components is not None:
            # Get the subpages from component selection.
            subpages = [
                self._config["subpages"][s - len(Components) - 1]
                for s in self._components if s > len(Components)
            ]
        else:
            subpages = self._config["subpages"]

        name = parameters[self._project_columns["swedish_name"]]
        for subpage in subpages:
            self._add_subpage(
                subpage,
                parameters,
                name
            )

        if self._goals:
            english_name = parameters[self._project_columns["english_name"]]
            self._goals[english_name]["added"] = True

        if (
                self._components is None
                or Components.CATEGORIES.value in self._components
        ):
            program = parameters[self._project_columns["program"]]
            self._add_project_categories(name, program)

    def _add_project_main_page(self, parameters, phab_id, phab_name):
        """Add the main project page, i.e. "Projekt:NAME".

        Parameters
        ----------
        parameters : dict
            Parameters for the project.
        phab_id : int
            Id for the project's Phabricator project.
        phab_name : str
            Name of the project's Phabricator project.
        """
        name = parameters[self._project_columns["swedish_name"]]
        page = Page(self._site, name, self._config["project_namespace"])
        if page.exists() and not self._overwrite:
            logging.warning(
                "Project page '{}' already exists. It will not be created.".format(page.title())  # noqa: E501
            )
            return

        template = Template(self._config["project_template"], True)
        project_parameters = self._config["project_parameters"].items()
        for template_parameter, value in project_parameters:
            # label = value.get("column")
            template.add_parameter(
                template_parameter,
                self._get_parameter_value(parameters, value)
                # parameters[self._project_columns[label]]
            )
        template.add_parameter("year", self._year)
        template.add_parameter("phabricatorId", phab_id)
        template.add_parameter("phabricatorName", phab_name)
        template.add_parameter("bot", "ja")
        content = "{}".format(template)
        page.text = content
        logging.info("Writing to project page '{}'".format(page.title()))
        logging.debug(page.text)
        self._write_page(page)

    def _write_page(self, page):
        """Write a page unless this is a dry run.

        Parameters
        ----------
        page : Page
            The page to write to.

        """
        if not self._dry_run:
            page.save(summary=self._config["edit_summary"])
        self._touched_pages.append(page)

    def _add_subpage(
            self,
            subpage,
            project_parameters,
            project_name,
    ):
        """Add a subpage under the project page.

        Parameters
        ----------
        subpage : dict
            Parameters for the page.
        project_parameters : dict
            Parameters for the project.
        project_name : str
        """

        # Always pass the year parameter.
        template_parameters = {"år": self._year}
        if "parameters" in subpage:
            # print(f"project_parameters = {project_parameters}")
            for key, value in subpage["parameters"].items():
                template_parameters[key] = self._get_parameter_value(project_parameters, value)
            #     if isinstance(value, dict):
            #         column = value.get("column")
            #         template_parameters[key] = project_parameters.get(
            #             self._project_columns.get(column)
            #         )
            #     else:
            #         template_parameters[key] = value
            print(template_parameters)
        if "add_goals_parameters" in subpage:
            # Special case for goals parameters, as they are not
            # just copied.
            if not self._goals:
                title = subpage["title"]
                logging.warning(
                    f"Goals need to be supplied for page '{title}', "
                    "it will not be added."
                )
                return

            template_key = \
                list(subpage["add_goals_parameters"].keys())[0]
            template_value = self._make_year_title(
                subpage["add_goals_parameters"][template_key]
            )
            english_name = project_parameters[
                self._project_columns["english_name"]
            ]
            project_goals = self._goals[english_name]
            template_parameters[template_key] = \
                Template(template_value, parameters=project_goals)
            template_parameters["måluppfyllnad"] = \
                self._create_goal_fulfillment_text(project_goals)
        full_title = "{}/{}".format(project_name, subpage["title"])
        self._add_page_from_template(
            self._config["project_namespace"],
            full_title,
            subpage["template_name"],
            template_parameters
        )

    def _get_parameter_value(self, project_parameters, specification):
        # Just get the first key and value since there should only be
        # one.
        value_type, value = list(specification.items())[0]
        print(f"value = {value}")
        if value_type == "string":
            return value
        elif value_type == "column":
            label = self._project_columns.get(value)
            print(f"label = {label}")
            return project_parameters.get(label)

    def _add_page_from_template(
            self,
            namespace,
            title,
            template_name,
            template_parameters
    ):
        """Add a page by substituting a template.

        Parameters
        ----------
        namespace : str
            Namespace of the page. If None, the default namespace will
            be used.
        title : str
            The title of the page.
        template_name : str
            The name of the template to substitute to create the subpage.
        template_parameters : list or OrderedDict
            Parameters to pass to the template.

        """

        if namespace is None:
            page = Page(self._site, title)
        else:
            page = Page(self._site, title, namespace)
        if page.exists() and not self._overwrite:
            logging.warning(
                "Page '{}' already exists. It will not be created.".format(
                    page.title()
                )
            )
        else:
            template = Template(template_name, True, template_parameters)
            page.text = template.multiline_string()
            logging.info("Writing to page '{}'.".format(page.title()))
            logging.debug(page.text)
            self._write_page(page)

    def _create_goal_fulfillment_text(self, goals):
        """Create a string with the fulfillment texts for a set of goals.

        Parameters
        ----------
        goals : dict
            Goals to add fulfillments for.

        Returns
        -------
        str
            Contains one fulfillment text as a wikitext list.

        """

        fulfillment_text = ""
        for goal_name in goals.keys():
            fulfillment_text += "\n* {}".format(
                self._goal_fulfillments[goal_name]
            )
        return fulfillment_text

    def _add_project_categories(self, project, program):
        """Add categories to the project's category page.

        Adds the project category to categories for year and program, if
        given.

        Parameters
        ----------
        project : str
            The project name in Swedish.
        program : str
            The program category to add the project category to. If the
            empty string, no program category is added.

        """

        year_category = "Projekt {}".format(self._year)
        categories = [year_category]
        if program:
            categories.append(program)
        self._add_category_page(project, categories)

    def _add_category_page(self, title, categories):
        """Add a page with categories.

        Parameters
        ----------
        title : str
            Title of the page.
        categories : list
            The categories to add to the page.

        """

        page = Page(self._site, title, "Category")
        if page.exists() and not self._overwrite:
            logging.warning(
                "Category page '{}' already exists. It will not be created.".format(page.title())  # noqa: E501
            )
        else:
            page.text = ""
            for category in categories:
                if category != title:
                    page.text += "[[Kategori:{}]]\n".format(category)
            logging.info("Writing to category page '{}'".format(page.title()))
            logging.debug(page.text)
            self._write_page(page)

    def add_year_pages(self):
        """Add pages for a new year.

        Most pages are added from the config, but there are a few
        special cases. Categories for the year are also added.

        """

        year_pages = self._config["year_pages"]
        simple_pages = year_pages["simple"]
        for raw_title, template_name in simple_pages.items():
            title = self._make_year_title(raw_title)
            if not self._prompt_add_page(title):
                continue

            self._add_page_from_template(
                None,
                title,
                template_name,
                [self._year]
            )
        if self._prompt_add_page(year_pages["projects"]["title"]):
            self._add_projects_year_page()
        if self._prompt_add_page("categories"):
            self._add_year_categories()
        if self._prompt_add_page(year_pages["current_projects_template"]):
            self._create_current_projects_template()
        if self._prompt_add_page(year_pages["volunteer_tasks"]["title"]):
            self._add_volunteer_tasks_page()

    def _make_year_title(self, raw_string):
        """Replace the placeholder "<YEAR>" with the actual year.

        Parameters
        ----------
        title : str
            Title of the page.

        Returns
        -------
        str
            Input string with "<YEAR>" replaced with the actual year.

        """

        title = raw_string.replace("<YEAR>", str(self._year))
        return title

    def _prompt_add_page(self, title):
        """Prompt user for writing a page.

        Parameters
        ----------
        title : str
            Title of the page.

        Returns
        -------
        bool
            True if the prompt add pages command line is set or if
            the user answers "y", else False.
        """
        if not self._prompt_add_pages:
            return True

        prompt = 'Add page "{}"? (y/N)'.format(self._make_year_title(title))
        return input(prompt).lower() == "y"

    def _add_projects_year_page(self):
        """Create a page with a list of the year's projects.

        Substitutes a template, adding the project data for each project.

        """

        config = self._config["year_pages"]["projects"]
        title = self._make_year_title(config["title"])
        content = ""

        for program in self._programs:
            content += "== {} ==\n".format(program)
            for project_number, project in self._projects.items():
                if project["program"] == program:
                    content += self._make_project_data_string(project_number)
            content += "\n"

        self._add_page_from_template(
            None,
            title,
            config["template"],
            {
                "år": self._year,
                "projekt": content
            }
        )

    def _get_projects_for_strategy(self, strategy):
        """Fetch project numbers for projects in a certain strategy.

        This is determined by comparing at the strategy numbers and
        the project numbers. Projects are part of a strategy if the
        two middle digits in the project number match the first two
        digits in the strategy number. E.g. a strategy with the number
        3100 contains the project with the numbers 183102 and 193103.

        Parameters
        ----------
        strategy : str
            The strategy number.

        Yields
        ------
        str
            Project numbers of projects that are part of the given strategy.

        """

        for number in self._projects.keys():
            if number[2:4] == strategy[0:2]:
                yield number

    def _make_project_data_string(self, project):
        """Make a project data string for project year page.

        Each project adds a project data template and a comment
        containing its project number.

        Parameters
        ----------
        project : str
            The project number.

        Returns
        -------
        str
            Wikitext string containing project data template and
            project number comment.

        """

        name = self._projects[project]["sv"]
        project_template = \
            Template(":Projekt:{}/Projektdata".format(name))
        comment = Template("Utkommenterat", True, [project])
        return "{}{}\n".format(project_template, comment)

    def add_project(self, number, swedish_name, english_name, program):
        """Store project information in a map.

        Parameters
        ----------
        number : str
            Project number.
        swedish_name : str
            Swedish project name.
        english_name : str
            English project name.
        program : str
            Which program the project is under.
        """

        self._projects[number] = {
            "sv": swedish_name,
            "en": english_name,
            "program": program
        }
        if program not in self._programs:
            self._programs.append(program)

    def _add_year_categories(self):
        """Add category pages for a year.

        All category pages are added to a category for the year. Some
        are added to additional categories.

        """

        categories_config = self._config["year_pages"]["categories"]
        general = self._make_year_title(categories_config["general"])
        for page, extra_category in categories_config["pages"].items():
            title = self._make_year_title(page)
            categories = [general]
            if extra_category:
                if isinstance(extra_category, list):
                    categories += extra_category
                else:
                    categories.append(extra_category)
            self._add_category_page(title, categories)

    def _create_current_projects_template(self):
        """Create a current projects template with the new projects."""
        page_name = self._make_year_title(
            self._config["year_pages"]["current_projects_template"]
        )
        page = Page(self._site, page_name)
        if page.exists() and not self._overwrite:
            logging.warning(
                "Page '{}' already exists. It will not be created.".format(
                    page.title()
                )
            )
            return

        project_format = "[[{ns}:{{proj}}|{{proj}}]]".format(
            ns=self._config["project_namespace"])
        delimiter = "''' · '''"
        template_data = {}
        for program in self._programs:
            projects = []
            for _, project in self._projects.items():
                if project["program"] == program:
                    projects.append(project["sv"])

            template_data[program] = delimiter.join(
                [project_format.format(proj=project)
                 for project in sorted(projects)])

        template = Template("Aktuella projekt/layout")
        template.add_parameter("år", self._year)
        template.add_parameter("access", template_data["Tillgång"])
        template.add_parameter("use", template_data["Användning"])
        template.add_parameter("community", template_data["Gemenskapen"])
        template.add_parameter("enabling", template_data["Möjliggörande"])

        page.text = template.multiline_string() + \
            "\n<noinclude>{{Dokumentation}}</noinclude>"
        logging.info("Writing to page '{}'.".format(page.title()))
        logging.debug(page.text)
        self._write_page(page)

    def _add_volunteer_tasks_page(self):
        """Add a page with volunteer tasks.

        Creates a list of volunteer pages sorted by program.
        """
        config = self._config["year_pages"]["volunteer_tasks"]
        title = self._make_year_title(config["title"])
        project_list_string = ""
        for program_name in self._programs:
            project_list_string += "== {} ==\n".format(program_name)
            for _, project in self._projects.items():
                if project["program"] == program_name:
                    project_name = project["sv"]
                    project_template = "{{" + \
                        ":Projekt:{}/Frivillig".format(project_name) + "}}\n"
                    project_list_string += project_template
            comment = Template("Utkommenterat", True, ["Platshållare"])
            project_list_string += "{}&nbsp;\n\n".format(comment)

        parameters = {
            "frivilliguppdrag": project_list_string,
            "år": self._year
        }
        self._add_page_from_template(
            None,
            title,
            config["template"],
            parameters
        )

    def single_project_info(self, number, sv_name):
        """
        Output information about any manual updates which must be done.

        Parameters
        ----------
        number : int
        sv_name : str
        """
        # Pages needing to be updated if the project was not in the data files
        # at the time of the start-of-the-year run.
        pages = []
        # Pages needing to be updated if the project was in the data files but
        # set to "skip" at the time of the start-of-the-year run.
        for k, v in self._config["year_pages"].items():
            if isinstance(v, str):
                pages.append(self._make_year_title(v))
            elif v.get("title"):
                pages.append(self._make_year_title(v["title"]))
        logging.warning(
            "Don't forget to manually add '{number} - {name}' to the "
            "following pages:\n* {pages}".format(
                number=number, name=sv_name, pages='\n* '.join(pages)
            )
        )

    def log_report(self):
        """Log a list of the pages that were modified."""
        logging.info("These pages were modified:")
        for page in self._touched_pages:
            logging.info(page.title())

    def update_project_name_templates(self):
        """Update project number and name templates."""
        name_template = Page(self._site, self._config["project_name_template"])
        number_template = Page(
            self._site,
            self._config["project_number_template"]
        )
        for number, name in self._projects.items():
            english_name = name["en"]
            swedish_name = name["sv"]

            name_row = (
                f"| {number} = "
                "{{#if: {{{en|}}}"
                f"| {english_name} | {swedish_name} "
                "}}"
            )
            self._insert_row_before_default(name_template, name_row, number)

            number_row = f"| {swedish_name} = {number}"
            self._insert_row_before_default(
                number_template,
                number_row,
                number
            )

        if self._prompt_add_page(name_template.title()):
            self._write_page(name_template)
        if self._prompt_add_page(number_template.title()):
            self._write_page(number_template)

    def _insert_row_before_default(self, template, row, number):
        """Add a row to the template just above the default row.

        If the template already containins the project number or if there
        is no default, nothing is added. Missing default also outputs
        a warning since that means something is wrong in the template.

        Parameters
        ----------
        template : str
        row : str
            The row to add.
        number : str
        """
        if re.search(fr"{number}", template.text):
            logging.debug(
                "Skipping adding existing project to template"
                f" {template}: {number}."
            )
            return

        default_row_pattern = r"(\| #default.*)"
        if not re.search(default_row_pattern, template.text):
            logging.warning(f"No default row in template {template}.")
            return

        # Add the row at the bottom, before the default statement.
        template.text = re.sub(
            default_row_pattern,
            fr"{row}\n\1",
            template.text
        )

class PageMissingError(Exception):
    def __init__(self, missing_page):
        message = (f"Page '{missing_page}' doesn't exist and is "
                   "required to create this page.")
        super().__init__(message)

