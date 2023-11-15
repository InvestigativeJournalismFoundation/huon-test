#There are a few recommended improvements for the script:
#
#
#1. Rename variables for better clarity: Some variable names could be improved to enhance code readability. For example, `href1` can be renamed to something more descriptive like `registration_href`. Similarly, `rdate_str` can be changed to `last_change_date_str`.
#
#
#2. Handle exceptions gracefully: The script uses `datetime.strptime` to parse a date string. If the date string is not in the expected format, it will raise a `ValueError`. It would be better to handle this exception and provide a more informative error message.
#
#Here's the updated script with the recommended improvements:


from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from lxml import etree

from pipeline.crawl import tree
from pipeline.crawl.scheduler import Scheduler
from pipeline.types import DMIN
from pipeline.utils.http import Request, SSLManager
from pipeline.utils.log import get_logger



SSLManager()._allow_legacy_renegotiation()
ROOT_URL = "https://novascotia.ca/"

logger = get_logger(__name__, debug=False)


def seed(scheduler: Scheduler) -> tree.Edge | None:
    """This is for the "historical" run.
    For now, it's pretty straightforward to get pages,
    and I'll rejig it to specify dates for the scheduler
    later after chat with Martin."""
    if scheduler.indexer.page_start >= 1900:
        return None
    i = scheduler.indexer.page_start - 1
    req = Request(
        method="GET",
        url=f"https://novascotia.ca/sns/Lobbyist/search.asp?page={i}",
    )

    return tree.Edge(
        label="search_results",
        req=req,
        p_rid="",
        p_rdate=DMIN,
    )


def sections(data: tree.Data) -> list[tree.Data]:
    label, text = data
    utf8_encoded_data = text.encode("utf-8")
    soup = BeautifulSoup(utf8_encoded_data, "lxml")

    # this next if statement selects all the links for the 1-25, 26-50 etc sections at the top
    if label == "search_results":
        table = soup.find("table", class_=lambda x: x and "innertable" in x)
        tr_tags = table.find_all("tr")[1:]
        return [tree.Data("sec_results", str(tag)) for tag in tr_tags]

    if label == "reg":
        return [data]

    raise ValueError(f"Unrecognized label: {label}")


def parse(
    data: tree.Data, p_rid: str, p_rdate: datetime
) -> tuple[str, datetime, list[tree.Edge]]:
    """
    outputs the results page for each section of results (i.e. 1-25, 26-50, etc)
    
    the new label is "sec_results", meaning second results, returns the second landing
    page of results. maybe a different name would be better. idk.

    michaela thats the most vague commend u've ever written

    the new label "reg" points to each registration page. One more loop is required to get
    date info for the rdate.
    """
    edges_to_return = []

    if data.label == "sec_results":
        soup = BeautifulSoup(data.data, "lxml")
        a_tags = soup.find_all("a", href=True)
        registration_href = a_tags[0]["href"]
        rid = (
            registration_href.split("regid=")[1].split("&")[0] if "regid=" in registration_href else None
        )
        edges_to_return = [
            tree.Edge(
                label="reg",
                req=Request(
                    method="GET",
                    url=urljoin(ROOT_URL, registration_href),
                ),
                p_rid=rid,
                p_rdate=p_rdate,
            )
        ]
        return rid, p_rdate, edges_to_return

    if data.label == "reg":
        soup = BeautifulSoup(data.data, "lxml")
        rdate_tag_row = soup.find("td", string="Last date of any changes").find_parent(
            "tr"
        )
        rdate_row = rdate_tag_row.find_next_sibling("tr")
        last_change_date_str = rdate_row.find("td").get_text().strip()
        try:
            last_change_date = datetime.strptime(last_change_date_str, "%d-%B-%Y")
        except ValueError:
            raise ValueError(f"Invalid date format: {last_change_date_str}")
        return p_rid, last_change_date, []