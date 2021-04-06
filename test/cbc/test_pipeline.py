import unittest
import cbc.pipeline as pipeline

INT_LIST = list(range(0, 10))


class PipelineTestCase(unittest.TestCase):
    def test_base_iterator(self):
        def gen_function():
            for i in INT_LIST:
                yield i

        iterator = pipeline.Iterator(gen_function)

        l = [i for i in iterator]
        self.assertEqual(INT_LIST, l)

    def test_base_modifier(self):
        m = pipeline.ItemModifier(f=lambda i: i+1)
        self.assertEqual(5, m(4))
        self.assertEqual(6, (m*m)(4))
        p = m ** pipeline.ListGenerator(INT_LIST)
        l = [i for i in p]
        self.assertEqual([i+1 for i in INT_LIST], l)
        q = m ** m ** pipeline.ListGenerator(INT_LIST)
        l2 = [i for i in q]
        self.assertEqual([i + 2 for i in INT_LIST], l)


if __name__ == '__main__':
    unittest.main()
