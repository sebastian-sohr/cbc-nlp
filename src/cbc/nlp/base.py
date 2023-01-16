import ast
import codecs
import string
from collections import Counter

import spacy
import nltk
import re

from cbc.pipeline import \
    ItemModifier, IteratorModifier, Iterator, IteratorConsumer, LineSourceIterator, STANDARD_SEPARATOR
from nltk.tokenize import TreebankWordTokenizer
import logging

logger = logging.getLogger('cbc.nlp.base')

nltk.download('stopwords')

STANDARD_STOPWORD = nltk.corpus.stopwords.words('german')
STANDARD_FILTER_SYMBOLS = (
    '|', '*', '``', "''", '“', '„', '–', '-', '"', ')', '(', "'", ".", ",", '`', ":", "?", ";",
    "‘", "{", "}", "#", "&", "!", "]", "[", "%", "−", "..."
)

RE_NUMBER = re.compile(r"^\d+[.,eE]?\d*?$")
RE_SINGLE_LETTER = re.compile(r"^\w$")
RE_REPLACE_SPACE_CHARS = re.compile(r'[|\"/()—]')
RE_REMOVE_CHARS = re.compile(r"[\\'\-]")

RESTR_STD_PARAGRAPH_DEL = r"\s*\n\s*\n\s*"
"""
Standard paragraph delimiter: At least two newlines which may include and be surrounded by
further arbitrary space
"""

RE_WHITESPACE = re.compile(r"\s+")

LEMMATIZE_MAX_SIZE = 10000

LEMMATIZE_MAX_CHUNK_SIZE = 100000

VOWELS = "aeiouäöüyAEIOUÄÖÜY"
CONSONANTS = "bcdfghjklmnpqrstvwxzBCDFGHJKLMNPQRSTVWXY"


def split_into_chunks(text, max_chunk_length=LEMMATIZE_MAX_CHUNK_SIZE):
    """
    Split a text in chunks of given maximum length splitting only at white space
    (leaving words intact)
    """
    l_ = len(text)
    i = 0
    j = l_
    chunks = []
    while i < l_:
        if j - i > max_chunk_length:
            j = text[0:i + max_chunk_length].rfind(" ")
        if j > i:
            chunks.append(text[i:j])
            i = j
            j = l_
        else:
            break
    return chunks


class Lower(ItemModifier):
    """
    Expects a list of strings as item.
    Transforms each member of the list to lower case.
    """

    def __init__(self):
        """
        (No arguments allowed.)
        """
        super(Lower, self).__init__(
            f=lambda tokens: [t.lower() for t in tokens]
        )


class ReSub(ItemModifier):
    def __init__(self, reg_ex_list, replace):
        my_re_list = tuple([re.compile(reg_ex) for reg_ex in reg_ex_list])

        def f(w):
            x = w
            for my_re in my_re_list:
                x = my_re.sub(replace, x)
            return x

        super(ReSub, self).__init__(f=f)


class ReSplit(ItemModifier):
    def __init__(self, reg_ex):
        my_re = re.compile(reg_ex)
        super(ReSplit, self).__init__(
            f=lambda t: my_re.split(t)
        )


class Append(ItemModifier):
    def __init__(self, append="_DE"):
        self.append = append
        super(Append, self).__init__(
            f=lambda tokens: [t + self.append for t in tokens]
        )


class LowerAppend(ItemModifier):
    def __init__(self, append="_DE"):
        self.append = append

        def f(tokens):
            return [t.lower() + self.append for t in tokens]
        super(LowerAppend, self).__init__(f=f)


class IsNLText(ItemModifier):
    """
    Check whether a string consist of Natural Language (NL) Text using
    heuristics on distribution of characters.

    Kwargs:
        :lb_vows_by_letters (float, default=0.25): lower bound on "vowels by letters"
        :ub_vows_by_letters (float, default=0.53): upper bound on "vowels by letters"
        :lb_letters_by_chars (float, default=0.67): lower bound on "letters by all chars"
        :ub_spaces_by_chars (float, default=0.2): lower bound on "spaces by all chars"
        :ub_digits_by_chars (float, default=0.2): lower bound on "digits by all chars"
    """

    def __init__(self,
                 lb_vows_by_letters=0.25,
                 ub_vows_by_letters=0.53,
                 lb_letters_by_chars=0.67,
                 ub_spaces_by_chars=0.2,
                 ub_digits_by_chars=0.2
                 ):
        self.lb_vows_by_letters = lb_vows_by_letters
        self.ub_vows_by_letters = ub_vows_by_letters
        self.lb_letters_by_chars = lb_letters_by_chars
        self.ub_spaces_by_chars = ub_spaces_by_chars
        self.ub_digits_by_chars = ub_digits_by_chars

        def f(w):
            dist = Counter(w)
            chars = len(w)
            vows = sum([dist.get(c) for c in VOWELS if c in dist])
            letters = sum([dist.get(c) for c in string.ascii_letters if c in dist])
            spaces = dist.get(" ", 0)
            digits = sum([dist.get(c) for c in string.digits if c in dist])
            result = None
            if \
                    chars > 0 and \
                    letters > 0 and \
                    self.ub_vows_by_letters > vows / letters > self.lb_vows_by_letters and \
                    letters / chars > self.lb_letters_by_chars and \
                    self.ub_spaces_by_chars > spaces / chars and \
                    self.ub_digits_by_chars > digits / chars:
                result = w
            return result

        super(IsNLText, self).__init__(f=f)


