from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

from regwatch.models import Reference


def _extract_notification_id(link: str) -> int:
    query = urlparse(link).query
    params = parse_qs(query)
    return int(params["Id"][0])


def parse_rss(xml_text: str) -> list[Reference]:
    root = ElementTree.fromstring(xml_text)
    references = []

    for item in root.iter("item"):
        link = item.findtext("link")
        pub_date_text = item.findtext("pubDate")

        references.append(
            Reference(
                notification_id=_extract_notification_id(link),
                title=item.findtext("title"),
                link=link,
                pub_date=parsedate_to_datetime(pub_date_text),
            )
        )

    return references
