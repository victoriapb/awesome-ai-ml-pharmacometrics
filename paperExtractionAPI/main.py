#!/usr/bin/env python3
"""
Automated Research Paper Detector & Classifier for AI/ML in Pharma
Fetches recent papers from PubMed and classifies them using Claude API
"""

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from time import sleep

import anthropic
import requests
from diskcache import Cache
from pyzotero import Zotero
from tqdm import tqdm

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

MAIN_QUERY = """(
  "machine learning"[MeSH Terms]
  OR "artificial intelligence"[MeSH Terms]
  OR "machine learning"[Title/Abstract]
  OR "artificial intelligence"[Title/Abstract]
  OR "deep learning"[Title/Abstract]
  OR "neural network*"[Title/Abstract]
  OR "random forest"[Title/Abstract]
  OR "support vector machine*"[Title/Abstract]
  OR "Gaussian process*"[Title/Abstract]
  OR "reinforcement learning"[Title/Abstract]
  OR "Bayesian machine learning"[Title/Abstract]
  OR "hybrid model*"[Title/Abstract]
  OR "mechanism-informed"[Title/Abstract]
)
AND
(
  pharmacokinetic*[Title/Abstract]
  OR pharmacodynamic*[Title/Abstract]
  OR PK/PD[Title/Abstract]
  OR "population pharmacokinetic*"[Title/Abstract]
  OR "nonlinear mixed effects"[Title/Abstract]
  OR NLME[Title/Abstract]
  OR PBPK[Title/Abstract]
  OR "physiologically based pharmacokinetic*"[Title/Abstract]
  OR QSP[Title/Abstract]
  OR "quantitative systems pharmacology"[Title/Abstract]
  OR "model-based drug development"[Title/Abstract]
  OR "model-informed drug development"[Title/Abstract]
  OR MIDD[Title/Abstract]
  OR pharmacometrics[Title/Abstract]
  OR "precision dosing"[Title/Abstract]
  OR "dose optimization"[Title/Abstract]
  OR "therapeutic drug monitoring"[Title/Abstract]
)
"""

FALLBACK_TAG = "Other/General"

# Updated mini-list of pharmacometrics applications
PMX_APPLICATION_TAGS = [
    "Outcome prediction",
    "Covariate selection / confounding adjustment",
    "Pharmacokinetic modeling",
    "Survival analysis",
    "Exposure–response analysis",
    "Pharmacodynamic modeling",
    "RWD phenotyping",
    "Drug toxicity prediction",
    "Drug repurposing",
    "Enrichment design",
    "Patient risk stratification / management",
    "Dose selection / optimization",
    "Adherence to drug regimen",
    "Synthetic control",
    "Postmarketing surveillance",
    "Endpoint / biomarker assessment",
    "Disease progression modeling",
    "Automation of PK/PD modeling",
    "Precision medicine / optimized treatment regimen",
    "Causal inference",
    "Data imputation",
    "Discovery of subpatient groups",
]

PAPER_TYPE_TAGS = ["review", "tutorial", "perspective"]

METHODOLOGY_TAGS = [
    "Supervised learning",
    "Unsupervised learning",
    "Deep learning",
    "Tree-based models",
    "Gaussian processes",
    "Bayesian ML",
    "Hybrid mechanistic–ML models",
    "Feature selection",
    "Model selection",
    "Surrogate modeling",
    "Emulation of NLME models",
    "Reinforcement learning",
    "Explainable AI",
    "Neural networks",
    "Ensemble learning",
    "Time-series modeling",
    "Mechanism-informed machine learning",
    "LLM",
    "AI Agents",
]


