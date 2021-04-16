"""
consileon.nlp.tokens
=====================

Frameword and tools for stream based processing of textual nlp.

The python concept of an "iterator" is heavily used.
This is a python class implementing the "iterator protocol", which consists of
__iter__() and __next__(). An iterator is something like an iterable
which can be reset by calling __iter__(). Therefore the elements of a loop can
be passed through many times.

Tokens implements some basic ideas which simplify working with iterators:

1)
    Modifiers operator on single items like _texts_ or _lists of tokens_. Those modifiers can be composed
    using the operator "*".

    Example:

    ::

import cbc.nlp.base        >>> import cbc.nlp.pipeline as pipeline
import cbc.nlp.base        >>> m = cbc.nlp.base.Lower() * cbc.nlp.base.LemmaTokenizeText()
        >>> m("Bälle sind meißt rund.")
        ['ball', 'sein', 'meißt', 'rund', '.']

2)
    _Generators_ create iterators "out of nothing". They are the starting point of _pipelines.
    Modifiers can be applied to iterators by using the operator `**`. It applies the modifiers
    operation to every single item of the iterator. Thus,

    Example:

    ::
import cbc.nlp.base        >>> import cbc.nlp.pipeline as pipeline
        >>> g = pipeline.ListGenerator(["Dies ist der erste Text.", "Dies ist ein weiterer Text."])
        >>> i = cbc.nlp.base.LemmaTokenizeText() ** g
        >>> print(list(i))

        Or, yielding the same

import cbc.nlp.base        >>> import cbc.nlp.pipeline as pipeline
        >>> i = cbc.nlp.base.LemmaTokenizeText() ** pipeline.ListGenerator(["Dies ist der erste Text.", "Dies ist ein weiterer Text."])

        or

import cbc.nlp.base        >>> import cbc.nlp.pipeline as pipeline
        >>> g = pipeline.ListGenerator(["Dies ist der erste Text.", "Dies ist ein weiterer Text."])
        >>> m = cbc.nlp.base.LemmaTokenizeText()
        >>> print(list(m ** g))


3)
    The are


Iterators may be used as *document input* for word2vec training.
"""
import random
import string

import nltk
import re
import xml.etree.ElementTree as eT

import logging
import numbers

import cbc.content as content


logger = logging.getLogger('cbc.pipeline')


class Iterator:
    """
    Base class for reusable iterators
    """

    def __init__(
            self,
            generator_function,
            is_tagged=False
    ):
        """
        Args:
            :generator_function (function): A function returning a python iterable of items

        Kwargs:
            :is_tagged (boolean, optional, default=True): The resuling iterator is producing "tagged" items
        """
        self.generator_function = generator_function
        self.generator = self.generator_function()
        self.is_tagged = is_tagged

    def __iter__(self):
        self.generator = None
        self.generator = self.generator_function()
        return self

    def __next__(self):
        try:
            result = next(self.generator)
            return result
        except Exception:
            raise StopIteration


class BaseGenerator:
    """
    An iterable having itself as generator function.
    Classes which _generate_ streams of texts from various nlp sources typically inherit
    from the class.
    These classes typically implement the method `__call__`.
    """

    def __call__(self):
        yield ["dummy"]

    def __init__(self, is_tagged=False):
        self.is_tagged = is_tagged
        self.generator = self.__call__()

    def __iter__(self):
        self.generator = None
        self.generator = self.__call__()
        return self

    def __next__(self):
        result = next(self.generator)
        if result is None:
            raise StopIteration
        else:
            return result


class IteratorModifier:
    """
    Base class for all classes which modify an iterator and which are not working
    'element wise' on items. E.g. "Merge", "SplitText".
    """

    def __pow__(self, iterator):
        return self.__call__(iterator)

    def __call__(self, iterator):
        def generator():
            for x in iterator:
                if x is not None:
                    yield x

        return Iterator(generator, iterator.is_tagged)


class IteratorConsumer:
    """
    Base class for operations which "consume" an iterator like writing
    its items to a file or applying some KI method on its items.
    """

    def __pow__(self, iterator):
        return self.__call__(iterator)

    def __call__(self, iterator):
        iterator.__iter__()
        print(str(next(iterator)))
        return self