class LemmatizeModifier(ItemModifier):
    def __init__(self,
                 lemmatizer=spacy.load("de_core_news_sm"),
                 chunksize=LEMMATIZE_MAX_SIZE
                 ):
        self.lemmatizer = lemmatizer
        self.chunksize = chunksize

        def f(tokens):
            result = [
                t.lemma_ for i in range(0, len(tokens), self.chunksize)
                for t in self.lemmatizer(
                    " ".join(tokens[i: i + self.chunksize])
                )
            ]
            return result
        super(LemmatizeModifier, self).__init__(f=f)


class Remove(ItemModifier):
    def __init__(self,
                 stopwords=STANDARD_STOPWORD,
                 filter_function=lambda w: RE_NUMBER.match(w) is None and RE_SINGLE_LETTER.match(w) is None,
                 filter_symbols=STANDARD_FILTER_SYMBOLS
                 ):
        self.stopwords = stopwords
        self.filter_function = filter_function
        self.filter_symbols = list(filter_symbols)
        self.ff = None
        self.create_ff()
        super(Remove, self).__init__(
            f=lambda tokens: list(filter(self.ff, tokens))
        )

    def create_ff(self):
        self.ff = \
            lambda w: self.filter_function(w) and w.lower() not in self.stopwords + self.filter_symbols

    def add_stopwords(self, a_list):
        self.stopwords = self.stopwords + a_list
        return self

    def add_filter_symbols(self, a_list):
        self.filter_symbols = self.filter_symbols + a_list
        return self


def tokenize_text(text, re_replace_space_chars=RE_REPLACE_SPACE_CHARS):
    t = text
    if re_replace_space_chars is not None:
        t = re_replace_space_chars.sub(" ", text)
    return TreebankWordTokenizer().tokenize(t)


class TokenizeText(ItemModifier):
    def __init__(self,
                 re_replace_space_chars=RE_REPLACE_SPACE_CHARS
                 ):
        self.re_replace_space_chars = re_replace_space_chars

        def f(text):
            t = text
            if self.re_replace_space_chars is not None:
                t = self.re_replace_space_chars.sub(" ", text)
            return TreebankWordTokenizer().tokenize(t)

        super(TokenizeText, self).__init__(f=f)


class LemmaTokenizeText(ItemModifier):
    def __init__(self,
                 lemmatizer=spacy.load("de_core_news_sm"),
                 max_chunk_length=LEMMATIZE_MAX_CHUNK_SIZE,
                 re_replace_space_chars=RE_REPLACE_SPACE_CHARS,
                 re_remove_chars=RE_REMOVE_CHARS
                 ):
        self.lemmatizer = lemmatizer
        self.maxChunkLength = max_chunk_length
        self.re_replace_space_chars = re_replace_space_chars
        self.re_remove_chars = re_remove_chars

        def f(text):
            txt = text
            if self.re_replace_space_chars is not None:
                txt = self.re_replace_space_chars.sub(" ", txt)
            if self.re_remove_chars is not None:
                txt = self.re_remove_chars.sub("", txt)
            txt = RE_WHITESPACE.sub(" ", txt)
            chunks = split_into_chunks(txt, self.maxChunkLength)
            return [t.lemma_.strip() for chunk in chunks for t in self.lemmatizer(chunk)]

        super(LemmaTokenizeText, self).__init__(f=f)


class SplitText(IteratorModifier):
    def __init__(self,
                 re_text_separator=r"\s*\n\s*\n\s*",
                 min_text_length=0,
                 do_trim_text=True
                 ):
        self.re_text_separator = re.compile(re_text_separator)
        self.minTextLength = min_text_length
        self.do_trim_text = do_trim_text

    def __call__(self, other):
        if other.is_tagged:
            def generator():
                n = 0
                for text in other:
                    p_c = 0
                    paragraphs = self.re_text_separator.split(text[0].strip())
                    for p in paragraphs:
                        if self.do_trim_text:
                            p = p.strip()
                        if len(p) >= self.minTextLength:
                            yield p, text[1] + [tuple(text[1] + [p_c])]
                        n += 1
                        p_c += 1
        else:
            def generator():
                n = 0
                for text in other:
                    paragraphs = self.re_text_separator.split(text.strip())
                    for p in paragraphs:
                        if self.do_trim_text:
                            p = p.strip()
                        if len(p) >= self.minTextLength:
                            yield p
                        n += 1
        return Iterator(generator, is_tagged=other.is_tagged)


