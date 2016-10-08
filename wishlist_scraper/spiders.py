#!/usr/bin/env python -tt

import copy
import _gdbm
import itertools
import json
import os
import re
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import bottlenose
import lxml
import scrapy.http
import scrapy.selector
import scrapy.spiders
import slimit
import slimit.parser
import slimit.visitors.nodevisitor

from .loaders import (
    WishlistItemLoader, WishlistItemImageLoader,
    WishlistItemAmazonPricesLoader, LibraryAvailabilityLoader)
from .utils import qualified_url


class WishlistSpider(scrapy.spiders.Spider):
    name = 'wishlist'
    start_urls = [
        'https://www.amazon.com/registry/wishlist/{}'.format(
            os.environ['WISHLIST_ID'])]

    def __init__(self, *args, **kwargs):
        super(WishlistSpider, self).__init__(*args, **kwargs)

        self.amazon_api_cache = _gdbm.open('amazon-api-cache.db', 'c')
        self.amazon = bottlenose.Amazon(
            os.environ['AWS_ACCESS_KEY_ID'],
            os.environ['AWS_SECRET_ACCESS_KEY'],
            os.environ['AMAZON_AFFILIATE_ID'],
            ErrorHandler=lambda err: self.amazon_api_error_handler(err),
            CacheWriter=lambda url, data: self.amazon_api_cache_write(
                url, data),
            CacheReader=lambda url: self.amazon_api_cache_read(url))

    def amazon_api_error_handler(self, err):
        exc = err['exception']
        if isinstance(exc, HTTPError) and exc.code == 503:
            time.sleep(1)
            return True

        return False

    def amazon_api_cache_write(self, url, data):
        self.amazon_api_cache[url] = data

    def amazon_api_cache_read(self, url):
        if url not in self.amazon_api_cache:
            return None
        return self.amazon_api_cache[url]

    def parse(self, response):
        for item in self.parse_wishlist_page(response):
            yield item

        pages = response.css('#wishlistPagination')[0].css('a::attr(href)')

        # The Wishlist page doesn't display all page numbers (i.e., it shows
        # '1 2 3 4 5 6 7 .. maxnum'), so determine the maximum page number
        # and build URLs iteratively until we reach it.
        max_page_num = 1
        template_page_url = response.url
        for page in pages:
            page_url = urlparse(qualified_url(response, page.extract()))
            qs = parse_qs(page_url.query)
            if 'page' not in qs:
                continue

            max_page_num = max(max_page_num, int(qs['page'][0]))
            template_page_url = page_url

        for page_num in range(2, max_page_num + 1):
            qs = parse_qs(template_page_url.query)
            qs['page'] = [page_num]

            page_url = list(template_page_url)
            page_url[4] = urlencode(dict([(k, qs[k][0]) for k in qs]))
            page_url = urlunparse(page_url)

            yield scrapy.http.Request(
                page_url, meta={'wishlist_page': page_num},
                callback=self.parse_wishlist_page)

    def parse_wishlist_page(self, response):
        items = response.css('div::attr(data-item-prime-info)')

        for i, item in enumerate(items):
            info = json.loads(item.extract())

            product_info = self.amazon.ItemLookup(
                ItemId=info['asin'], ResponseGroup='Medium')

            sel = scrapy.selector.Selector(text=product_info, type='xml')
            sel.register_namespace(
                'aws',
                'http://webservices.amazon.com/AWSECommerceService/2013-08-01')

            item_loader = WishlistItemLoader(selector=sel)
            item_loader.add_value(
                'sort_key',
                '{}/{}'.format(response.meta.get('wishlist_page', 1), i))

            item_loader.add_xpath(
                'isbn', '//aws:ItemAttributes/aws:EISBN/text()')
            item_loader.add_xpath(
                'isbn', '//aws:ItemAttributes/aws:ISBN/text()')
            if not item_loader.get_output_value('isbn'):
                continue

            item_loader.add_xpath(
                'format', '//aws:ItemAttributes/aws:Format/text()')
            item_loader.add_xpath(
                'title', '//aws:ItemAttributes/aws:Title/text()')
            item_loader.add_xpath(
                'by', '//aws:ItemAttributes/aws:Author/text()')
            item_loader.add_xpath(
                'by', '//aws:ItemAttributes/aws:Creator/text()')
            item_loader.add_xpath(
                'by', '//aws:ItemAttributes/aws:Artist/text()')

            item_loader.add_xpath(
                'amazon_url', '//aws:Item/aws:DetailPageURL/text()')

            image = WishlistItemImageLoader(
                selector=sel.xpath('//aws:MediumImage'))
            image.add_xpath('url', 'aws:URL/text()')
            image.add_xpath('width', 'aws:Width/text()')
            image.add_xpath('height', 'aws:Height/text()')
            image.add_xpath('caption', '//aws:ItemAttributes/aws:Title/text()')
            item_loader.add_value('image', image.load_item())

            amazon_prices = WishlistItemAmazonPricesLoader(
                selector=sel.xpath('//aws:OfferSummary'))
            amazon_prices.add_xpath(
                'list', 'aws:ListPrice/aws:FormattedPrice/text()')
            amazon_prices.add_xpath('new_count', 'aws:TotalNew/text()')
            amazon_prices.add_xpath(
                'new_lowest_price',
                'aws:LowestNewPrice/aws:FormattedPrice/text()')
            amazon_prices.add_xpath('used_count', 'aws:TotalUsed/text()')
            amazon_prices.add_xpath(
                'used_lowest_price',
                'aws:LowestUsedPrice/aws:FormattedPrice/text()')
            item_loader.add_value('amazon_prices', amazon_prices.load_item())

            yield item_loader.load_item()