class ItemModifier:
    """

    Base class for operators on arbitrary objects which may serve as items
    of iterators.

    The class is the base class of many "predefined" modifiers, but also has
    but can also be used directly. It is initialized with a function operating
    on items:

    ::

import cbc.nlp.base        >>> import cbc.nlp.pipeline as pipeline
        >>> dublicate = pipeline.ItemModifier(f=lambda l : l * 2)
        >>> m = dublicate * cbc.nlp.base.TokenizeText()
        >>> m("Der Ball ist rund.")

        ['Der', 'Ball', 'ist', 'rund', '.', 'Der', 'Ball', 'ist', 'rund', '.']

    """

    @staticmethod
    def __create_call_function(f, is_tagged):
        if is_tagged:
            def cf(x):
                f_x0 = f(x[0])
                if f_x0 is not None:
                    return f_x0, x[1]
                else:
                    return None

            result = cf
        else:
            result = f
        return result

    def __init__(self, f=lambda x: x):
        """
        Initialize object with function operating on item

        :f (function): the function operating on the items
        """
        self.f = f

    def __call__(self, x):
        return self.f(x)

    def __mul__(self, other):
        return MulItemModifier(self, other)

    def __pow__(self, other):
        return self.apply_to_iterator(other)

    def apply_to_iterator(self, iterator):
        cf = ItemModifier.__create_call_function(self.f, iterator.is_tagged)

        def generator():
            for x in iterator:
                if x is not None:
                    x = cf(x)
                if x is not None:
                    yield x
        return Iterator(generator, iterator.is_tagged)


class MulItemModifier(ItemModifier):
    """
    Class used _internally_ to *compose* two ItemModifiers
    """

    def __init__(self, left, right):
        """
            Args:

                :left (ItemModifier): left side of composition

                :right (ItemModifier): right side of composition
        """
        self.left = left
        self.right = right

        def f(x):
            return self.left.f(self.right.f(x))
        super(MulItemModifier, self).__init__(f=f)

    def __mul__(self, other):
        return MulItemModifier(self, other)

    def __pow__(self, other):
        return self.apply_to_iterator(other)


class FileSourceGenerator(BaseGenerator):
    def __init__(
            self,
            source_files,
            log_freq=1000,
            is_tagged=False,
            tag_rule=0,  # 0 = "filename", 1 = "number"
            content_handler=None,
            base_folder='.',
            file_type=str
        ):
        self.sourceFiles = source_files
        self.logFreq = log_freq
        self.tag_rule = tag_rule
        self.num_source_files = len(self.sourceFiles)
        if content_handler is None:
            self.contentHandler = content.FileSystemContentHandler(base_folder=base_folder)
        else:
            self.contentHandler = content_handler
        logger.info("num_source_files : %i" % self.num_source_files)

        if file_type == str:
            def get_object(prefix, key):
                return self.contentHandler.get_text(key, prefix=prefix)
        elif file_type == bytes:
            def get_object(prefix, key):
                return self.contentHandler.get_bytes(key, prefix=prefix)

        self.get_object = get_object
        super(FileSourceGenerator, self).__init__(is_tagged=is_tagged)

    def __call__(self):
        do_tag = None
        if self.is_tagged:
            if self.tag_rule == 0:
                def do_tag(res_, p_, f_, _):
                    return res_, [p_, f_]
            elif self.tag_rule == 1:
                def do_tag(res_, _, __, n_):
                    return res_, [n_]
        else:
            def do_tag(res_, _, __, ___):
                return res_
        n = 0
        for ref in self.sourceFiles:
            if isinstance(ref, tuple):
                (prefix, key) = ref
            elif isinstance(ref, str):
                prefix, key = "", ref
            try:
                result = self.get_object(prefix, key)
                if n % self.logFreq == 0:
                    logger.info("xml out=%i, read=%i, (%s / %s)" % (n, self.num_source_files, prefix, key))
                yield do_tag(result, prefix, key, n)
                n += 1
            except IOError:
                logger.error("could not read %s in %s" % (key, prefix), exc_info=True)


class XmlParser(ItemModifier):
    def __init__(
            self,
            content_tag="content",
            min_text_length=10
        ):
        self.contentTag = content_tag
        self.minTextLength = min_text_length
        def f(xml_string):
            result = None
            try:
                xml = eT.fromstring(xml_string)
                content = " ".join([c.text for c in xml.findall("./" + self.contentTag) if c.text is not None]).strip()
                xml.clear()
                if len(content) >= self.minTextLength:
                    result = content
            except IOError:
                logger.error("could not parse %s:\n" % xml_string, exc_info=True)
            return result

        super(XmlParser, self).__init__(f=f)


