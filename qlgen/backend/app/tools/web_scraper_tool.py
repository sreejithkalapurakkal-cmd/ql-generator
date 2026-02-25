import httpx
from strands import tool


@tool
def scrape_webpage(url: str) -> dict:
    """
    Scrape a webpage to extract text content.
    BEST FOR: Reading company about pages, team pages, technology pages,
    and blog posts to extract detailed information not available via APIs.
    USE IN STAGES: Any stage - especially Contact Discovery (team pages)
    and BANT Scoring (gathering evidence).

    Args:
        url: The URL to scrape

    Returns:
        dict with 'url', 'title', 'content' (extracted text), 'links'
    """
    try:
        from bs4 import BeautifulSoup

        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 qlGen Research Bot"},
        )
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        return {
            "url": url,
            "title": soup.title.string if soup.title else "",
            "content": soup.get_text(separator="\n", strip=True)[:5000],
            "links": [a.get("href") for a in soup.find_all("a", href=True)[:50]],
        }
    except Exception as e:
        return {"url": url, "error": str(e), "content": "", "links": []}