class LibrarySpider(scrapy.spiders.Spider):
    name = 'library'

    libraries = ['BRL', 'MLN']

    @classmethod
    def _unescape(cls, text):
        return lxml.html.fromstring(text).text

    @classmethod
    def _extract_script(cls, selector):
        return [
            re.sub(
                r'(<!--.*$)|(\s+-->.*$)', '',
                script.extract(), flags=re.MULTILINE)
            for script
             in selector.css('script::text')
        ]

    @classmethod
    def _extract_js_vars(cls, selector):
        parser = slimit.parser.Parser()

        js_vars = {}
        for script in cls._extract_script(selector):
            tree = parser.parse(script)
            js_vars.update({
                node.identifier.value: (
                    # Dispel leading/trailing quotes on string values.
                    node.initializer.value[1:-1]
                    if isinstance(node.initializer, slimit.ast.String)
                    else node.initializer.value)
                for node in slimit.visitors.nodevisitor.visit(tree)
                 if (isinstance(node, slimit.ast.VarDecl) and
                     isinstance(
                         node.initializer,
                         (slimit.ast.String, slimit.ast.Number)))
            })

        return js_vars

    @classmethod
    def _searchable_title(cls, title):
        title = re.sub(r'[:;]\s*[^:;]+$', '', title)
        title = re.sub(r'\s*\(.*\)$', '', title)
        return title

    @classmethod
    def _searchable_author(cls, author):
        author = re.sub(r'\s+Ph\.?\s*D\.?$', '', author)
        return author

    @classmethod
    def _build_BRL_url(cls, item, library):
        query_string = urlencode((
            ('custom_query', u'title:({}) AND contributor:({})'.format(
                cls._searchable_title(item['title']),
                cls._searchable_author(item.get('by', ''))).encode('utf-8')),
            ('searchscope', 'MBLN'),
            ('suppress', 'true'),
            ('custom_edit', 'false'),
        ), True)

        return 'http://bpl.bibliocommons.com/search?{}'.format(
            query_string)

    @classmethod
    def _build_HLS_url(cls, item, library):
        query_string = urlencode((
            ('func', 'find-c'),
            ('CCL_TERM', u'(WTN={} AND WAN={} AND WLG=eng)'.format(
                cls._searchable_title(item['title']),
                cls._searchable_author(item['by'])).encode('utf-8')),
            ('adjacent', 1),
        ), True)

        return 'http://lms01.harvard.edu/F/?{}'.format(query_string)

    @classmethod
    def _build_MLN_url(cls, item, library):
        query_string = urlencode((
            ('SEARCH', u't:({}) and a:({})'.format(
                cls._searchable_title(item['title']),
                cls._searchable_author(item.get('by', ''))).encode('utf-8')),
            ('searchscope', 1),
        ), True)

        return 'http://library.minlib.net/search/X?{}'.format(query_string)

    def start_requests(self):
        with open('wishlist.json') as items_fp:
            items = json.load(items_fp)

        for item, library in itertools.product(items, self.libraries):
            yield scrapy.http.Request(
                getattr(self, '_build_{}_url'.format(library))(
                    item, library),
                meta={'item': item},
                callback=getattr(
                    self, 'parse_{}_response'.format(library))
            )

    def parse_BRL_response(self, response):
        # http://bpl.bibliocommons.com/search?custom_query=identifier%3A(9780446573016)%20%20%20formatcode%3A(BK%20OR%20EBOOK%20)&search_scope=MBLN&suppress=true&custom_edit=false
        if 'No direct matches were found.' in response.body.decode():
            return

        for result in response.css('.listItem'):
            meta = copy.copy(response.meta)
            format = result.css('.format')[0].extract()

            if 'eBook' in format:
                search_string = 'digital_availability'
                callback = self.parse_item_BRL_ebook_availability

                meta['item_url'] = qualified_url(
                    response,
                    result.css('.jacketCoverLink').xpath('@href')[0].extract()
                )
            elif 'Book' in format:
                search_string = 'show_circulation'
                callback = self.parse_item_BRL_availability

                meta['item_url'] = qualified_url(
                    response,
                    result.xpath(
                        '//*[contains(@href, "item/show")]/@href')[0].extract()
                )
            else:
                continue

            availability_url = result.xpath(
                '//*[contains(@href, "{}")]/@href'.format(search_string))
            if not availability_url:
                continue

            availability_url = availability_url[0].extract()
            if 'eBook' in format:
                availability_url += '.json'

            yield scrapy.http.Request(
                qualified_url(response, availability_url),
                meta=meta, callback=callback)

    def parse_item_BRL_ebook_availability(self, response):
        decoded = json.loads(response.body.decode())

        # decoded['html'] for number of holds
        # <span class="label availability digital_availability"><span class="digital not_yet_available">Not Currently Available.</span><span class="holdposition">Holds: 7 holds on 8 Volumes</span></span>

        avail_item = LibraryAvailabilityLoader(selector=response)
        avail_item.add_value('item', response.meta['item'])
        avail_item.add_value('library', 'MBLN')
        avail_item.add_value('digital_url', response.meta['item_url'])
        avail_item.add_value('branch', 'INTERNET')
        avail_item.add_value('collection', '')
        avail_item.add_value('call_num', 'INTERNET')
        avail_item.add_value('available', str(decoded['available']))
        yield avail_item.load_item()

    def parse_item_BRL_availability(self, response):
        # http://bpl.bibliocommons.com//item/show_circulation/1598453075?search_scope=MBLN
        if not response.css('.branch'):
            return

        for branch in response.css('.branch'):
            available_at = branch.css('tbody tr')
            for row in available_at:
                if row.css('.note'):
                    continue

                avail_item = LibraryAvailabilityLoader(selector=row)
                avail_item.add_value('item', response.meta['item'])
                avail_item.add_value('library', 'MBLN')
                avail_item.add_value('catalog_url', response.meta['item_url'])
                avail_item.add_xpath('branch', 'td[1]/text()')
                avail_item.add_xpath('collection', 'td[2]/text()')
                avail_item.add_xpath('call_num', 'td[3]/text()')
                avail_item.add_xpath('available', 'td[4]/text()')
                yield avail_item.load_item()

    def parse_HLS_response(self, response):
        # http://hollisclassic.harvard.edu/F/?func=find-b&find_code=IBN&request=9780312272050
        js_vars = self._extract_js_vars(response)
        redirect_url = self._unescape(
            '{}{}'.format(js_vars['url'], js_vars['callback_url']))
        yield scrapy.http.Request(
            redirect_url, meta=response.meta,
            callback=self.parse_item_HLS_sso_redirect)

    def parse_item_HLS_sso_redirect(self, response):
        # <A HREF=http://lms01.harvard.edu:80/F/3JXTKP544E6B88MX7KBBLG2BKGTJNN4TVD8M8Y5BRL65FQE5R4-00988?func=item-global&doc_library=HVD01&doc_number=009100826&year=&volume=&sub_library=>Availability</A>
        url = response.css('a::attr("href")')[0].extract()
        redirect_url = qualified_url(response, self._unescape(url))
        yield scrapy.http.Request(
            redirect_url, meta=response.meta,
            callback=self.parse_item_HLS_item_list)

    def parse_item_HLS_item_list(self, response):
        # http://lms01.harvard.edu/F/4MPLXBRST48H83712RTD3UHGFJNUMN52X5978M9KLH3P3XQLEI-39748?func=find-c&CCL_TERM=%28WTN%3DBecoming+a+Manager+AND+WAN%3DLinda+A.+Hill%29&adjacent=1&pds_handle=GUEST
        if response.xpath('//a[text() = "Availability"]/@href'):
            for item in self.parse_item_HLS_item(response):
                yield item
                return

        available_at = response.xpath(
            '//a[text() = "Author"]/../../following-sibling::tr')
        if not available_at:
            return

        # Parse the recordLink variable's HTML <A> tag for the item's URL.
        js_vars = self._extract_js_vars(response)
        item_url = scrapy.selector.Selector(
            text=js_vars['recordLink'], type='html').css(
                'a::attr("href")')[0].extract()
        item_url = qualified_url(response, self._unescape(item_url))

        yield scrapy.http.Request(
            item_url, meta=response.meta, callback=self.parse_item_HLS_item)

    def parse_item_HLS_item(self, response):
        availability = response.xpath(
            '//a[text() = "Availability"]/@href')
        if not availability:
            # Hollis doesn't know about this item.
            return

        availability_url = availability[0].extract()
        yield scrapy.http.Request(
            availability_url, meta=response.meta,
            callback=self.parse_item_HLS_item_availability)

    def parse_item_HLS_item_availability(self, response):
        # http://lms01.harvard.edu:80/F/E3TTJIQAAJCMJL6RLU4BH9J4MIY3TEJ1JPLGA3MFA1HYVGJT36-11386?func=item-global&doc_library=HVD01&doc_number=013957901&year=&volume=&sub_library=
        available_at = response.xpath(
            '//th[text() = "Collection"]/../following-sibling::tr')
        for library in available_at:
            avail_item = LibraryAvailabilityLoader(selector=library)
            avail_item.add_value('item', response.meta['item'])
            avail_item.add_value('library', 'Harvard')
            avail_item.add_value('catalog_url', response.url)
            avail_item.add_xpath('branch', 'td[1]/text()')
            avail_item.add_xpath('collection', 'td[2]/text()')

            collection = avail_item.get_output_value('collection')
            if collection and 'depository' in collection.lower():
                avail_item.add_value('call_num', 'Depository')
            avail_item.add_xpath('call_num', 'td[3]/text()')

            js_vars = self._extract_js_vars(response)
            if 'checkout' not in js_vars:
                # http://lms01.harvard.edu/F/EICPLBCNJS2JIC3FYBSJF5KSN3RULBQX6S4SUBE67DPKR5T29D-20229?func=item-global&doc_library=HVD01&doc_number=014083018&year=&volume=&sub_library=%27
                # FIXME: online resource?
                return
            avail_item.add_value('available', js_vars['checkout'])

            yield avail_item.load_item()

    def parse_MLN_response(self, response):
        if '1 result found' in response.body.decode():
            for item in self.parse_item_MLN(response):
                yield item
                return

        for holding in response.css('.briefcitRow'):
            title_region = holding.css('.briefcitTitle')[0]

            if 'sound recording' in title_region.extract():
                continue

            media_type = holding.css('.briefcitMatType')[0].extract()
            if 'AUDIOBOOK' in media_type:
                continue
            if 'SPOKEN CD' in media_type:
                continue

            yield scrapy.http.Request(
                qualified_url(
                    response, title_region.css('a::attr(href)')[0].extract()),
                meta=response.meta,
                callback=self.parse_item_MLN)

    def parse_item_MLN(self, response):
        full_availability_url = response.xpath(
            '//form[contains(@action, "holdings")]/@action')
        # If a full availability form exists, use that since the
        # list on the item's page will be truncated.
        if full_availability_url:
            yield scrapy.http.Request(
                qualified_url(response, full_availability_url[0].extract()),
                meta=response.meta,
                callback=self.parse_item_MLN_item_full_availability)
            return

        for item in self.parse_item_MLN_item_full_availability(response):
            yield item

    def parse_item_MLN_item_full_availability(self, response):
        locations = response.css('.bibItemsEntry')
        for location in locations:
            avail_item = LibraryAvailabilityLoader(selector=location)
            avail_item.add_value('item', response.meta['item'])
            avail_item.add_value('library', 'Minuteman')
            avail_item.add_value('catalog_url', response.url)

            location_text = location.css('td:nth-child(1)')
            if 'INTERNET' in location_text[0].extract():
                branch = 'INTERNET'
                collection = ''
            else:
                location_text = ' '.join(
                    location_text.css('a::text').extract())
                if '/' in location_text:
                    location_components = location_text.split('/')
                    branch = location_components[:-1]
                    collection = location_components[-1]
                else:
                    branch = location_text
                    collection = ''
            avail_item.add_value('branch', branch)
            avail_item.add_value('collection', collection)

            available = ' '.join(
                location.css('td:nth-child(3)::text').extract())
            avail_item.add_value('available', available)

            if 'E-RESOURCE' in available:
                avail_item.add_value('call_num', 'E-RESOURCE')

                if 'Commonwealth eBook Collections' in response.css('.bibItemsEntry')[0].extract():
                    # Some electronic content is not available to all libraries.
                    # Links to http://www.mln.lib.ma.us/scripts/db_authorization.plx
                    continue

                bib_links = response.css('.bibLinks')
                if bib_links:
                    url = bib_links[0].css('a::attr(href)').extract()
                else:
                    url = response.xpath(
                        '//a[contains(text(), "Digital Media Catalog")]/@href'
                    ).extract()

                if not url:
                    continue

                avail_item.add_value(
                    'digital_url', qualified_url(response, url[0].strip())
                )
            else:
                avail_item.add_css('call_num', 'td:nth-child(2) a::text')

            yield avail_item.load_item()