def get_pmids(
    base_query: str,
    days_back: int = 1,
    max_results: int = 200,
):
    """
    Query PubMed using a fixed Boolean query plus a sliding publication date window.

    Parameters
    ----------
    base_query : str
        PubMed Boolean query (e.g. pharmacometrics OR clinical pharmacology)
    days_back : int
        How many days back from today to search
    max_results : int
        Maximum number of PMIDs to return

    Returns
    -------
    list[str]
        List of PubMed IDs (PMIDs)
    """

    # Get today's date in UTC (PubMed uses publication dates, not local time)
    end_date = datetime.now(UTC).date()

    # Compute the start date by subtracting days_back
    start_date = end_date - timedelta(days=days_back)

    # Construct PubMed date filter syntax
    # Example:
    # "2025/01/30"[Date - Publication] : "2025/01/31"[Date - Publication]
    date_clause = (
        f'"{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : '
        f'"{end_date.strftime("%Y/%m/%d")}"[Date - Publication]'
    )

    # Combine the base query with the date constraint
    # Using parentheses ensures correct Boolean precedence
    full_query = f"""
    ({base_query})
    AND
    ({date_clause})
    """

    # PubMed E-utilities endpoint for searching
    search_url = f"{BASE_URL}esearch.fcgi"

    # Parameters passed to PubMed
    search_params = {
        "db": "pubmed",  # database to search
        "term": full_query,  # search query
        "retmax": max_results,  # max number of results
        "retmode": "json",  # JSON response (easier to parse)
        "usehistory": "n",  # do not store query on NCBI servers
    }

    # Execute HTTP GET request with a timeout for safety
    response = requests.get(search_url, params=search_params, timeout=30)

    # Raise an exception if PubMed returns HTTP errors (4xx / 5xx)
    response.raise_for_status()

    # Parse JSON response into Python dict
    data = response.json()

    # Safely extract list of PMIDs
    # If any key is missing, return an empty list
    return data.get("esearchresult", {}).get("idlist", [])


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
    """
    Classify a paper into multiple axes: paper_type, application, methodology.
    Always returns an AI summary.

    Rules:
    - If all axes are empty, assign [Other/General]
    - If at least one axis has a tag, only use the tags returned by Claude
    - Summary is always returned
    """

    if abstract is None:
        abstract = ""

    # --- Claude not configured ---
    if anthropic_client is None:
        return (
            {
                "paper_type": [FALLBACK_TAG],
                "application": [FALLBACK_TAG],
                "methodology": [FALLBACK_TAG],
            },
            "Claude not configured",
        )

    # Build the prompt dynamically from external tag lists
    prompt = f"""
You are an experienced pharmacometrician with expertise in AI/ML applications in drug development and clinical pharmacology.

Classify the following paper into ZERO OR MORE tags per category. If the paper does not use or surveys AI/ML methods, then consider for all the classification the category not_AI_ML
Only assign a tag if clearly supported by the title or abstract. In the methodology choose the tag of the AI/ML methodology that is being used or surveyed in the paper that is best described by the Methodology Tags.
Return STRICT JSON only.

Paper Title:
{title}

Abstract:
{abstract[:1500]}

Tag schema:

paper_type (choose any):
{chr(10).join(f"- {t}" for t in PAPER_TYPE_TAGS)}

application (choose any):
{chr(10).join(f"- {t}" for t in PMX_APPLICATION_TAGS)}

methodology (choose any):
{chr(10).join(f"- {t}" for t in METHODOLOGY_TAGS)}

Response format:
{{
  "paper_type": [],
  "application": [],
  "methodology": [],
  "summary": "One sentence summary. The summary should describe how AI/ML is being used/surveyed in the paper and the main purpose of the paper (max 200 chars)"
}}
"""

    try:
        # --- Call Claude ---
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text

        # --- Default summary fallback ---
        summary = "AI/ML application in pharmacometrics or clinical pharmacology"

        # Try to parse JSON from Claude response

        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}") + 1
        result = {}
        if start_idx != -1 and end_idx != 0:
            result = json.loads(response_text[start_idx:end_idx])
        summary = result.get("summary", summary)

        # --- Extract tags per axis ---
        classification = {
            axis: result.get(axis, [])
            for axis in ["paper_type", "application", "methodology"]
        }

        # --- If all axes empty, assign fallback Other/General only to application ---
        if all(len(tags) == 0 for tags in classification.values()):
            classification["application"] = [FALLBACK_TAG]

        return classification, summary

    except Exception as e:
        print(f"Error classifying paper '{title}': {e}")
        return (
            {
                "paper_type": [FALLBACK_TAG],
                "application": [FALLBACK_TAG],
                "methodology": [FALLBACK_TAG],
            },
            "Error during classification",
        )


def tags2classification(tags, key=None):
    classification = defaultdict(list)
    for tag in tags:
        axis, val = tag["tag"].split(":")
        classification[axis].append(val)
    if key is not None:
        return classification.get(key, [])
    else:
        return classification


def generate_readme_toc(cat_map):
    """
    Generate an alphabetical Markdown Table of Contents for PMX applications.
    """
    toc_lines = ["## Table of Contents\n"]
    for cat in sorted(cat_map.keys()):  # Sort alphabetically
        link = re.sub(r"\s+", "-", re.sub(r"[,()/–]", "", cat)).lower()
        toc_lines.append(f"- [{cat}](#{link})")
    return "\n".join(toc_lines) + "\n"


