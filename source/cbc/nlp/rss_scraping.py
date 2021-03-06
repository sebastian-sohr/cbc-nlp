"""
cbc.nlp.rss_scraping
=======================

Read and store content from rss feeds
"""

import hashlib
import logging
import random
import re
import time
import xml.etree.ElementTree as Et
from urllib.request import Request, urlopen
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import ParseError
from tika import parser as tk_parser
import ssl
import gc

ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger('cbc.nlp.rss_scraping')


class RssScraper:
    """
    Class responsible for handling a list of rss feeds which are semantically related and which are handled
    the same was
    """

    def __init__(
        self,
        urls=(),
        extractor=None,
        time_wait_seconds=3600,
        time_wait_between_items=0.01,
        prefix="",
        content_handler=None,
        timeout=None,
        raw_content_handler=None,
        num_of_loops=1
    ):
        logger.info("Initializing scraper: '%s'" % prefix)
        self.urls = list(urls)
        self.extractors = {'default': extractor}
        self.knownItems = {}
        self.timeWaitSeconds = time_wait_seconds
        self.userAgent = 'Mozilla/5.0'
        self.timeWaitBetweenItems = time_wait_between_items
        self.prefix = prefix
        self.timeout = timeout
        self.raw_content_handler = raw_content_handler
        self.content_handler = content_handler
        self.num_of_loops = num_of_loops
        if self.content_handler is not None:
            logger.info("Reading known items for '%s'." % prefix)
            self.knownItems = {f: "x" for f in content_handler.list(self.prefix)}
            logger.info("Ready: Reading known items for '%s', number: %i ." % (prefix, len(self.knownItems)))

    def get_item(self, a_key):
        """
        Read a single rss item from a file

        Args:
            :a_file_name str: full name (including path) of file containing the item
        """
        result = Et.fromstring(self.content_handler.get_text(a_key, prefix=self.prefix))
        return result

    def save_item(self, an_item, a_key, item_url="-"):
        if self.content_handler is not None:
            self.content_handler.save_text(
                a_key,
                Et.tostring(an_item, encoding='utf-8', method='xml').decode('utf-8'),
                prefix=self.prefix
            )

    def save_raw(self, bytes, a_key, item_url="-"):
        if self.raw_content_handler is not None:
            self.raw_content_handler.save_bytes(
                a_key,
                bytes,
                prefix=self.prefix
            )

    def pull_once(self):
        num_all = 0
        num_new = 0
        for i in self.get_all_items():
            num_all = num_all + 1
            l_ = RssScraper.get_link_from_item(i)
            key = RssScraper.get_md5_hash(l_)
            file_name =  key + ".xml"
            raw_bytes = None
            if file_name not in self.knownItems:
                found_content = False
                for aLanguage in self.extractors:
                    raw_bytes_ = RssScraper.add_content_to_item(
                        i,
                        self.extractors[aLanguage],
                        aLanguage,
                        time_wait=self.timeWaitBetweenItems,
                        timeout=self.timeout
                    )
                    if raw_bytes is None and raw_bytes_ is not None:
                        raw_bytes = raw_bytes_
                    found_content = found_content or (raw_bytes_ is not None)
                if found_content:
                    num_new = num_new + 1
                    if self.content_handler is not None:
                        self.knownItems[file_name] = "x"
                    else:
                        self.knownItems[file_name] = i
                    self.save_item(i, file_name, item_url=l_)
                    self.save_raw(raw_bytes, key + ".raw", item_url=l_)
        logger.info("%s : Inserted %i new items (from %i)" % (self.prefix, num_new, num_all))

    def poll(self, num_of_loops=None, time_wait_seconds=None):
        i = 0
        if num_of_loops is None:
            num_of_loops = self.num_of_loops
        if time_wait_seconds is None:
            time_wait_seconds = self.timeWaitSeconds
        while i != num_of_loops:
            logger.info("Scraper %s, starting round %i / %i" % (self.prefix, i+1, num_of_loops))
            self.pull_once()
            logger.info("Scraper %s, round %i / %i, sleeping %i seconds" % (self.prefix, i+1, num_of_loops, time_wait_seconds))
            if i+1 == num_of_loops:
                del self.knownItems
                gc.collect()
            time.sleep(time_wait_seconds)
            logger.info("Ready: Scraper %s, round %i / %i" % (self.prefix, i+1, num_of_loops))
            i = i+1

    def get_all_items(self):
        rss_docs = [
            RssScraper.append_channel_info_to_items(
                RssScraper.parse_xml_from_url(
                    url,
                    timeout=self.timeout
                )
            )
            for url in self.urls
        ]
        result = [i for doc in rss_docs if doc is not None for i in doc.findall('./channel/item')]
        return result

    def get_all_item_links(self):
        return [RssScraper.get_link_from_item(i) for i in self.get_all_items()]

    @staticmethod
    def add_content_to_item(an_item, an_extractor, language='default', time_wait=0.0, timeout=None):
        link_url = RssScraper.get_link_from_item(an_item)
        content_ = None
        html = None
        if link_url is not None:
            time.sleep(time_wait)
            html = RssScraper.read_doc_from_url(link_url, timeout=timeout)
            if html is not None:
                old_content = an_item.find('content[@language="' + language + '"]')
                if old_content is not None:
                    an_item.remove(old_content)
                a_text = an_extractor(html)
                content_ = Element("content")
                if language is not None:
                    content_.set('language', language)
                content_.text = a_text
                an_item.append(content_)
        return html

    @staticmethod
    def get_link_from_item(an_item):
        link = an_item.find('link')
        link_url = None
        if link is not None:
            link_url = link.text
        return link_url

    @staticmethod
    def get_md5_hash(s):
        m = hashlib.md5()
        result = None
        try:
            m.update(s.encode('utf-8', errors='backslashreplace'))
            result = m.hexdigest()
        except UnicodeError:
            logger.exception("could not encode " + s)
            print("could not encode " + s)
        return result

    @staticmethod
    def append_channel_info_to_items(a_doc):
        if a_doc is not None:
            the_channel = a_doc.findall('./channel')[0]
            channel_elem = Element("channel")
            for tagName in ['title', 'description', 'link', 'language']:
                tag = the_channel.find(tagName)
                if tag is not None:
                    channel_elem.append(tag)
            for i in a_doc.findall('./channel/item'):
                i.append(channel_elem)
        return a_doc

    @staticmethod
    def read_doc_from_url(an_url, timeout=None):
        result = None
        try:
            req = Request(an_url, headers={'User-Agent': 'Mozilla/5.0'})
            if timeout is not None:
                result = urlopen(req, timeout=timeout).read()
            else:
                result = urlopen(req).read()
        except IOError:
            logger.error("could not read from %s" % an_url)
            print("could not read from %s" % an_url)
        return result

    @staticmethod
    def parse_xml_from_url(an_url, timeout=None):
        result = None
        if an_url is not None:
            doc = RssScraper.read_doc_from_url(an_url, timeout=timeout)
            if doc is not None:
                try:
                    result = Et.fromstring(RssScraper.read_doc_from_url(an_url, timeout=timeout))
                except ParseError:
                    logger.error("Could not parse xml from '%s'" % an_url)
            else:
                logger.warning("Could not retrieve doc from url\n %s" % an_url)
        return result

    def reload_content(self, a_file_name):
        the_item = self.get_item(a_file_name)
        if the_item is not None:
            for aLanguage in self.extractors:
                RssScraper.add_content_to_item(the_item, self.extractors[aLanguage], aLanguage)
        return the_item

    def regenerate_content(self, a_file_list):
        for f in a_file_list:
            item = self.reload_content(f)
            self.save_item(item, f)


