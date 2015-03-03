from unittest import TestCase
from thr.http2redis import main


class Http2Redis(TestCase):

    def test_main(self):
        main()
