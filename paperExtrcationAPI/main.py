#!/usr/bin/env python3
"""
Automated Research Paper Detector & Classifier for AI/ML in Pharma
Fetches recent papers from PubMed and classifies them using Claude API
"""

import argparse
import json
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
from time import sleep

import anthropic
import requests
from diskcache import Cache
from pyzotero import Zotero

cache = Cache(".cache")

zot = None
if "ZOTERO_API_KEY" in os.environ:
    zot = Zotero(
        "6377183", "group", os.environ["ZOTERO_API_KEY"]
    )  # local=True for read access to local Zotero

# Initialize Claude client
api_key = os.environ.get("ANTHROPIC_API_KEY")

anthropic_client = None
if "ANTHROPIC_API_KEY" in os.environ:
    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# Configuration
CATEGORIES = [
    "Drug Discovery",
    "PBPK/Physiologically-Based Modeling",
    "Pharmacometrics/Population PK-PD",
    "QSP (Quantitative Systems Pharmacology)",
    "Clinical Trial Design/Optimization",
    "Safety & Toxicology",
    "Formulation & Manufacturing",
    "Other/General",
]

SEARCH_TERMS = [
    "machine learning pharmacology",
    "artificial intelligence drug discovery",
    "deep learning pharmacokinetics",
    "AI PKPD",
    "neural network pharmaceutical",
    "machine learning clinical trial",
]


def get_pmids(term, days_back=1, max_results=20):
    # Define time range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_range = f"{start_date.strftime('%Y/%m/%d')}:{end_date.strftime('%Y/%m/%d')}"

    search_query = f"{term} AND {date_range}[PDAT]"
    search_url = f"{BASE_URL}esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": search_query,
        "retmax": max_results,
        "retmode": "json",
    }
    search_response = requests.get(search_url, params=search_params)
    search_data = search_response.json()

    pmids = []
    if "esearchresult" in search_data and "idlist" in search_data["esearchresult"]:
        pmids = search_data["esearchresult"]["idlist"]
    return pmids


def get_article_entry(elem, key):
    res = elem.find(f".//{key}")
    if res is not None:
        return "".join(res.itertext())


@cache.memoize()
def query_pmid(pmid):
    # Fetch paper details
    fetch_url = f"{BASE_URL}efetch.fcgi"
    fetch_params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
    fetch_response = requests.get(fetch_url, params=fetch_params)

    root = ET.fromstring(fetch_response.content)

    articles = []
    for article in root.findall(".//PubmedArticle"):
        # Extract article info
        pmid = get_article_entry(article, "PMID")
        article_dict = {
            "itemType": "journalArticle",
            "title": get_article_entry(article, "ArticleTitle"),
            "abstractNote": get_article_entry(article, "AbstractText"),
            "PMID": pmid,
            "date": get_article_entry(article, "PubDate"),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "DOI": get_article_entry(article, "ArticleId[@IdType='doi']"),
            "creators": [
                {
                    "creatorType": "author",
                    "firstName": author.findtext("ForeName"),
                    "lastName": author.findtext("LastName"),
                }
                for author in article.findall(".//AuthorList/Author")
            ],
        }
        articles.append(article_dict)
    if len(articles) > 1:
        raise RuntimeError(f"Too many articles for given PMID ({pmid})")
    return articles[0]


@cache.memoize()
def classify_paper(title, abstract):
    """Use Claude API to classify and summarize paper"""

    if abstract is None:
        abstract = ""
    prompt = f"""You are a pharmaceutical research expert. Classify this research paper into ONE of these categories and provide a brief 1-sentence summary.

Categories:
{chr(10).join(f"- {cat}" for cat in CATEGORIES)}

Paper Title: {title}

Abstract: {abstract[:1500]}

Respond in JSON format only:
{{
  "category": "exact category name from list above",
  "summary": "one sentence summary (max 150 chars)"
}}"""

    try:
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        # Extract JSON from response
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}") + 1

        if start_idx != -1 and end_idx > start_idx:
            result = json.loads(response_text[start_idx:end_idx])
            return result["category"], result["summary"]
        else:
            return "Other/General", "AI/ML application in pharmaceutical research"

    except Exception as e:
        print(f"Error classifying paper {title}: {e}")
        return "Other/General", "AI/ML application in pharmaceutical research"


def update_readme(articles, cat_map, filename="README.md"):
    header = f"""# Awesome AI/ML in Pharma 🧬🤖

A curated list of recent research papers on AI/ML applications in pharmaceutical sciences, automatically updated daily.

**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}

---
"""

    with open(filename, "w") as fh:
        fh.write(header)

        for cat, pmids in cat_map.items():
            fh.write(f"\n## {cat}\n")

            for pmid in pmids:
                article = articles[pmid]
                fh.write(
                    f"\n- **[{article['title']}]({article['url']})**"
                    f"\n\t- {article['extra']}"
                    f"\n\t- Published: {article['date']}\n"
                )


def main(
    filename="all_articles.json",
    readme_path="../README.md",
    days_back=1,
    max_results=20,
):
    """Main execution"""
    # Load previously fetched papers
    articles = dict()
    if os.path.isfile(filename):
        with open(filename, "r") as fh:
            articles = json.load(fh)

    # Download new papers
    pmids = {
        pmid
        for term in SEARCH_TERMS
        for pmid in get_pmids(term, days_back, max_results)
    }
    print("🔬 Fetching recent AI/ML pharma papers from PubMed...")
    articles.update({pmid: query_pmid(pmid) for pmid in pmids if pmid not in articles})
    print(f"Got {len(articles)} articles")

    # If zotero is accessible (API key is given), then check which papers have
    # been already uploaded
    if zot is not None:
        pmids_in_zot = {x["data"]["PMID"] for x in zot.items()}
        pmids_to_upload = set(articles.keys()) - pmids_in_zot

    print("🤖 Classifying papers with Claude and uploading to zotero...")
    cat2pmid = defaultdict(list)
    for pmid, article in articles.items():
        # Get category from claude
        category = "Undetermined"
        summary = ""
        if anthropic_client is not None:
            category, summary = classify_paper(
                article["title"], article["abstractNote"]
            )

        cat2pmid[category].append(pmid)

        if category != "Undetermined":
            article["tags"] = [{"tag": category}]
        article["extra"] = f"AI summary: {summary}"

        # Upload to zotero
        if zot is not None and article["PMID"] in pmids_to_upload:
            zot.create_items([article])
            sleep(1)

    # Update json file
    with open(filename, "w") as fh:
        json.dump(articles, fh, indent=1)

    print("📝 Updating README.md...")
    update_readme(articles, cat2pmid, readme_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("paperExtractionAPI.py")
    parser.add_argument(
        "-f",
        "--filename",
        default="all_articles.json",
        help="File to store all information for the papers",
    )
    parser.add_argument(
        "--readme_path", default="../README.md", help="Path to README file to generate"
    )
    parser.add_argument(
        "--days_back", default=1, type=int, help="How far back to query PubMed API"
    )
    parser.add_argument(
        "--max_results", default=20, type=int, help="Max number of results"
    )

    args = parser.parse_args()

    main(**vars(args))