def get_text_from_pdf_buffer(some_bytes):
    result = None
    if some_bytes is not None and some_bytes.startswith(b'%PDF'):
        text = tk_parser.from_buffer(some_bytes)['content']
        result = re.sub(r'(\w)- *\n([a-zäüö])', r'\1\2', text).strip()
    return result


def create_rss_file_list(content_provider, channels, do_random_shuffle=True):
    """
    Create a list of xml files which are stored within the structure of the "rss grabber".

    Args:
        :database_dir (str): the directory which has the "channel directories" as its subfolders.

        :channels (list of str): the list of subfolders of the "database_dir" which contain the xml files
            which are considered as content items

    """
    files = [
        (prefix, key) for prefix in channels for key in content_provider.list(prefix=prefix) if key.endswith(".xml")
    ]
    if do_random_shuffle:
        random.shuffle(files)
    return files


def load_xml_doc(content_provider, key, prefix=""):
    """
    Read xml object from a text provided by a content_provider

    Args:
        :filename (str): the full filename of a file containing an xml file

    Returns:
        The xml object of type xml.etree.ElementTree.Element

    """
    return Et.fromstring(content_provider.get_text(key, prefix=prefix))


def get_texts_from_item(key, prefix=""):
    """
    Read the content of the tags "title", "description", "content" from an xml file (typically in the "item" format)

    Args:
        :filename (str): the full filename of a file containing an xml file

    Returns:
        :(title, description, content) (str, str, str): the respective tags of the xml file

    """
    xml = load_xml_doc(key, prefix=prefix)
    try:
        content_ = " ".join([c.text for c in xml.findall("./" + "content") if c.text is not None]).strip()
    except (ParseError, TypeError):
        content_ = ""
    try:
        title = " ".join([c.text for c in xml.findall("./" + "title") if c.text is not None]).strip()
    except (ParseError, TypeError):
        title = ""
    try:
        description = " ".join([c.text for c in xml.findall("./" + "description") if c.text is not None]).strip()
    except (ParseError, TypeError):
        description = ""
    return title, description, content_
