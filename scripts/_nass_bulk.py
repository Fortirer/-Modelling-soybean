"""Shared helper: the NASS Quick Stats bulk data files are named with the date
they were generated (qs.crops_YYYYMMDD.txt.gz), and NASS republishes a new one
roughly daily. Hardcoding a date, as scripts 01, 23 and 29 originally did,
goes stale in weeks and then 404s -- caught when adding a fifth state (NE) a
few days after the fourth (MN) was added, when script 01's hardcoded
2026-09-22 snapshot had already rotated past. This discovers the CURRENT
filename from the public directory listing instead, so the auto-download path
never needs a manual date bump again.
"""
import re
import urllib.parse
import urllib.request

# In November 2026 NASS moved the listing to /datasets (no trailing slash; the
# old /datasets/ now 404s) and the files under /sites/default/files/datasets/.
# Links are therefore resolved from the page itself rather than assumed.
INDEX_URL = "https://www.nass.usda.gov/datasets"


def latest_bulk_url(prefix):
    """`prefix` e.g. 'qs.crops_' or 'qs.census2022' (no date, that part). Returns
    the full https URL of the newest matching file on the NASS datasets page.
    """
    req = urllib.request.Request(INDEX_URL, headers={"User-Agent": "research-script"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    links = sorted(set(re.findall(rf'href="([^"]*{re.escape(prefix)}[\w.\-]*\.txt\.gz)"', html)))
    if not links:
        raise RuntimeError(f"no file on {INDEX_URL} matches prefix {prefix!r} -- "
                           f"NASS may have changed its naming or the page layout")
    # file names end in YYYYMMDD, so sorting by name sorts by date
    newest = max(links, key=lambda link: link.rsplit("/", 1)[-1])
    return urllib.parse.urljoin(INDEX_URL + "/", newest)
