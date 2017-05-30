from .items import LibraryAvailability

class LibraryAvailabilityPipeline(object):
    def process_item(self, item, spider):
        if type(item) != LibraryAvailability:
            return item

        item.setdefault('available', False)
        item.setdefault('copies', '1')
        item.setdefault('holds', '0')
        return item
