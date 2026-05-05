import json
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


TOURNAMENTS = [
    {
        "name": "MCT Cricket",
        "base_url": "https://cricclubs.com/mctcricket/",
        "matches_url": "https://cricclubs.com/mctcricket/listMatches.do?clubId=5402",
        "club_id": "5402",
        "teams": ["LCC Panthers", "LCC Tigers"],
    },
    {
        "name": "Kentucky Premier League KPL",
        "base_url": "https://cricclubs.com/KentuckyPremierLeagueKPL/",
        "matches_url": "https://cricclubs.com/KentuckyPremierLeagueKPL/listMatches.do?clubId=32225",
        "club_id": "32225",
        "teams": ["LCC Storm", "LCC Cyclone", "LCC Legends"],
    },
]


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def table_rows(soup):
    rows = []
    for tr in soup.select("tr"):
        cells = [clean(c.get_text(" ")) for c in tr.select("th,td")]
        if cells:
            rows.append(cells)
    return rows


def has_lcc_team(text, teams):
    text = text.lower()
    return any(team.lower() in text for team in teams)


def extract_links(soup, base_url):
    links = []
    for a in soup.select("a[href]"):
        text = clean(a.get_text(" "))
        href = a.get("href")
        full_url = urljoin(base_url, href)
        links.append({"text": text, "url": full_url})
    return links


def scrape_matches(tournament):
    soup = get_soup(tournament["matches_url"])
    rows = table_rows(soup)
    links = extract_links(soup, tournament["base_url"])

    matches = []

    for row in rows:
        row_text = " | ".join(row)

        if not has_lcc_team(row_text, tournament["teams"]):
            continue

        scorecard_url = ""

        for link in links:
            if "scorecard" in link["url"].lower() or "match" in link["url"].lower():
                if has_lcc_team(link["text"], tournament["teams"]) or not link["text"]:
                    scorecard_url = link["url"]
                    break

        found_team = next(
            (team for team in tournament["teams"] if team.lower() in row_text.lower()),
            "",
        )

        matches.append({
            "tournament": tournament["name"],
            "team": found_team,
            "raw": row,
            "rawText": row_text,
            "scorecardUrl": scorecard_url or tournament["matches_url"],
        })

    return matches


def scrape_points_table(tournament):
    possible_urls = [
        f"{tournament['base_url']}viewPointsTable.do?clubId={tournament['club_id']}",
        f"{tournament['base_url']}viewPointsTable.do?clubId={tournament['club_id']}&teamId=",
    ]

    points = []

    for url in possible_urls:
        try:
            soup = get_soup(url)
            rows = table_rows(soup)

            for row in rows:
                row_text = " | ".join(row)
                if has_lcc_team(row_text, tournament["teams"]):
                    points.append({
                        "tournament": tournament["name"],
                        "team": next(
                            (team for team in tournament["teams"] if team.lower() in row_text.lower()),
                            "",
                        ),
                        "raw": row,
                        "rawText": row_text,
                    })
        except Exception:
            continue

    return points


def scrape_stats(tournament):
    possible_urls = [
        f"{tournament['base_url']}battingRecords.do?clubId={tournament['club_id']}",
        f"{tournament['base_url']}bowlingRecords.do?clubId={tournament['club_id']}",
        f"{tournament['base_url']}viewPlayerStatistics.do?clubId={tournament['club_id']}",
    ]

    stats = []

    for url in possible_urls:
        try:
            soup = get_soup(url)
            rows = table_rows(soup)

            for row in rows:
                row_text = " | ".join(row)
                if has_lcc_team(row_text, tournament["teams"]):
                    stats.append({
                        "tournament": tournament["name"],
                        "sourceUrl": url,
                        "raw": row,
                        "rawText": row_text,
                    })
        except Exception:
            continue

    return stats


def main():
    all_matches = []
    all_points = []
    all_stats = []

    for tournament in TOURNAMENTS:
        print(f"Scraping {tournament['name']}")

        try:
            all_matches.extend(scrape_matches(tournament))
        except Exception as e:
            print(f"Matches failed for {tournament['name']}: {e}")

        try:
            all_points.extend(scrape_points_table(tournament))
        except Exception as e:
            print(f"Points failed for {tournament['name']}: {e}")

        try:
            all_stats.extend(scrape_stats(tournament))
        except Exception as e:
            print(f"Stats failed for {tournament['name']}: {e}")

    data = {
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
        "teams": [
            "LCC Panthers",
            "LCC Tigers",
            "LCC Storm",
            "LCC Cyclone",
            "LCC Legends",
        ],
        "matches": all_matches,
        "pointsTable": all_points,
        "stats": all_stats,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("data.json updated")


if __name__ == "__main__":
    main()