class LineSourceTokenizer(LineSourceIterator):
    def __init__(self,
                 input_file,
                 tokenizer=TokenizeText(),
                 **kwargs
                 ):
        self.tokenizer = tokenizer
        super(LineSourceTokenizer, self).__init__(input_file, **kwargs)
        self.handle_first_line()
        if self.is_tagged:
            def get_line(line):
                ll = line.split(self.tag_separator)
                return tokenizer(ll[0]), ast.literal_eval(ll[1])
        else:
            def get_line(line):
                return tokenizer(line)
        self.get_line = get_line


class Re(ItemModifier):
    def __init__(self, reg_ex):
        my_re = re.compile(reg_ex)
        super(Re, self).__init__(
            f=lambda t: list(filter(lambda w: my_re.match(w) is None, t))
        )


class MinMaxTokens(IteratorModifier):
    def __init__(self, min_tokens=1, max_tokens=-1):
        self.minTokens = min_tokens
        self.maxTokens = max_tokens

    def __call__(self, iterator):
        if self.maxTokens >= 0:
            if iterator.is_tagged:
                def generator():
                    for t in iterator:
                        if self.minTokens <= len(t[0]) <= self.maxTokens:
                            yield t
            else:
                def generator():
                    for t in iterator:
                        if self.minTokens <= len(t) <= self.maxTokens:
                            yield t
        else:
            if iterator.is_tagged:
                def generator():
                    for t in iterator:
                        if len(t[0]) >= self.minTokens:
                            yield t
            else:
                def generator():
                    for t in iterator:
                        if len(t) >= self.minTokens:
                            yield t
        return Iterator(generator, is_tagged=iterator.is_tagged)


class TokensToFile(IteratorConsumer):
    def __init__(self,
                 filename,
                 output_tag=True,
                 tag_separator=STANDARD_SEPARATOR,
                 output_encoding='utf-8',
                 input_type=list
                 ):
        self.filename = filename
        self.output_tag = output_tag
        self.tag_separator = tag_separator
        self.output_encoding = output_encoding
        self.input_type = input_type

    def __call__(self, iterator):
        if iterator.is_tagged:
            if self.output_tag:
                if self.input_type == list:
                    def to_str(t_):
                        return " ".join(t_[0]) + self.tag_separator + str(t_[1])
                elif self.input_type == str:
                    def to_str(t_):
                        return t_[0] + self.tag_separator + str(t_[1])
                else:
                    raise (TypeError, "Unsupported input type %i" % str(self.input_type))
            else:
                if self.input_type == list:
                    def to_str(t_):
                        return " ".join(t_[0])
                elif self.input_type == str:
                    def to_str(t_):
                        return t_[0]
                else:
                    raise (TypeError, "Unsupported input type %i" % str(self.input_type))
        else:
            if self.input_type == list:
                def to_str(t_):
                    return " ".join(t_)
            elif self.input_type == str:
                def to_str(t_):
                    return t_
            else:
                raise (TypeError, "Unsupported input type %i" % str(self.input_type))
        n = 0
        try:
            if self.output_encoding is None:
                file = codecs.open(self.filename, 'w')
            else:
                file = codecs.open(self.filename, 'w', self.output_encoding)
            for t in iterator:
                n += 1
                file.write(to_str(t))
                file.write("\n")
            file.close()
        except IOError:
            s = "could not write to file '%s'" % self.filename
            logger.error(s, exc_info=True)
        self.number = n
        return self


class CountTokens(IteratorConsumer):
    def __init__(self, word_counter=None, tagged_counter=None):
        if word_counter is None:
            self.word_counter = Counter()
        else:
            self.word_counter = word_counter
        if tagged_counter is None:
            self.tagged_counter = Counter()
        else:
            self.tagged_counter = tagged_counter

    def __call__(self, iterator):
        if iterator.is_tagged:
            def count(tokens_):
                self.word_counter.update(tokens_[0])
                self.tagged_counter.update([(w, ";".join([str(t) for t in tokens_[1]])) for w in tokens_[0]])
        else:
            def count(tokens_):
                self.word_counter.update(tokens_)
        for tokens in iterator:
            count(tokens)
        return self
