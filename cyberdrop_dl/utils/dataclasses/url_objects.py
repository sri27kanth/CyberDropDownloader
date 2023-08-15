from dataclasses import field

from yarl import URL


class MediaItem:
    def __init__(self, url: URL, referer: URL, complete: bool, filename: str, ext: str, original_filename: str):
        self.url = url
        self.referer = referer
        self.complete = complete
        self.filename = filename
        self.ext = ext
        self.original_filename = original_filename
        self.filesize: int = field(init=False)


class ScrapeItem:
    def __init__(self, url: URL, parent_title: str):
        self.url: URL = url
        self.parent_title: str = parent_title