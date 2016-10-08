from scrapy.loader.processors import (
    Compose, Join, MapCompose, TakeFirst)
from scrapy.item import Item, Field


class WishlistItemImage(Item):
    url = Field(output_processor=TakeFirst())
    width = Field(output_processor=TakeFirst())
    height = Field(output_processor=TakeFirst())
    caption = Field(output_processor=TakeFirst())


class WishlistItemAmazonPrices(Item):
    list = Field()
    new_count = Field()
    new_lowest_price = Field()
    used_count = Field()
    used_lowest_price = Field()


class WishlistItem(Item):
    isbn = Field()
    format = Field()
    title = Field()
    by = Field(output_processor=TakeFirst())
    amazon_url = Field()
    image = Field(output_processor=TakeFirst())
    amazon_prices = Field(output_processor=TakeFirst())
    sort_key = Field(output_processor=Join('/'))


class LibraryAvailability(Item):
    def parse_available(value):
        if value.lower() in ['available', 'in', 'not checked out']:
            return True
        return False

    def parse_call_num(value):
        return value.replace(u'\xa0', ' ')

    item = Field(output_processor=TakeFirst())
    library = Field()
    catalog_url = Field()
    branch = Field()
    collection = Field()
    call_num = Field(
        output_processor=Compose(
            MapCompose(lambda s: s.strip()), TakeFirst(), parse_call_num))
    digital_url = Field(
        output_processor=Compose(MapCompose(lambda s: s.strip()), TakeFirst()))
    available = Field(
        output_processor=Compose(
            MapCompose(lambda s: s.strip()), TakeFirst(), parse_available))
