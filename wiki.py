import logging
import re

import mwparserfromhell as mwp
from wikitables.util import ftag

from pywikibot import Page, Site

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

    def __init__(self, config, project_columns, dry_run, overwrite, year):
        self._site = Site()
        self._config = config
        self._project_columns = project_columns
        self._dry_run = dry_run
        self._overwrite = overwrite
        self._year = year
        self._projects = {}
        self._programs = []
        self._external_projects = []

    def add_project_page(
            self,
            phab_id,
            phab_name,
            parameters,
            goals,
            goal_fulfillments
    ):
        """Add the main project page.

        Parameters
        ----------
        name : str
            The project name in Swedish. This will be used as title
            for the page.
        description : str
            Passed to template as parameter "beskrivning".
        partners : str
            Passed to template as parameter "samarbetspartners".

        """
        name = parameters[self._project_columns["swedish_name"]]
        page = Page(self._site, name, self._config["project_namespace"])
        if page.exists() and not self._overwrite:
            logging.warning(
                "Project page '{}' already exists. It will not be created.".format(page.title())  # noqa: E501
            )
        else:
            template = Template(self._config["project_template"], True)
            project_parameters = self._config["project_parameters"].items()
            for template_parameter, label in project_parameters:
                template.add_parameter(
                    template_parameter,
                    parameters[self._project_columns[label]])
            template.add_parameter("year", self._year)
            template.add_parameter("phabricatorId", phab_id)
            template.add_parameter("phabricatorName", phab_name)
            content = "{}".format(template)
            page.text = content
            logging.info("Writing to project page '{}'".format(page.title()))
            logging.debug(page.text)
            if not self._dry_run:
                page.save()
        for subpage in self._config["subpages"]:
            subpage_parameters = {}
            if "parameters" in subpage:
                for key, label in subpage["parameters"].items():
                    subpage_parameters[key] = parameters[
                        self._project_columns[label]]
            if "add_goals_parameters" in subpage:
                # Special case for goals parameters, as they are not
                # just copied.
                template_key = \
                    list(subpage["add_goals_parameters"].keys())[0]
                template_value = \
                    subpage["add_goals_parameters"][template_key]
                subpage_parameters[template_key] = \
                    Template(template_value, parameters=goals)
                subpage_parameters["måluppfyllnad"] = \
                    self._create_goal_fulfillment_text(
                        goals.keys(),
                        goal_fulfillments
                    )  # noqa:E123
            self._add_subpage(
                name,
                subpage["title"],
                subpage["template_name"],
                subpage_parameters
            )

    def _add_subpage(
            self,
            project,
            title,
            template_name,
            template_parameters=None
    ):
        """Add a subpage under the project page.

        Parameters
        ----------
        project : str
            The project name in Swedish.
        title : str
            The title of the subpage. Only the prefix, i.e. the
            substring after the last slash. This will be prepended by
            the project name to create the complete subpage title.
        template_name : str
            The name of the template to substitute to create the subpage.
        template_parameters : dict
            The parameters to pass to the template.

        """

        full_title = "{}/{}".format(project, title)
        self._add_page_from_template(
            self._config["project_namespace"],
            full_title,
            template_name,
            template_parameters
        )

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
            if not self._dry_run:
                page.save()

    def _create_goal_fulfillment_text(self, goals, fulfillments):
        """Create a string with the fulfillment texts for a set of goals.

        Parameters
        ----------
        goals : list
            Goal names for which to add fulfillments.
        fulfillments : dict
            Map of goal names and fulfillment texts.

        Returns
        -------
        str
            Contains one fulfillment text as a wikitext list.

        """

        fulfillment_text = ""
        for goal in goals:
            fulfillment_text += "\n* {}".format(fulfillments[goal])
        return fulfillment_text

    def add_project_categories(self, project, area):
        """Add categories to the project's category page.

        Adds the project category to categories for year and area, if
        given.

        Parameters
        ----------
        project : str
            The project name in Swedish.
        area : str
            The area category to add the project category to. If the
            empty string, no area category is added.

        """

        year_category = "Projekt {}".format(self._year)
        categories = [year_category]
        if area:
            categories.append(area)
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
            if not self._dry_run:
                page.save()

    def add_year_pages(self):
        """Add pages for a new year.

        Most pages are added from the config, but there are a few
        special cases. Categories for the year are also added.

        """

        simple_pages = self._config["year_pages"]["simple"]
        for raw_title, template_name in simple_pages.items():
            title = self._make_year_title(raw_title)
            self._add_page_from_template(
                None,
                title,
                template_name,
                [self._year]
            )
        self._add_projects_year_page()
        self._add_program_overview_year_page()
        self._add_year_categories()

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

    def _add_projects_year_page(self):
        """Create a page with a list of the year's projects.

        Substitutes a template, adding the project data for each project.

        """

        config = self._config["year_pages"]["projects"]
        content = ""
        content += "== {} {} ==\n".format(
            config["external"]["number"],
            config["external"]["name"]
        )
        for project in self._external_projects:
            content += self._make_project_data_string(project)
        for program in self._programs:
            content += "== {} {} ==\n".format(
                program["number"],
                program["name"]
            )
            for strategy in program["strategies"]:
                content += "=== {} {} ===\n".format(
                    strategy["number"],
                    strategy["short_description"]
                )
                for project in strategy["projects"]:
                    content += self._make_project_data_string(project)
        page = self._config["year_pages"]["projects"]
        title = self._make_year_title(page["title"])
        self._add_page_from_template(
            None,
            title,
            page["template"],
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

        for number, name in self._projects.items():
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

        name = self._projects[project]
        project_template = \
            Template(":Projekt:{}/Projektdata".format(name))
        comment = Template("Utkommenterat", True, [project])
        return "{}{}\n".format(project_template, comment)

    def add_project(self, number, name):
        """Store project number and name in a map.

        Parameters
        ----------
        number : str
            Project number.
        name : str
            Project name.

        """

        self._projects[number] = name

    def parse_programs(self):
        """Parse table with descriptions for program, strategies and names.

        Assumes a wikipage with a table formatted in a particular way,
        with cells spanning mutiple rows and HTML comments containing
        some of the information. An instance of such a table can be
        found on:
        https://se.wikimedia.org/w/index.php?title=Verksamhetsplan_2019/Tabell_%C3%B6ver_program,_strategi_och_m%C3%A5l&oldid=75471.

        """

        operational_plan_page = Page(
            self._site,
            self._make_year_title(
                self._config["year_pages"]["operational_plan"])
        )
        # Get table string. This assumes that it is the first table on
        # the page.
        table_string = str(mwp.parse(
            operational_plan_page.text
        ).filter_tags(matches=ftag('table'))[0])
        # Remove ref tags and links.
        table_string = re.sub(
            r"(<ref.*?>.*?</ref>|\[\[.*?\||\]\])",
            "",
            table_string,
            flags=re.S
        )
        self._external_projects = list(self._projects.keys())
        # Split table on rows.
        rows = table_string.split("|-")
        for row in rows[1:]:
            # Skip first rows; we don't need the headers.
            if not row.rstrip("|}").strip():
                # This is just the end table row, skip it.
                continue
            # Split rows on pipes and remove formatting.
            cells = list(filter(None, map(
                lambda c: c.split("|")[-1].strip(),
                re.split(r"[\|\n]\|", row)
            )))
            if len(cells) == 3:
                # Row includes program.
                program_name, program_number = \
                    re.match(r"(.*)\s+<!--\s*(.*)\s*-->", cells[0]).groups()
                self._programs.append({
                    "number": program_number,
                    "name": program_name,
                    "strategies": []
                })
            if len(cells) >= 2:
                # Row includes strategy, which is always in the cell
                # second from the right.
                strategy, strategy_number, strategy_short = \
                    re.match(
                        r"(.*)\s*<!--\s*(\d+)\s*(.*)\s-->",
                        cells[-2]
                    ).groups()
                self._programs[-1]["strategies"].append({
                    "number": strategy_number,
                    "description": strategy,
                    "short_description": strategy_short,
                    "projects": [],
                    "goals": []
                })
                for project in self._get_projects_for_strategy(
                        strategy_number
                ):
                    # Add projects for this strategy.
                    self._programs[-1]["strategies"][-1]["projects"].append(
                        project
                    )
                    self._external_projects.remove(project)
            # The rightmost cell always contains a goal.
            goal = cells[-1]
            self._programs[-1]["strategies"][-1]["goals"].append(goal)

    def _add_program_overview_year_page(self):
        """Add a page with program overview.

        Uses several templates to build a table with information about
        and status of goals and projects, ordered by program and
        strategy.

        """

        config = self._config["year_pages"]["program_overview"]
        templates = config["templates"]
        content_parameter = ""
        for project in self._external_projects:
            content_parameter += Template(
                templates["project"],
                True,
                [project]
            ).multiline_string()
            content_parameter += "\n"
        for p, program in enumerate(self._programs):
            content_parameter += Template(
                templates["program"],
                True,
                {
                    "program": program["name"],
                    "färg": config["colours"][p]
                }
            ).multiline_string()
            content_parameter += "\n"
            for strategy in program["strategies"]:
                content_parameter += Template(
                    templates["strategy"],
                    True,
                    [strategy["description"]]
                ).multiline_string()
                content_parameter += "\n"
                for goal in strategy["goals"]:
                    content_parameter += Template(
                        templates["goal"],
                        True,
                        [goal]
                    ).multiline_string()
                    content_parameter += "\n"
                for project in strategy["projects"]:
                    content_parameter += Template(
                        templates["project"],
                        True,
                        [project]
                    ).multiline_string()
                    content_parameter += "\n"
        title = self._make_year_title(
            self._config["year_pages"]["program_overview"]["title"]
        )
        self._add_page_from_template(
            None,
            title,
            templates["page"],
            {
                "år": self._year,
                "tabellinnehåll": content_parameter
            }
        )

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
