import unittest
from time import strftime
import pathlib
from cbc.content import FileSystemContentHandler, AwsS3ContentHandler

BASE_DIR = pathlib.Path("../../temp/unittest/content")
FS_CONTENT_HANDLER = FileSystemContentHandler(base_folder=BASE_DIR)

S3_BUCKET = 'cbc-rss-test'
BASE_PREFIX = 'unittest'
S3_CONTENT_HANDLER = AwsS3ContentHandler(bucket=S3_BUCKET, base_prefix=BASE_PREFIX)

PREFIX = "test"
TEXT_KEY = "f_" + strftime("%Y%m%d_%H%M%S") + ".txt"
TEXT = "Test-File äöüÄÖÜ?€èéâ"

BYTES_KEY = "b_" + strftime("%Y%m%d_%H%M%S")
BYTES = "Test äöüÄÖÜ?€èéâ".encode('utf-8')


class FsContentHandlerTestCase(unittest.TestCase):
    def test_create_text_file(self):
        FS_CONTENT_HANDLER.save_text(TEXT_KEY, TEXT, prefix=PREFIX)
        self.assertTrue((BASE_DIR / PREFIX / TEXT_KEY).is_file())

    def test_create_binary_file(self):
        FS_CONTENT_HANDLER.save_bytes(BYTES_KEY, BYTES, prefix=PREFIX)
        self.assertTrue(True)

    def test_list(self):
        content_handler = FileSystemContentHandler(base_folder=str(BASE_DIR))
        l = content_handler.list(prefix=PREFIX)
        self.assertTrue(TEXT_KEY in l and BYTES_KEY in l)

    def test_get_text(self):
        text = FS_CONTENT_HANDLER.get_text(TEXT_KEY, prefix=PREFIX)
        self.assertEqual(text, TEXT)

    def test_get_bytes(self):
        bytes_ = FS_CONTENT_HANDLER.get_bytes(BYTES_KEY, prefix=PREFIX)
        self.assertEqual(bytes_, BYTES)


class S3ContentHandlerTestCase(unittest.TestCase):
    def test_create_text_file(self):
        S3_CONTENT_HANDLER.save_text(TEXT_KEY, TEXT, prefix=PREFIX)
        self.assertTrue(True)

    def test_create_binary_file(self):
        S3_CONTENT_HANDLER.save_bytes(BYTES_KEY, BYTES, prefix=PREFIX)
        self.assertTrue(True)

    def test_list(self):
        l = S3_CONTENT_HANDLER.list(prefix=PREFIX)
        self.assertTrue(TEXT_KEY in l and BYTES_KEY in l)

    def test_get_text(self):
        text = S3_CONTENT_HANDLER.get_text(TEXT_KEY, prefix=PREFIX)
        self.assertEqual(text, TEXT)

    def test_get_bytes(self):
        bytes_ = S3_CONTENT_HANDLER.get_bytes(BYTES_KEY, prefix=PREFIX)
        self.assertEqual(bytes_, BYTES)


def test_get_file(self):
    if __name__ == '__main__':
        unittest.main()

