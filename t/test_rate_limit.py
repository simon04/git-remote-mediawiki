"""HTTP 429 Too Many Requests: wait as the wiki asks, then carry on."""

import unittest

from gitmwtest import GitMediaWikiTestCase


class RateLimitTest(GitMediaWikiTestCase):
    def test_clone_waits_out_a_rate_limit(self) -> None:
        for title in ('Foo', 'Bar', 'Baz'):
            self.wiki.edit_page(title, f'{title} contents')
        # Past connecting to the wiki, while listing its pages.
        self.wiki.rate_limit_after = 2
        self.wiki.rate_limited = 2

        completed = self.git('clone', self.remote, 'repo')

        self.assertEqual(2, self.wiki.rate_limited_answers)
        self.assertIn('rate limiting requests (HTTP 429), waiting 1 seconds', completed.stderr)
        self.assertRepositoryMatchesWiki(self.workdir / 'repo', ['Main Page', 'Foo', 'Bar', 'Baz'])
        self.assertNothingUnhandled()

    def test_clone_gives_up_without_a_traceback(self) -> None:
        self.wiki.rate_limit_after = 2
        self.wiki.rate_limited = 100

        completed = self.git('clone', self.remote, 'repo', check=False)

        self.assertNotEqual(0, completed.returncode)
        self.assertIn('still answers HTTP 429 Too Many Requests after 6 retries', completed.stderr)
        self.assertNotIn('Traceback', completed.stderr)
        self.assertEqual(7, self.wiki.rate_limited_answers)


if __name__ == '__main__':
    unittest.main()
