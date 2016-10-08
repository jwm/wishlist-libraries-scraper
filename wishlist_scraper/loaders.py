from scrapy.item import Item
from scrapy.loader import ItemLoader
from scrapy.loader.processors import Compose, Join, MapCompose

from .items import (
    WishlistItem, WishlistItemImage, WishlistItemAmazonPrices,
    LibraryAvailability)


def strip_value(value):
    if issubclass(type(value), Item):
        return value
    return value.strip()


class WishlistItemLoader(ItemLoader):
    default_item_class = WishlistItem
    default_output_processor = Compose(MapCompose(strip_value), Join())


class WishlistItemAmazonPricesLoader(ItemLoader):
    default_item_class = WishlistItemAmazonPrices
    default_output_processor = Compose(MapCompose(strip_value), Join())


class WishlistItemImageLoader(ItemLoader):
    default_item_class = WishlistItemImage
    default_output_processor = Compose(MapCompose(strip_value), Join())


class LibraryAvailabilityLoader(ItemLoader):
    default_item_class = LibraryAvailability
    default_output_processor = Compose(MapCompose(strip_value), Join())
