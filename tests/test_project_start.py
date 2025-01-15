import unittest

import project_start


class TestProjectStart(unittest.TestCase):

    def test_is_active_active(self):
        project_information = {
            "ACTIVE": "1"
        }
        project_columns = {
            "active": "ACTIVE"
        }

        self.assertTrue(project_start.is_active(
            project_information,
            project_columns
        ))

    def test_is_active_inactive(self):
        project_information = {
            "ACTIVE": "0"
        }
        project_columns = {
            "active": "ACTIVE"
        }

        self.assertFalse(project_start.is_active(
            project_information,
            project_columns
        ))
