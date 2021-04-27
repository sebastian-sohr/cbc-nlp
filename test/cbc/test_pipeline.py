import unittest
import cbc.pipeline as pipeline
from time import strftime
from pathlib import Path
from cbc.content import FileSystemContentHandler, AwsS3ContentHandler, IteratorReader
import re
from hashlib import md5

INT_LIST = list(range(0, 10))

BASE_DIR = Path("../../temp/unittest")

FS_CONTENT_HANDLER = FileSystemContentHandler(base_prefix=BASE_DIR)

S3_BUCKET = 'cbc-rss-test'
BASE_PREFIX = 'unittest'
S3_CONTENT_HANDLER = AwsS3ContentHandler(bucket=S3_BUCKET, base_prefix=BASE_PREFIX)

PREFIX = "pipeline"
TEXT_KEY = "f_" + strftime("%Y%m%d_%H%M%S") + ".txt"
TEXT = "Test-File äöüÄÖÜ?€èéâ"

TOKEN_FILE = "../../examples/sample_data/rss_tokens.txt"

STREAM_KEY = "s_" + strftime("%Y%m%d_%H%M%S") + ".txt"


class PipelineTestCase(unittest.TestCase):
    def test_base_iterator(self):
        def gen_function():
            for i in INT_LIST:
                yield i

        iterator = pipeline.Iterator(gen_function)

        l = [i for i in iterator]
        self.assertEqual(INT_LIST, l)

    def test_base_modifier(self):
        gen = pipeline.ListGenerator(INT_LIST)
        m = pipeline.ItemModifier(f=lambda i: i+1)
        self.assertEqual(5, m(4))
        self.assertEqual(6, (m*m)(4))
        p = m ** gen
        l = [i for i in p]
        self.assertEqual([i+1 for i in INT_LIST], l)
        q = m ** m ** gen
        l2 = [i for i in q]
        self.assertEqual([i + 2 for i in INT_LIST], l2)
        even = pipeline.ItemModifier(f=lambda i: i if i % 2 == 0 else None, tag_set=(True, True))
        p2 = even ** gen
        l3 = [i for i in p2]
        compare = [(INT_LIST[i], [i]) for i in range(0, len(INT_LIST)) if INT_LIST[i] % 2 == 0]
        for i in range(0, len(compare)):
            compare[i][1].append(i)
        self.assertEqual(l3, compare)

    def test_merge(self):
        l_0 = [i for i in INT_LIST if i % 2 == 0]
        l_1 = [i for i in INT_LIST if i % 2 == 1]
        p_0 = pipeline.ListGenerator(l_0)
        p_1 = pipeline.ListGenerator(l_1)
        p_m1 = pipeline.Merge() ** (p_0, p_1)
        self.assertEqual(INT_LIST, list(p_m1))

        l_3 = [1]
        p_3 = pipeline.ListGenerator(l_3)
        p_m2 = pipeline.Merge() ** (p_0, p_3)
        self.assertEqual([0, 1, 2, 4, 6, 8], list(p_m2))

        l_4 = [-1, -2]
        p_4 = pipeline.ListGenerator(l_4)
        p_m3 = pipeline.Merge() ** (p_0, p_3, p_4)
        self.assertEqual([0, 1, -1, 2, -2, 4, 6, 8], list(p_m3))

        p_m4 = pipeline.Merge() ** ((p_0, 2.0), (p_4, 1.0))
        self.assertEqual([0, 2, -1, 4, 6, -2, 8], list(p_m4))

        p_m5 = pipeline.Merge() ** ((p_0, 1.5), (p_4, 1.0))
        self.assertEqual([0, -1, 2, 4, -2, 6, 8], list(p_m5))

    def test_repeat(self):
        p_1 = pipeline.Repeat(total_repeats=5) ** pipeline.ListGenerator([1])
        self.assertEqual([1] * 5, list(p_1))
        p_2 = pipeline.Repeat(total_items=13) ** pipeline.ListGenerator(INT_LIST)
        self.assertEqual(INT_LIST + INT_LIST[0:3], list(p_2))

    def test_subset(self):
        p = pipeline.ListGenerator(INT_LIST)
        p_1 = pipeline.Subset(output_until=5) ** p
        self.assertEqual(INT_LIST[0:5], list(p_1))

        p_2 = pipeline.Subset(output_from=5) ** p
        self.assertEqual(INT_LIST[5:], list(p_2))

        p_3 = pipeline.Subset(output_from=2, output_until=3) ** p
        self.assertEqual(INT_LIST[2:3], list(p_3))

        p_4 = pipeline.Subset(output_from=3, output_length=2) ** p
        self.assertEqual(INT_LIST[3:3+2], list(p_4))

        p_5 = pipeline.Subset(distance=2) ** p
        self.assertEqual([INT_LIST[i] for i in range(0, len(INT_LIST)) if i % 2 == 0], list(p_5))

        p_6 = pipeline.Subset(output_from=3, distance=2) ** p
        self.assertEqual([INT_LIST[i] for i in range(0, len(INT_LIST)) if i % 2 == 0 and i >= 3], list(p_6))

        p_7 = pipeline.Subset(distance=len(INT_LIST) - 1) ** p
        self.assertEqual([INT_LIST[0], INT_LIST[len(INT_LIST) - 1]], list(p_7))

    def test_FileSourceGenerator_fs(self):
        ts = strftime("%Y%m%d_%H%M%S")
        r = pipeline.RandomStringsGenerator()
        i = 0
        fn_map = {}
        for text in r:
            key = "test_fsg_%s_%03i.txt" % (ts, i)
            fn_map[key] = text
            FS_CONTENT_HANDLER.save_text(key, text, prefix=PREFIX)
            i += 1
        l_ = [
            (PREFIX, f) for f in FS_CONTENT_HANDLER.list(prefix=PREFIX)
            if re.match(r"test_fsg_%s_\d+\.txt" % ts, f)
        ]
        self.assertEqual(len(l_), i)
        i = 0
        p = pipeline.FileSourceGenerator(l_, content_handler=FS_CONTENT_HANDLER, tag_set=(True, True, True))
        for item in p:
            self.assertEqual(item, (fn_map[l_[i][1]], [PREFIX, l_[i][1], i]))
            i += 1
        content_handler = FileSystemContentHandler(base_prefix=BASE_DIR / PREFIX)
        l2 = [
            f for f in content_handler.list()
            if re.match(r".*test_fsg_%s_\d+\.txt" % ts, f)
        ]
        self.assertEqual(len(l2), i)
        i = 0
        p = pipeline.FileSourceGenerator(l2, content_handler=content_handler)
        for item in p:
            self.assertEqual(item, fn_map[l2[i]])
            i += 1

    def test_FileSourceGenerator_s3(self):
        ts = strftime("%Y%m%d_%H%M%S")
        r = pipeline.RandomStringsGenerator(number_of_docs=3, number_of_words=100, length_of_words=7)
        i = 0
        fn_map = {}
        for text in r:
            key = "test_fsg_%s_%03i.txt" % (ts, i)
            fn_map[key] = text
            fn_map[PREFIX + "/" + key] = text
            S3_CONTENT_HANDLER.save_text(key, text, prefix=PREFIX)
            i += 1
        l = [
            (PREFIX, f) for f in S3_CONTENT_HANDLER.list(prefix=PREFIX)
            if re.match(r"test_fsg_%s_\d+\.txt" % ts, f)
        ]
        self.assertEqual(len(l), i)
        i = 0
        p = pipeline.FileSourceGenerator(l, content_handler=S3_CONTENT_HANDLER, tag_set=(False, True, False))
        for item in p:
            self.assertEqual(item, (fn_map[l[i][1]], [l[i][1]]))
            i += 1
        l2 = [
            f for f in S3_CONTENT_HANDLER.list()
            if re.match(r".*test_fsg_%s_\d+\.txt" % ts, f)
        ]
        self.assertEqual(len(l2), i)
        i = 0
        p = pipeline.FileSourceGenerator(l2, content_handler=S3_CONTENT_HANDLER)
        for text in p:
            self.assertEqual(text, fn_map[l2[i]])
            i += 1

    def test_XmlParser(self):
        ts = strftime("%Y%m%d_%H%M%S")
        r = pipeline.RandomStringsGenerator()
        i = 0
        fn_map = {}
        for text in r:
            text_c = "<a><content><![CDATA[%s]]></content></a>" % text
            key_c = "test_%s_c%03i.xml" % (ts, i)
            fn_map[key_c] = text
            FS_CONTENT_HANDLER.save_text(key_c, text_c, prefix=PREFIX)
            text_b = "<a><b><![CDATA[%s]]></b></a>" % text
            key_b = "test_%s_b%03i.xml" % (ts, i)
            fn_map[key_b] = text
            FS_CONTENT_HANDLER.save_text(key_b, text_b, prefix=PREFIX)
            i += 1

        l_c = [
            (PREFIX, f) for f in FS_CONTENT_HANDLER.list(prefix=PREFIX)
            if re.match(r"test_%s_c\d+\.xml" % ts, f)
        ]
        self.assertEqual(len(l_c), i)
        i = 0
        p = pipeline.XmlParser() ** pipeline.FileSourceGenerator(l_c, content_handler=FS_CONTENT_HANDLER)
        for text in p:
            self.assertEqual(text, fn_map[l_c[i][1]])
            i += 1

        l_b = [
            (PREFIX, f) for f in FS_CONTENT_HANDLER.list(prefix=PREFIX)
            if re.match(r"test_%s_b\d+\.xml" % ts, f)
        ]
        self.assertEqual(len(l_b), i)
        i = 0
        p = pipeline.XmlParser(content_tag="b") ** \
            pipeline.FileSourceGenerator(l_b, content_handler=FS_CONTENT_HANDLER, tag_set=(False, False, True))
        for item in p:
            self.assertEqual(item, (fn_map[l_b[i][1]], [i]))
            i += 1

    def test_stream_to_s3(self):
        p = pipeline.LineSourceIterator(TOKEN_FILE)
        sig = md5()
        for line in p:
            sig.update(line.encode('utf-8'))
        orig_hash = sig.hexdigest()
        p.__iter__()
        p_reader = IteratorReader(p, to_bytes_function=lambda s: s.encode('utf-8'))
        S3_CONTENT_HANDLER.write_input_stream(p_reader, STREAM_KEY, prefix=PREFIX)
        sig = md5()
        for line in S3_CONTENT_HANDLER.iterate_lines(STREAM_KEY, prefix=PREFIX):
            sig.update(line.encode('utf-8'))
        compare_hash = sig.hexdigest()
        self.assertEqual(orig_hash, compare_hash)
        content_handler = S3_CONTENT_HANDLER


if __name__ == '__main__':
    unittest.main()
