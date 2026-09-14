"""Hand-counted source fixture, built through the actual Steps 5-7 pipelines."""
import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/analysis"))
from build_phonotactics import build as build5
from build_syllable_candidates import build as build6
from build_prosody_evidence import build as build7


def fixture():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE reference_source(id TEXT PRIMARY KEY,name TEXT,version TEXT);
        INSERT INTO reference_source VALUES('lexibank','Lexibank Analysed','2.2.1');
        CREATE TABLE lexibank_language(id INTEGER PRIMARY KEY,lexibank_id TEXT,name TEXT,glottocode TEXT);
        INSERT INTO lexibank_language VALUES(1,'northeuralex-eng','English','stan1293'),
            (2,'other-eng','Other English','stan1293'),(3,'no-nucleus','No nucleus','test1234'),
            (4,'empty','Empty doculect','empt1234');
        CREATE TABLE lexibank_phoneme(id INTEGER PRIMARY KEY,description TEXT);
        INSERT INTO lexibank_phoneme VALUES(1,'stop consonant'),(2,'open vowel'),(3,'stop consonant'),
            (4,'near-open vowel'),(8,'long open vowel');
        CREATE TABLE lexibank_segment_token(id INTEGER PRIMARY KEY,token TEXT,token_type TEXT,phoneme_id INTEGER);
        INSERT INTO lexibank_segment_token VALUES(1,'p','phoneme',1),(2,'a','phoneme',2),
            (3,'t','phoneme',3),(4,'ɐ','phoneme',4),(5,'+','boundary',NULL),
            (6,'∼','special',NULL),(7,'⁵','tone',NULL),(8,'aː','phoneme',8);
        CREATE TABLE lexibank_form(id INTEGER PRIMARY KEY,language_id INTEGER,form TEXT,value TEXT,
            segments TEXT,segment_count INTEGER,cv_template TEXT,prosodic_string TEXT);
        CREATE INDEX form_language ON lexibank_form(language_id);
        CREATE TABLE lexibank_form_segment(form_id INTEGER,segment_order INTEGER,token_id INTEGER,
            PRIMARY KEY(form_id,segment_order));
        CREATE TABLE phonology_analysis(id TEXT PRIMARY KEY,method_version TEXT,inventory_unit_count INTEGER,language_unit_count INTEGER);
        INSERT INTO phonology_analysis VALUES('phoible_v2_0_step4','1.0.0',20,10);
        CREATE TABLE phoible_segment(id INTEGER PRIMARY KEY,phoneme TEXT,segment_class TEXT);
        INSERT INTO phoible_segment VALUES(1,'p','consonant'),(2,'a','vowel'),(3,'t','consonant');
        CREATE TABLE phonology_inventory_profile(analysis_id TEXT,distinct_segment_count INTEGER,
            consonant_count INTEGER,vowel_count INTEGER,tone_count INTEGER);
        CREATE TABLE phonology_segment_prevalence(analysis_id TEXT,scope TEXT,segment_id INTEGER,
            unit_count INTEGER,total_unit_count INTEGER,prevalence REAL);
        CREATE TABLE phonology_segment_cooccurrence(analysis_id TEXT,scope TEXT,segment_a_id INTEGER,
            segment_b_id INTEGER,joint_unit_count INTEGER,expected_joint_count REAL,evidence_type TEXT,
            lift REAL,phi_coefficient REAL);
    """)
    aid = "phoible_v2_0_step4"
    db.executemany("INSERT INTO phonology_inventory_profile VALUES(?,2,1,1,0)", [(aid,)] * 20)
    for scope, units in (("inventory", 20), ("language", 10)):
        db.executemany("INSERT INTO phonology_segment_prevalence VALUES(?,?,?,?,?,?)",
                       [(aid, scope, sid, units if sid == 2 else units // 2, units, 1.0 if sid == 2 else 0.5) for sid in (1, 2, 3)])
        for a, b in ((1, 2), (2, 3)):
            db.execute("INSERT INTO phonology_segment_cooccurrence VALUES(?,?,?,?,?,?,?,?,?)",
                       (aid, scope, a, b, units // 2, units / 2, "observed", 1.0, 0.0))
    db.execute("INSERT INTO phonology_segment_cooccurrence VALUES(?,?,?,?,?,?,?,?,?)", (aid, "inventory", 1, 3, 0, 5.0, "expected_absence", 0.0, -1.0))
    sources = [(1, 1, "ˈpa", "p a", "CV"), (2, 1, "tap", "t a p", "CVC"),
               (3, 1, "pa", "p + a", "C+V"), (4, 1, "aɐ", "a ɐ", "VV"),
               (5, 1, "aː⁵", "aː ⁵", "VT"), (6, 2, "a", "a", "V"), (7, 3, "p", "p", "C")]
    ids = dict(db.execute("SELECT token,id FROM lexibank_segment_token"))
    for fid, lid, form, segments, cv in sources:
        seq = segments.split()
        db.execute("INSERT INTO lexibank_form VALUES(?,?,?,?,?,?,?,?)", (fid, lid, form, form, segments, len(seq), cv, cv))
        db.executemany("INSERT INTO lexibank_form_segment VALUES(?,?,?)", [(fid, n, ids[t]) for n, t in enumerate(seq, 1)])
    db.commit()
    for build in (build5, build6, build7):
        with db:
            db.execute("BEGIN IMMEDIATE")
            build(db, lambda _: None)
    return db
