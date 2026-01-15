#!/usr/bin/env python3
"""
Automated Research Paper Detector & Classifier for AI/ML in Pharma
Fetches recent papers from PubMed and classifies them using Claude API
"""

import os
import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import anthropic

# Configuration
CATEGORIES = [
    "Drug Discovery",
    "PBPK/Physiologically-Based Modeling",
    "Pharmacometrics/Population PK-PD",
    "QSP (Quantitative Systems Pharmacology)",
    "Clinical Trial Design/Optimization",
    "Safety & Toxicology",
    "Formulation & Manufacturing",
    "Other/General"
]

SEARCH_TERMS = [
    "machine learning pharmacology",
    "artificial intelligence drug discovery",
    "deep learning pharmacokinetics",
    "AI PKPD",
    "neural network pharmaceutical",
    "machine learning clinical trial"
]


def fetch_pubmed_papers(days_back=1, max_results=20):
    """Fetch recent papers from PubMed API"""
    
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    papers = []
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_range = f"{start_date.strftime('%Y/%m/%d')}:{end_date.strftime('%Y/%m/%d')}"
    
    for term in SEARCH_TERMS:
        # Search PubMed
        search_query = f"{term} AND {date_range}[PDAT]"
        search_url = f"{base_url}esearch.fcgi"
        search_params = {
            'db': 'pubmed',
            'term': search_query,
            'retmax': max_results,
            'retmode': 'json'
        }
        
        try:
            search_response = requests.get(search_url, params=search_params)
            search_data = search_response.json()
            
            if 'esearchresult' not in search_data or 'idlist' not in search_data['esearchresult']:
                continue
                
            pmids = search_data['esearchresult']['idlist']
            
            if not pmids:
                continue
            
            # Fetch paper details
            fetch_url = f"{base_url}efetch.fcgi"
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(pmids),
                'retmode': 'xml'
            }
            
            fetch_response = requests.get(fetch_url, params=fetch_params)
            
            # Parse XML response (simple parsing)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(fetch_response.content)
            
            for article in root.findall('.//PubmedArticle'):
                try:
                    # Extract article info
                    title_elem = article.find('.//ArticleTitle')
                    abstract_elem = article.find('.//AbstractText')
                    pmid_elem = article.find('.//PMID')
                    pub_date = article.find('.//PubDate')
                    
                    if title_elem is None or pmid_elem is None:
                        continue
                    
                    title = ''.join(title_elem.itertext())
                    abstract = ''.join(abstract_elem.itertext()) if abstract_elem is not None else ""
                    pmid = pmid_elem.text
                    
                    # Extract publication date
                    year = pub_date.find('Year')
                    month = pub_date.find('Month')
                    day = pub_date.find('Day')
                    
                    pub_date_str = ""
                    if year is not None:
                        pub_date_str = year.text
                        if month is not None:
                            pub_date_str += f"-{month.text}"
                            if day is not None:
                                pub_date_str += f"-{day.text}"
                    
                    paper = {
                        'pmid': pmid,
                        'title': title,
                        'abstract': abstract,
                        'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        'pub_date': pub_date_str
                    }
                    
                    # Avoid duplicates
                    if not any(p['pmid'] == pmid for p in papers):
                        papers.append(paper)
                        
                except Exception as e:
                    print(f"Error parsing article: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error fetching papers for term '{term}': {e}")
            continue
    
    return papers


def classify_paper(paper, client):
    """Use Claude API to classify and summarize paper"""
    
    prompt = f"""You are a pharmaceutical research expert. Classify this research paper into ONE of these categories and provide a brief 1-sentence summary.

Categories:
{chr(10).join(f"- {cat}" for cat in CATEGORIES)}

Paper Title: {paper['title']}

Abstract: {paper['abstract'][:1500]}

Respond in JSON format only:
{{
  "category": "exact category name from list above",
  "summary": "one sentence summary (max 150 chars)"
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text
        # Extract JSON from response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            result = json.loads(response_text[start_idx:end_idx])
            return result['category'], result['summary']
        else:
            return "Other/General", "AI/ML application in pharmaceutical research"
            
    except Exception as e:
        print(f"Error classifying paper {paper['pmid']}: {e}")
        return "Other/General", "AI/ML application in pharmaceutical research"


def update_readme(categorized_papers):
    """Update README.md with new papers"""
    
    readme_path = "README.md"
    
    # Read existing README or create new one
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
    else:
        existing_content = """# Awesome AI/ML in Pharma 🧬🤖

A curated list of recent research papers on AI/ML applications in pharmaceutical sciences, automatically updated daily.

**Last Updated**: {date}

---

"""
    
    # Update date
    existing_content = existing_content.split('\n')
    for i, line in enumerate(existing_content):
        if '**Last Updated**:' in line:
            existing_content[i] = f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"
            break
    existing_content = '\n'.join(existing_content)
    
    # Build new entries by category
    new_entries = defaultdict(list)
    
    for paper in categorized_papers:
        category = paper['category']
        entry = f"- **[{paper['title']}]({paper['url']})** - {paper['summary']} _{paper['pub_date']}_"
        new_entries[category].append(entry)
    
    # Add new entries to README
    for category in CATEGORIES:
        if category not in new_entries:
            continue
            
        # Find or create category section
        category_header = f"## {category}"
        
        if category_header not in existing_content:
            # Add new category section
            existing_content += f"\n\n{category_header}\n\n"
        
        # Add papers under category
        for entry in new_entries[category]:
            if entry not in existing_content:
                # Find the category section and add entry
                lines = existing_content.split('\n')
                for i, line in enumerate(lines):
                    if line == category_header:
                        # Find next category or end of file
                        j = i + 1
                        while j < len(lines) and not lines[j].startswith('## '):
                            j += 1
                        # Insert before next category
                        lines.insert(j, entry)
                        break
                existing_content = '\n'.join(lines)
    
    # Write updated README
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(existing_content)
    
    print(f"✓ Updated README.md with {len(categorized_papers)} papers")


def main():
    """Main execution"""
    
    print("🔬 Fetching recent AI/ML pharma papers from PubMed...")
    
    # Fetch papers from last 1 day
    papers = fetch_pubmed_papers(days_back=1, max_results=20)
    print(f"✓ Found {len(papers)} papers")
    
    if not papers:
        print("No new papers found.")
        return
    
    # Initialize Claude client
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    print("🤖 Classifying papers with Claude...")
    
    # Classify each paper
    categorized_papers = []
    for i, paper in enumerate(papers, 1):
        print(f"  [{i}/{len(papers)}] {paper['title'][:60]}...")
        category, summary = classify_paper(paper, client)
        
        categorized_papers.append({
            'title': paper['title'],
            'url': paper['url'],
            'summary': summary,
            'category': category,
            'pub_date': paper['pub_date']
        })
    
    print(f"✓ Classified {len(categorized_papers)} papers")
    
    # Update README
    print("📝 Updating README.md...")
    update_readme(categorized_papers)
    
    print("✅ Done! Check README.md for updates.")


if __name__ == "__main__":
    main()
