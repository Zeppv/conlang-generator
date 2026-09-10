from pathlib import Path
from urllib.request import urlretrieve


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIRECTORY = (
    ROOT
    / "data"
    / "raw"
    / "concepticon_wordnet"
)

OUTPUT_FILE = (
    OUTPUT_DIRECTORY
    / "Borin-2015-1532.tsv"
)


URL = (
    "https://raw.githubusercontent.com/"
    "concepticon/concepticon-data/"
    "v3.4.0/"
    "concepticondata/conceptlists/"
    "Borin-2015-1532.tsv"
)


OUTPUT_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True
)


if OUTPUT_FILE.exists():

    print(
        "WordNet mapping already exists:"
    )

    print(OUTPUT_FILE)

else:

    print(
        "Downloading curated "
        "Concepticon-WordNet mapping..."
    )

    urlretrieve(
        URL,
        OUTPUT_FILE
    )

    print("Downloaded:")
    print(OUTPUT_FILE)