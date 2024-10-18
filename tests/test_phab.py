import unittest
from unittest.mock import MagicMock, patch

from phab import Phab


class TestPhab(unittest.TestCase):

    def setUp(self):
        parameters = [None] * 2
        self._phab = Phab(*parameters)

    @patch("phab.requests")
    def test_add_project(self, mock_requests):
        self._phab._config = {
            "parent_project_id": 1,
            "request_delay": 0,
            "api_url": "http://site.url"
        }

        def mock_post(url, data):
            if url.endswith("/project.search"):
                if data.get("constraints[ids][0]") == 1:
                    parent_project_data = {
                        "id": 1,
                        "phid": "PHID-PROJ-abc123",
                        "fields": {
                            "name": "Parent"
                        }
                    }
                    return mock_phab_request(parent_project_data)

                if (data.get("constraints[query]")
                        == "Parent-Project-in-English"):
                    return mock_phab_request()

            if url.endswith("/project.edit"):
                result_object = {"id": 2}
                return mock_phab_request(result_object=result_object)

        mock_requests.post.side_effect = mock_post
        name_en = "Project-in-English"
        name_sv = "Projekt-på-svenska"
        description = "Description of the project."

        result = self._phab.add_project(name_en, name_sv, description)

        request_calls = mock_requests.post.mock_calls
        assert request_calls[2].args[0] == "http://site.url/project.edit"
        edit_arguments = request_calls[2].args[1]
        assert edit_arguments.get("transactions[0][type]") == "name"
        assert edit_arguments.get(
            "transactions[0][value]") == "Parent-Project-in-English"
        assert edit_arguments.get("transactions[1][type]") == "slugs"
        assert edit_arguments.get(
            "transactions[1][value][0]") == "Parent-Projekt-på-svenska"
        assert edit_arguments.get("transactions[2][type]") == "description"
        assert edit_arguments.get(
            "transactions[2][value]") == "Description of the project."
        assert edit_arguments.get("transactions[3][type]") == "parent"
        assert edit_arguments.get(
            "transactions[3][value]") == "PHID-PROJ-abc123"
        assert result == (2, "Parent-Project-in-English")


def mock_phab_request(result_data=None, result_object=None):
    """Create a mock response.

    Parameters
    ----------
    result_data : dict, optional
        `result.data` in the response will be a list containing this. Empty
        list if not given.
    result_object : dict, optional
        `result.object` the response. Empty dict if not given.

    Returns
    -------
    MagicMock
        Mocked response containing the data given in the parameters. Also
        contains other parameters that are required.

    """
    data = [result_data] if result_data else []
    object_ = result_object if result_object else {}
    response_data = {
        "error_info": "",
        "result": {
            "data": data,
            "object": object_
        }
    }
    response = MagicMock()
    response.json.return_value = response_data
    return response
