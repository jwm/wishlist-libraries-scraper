BOT_NAME = 'amazon_wishlist'

SPIDER_MODULES = ['wishlist_scraper.spiders']
CONCURRENT_REQUESTS = 1
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 18 * 60 * 60
SPIDER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.cookies.CookiesMiddleware': 100,
}
COOKIES_ENABLED = True