def update_readme(articles, cat_map, review_pmids, filename="README.md"):
    header = f"""# Awesome AI/ML Applications in Pharmacometrics 🧬🤖

A curated list of research papers on AI/ML applications in pharmacometrics and clinical pharmacology, regularly updated.

**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}

Interactive explorer: <https://aiml-sig.github.io/awesome-ai-ml-pharmacometrics/>

---
"""

    toc = generate_readme_toc(cat_map)

    with open(filename, "w") as fh:
        fh.write(header)
        fh.write(toc)

        # Write PMX application sections in alphabetical order
        for cat in sorted(cat_map.keys()):
            pmids = cat_map[cat]
            fh.write(f"\n## {cat}\n")
            for pmid in pmids:
                # Collect reviews/tutorials/perspectives for bottom
                if pmid in review_pmids:
                    continue

                article = articles[pmid]
                methodologies = tags2classification(
                    article.get("tags", {}), "methodology"
                )
                methodology_str = (
                    f"\t- Methodology: {', '.join(methodologies)}\n"
                    if methodologies
                    else ""
                )

                fh.write(
                    f"\n- **[{article['title']}]({article['url']})**\n"
                    f"{methodology_str}"
                    f"\t- Published: {article.get('date', 'N/A')}\n"
                    f"\t- Summary: {article.get('extra', '')}\n"
                )

        # Append reviews/tutorials/perspectives at the bottom (also alphabetical by title)
        if review_pmids:
            fh.write("\n## Reviews / Tutorials / Perspectives\n")
            for pmid in sorted(review_pmids, key=lambda x: articles[x]["title"]):
                article = articles[pmid]
                methodologies = tags2classification(
                    article.get("tags", {}), "methodology"
                )
                methodology_str = (
                    f"\t- Methodology: {', '.join(methodologies)}\n"
                    if methodologies
                    else ""
                )

                fh.write(
                    f"\n- **[{article['title']}]({article['url']})**\n"
                    f"{methodology_str}"
                    f"\t- Published: {article.get('date', 'N/A')}\n"
                    f"\t- Summary: {article.get('extra', '')}\n"
                )


def filter_applications(applications):
    pmx_apps = [t for t in applications if t not in (FALLBACK_TAG, "not_AI_ML")]
    if not pmx_apps:
        pmx_apps = [FALLBACK_TAG]
    return pmx_apps


def is_review(paper_types):
    return any([x in ("review", "tutorial", "perspective") for x in paper_types])


def contains_not_ai_ml(classification):
    return any([tag == "not_AI_ML" for tags in classification.values() for tag in tags])


def main(
    filename="all_articles.json",
    readme_path="README.md",
    days_back=365,
    max_results=100,
    zotero=True,
):
    """
    Full pipeline:
    - Load existing articles
    - Query PubMed for recent papers
    - Classify using Claude
    - Prepare cat_map based on PMX applications
    - Upload to Zotero if configured
    - Update README
    """

    articles = {}
    if os.path.isfile(filename):
        with open(filename, "r") as fh:
            articles = json.load(fh)

    # Download new papers
    print("🔬 Fetching recent AI/ML pharma papers from PubMed...")
    pmids = {pmid for pmid in get_pmids(MAIN_QUERY, days_back, max_results)}
    new_pmids = [pmid for pmid in pmids if pmid not in articles]
    bar_format = "Downloading info from Pubmed {n} / {total}"
    articles.update(
        {pmid: query_pmid(pmid) for pmid in tqdm(new_pmids, bar_format=bar_format)}
    )

    # If zotero is accessible (API key is given), then check which papers have
    # been already uploaded
    # Only store PMX applications as README sections
    cat_map = defaultdict(list)
    review_pmids = []
    not_ai_ml_pmids = []
    for pmid, article in tqdm(articles.items(), bar_format="Classifying {n} / {total}"):
        classification, summary = classify_paper(
            article.get("title"), article.get("abstractNote", "")
        )

        # Update article entries based on response from claude
        article["extra"] = summary  # Always keep AI summary
        article["tags"] = [
            {"tag": f"{axis}:{t}"}
            for axis, tags in classification.items()
            for t in tags
        ]

        # If classified as not AI/ML paper, then don't add to list of papers to be put
        # into readme and to be uploaded to zotero
        if contains_not_ai_ml(classification):
            not_ai_ml_pmids.append(pmid)
            continue

        # --- README aggregation: only use PMX applications as section headers ---
        if is_review(classification.get("paper_type", [])):
            review_pmids.append(pmid)
        else:
            for app in filter_applications(classification.get("application", [])):
                cat_map[app].append(pmid)

    # Upload to zotero
    if zot is not None and zotero:
        print("Checking papers in zotero...")

        pmids_in_zot = {x["data"]["PMID"] for x in zot.all_top()}
        # pmids_to_upload = set(articles.keys()) - pmids_in_zot - set(not_ai_ml_pmids)
        pmids_to_upload = [
            pmid
            for pmid in articles.keys()
            if pmid not in pmids_in_zot and pmid not in not_ai_ml_pmids
        ]
        bar_format = "Uploading to zotero {n} / {total}"
        for pmid in tqdm(pmids_to_upload, bar_format=bar_format):
            zot.create_items([articles[pmid]])
            sleep(1)

    # Update json file
    print("📝 Updating JSON file...")
    with open(filename, "w") as fh:
        json.dump(articles, fh, indent=1)

    # Update the readme file
    print("📝 Updating README.md...")
    update_readme(articles, cat_map, review_pmids, filename=readme_path)

    print("✅ Pipeline complete!")


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
    parser.add_argument("--zotero", action=argparse.BooleanOptionalAction, default=True)

    args = parser.parse_args()

    main(**vars(args))
