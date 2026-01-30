
# paperExtractionAPI

## Setup

Setup the environment with:
```
uv sync
```

## Usage

To run the script:
```
uv run main.py
```

Alternatively, activate the virtual environment with:
```
source .venv/bin/activate
```
and then:
```
python3 main.py
```

You can increase from how many previous days papers are queried to PubMed API
and the maximum number of results with:
```
python3 main.py --days_back <num_days> --max_results <max_results>
```

In order to upload to Zotero library, you need to add `ZOTERO_API_KEY` environment variable like so:
```
export ZOTERO_API_KEY="<your_zotero_api_key>"
```

In order to use classification with claude you also need to add `ANTHROPIC_API_KEY` environment variable:
```
export ANTHROPIC_API_KEY="<your_claude_api_key>"
```