class Merge(IteratorModifier):
    def __init__(self, append_number_to_tag=False):
        self.append_number_to_tag = append_number_to_tag

    def gen_info_from_input(self, other):
        iters = []
        weights = []
        if (isinstance(other, tuple) or isinstance(other, list)) and len(other) >= 2:
            for o in other:
                iter_, weight = self.gen_info_from_list_item(o)
                iters.append(iter_)
                weights.append(weight)
        else:
            raise Exception("Right side of Merge has to be 'tuple' or 'list' of length >= 2")
        return iters, weights

    @staticmethod
    def gen_info_from_list_item(item):
        weight = 1.0
        if isinstance(item, tuple):
            iterator = item[0]
            if len(item) > 1:
                weight = item[1]
            if not (isinstance(weight, numbers.Number) and weight > 0.0):
                raise Exception("MergeTwo : Object %s is no positive number" % str(weight))
        else:
            iterator = item
        return iterator, weight

    def __call__(self, other):
        iters, weights = self.gen_info_from_input(other)
        steps = [1.0 / w for w in weights]
        tags = [i.is_tagged for i in iters]
        if all(tags) != any(tags):
            raise (
                Exception(
                    "For 'Merge' : Either all or none of Iterators on the right side must be tagged !"
                )
            )
        is_tagged = all(tags)
        if is_tagged and self.append_number_to_tag:
            def mask_output(x, i):
                x[1].append(i)
                return x
        else:
            def mask_output(x, _):
                return x

        def generator():
            counts = {i: s for i, s in enumerate(steps)}
            for i in iters:
                i.__iter__()
            items = [True] * len(iters)
            while any(items):
                next_index = min(counts, key=counts.get)
                if items[next_index]:
                    try:
                        next_item = next(iters[next_index])
                        items[next_index] = True
                        yield mask_output(next_item, next_index)
                    except StopIteration:
                        logger.debug("iter %i finished" % next_index)
                        items[next_index] = False
                counts[next_index] += steps[next_index]

        return Iterator(generator, is_tagged=is_tagged)


class Subset(IteratorModifier):
    def __init__(self, output_from=0, output_until=-1, distance=1, output_length=-1):
        self.outputFrom = output_from
        self.outputUntil = output_until
        self.distance = distance
        self.outputLength = output_length
        super(Subset, self).__init__()

    def __call__(self, iterator):
        def generator():
            n = 0
            out = 0
            for t in iterator:
                if 0 <= self.outputUntil <= n or 0 <= self.outputLength <= out:
                    break
                if n % self.distance == 0 and n >= self.outputFrom:
                    yield t
                    out += 1
                n += 1

        return Iterator(generator, is_tagged=iterator.is_tagged)


class Repeat(IteratorModifier):
    def __init__(self, total_repeats=1, total_items=None):
        self.total_repeats = total_repeats
        self.total_items = total_items

    def __call__(self, iterator):
        if self.total_items is not None:
            def generator():
                n = 0
                r = 0
                while n < self.total_items:
                    for i in iterator:
                        if n >= self.total_items:
                            break
                        n += 1
                        yield i
                    r += 1
                    logger.debug("Repeat - repeats=%i, items=%i" % (r, n))

            result = Iterator(generator, is_tagged=iterator.is_tagged)
        elif self.total_repeats is not None:
            def generator():
                n = 0
                r = 0
                while r < self.total_repeats:
                    for i in iterator:
                        n += 1
                        yield i
                    r += 1
                logger.debug("Repeat - repeats=%i, items=%i" % (r, n))

            result = Iterator(generator, is_tagged=iterator.is_tagged)
        else:
            raise Exception("Either 'total_items' or 'total_repeats' has to be not None")
        return result


class ListGenerator(BaseGenerator):
    def __init__(self, input_list, is_tagged=False):
        self.input_list = input_list
        super(ListGenerator, self).__init__(is_tagged=is_tagged)

    def __call__(self):
        if self.is_tagged:
            for d in enumerate(self.input_list):
                yield d[1], [d[0]]
        else:
            for d in self.input_list:
                yield d


class Untag(IteratorModifier):
    def __call__(self, iterator):
        if not iterator.is_tagged:
            raise Exception(
                "Untag: 'iterator' is not tagged - 'Untag' expects a tagged iterator and untags it."
            )

        def generator():
            for x in iterator:
                yield x[0]

        return Iterator(generator, is_tagged=False)


class RandomStringsGenerator(ListGenerator):
    def __init__(self, number_of_docs=10, length_of_words=5, number_of_words=15, is_tagged=False):
        def gen_word():
            all_letters = string.ascii_lowercase + string.ascii_uppercase
            lc_letters = string.ascii_lowercase
            return random.choice(all_letters) + \
                ''.join(random.choice(lc_letters) for _ in range(length_of_words - 1))

        def gen_doc():
            d = ' '.join(gen_word() for _ in range(number_of_words))
            return d[0].upper() + d[1:] + "."

        my_list = [gen_doc() for _ in range(number_of_docs)]
        super(RandomStringsGenerator, self).__init__(my_list, is_tagged=is_tagged)