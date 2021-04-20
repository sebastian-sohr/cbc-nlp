import unittest
from time import strftime
import pathlib
from cbc.content import FileSystemContentHandler, AwsS3ContentHandler, IteratorReader

BASE_DIR = "../../temp/unittest"
FS_CONTENT_HANDLER = FileSystemContentHandler(base_prefix=BASE_DIR)

S3_BUCKET = 'cbc-rss-test'
BASE_PREFIX = 'unittest'
S3_CONTENT_HANDLER = AwsS3ContentHandler(bucket=S3_BUCKET, base_prefix=BASE_PREFIX)

PREFIX = "content"
TEXT_KEY = "f_" + strftime("%Y%m%d_%H%M%S") + ".txt"
TEXT = "Test-File äöüÄÖÜ?€èéâ"

BYTES_KEY = "b_" + strftime("%Y%m%d_%H%M%S")
BYTES_STREAM_KEY = "bs_" + strftime("%Y%m%d_%H%M%S")
BYTES = "Test äöüÄÖÜ?€èéâ".encode('utf-8')


class FsContentHandlerTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self.content_handler = kwargs.pop("content_handler", FS_CONTENT_HANDLER)
        super().__init__(*args, **kwargs)

    def test_files(self):
        self.content_handler.save_text(TEXT_KEY, TEXT, prefix=PREFIX)
        text = self.content_handler.get_text(TEXT_KEY, prefix=PREFIX)
        self.assertEqual(text, TEXT)
        self.content_handler.save_bytes(BYTES_KEY, BYTES, prefix=PREFIX)
        bytes_ = self.content_handler.get_bytes(BYTES_KEY, prefix=PREFIX)
        self.assertEqual(bytes_, BYTES)
        l = self.content_handler.list(prefix=PREFIX)
        self.assertTrue(TEXT_KEY in l and BYTES_KEY in l)

    def test_write_input_stream(self):
        def iter():
            for i in ('a', 'b', 'c', 'd', 'e', 'f', 'g'):
                res = i * 3
                yield res.encode("utf8")

        compare = b"".join(iter())
        iter_reader = IteratorReader(iter())
        self.content_handler.write_input_stream(iter_reader, BYTES_STREAM_KEY, prefix=PREFIX)
        bytes_ = self.content_handler.get_bytes(BYTES_STREAM_KEY, prefix=PREFIX)
        self.assertEqual(bytes_, compare)


class S3ContentHandlerTestCase(FsContentHandlerTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, content_handler=S3_CONTENT_HANDLER)


def test_get_file(self):
    if __name__ == '__main__':
        unittest.main()

