import unittest
from unittest.mock import MagicMock

import pywikibot
from pywikibot import Page, Site
from pywikibot.data.api import Request

from wiki import Wiki


class TestWiki(unittest.TestCase):

    def setUp(self):
        parameters = [None] * 9
        self._wiki = Wiki(*parameters)

    def test_write_page_exists_show_diff(self):
        self._wiki._site = MagicMock(Site)
        self._wiki._config = {"edit_summary": "edit_summary"}
        page = MagicMock(Page)
        page.exists = MagicMock(return_value=True)
        page.get = MagicMock(return_value="Old text")
        request = MagicMock(Request)
        data = {"parse": {"text": {"*": "New text"}}}
        request.submit = MagicMock(return_value=data)
        self._wiki._site.simple_request = MagicMock(return_value=request)
        pywikibot.diff.cherry_pick = MagicMock()

        self._wiki._write_page(page)

        pywikibot.diff.cherry_pick.assert_called_with("Old text", "New text")

    def test_write_page_merged_text_saved(self):
        self._wiki._site = MagicMock(Site)
        self._wiki._config = {"edit_summary": "edit_summary"}
        page = MagicMock(Page)
        page.exists = MagicMock(return_value=True)
        page.text = "Old text"
        page.get = MagicMock(return_value="Old text")
        self._wiki._site.simple_request = MagicMock()
        merged_text = "Merged text"
        pywikibot.diff.cherry_pick = MagicMock(return_value=merged_text)

        self._wiki._write_page(page)

        self.assertEqual(page.text, merged_text)
        page.save.assert_called()
