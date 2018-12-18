from collections import OrderedDict
import logging

from pywikibot import Site
from pywikibot import Page

from template import Template

"""
Attributes
----------
PROJECT_NAMESPACE : str
    The namespace where the project pages will be created.

"""

PROJECT_NAMESPACE = "Projekt"


class Wiki:
    """Handles wiki interaction.

    Uses `pywikibot` to write to the wiki.

    Attributes
    ----------
    _site : Site
        `Site` object used by Pywikibot
    """

    def __init__(self):
        self._site = Site()

    def add_project_page(
            self,
            name,
            description,
            partners,
            phab_id,
            phab_name
    ):
        """Add the main project page.

        Parameters
        ----------
        name : str
            The project name in Swedish. This will be used as title for the page.
        description : str
            Passed to template as parameter "beskrivning".
        partners : str
            Passed to template as parameter "samarbetspartners".

        """
        template = Template("Projekt-sida", True)
        template.add_parameter("beskrivning", description)
        template.add_parameter("samarbetspartners", partners)
        template.add_parameter("phabricatorId", phab_id)
        template.add_parameter("phabricatorName", phab_name)
        page = Page(self._site, name, PROJECT_NAMESPACE)
        content = "{}".format(template)
        page.text = content
        page.save("[TEST] Skapa projektsida.")

    def add_volunteer_subpage(self, project, email_prefix):
        """Add a volunteer subpage under the project page.

        The title of this page is "Frivillig". It is created by
        substituting the template "Frivillig-sida".

        Parameters
        ----------
        project : str
            The project name in Swedish.
        email_prefix : str
            Passed to template as parameter "e-post_prefix".

        """
        title = "Frivillig"
        summary = "[TEST] Skapa undersida för frivilliga."
        parameters = {"e-post_prefix": email_prefix}
        self._add_subpage(
            project,
            title,
            summary,
            "Frivillig-sida",
            parameters
        )

    def _add_subpage(
            self,
            project,
            title,
            summary,
            template_name,
            template_parameters=None
    ):
        """Add a  subpage under the project page.

        Parameters
        ----------
        project : str
            The project name in Swedish.
        title : str
            The title of the subpage. Only the prefix, i.e. the
            substring after the last slash. This will be prepended by
            the project name to create the complete subpage title.
        summary : str
            The summary that will be used for the edit.
        template_name : str
            The name of the template to substitute to create the subpage.
        template_parameters : dict
            The parameters to pass to the template.

        """
        full_title = "{}/{}".format(project, title)
        page = Page(self._site, full_title, PROJECT_NAMESPACE)
        template = Template(template_name, True)
        if template_parameters:
            for key, value in template_parameters.items():
                template.add_parameter(key, value)
        page.text = "{}".format(template.multiline_string())
        logging.debug("Writing to subpage '{}'.".format(page))
        logging.debug(page.text)
        page.save(summary)

    def add_global_metrics_subpage(self, project):
        """Add a global metrics subpage under the project page.

        The title of this page is "Global Metrics". It is created by
        substituting the template "Global Metrics-sida".

        Parameters
        ----------
        project : str
            The project name in Swedish.

        """
        title = "Global_Metrics"
        summary = "[TEST] Skapa undersida för global metrics."
        self._add_subpage(project, title, summary, "Global Metrics-sida")

    def add_mentions_subpage(self, project):
        """Add a mentions subpage under the project page.

        The title of this page is "Omnämnande". It is created by
        substituting the template "Omnämnande-sida".

        Parameters
        ----------
        project : str
            The project name in Swedish.

        """
        title = "Omnämnande"
        summary = "[TEST] Skapa undersida för omnämnande."
        self._add_subpage(project, title, summary, "Omnämnande-sida")

    def add_project_data_subpage(
            self,
            project,
            owner,
            start,
            end,
            financier,
            budget,
            goals,
            goal_fulfillments
    ):
        """Add a project data subpage under the project page.

        The title of this page is "Projektdata". It is created by
        substituting the template "Projektdata-sida".

        Parameters
        ----------
        project : str
            The project name in Swedish.
        owner : str
            Passed to template as parameter "ansvarig".
        start : str
            Passed to template as parameter "projektstart".
        end : str
            Passed to template as parameter "projektslut".
        financier : str
            Passed to template as parameter "finansiär".
        budget : str
            Passed to template as parameter "budget".
        goals : OrderedDict
            A map of goal names and planned values for this project.
        goals : dict
            A map of goal names and fulfillment texts.

        """
        title = "Projektdata"
        summary = "[TEST] Skapa undersida för projektdata."
        parameters = OrderedDict()
        parameters["ansvarig"] = owner
        parameters["projektstart"] = start
        parameters["projektslut"] = end
        parameters["finansiär"] = financier
        parameters["budget"] = budget
        parameters["interna_mål"] = \
            Template("Måltexter 2018", parameters=goals)
        parameters["måluppfyllnad"] = \
            self._create_goal_fulfillment_text(goals.keys(), goal_fulfillments)
        self._add_subpage(
            project,
            title,
            summary,
            "Projektdata-sida",
            parameters
        )

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
        string
            Contains one fulfillment text as a wikitext list.
        """
        fulfillment_text = ""
        for goal in goals:
            fulfillment_text += "\n* {}".format(fulfillments[goal])
        return fulfillment_text

    def add_categories(self, project, year, area):
        """Add categories to the project's category page.

        Adds the project category to two categories: one for year and one for area.

        Parameters
        ----------
        project : str
            The project name in Swedish.
        year : int
            The year category to add the project category to.
        area : str
            The area category to add the project category to.
        """
        year_category = "Projekt {}".format(year)
        page = Page(self._site, project, "Kategori")
        page.text = "[[Kategori:{}]]".format(year_category)
        page.text += "\n[[Kategori:{}]]".format(area)
        page.save("[TEST] Skapa projektkategori.")
