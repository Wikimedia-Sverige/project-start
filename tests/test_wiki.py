import unittest
from unittest.mock import MagicMock

import pywikibot
from pywikibot import Page
from pywikibot import Site
from pywikibot.data.api import Request

from wiki import Wiki


class TestWiki(unittest.TestCase):

    def test_write_page_exists_show_diff(self):
        page = MagicMock(Page)
        page.exists = MagicMock(return_value=True)
        page.get = MagicMock(return_value="Old text")
        parameters = [None] * 9
        parameters[0] = {"edit_summary": "edit_summary"}
        wiki = Wiki(*parameters)
        wiki._site = MagicMock(Site)
        request = MagicMock(Request)
        data = {"parse": {"text": {"*": "New text"}}}
        request.submit = MagicMock(return_value=data)
        wiki._site.simple_request = MagicMock(return_value=request)
        print(wiki._site)
        pywikibot.diff.cherry_pick = MagicMock()

        wiki._write_page(page)

        pywikibot.diff.cherry_pick.assert_called_with("Old text", "New text")

# if __name__ == '__main__':
#     unittest.main()
