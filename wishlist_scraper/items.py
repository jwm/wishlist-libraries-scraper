import re

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


class WishlistItemAmazonRatingOverview(Item):
    def parse_avg_rating(value):
        return value.split()[0]

    url = Field()
    avg_rating = Field(
        output_processor=Compose(
            MapCompose(lambda s: s.strip()), TakeFirst(), parse_avg_rating))
    star_url = Field()


class WishlistItem(Item):
    isbn = Field()
    format = Field()
    title = Field()
    by = Field(output_processor=TakeFirst())
    amazon_url = Field()
    image = Field(output_processor=TakeFirst())
    amazon_prices = Field(output_processor=TakeFirst())
    rating_overview = Field(output_processor=TakeFirst())
    sort_key = Field(output_processor=Join('/'))


class LibraryAvailability(Item):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setdefault('available', False)
        self.setdefault('copies', 1)
        self.setdefault('holds', 0)

    def parse_available(value):
        return value.lower() in ['true', 'available', 'in', 'not checked out']

    def parse_call_num(value):
        return value.replace(u'\xa0', ' ')

    def parse_copies(value):
        if not value:
            return

        matches = re.search(r'Holds: (\d+) on (\d+)', value)
        if not matches:
            return

        return matches.group(2)

    def parse_holds(value):
        if not value:
            return

        matches = re.search(r'Holds: (\d+) on (\d+)', value)
        if not matches:
            return

        return matches.group(1)

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
    copies = Field(
        serializer=int,
        output_processor=Compose(
            MapCompose(lambda s: s.strip()), TakeFirst(), parse_copies))
    available = Field(
        output_processor=Compose(
            MapCompose(lambda s: s.strip()), TakeFirst(), parse_available))
    holds = Field(
        serializer=int,
        output_processor=Compose(
            MapCompose(lambda s: s.strip()), TakeFirst(), parse_holds))
