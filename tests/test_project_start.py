import unittest
from unittest.mock import MagicMock

import project_start
from wiki import Wiki


class TestProjectStart(unittest.TestCase):

    def test_process_project_exclude_skipped(self):
        project_start.add_phab_project = MagicMock(
            return_value=(1, "phab_name")
        )
        project_start.add_wiki_project_pages = MagicMock()
        project_start.goals = None
        project_start.components = None
        project_start.wiki = MagicMock(Wiki)
        project_start.wiki.add_project = MagicMock()
        project_information = {
            "SUPER PROJECT": "",
            "ENGLISH NAME": "",
            "SWEDISH NAME": "",
            "PROJECT NUMBER": "",
            "PROGRAM": "",
            "ACTIVE": "0"
        }
        project_columns = {
            "super_project": "SUPER PROJECT",
            "english_name": "ENGLISH NAME",
            "swedish_name": "SWEDISH NAME",
            "project_number": "PROJECT NUMBER",
            "program": "PROGRAM",
            "active": "ACTIVE"
        }

        project_start.process_project(project_information, project_columns)

        project_start.add_phab_project.assert_not_called()
        project_start.add_wiki_project_pages.assert_not_called()
        project_start.wiki.add_project.assert_not_called()
