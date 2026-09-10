from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


STEPS = [

    (
        "Build base Concept Graph",
        ROOT
        / "scripts"
        / "import"
        / "build_concept_graph.py"
    ),

    (
        "Import Open English WordNet",
        ROOT
        / "scripts"
        / "import"
        / "import_wordnet.py"
    ),

    (
        "Map WordNet to concepts",
        ROOT
        / "scripts"
        / "import"
        / "map_wordnet_to_concepts.py"
    ),

    (
        "Build WordNet concept relations",
        ROOT
        / "scripts"
        / "import"
        / "build_wordnet_relations.py"
    ),

    (
        "Import DatSemShift",
        ROOT
        / "scripts"
        / "import"
        / "import_datsemshift.py"
    ),

    (
        "Build semantic scores",
        ROOT
        / "scripts"
        / "analysis"
        / "build_semantic_scores.py"
    ),
]


print()
print("=============================================")
print("REBUILDING CONLANG SEMANTIC ENGINE")
print("=============================================")


for name, script in STEPS:

    print()
    print("---------------------------------------------")
    print(name)
    print("---------------------------------------------")


    if not script.exists():

        raise FileNotFoundError(
            f"Missing script:\n{script}"
        )


    subprocess.run(
        [
            sys.executable,
            str(script)
        ],
        check=True
    )


print()
print("=============================================")
print("SEMANTIC ENGINE REBUILD COMPLETE")
print("=============================================")
print()