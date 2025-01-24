import logging
import os
from time import sleep, time

import pywikibot
import requests
from dotenv import load_dotenv


class Phab:
    """Handles Phabricator interaction.

    Uses the Conduit API for requests.

    Attributes
    ----------
    _config : dict
        Parameters read from configuration file.
    _dry_run : bool
        If True, no data is written to Phabricator.
    _last_request_time : float
        Time when last request was made, in seconds.
    """

    def __init__(self, main_config, dry_run):
        self._config = main_config.get("phab")
        self._wiki_config = main_config.get("wiki")
        self._dry_run = dry_run
        self._last_request_time = 0.0
        load_dotenv()
        self._api_token = os.getenv("PHAB_API_TOKEN")

    def add_project(self, name_en, name_sv, description):
        """Add project.

        Parameters
        ----------
        name_en : str
            English name of the project. This is modified to follow the
            conventions specified at:
            https://www.mediawiki.org/wiki/Phabricator/Creating_and_renaming_projects#Good_practices_for_name_and_description
        name_sv : str
            Swedish name of the project. Used as additional hashtag to improve
            search.
        description : str
            Description of the project in English. This is added as
            description in the project.

        Returns
        -------
        tuple
            Project id and name of the project that was created.

        """
        parent_phid, parent_name = \
            self._get_project_phid_and_name(self._config["parent_project_id"])
        phab_name_en = self._to_phab_project_name(name_en, parent_name)
        phab_name_sv = self._to_phab_project_name(name_sv, parent_name)
        project_id = self._get_project_id(phab_name_en)
        if project_id is not None:
            logging.warning(
                "Project '{}' already exists. It will not be created.".format(
                    phab_name_en
                )
            )
        else:
            description = self._make_description(description, name_sv)
            parameters = {
                "transactions": {
                    "0": {
                        "type": "name",
                        "value": phab_name_en
                    },
                    "1": {
                        "type": "slugs",
                        "value": [phab_name_sv]
                    },
                    "2": {
                        "type": "description",
                        "value": description
                    },
                    "3": {
                        "type": "parent",
                        "value": parent_phid
                    }
                }
            }
            if self._dry_run:
                project_id = 1
            else:
                response = self._make_request("project.edit", parameters)
                project_id = response["result"]["object"]["id"]
        return project_id, phab_name_en

    def _get_project_phid_and_name(self, id_):
        """Get the PHID and name of a project.

        Uses the Conduit endpoint "project.search".

        Parameters
        ----------
        id_ : int
            Id of the project to get info for.

        Returns
        -------
        str
            PHID of the given project. The format of the PHID is
            "PHID-PROJ-..." for projects. Note that this is not the
            same as the project id, which is just a number.
        str
            Name of the given project.

        """
        parameters = {"constraints": {"ids": [id_]}}
        response = self._make_request("project.search", parameters)
        phid = response["result"]["data"][0]["phid"]
        name = response["result"]["data"][0]["fields"]["name"]
        return phid, name

    def _make_request(self, endpoint, parameters_dict):
        """Make a request to the Conduit API.

        Parameters
        ----------
        endpoint : str
            Name of the endpoint to send the request to.
        parameters_dict : dict
            The parameters to send with the request.

        Returns
        -------
        dict
            Response from the API, parsed from Json.

        Raises
        ------
        PhabApiError
            If the Conduit API response contains an error.
        """
        wait_time = self._last_request_time - time() + \
            self._config["request_delay"]
        if wait_time > 0:
            logging.debug("Waiting for {} seconds before making the next request to Conduit.".format(wait_time))  # noqa: E501
            sleep(wait_time)
        parameters = self._to_phab_parameters(parameters_dict)
        # Add placeholder API token to not reveal the real one in logs.
        logged_parameters = parameters.copy()
        logged_parameters["api.token"] = "api-REDACTED"
        logging.debug(
            "POST to Phabricator API on {}/{}: {}".format(
                self._config["api_url"],
                endpoint,
                logged_parameters
            )
        )
        parameters["api.token"] = self._api_token
        self._last_request_time = time()
        response = requests.post(
            "{}/{}".format(self._config["api_url"], endpoint),
            parameters
        ).json()
        if response["error_info"]:
            raise PhabApiError("Error from Phabricator API: {}".format(
                response["error_info"]
            ))
        logging.debug("Response: {}".format(response))
        return response

    def _to_phab_parameters(
            self,
            dict_parameters,
            phab_parameters=None,
            prefix="",
            top=True
    ):
        """Convert a dict of parameters into Conduit request format.

        Conduit accepts structured parameters of the format:
            transactions[0][type]=parent
            transactions[0][value]=PHID-PROJ-ft7vbzykjs52i5vguajb
            transactions[1][type]=name
            transactions[1][value]=WMSE-Project
        These are mapped from a dict like:
            {
                "transactions": {
                    "0": {
                        "type": "parent",
                        "value": "PHID-PROJ-ft7vbzykjs52i5vguajb"
                    },
                    "1": {
                        "type": "name",
                        "value": "WMSE-Project"
                    }
                }
            }

        Parameters
        ----------
        dict_parameters : dict
            Input parameters.
        phab_parameters : dict
            Output parameters in the Conduit format. Parameters are
            added as they are discovered.
        prefix : str
            Prefix of a parameter name,
            e.g. "transactions[0][type]". This get extended when the
            function traverses along a parameter path.
        top : bool
            Whether the call is for a top level parameter. If True,
            square brackets aren't added when adding parameter name to
            prefix.

        Returns
        -------
        dict
            Parameters with names in the Conduit format.

        """
        if phab_parameters is None:
            phab_parameters = {}
        for key, value in dict_parameters.items():
            if type(value) is dict:
                if top:
                    new_prefix = "{}{}".format(prefix, key)
                else:
                    new_prefix = "{}[{}]".format(prefix, key)
                new_parameters = \
                    self._to_phab_parameters(
                        value,
                        phab_parameters,
                        new_prefix,
                        False
                    )
                phab_parameters.update(new_parameters)
            elif type(value) is list:
                for index, item in enumerate(value):
                    parameter_key = \
                        "{}[{}][{}]".format(prefix, key, index)
                    phab_parameters[parameter_key] = item
            else:
                parameter_key = "{}[{}]".format(prefix, key)
                phab_parameters[parameter_key] = value
        return phab_parameters

    def _to_phab_project_name(self, name, parent_name):
        """Convert a project name to follow Wikimedia conventions.

        Parameters
        ----------
        name : str
            Project name.
        parent_name : str
            Parent project name.

        Returns
        -------
        str
            Project name with spaces replaced by dashes and prefixed
            by the parent name.

        """
        return "{}-{}".format(parent_name, name.replace(" ", "-"))

    def _get_project_id(self, name):
        """Get the id of a project.

        Parameters
        ----------
        name : str
            Project name.

        Returns
        -------
        int
            Project id.

        """
        parameters = {"constraints": {"query": name}}
        response = self._make_request("project.search", parameters)
        if len(response["result"]["data"]) == 0:
            return None
        else:
            return response["result"]["data"][0]["id"]

    def _make_description(self, description, name_sv):
        """Make a project description.

        Adds a link to the wiki project page at the start.

        Parameters
        ----------
        description : str
            Text to use in description.
        name_sv : str
            Project name in Swedish.

        Returns
        -------
        str
            Project description.
        """
        siteinfo = pywikibot.Site().siteinfo
        article_path = (siteinfo.get('articlepath').removesuffix('$1')
                        .removesuffix('/'))
        wiki_url = f"{siteinfo.get('server')}{article_path}"
        project_namespace = self._wiki_config.get("project_namespace")
        return (f"//[[{wiki_url}/{project_namespace}:{name_sv} | "
                f"More project information (in Swedish)]]//\n\n{description}")


class PhabApiError(Exception):
    """Raised when Conduit API returns an error."""
    pass
