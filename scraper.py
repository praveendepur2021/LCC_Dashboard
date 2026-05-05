import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


TOURNAMENTS = [
    {
        "name": "MCT Cricket",
        "base_url": "https://cricclubs.com/mctcricket/",
        "matches_url": "https://cricclubs.com/mctcricket/listMatches.do?clubId=5402",
        "club_id": "5402",
        "teams": {
            "LCC Panthers": [
                "LCC Panthers",
                "LCC PANTHERS",
                "Louisville CC Panthers",
                "Louisville Cc Panthers",
                "Louisville Cricket Club Panthers",
            ],
            "LCC Tigers": [
                "LCC Tigers",
                "LCC TIGERS",
                "Louisville CC Tigers",
                "Louisville Cc Tigers",
                "Louisville Cricket Club Tigers",
            ],
        },
    },
    {
        "name": "Kentucky Premier League KPL",
        "base_url": "https://cricclubs.com/KentuckyPremierLeagueKPL/",
        "matches_url": "https://cricclubs.com/KentuckyPremierLeagueKPL/listMatches.do?clubId=32225",
        "club_id": "32225",
        "teams": {
            "LCC Storm": [
                "LCC Storm",
                "Louisville CC - Storm",
                "Louisville CC Storm",
                "Louisville Cc - Storm",
            ],
            "LCC Cyclone": [
                "LCC Cyclone",
                "Louisville CC - Cyclone",
                "Louisville CC Cyclone",
                "Louisville Cc - Cyclone",
            ],
            "LCC Legends": [
                "LCC Legends",
                "Louisville CC - Legends",
                "Louisville CC Legends",
                "Louisville Cc - Legends",
            ],
        },
    },
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def get_soup(url):
    print(f"Fetching: {url}")

    response = requests.get(url, headers=HEADERS, timeout=40)
    print(f"Status: {response.status_code}")

    response.raise_for_status()

    html = response.text
    print(f"HTML length: {len(html)}")

    return BeautifulSoup(html, "lxml")


def find_lcc_team(text, team_aliases):
    text_lower = text.lower()

    for display_name, aliases in team_aliases.items():
        for alias in aliases:
            if alias.lower() in text_lower:
                return display_name

    return ""


def has_lcc_team(text, team_aliases):
    return bool(find_lcc_team(text, team_aliases))


def get_table_rows(soup):
    rows = []

    for tr in soup.select("tr"):
        cells = [clean(cell.get_text(" ")) for cell in tr.select("th,td")]
        cells = [cell for cell in cells if cell]

        if cells:
            rows.append(cells)

    return rows


def get_all_links(soup, base_url):
    links = []

    for a in soup.select("a[href]"):
        text = clean(a.get_text(" "))
        href = a.get("href", "")
        full_url = urljoin(base_url, href)

        links.append({
            "text": text,
            "url": full_url,
        })

    return links


def find_scorecard_link(row_text, links, fallback_url):
    row_lower = row_text.lower()

    for link in links:
        link_text = link["text"].lower()
        link_url = link["url"].lower()

        if (
            "scorecard" in link_url
            or "matchid" in link_url
            or "viewscorecard" in link_url
            or "viewScorecard" in link["url"]
        ):
            return link["url"]

        if link_text and link_text in row_lower:
            return link["url"]

    return fallback_url


def scrape_matches(tournament):
    soup = get_soup(tournament["matches_url"])

    rows = get_table_rows(soup)
    links = get_all_links(soup, tournament["base_url"])

    print(f"{tournament['name']} match rows found: {len(rows)}")

    matches = []

    for row in rows:
        row_text = " | ".join(row)

        team = find_lcc_team(row_text, tournament["teams"])

        if not team:
            continue

        matches.append({
            "tournament": tournament["name"],
            "team": team,
            "raw": row,
            "rawText": row_text,
            "scorecardUrl": find_scorecard_link(
                row_text,
                links,
                tournament["matches_url"],
            ),
        })

    print(f"{tournament['name']} LCC matches found: {len(matches)}")
    return matches


def scrape_points_table(tournament):
    urls = [
        f"{tournament['base_url']}viewPointsTable.do?clubId={tournament['club_id']}",
        f"{tournament['base_url']}pointsTable.do?clubId={tournament['club_id']}",
        f"{tournament['base_url']}standings.do?clubId={tournament['club_id']}",
    ]

    points = []

    for url in urls:
        try:
            soup = get_soup(url)
            rows = get_table_rows(soup)

            print(f"{tournament['name']} points rows from {url}: {len(rows)}")

            for row in rows:
                row_text = " | ".join(row)
                team = find_lcc_team(row_text, tournament["teams"])

                if not team:
                    continue

                points.append({
                    "tournament": tournament["name"],
                    "team": team,
                    "raw": row,
                    "rawText": row_text,
                    "sourceUrl": url,
                })

        except Exception as e:
            print(f"Points failed for {url}: {e}")

    unique = {}
    for row in points:
        key = f"{row['tournament']}|{row['team']}|{row['rawText']}"
        unique[key] = row

    return list(unique.values())


def scrape_stats(tournament):
    urls = [
        f"{tournament['base_url']}battingRecords.do?clubId={tournament['club_id']}",
        f"{tournament['base_url']}bowlingRecords.do?clubId={tournament['club_id']}",
        f"{tournament['base_url']}viewPlayerStatistics.do?clubId={tournament['club_id']}",
        f"{tournament['base_url']}playerRanking.do?clubId={tournament['club_id']}",
    ]

    stats = []

    for url in urls:
        try:
            soup = get_soup(url)
            rows = get_table_rows(soup)

            print(f"{tournament['name']} stats rows from {url}: {len(rows)}")

            stat_type = "Stats"

            if "batting" in url.lower():
                stat_type = "Batting"
            elif "bowling" in url.lower():
                stat_type = "Bowling"

            for row in rows:
                row_text = " | ".join(row)
                team = find_lcc_team(row_text, tournament["teams"])

                if not team:
                    continue

                stats.append({
                    "tournament": tournament["name"],
                    "team": team,
                    "type": stat_type,
                    "raw": row,
                    "rawText": row_text,
                    "sourceUrl": url,
                })

        except Exception as e:
            print(f"Stats failed for {url}: {e}")

    unique = {}
    for row in stats:
        key = f"{row['tournament']}|{row['type']}|{row['team']}|{row['rawText']}"
        unique[key] = row

    return list(unique.values())


def main():
    all_matches = []
    all_points = []
    all_stats = []

    for tournament in TOURNAMENTS:
        print("=" * 80)
        print(f"Scraping tournament: {tournament['name']}")

        try:
            all_matches.extend(scrape_matches(tournament))
        except Exception as e:
            print(f"Matches failed for {tournament['name']}: {e}")

        try:
            all_points.extend(scrape_points_table(tournament))
        except Exception as e:
            print(f"Points table failed for {tournament['name']}: {e}")

        try:
            all_stats.extend(scrape_stats(tournament))
        except Exception as e:
            print(f"Stats failed for {tournament['name']}: {e}")

    data = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
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

    with open("data.json", "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    print("=" * 80)
    print("data.json updated")
    print(f"Matches: {len(all_matches)}")
    print(f"Points rows: {len(all_points)}")
    print(f"Stats rows: {len(all_stats)}")


if __name__ == "__main__":
    main()
