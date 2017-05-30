BOT_NAME = 'amazon_wishlist'

SPIDER_MODULES = ['wishlist_scraper.spiders']
CONCURRENT_REQUESTS = 1
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 18 * 60 * 60
ITEM_PIPELINES = {
    'wishlist_scraper.pipelines.LibraryAvailabilityPipeline': 100,
}
SPIDER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.cookies.CookiesMiddleware': 100,
}
COOKIES_ENABLED = True
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:49.0) Gecko/20100101 Firefox/49.0'
