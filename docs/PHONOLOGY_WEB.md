# Phonology website evaluator — Step 9

Step 8 was confirmed complete on the user's database. Step 9 makes its evidence
available through the existing Worker/React application. It evaluates a proposal;
it does not generate a language or assign a universal naturalness percentage.

## Install and run

From the project root, after applying `phonology-step9.patch`:

```bat
python scripts\analysis\sync_phonology_web.py
```

Wait for `PHONOLOGY WEB SYNC COMPLETE`, then start or restart development:

```bat
npm run dev
```

Open the address printed by Vite, choose **Phonology**, then **Evaluate sound
system**. The existing Concept Explorer remains available from the navigation.
The default example uses the same proposal and English doculect as Step 8.
Do not rerun the earlier analysis builders or the full 14-part reference import.

Enter individual IPA tokens separated by spaces. Put each sample word on its own
line. A multi-character sound such as `kʰ` is one token; do not insert a space
inside it. Templates contain one V nucleus and any number of C positions on
either side. The evaluator does not automatically syllabify supplied words.

## What the sync actually transfers

- Complete PHOIBLE sound catalog, inventory sizes, both scopes of prevalence and
  stored pair associations.
- The Lexibank token catalog needed for exact token and marker interpretation.
- The selected doculects' Step 5–7 summary rows, names/IDs and build provenance.

It does not transfer millions of raw form/segment rows, change semantic tables,
or write to `reference.sqlite`. The first default package measured 36.44 MiB of
summary payload in the development real-data check. Source metadata and selected
doculects can change the precise size. SQL quoting/chunk metadata add some overhead.

The default includes `northeuralex-eng` only for lexical comparison. English is
not a universal benchmark. The full 5,501-doculect corpus remains in the source
database; the UI only offers doculects included in the active serving snapshot.

To choose a different set, use exact Lexibank IDs with repeated `--doculect`
options. Supply the complete desired set each time. The default English ID is
only added when no `--doculect` option is supplied. The ID is a dataset/doculect
identifier, not a language name or Glottocode. No fuzzy selection occurs.

```bat
python scripts\analysis\sync_phonology_web.py --doculect northeuralex-eng
```

Preparation without any D1 change is available with `--prepare-only`. The
generated package lives in `data/compiled/phonology-web/`. Files in that directory
are reproducible local outputs; the manifest specifies which parts belong to
the current package. Old filenames outside that manifest are not imported.

## Safety and resuming

The sync writes only `phonology_web_chunk`, `phonology_web_part` and
`phonology_web_active` in **local** `conlang-reference`. It provides no remote
flag. It reads the SQLite source through a consistent read transaction.

Each content-addressed snapshot is independent. Four-MiB SQL parts use replaceable
rows, so an interrupted part can be safely replayed. Completed parts have
content-hash receipts. One persistent local Wrangler runtime handles the entire
sync, avoiding a separate CLI startup for every part and verification query.
Each part and its receipt execute in one D1 batch. After import, the script checks counts and reads back the
payloads in bounded pages to verify every record's SHA-256 fingerprint. Only
then does a single statement switch the active pointer. Earlier snapshots stay
available; this step does not delete them or attempt automatic cleanup.

If interrupted, rerun the same command. Do not delete Wrangler state. A failed
verification leaves the previous active snapshot in place. Corrupt receipts are
cleared after a payload-hash failure so the next run can repair that package.
A count mismatch may indicate extra or missing chunks and should be diagnosed
from the error rather than solved with a full database reset.

Each Worker request pins the snapshot ID it first reads. It verifies chunks and
whole-record fingerprints, preventing a request from mixing different builds
during activation. Missing/corrupt evidence returns 503 rather than invented
numbers. Invalid proposals return 400. The API accepts at most 1 MiB of request
data plus the existing evaluator's field limits.

The active table retains `previous_snapshot`. This supports deliberate rollback
without reconstructing source evidence; automatic old-snapshot cleanup is not
implemented. Repeated new builds can therefore grow the local serving database.
Changing only frontend code requires no data sync.

## Results and limits

See `PHONOLOGY_EVALUATOR.md` for formulas and interpretation. The website keeps:

- Exact PHOIBLE mapping and its coverage; unknown sounds are not automatically invalid.
- Inventory and language evidence populations separate.
- Missing stored pairs separate from recorded expected absences.
- Word-sequence observation fractions separate from token-mapping coverage.
- One doculect per comparison, even when two doculects share a Glottocode.
- Syllable eligibility and ambiguity visible; alternatives are not probabilities.
- Prosodic systems unassessed when only annotation evidence is available.

Changing inputs hides old results until a fresh evaluation completes. Long pair
lists show up to 100 rows; the downloadable JSON contains all results, word-edge
evidence and provenance. The download is an evidence report, not persistent
project storage. User accounts/project persistence are later roadmap work.

## Verification

The focused suite passes 55 tests, including 15 complete Python/TypeScript report
parity cases, unknown and
empty evidence, marker handling, source-count mismatch rejection, snapshot SQL
round trips, interruption/resume and checksum verification. Separate integration
tests use actual local D1 with an isolated persistence directory, exercise the
Worker routes, and check the existing Concept Explorer routes with a semantic
fixture. This does not replace a full semantic-source validation.

Real-data verification also uses the complete PHOIBLE statistics (3,175 sounds,
3,020 inventory profiles, 6,350 prevalence rows, 570,320 pair rows) and 961
analysed `northeuralex-eng` forms summarized through Steps 5–7 in an isolated
database. The real serving payload is 36.44 MiB in ten parts. Worker reports
match Python in both PHOIBLE scopes and when no lexical reference is selected.
The semantic regression data are a fixture, not a copy of the full user database.
The persistent-runtime integration run completed in 86.4 seconds here, including
initial import, complete checksum verification, API checks, intentional corruption
and repair, and a repeated sync that skipped imported parts. That excludes
building the source fixture and is not a Windows runtime guarantee.

Developer commands (not required user installation steps):

```text
python -m unittest discover -s tests
python tests/run_phonology_web.py
python tests/run_phonotactics_corpus.py --web
npm run build
npm run lint
```

The optional browser interaction test `node tests/phonology-browser.mjs` requires
Playwright and Chromium plus a local frontend server. It uses source-derived
fixture API responses; actual D1/API correctness is checked separately above.
No new npm runtime dependency is required by the application.

The current environment could not complete the browser run: Chromium was absent,
and its download failed. Vite development startup also encountered an environment
network-interface restriction. The production build passes and the Worker is
tested on actual local D1; visual/browser sign-off remains pending on the user's
machine. Do not describe the unexecuted browser test as passed.

These checks validate local development behavior. Public hosting capacity,
latency, remote D1 limits and multi-user deployment still require a production
readiness step. No production site has been deployed by this update.
