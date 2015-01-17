BOT_NAME = 'amazon_wishlist'

SPIDER_MODULES = ['wishlist_scraper.spiders']
CONCURRENT_REQUESTS = 1
HTTPCACHE_ENABLED = True
SPIDER_MIDDLEWARES = {
    'scrapy.contrib.downloadermiddleware.cookies.CookiesMiddleware': '100',
}
COOKIES_ENABLED = True
