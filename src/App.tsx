import { useState } from "react";
import type { FormEvent } from "react";
import "./App.css";

type Concept = {
	id: number;
	concepticon_id: string;
	gloss: string;
	definition: string | null;
	semantic_field: string | null;
	ontological_category: string | null;
};

type Relation = {
	related_concept_id: number;
	related_gloss: string;
	relation_type: string;
	source_id: string;
	language_count: number | null;
	family_count: number | null;
	evidence_count: number;
};

type ConceptDetail = {
	concept: Concept;
	relations: Relation[];
};

type SearchResponse = {
	results?: Concept[];
	error?: string;
};

type ConceptResponse = {
	concept?: Concept;
	relations?: Relation[];
	error?: string;
};

function App() {
	const [search, setSearch] = useState("mountain");
	const [results, setResults] = useState<Concept[]>([]);
	const [selected, setSelected] = useState<ConceptDetail | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState("");

	async function searchConcepts(event?: FormEvent<HTMLFormElement>) {
		event?.preventDefault();

		const query = search.trim();

		if (!query) {
			return;
		}

		setLoading(true);
		setError("");
		setSelected(null);

		try {
			const response = await fetch(
				`/api/concepts?search=${encodeURIComponent(query)}`
			);

			const data = (await response.json()) as SearchResponse;

			if (!response.ok) {
				throw new Error(data.error ?? "Search failed.");
			}

			const searchResults = data.results ?? [];

      setResults(searchResults);

      // Automatically open the best result.
      // Exact matches are already sorted first by the API.
      if (searchResults.length > 0) {
        await openConcept(
          searchResults[0].id
        );
      }
		} catch (err) {
			setError(
				err instanceof Error
					? err.message
					: "Search failed."
			);
		} finally {
			setLoading(false);
		}
	}

	async function openConcept(conceptId: number) {
		setLoading(true);
		setError("");

		try {
			const response = await fetch(
				`/api/concepts/${conceptId}`
			);

			const data = (await response.json()) as ConceptResponse;

			if (!response.ok) {
				throw new Error(
					data.error ?? "Unable to load concept."
				);
			}

			if (!data.concept) {
				throw new Error(
					"The API returned no concept."
				);
			}

			setSelected({
				concept: data.concept,
				relations: data.relations ?? [],
			});
		} catch (err) {
			setError(
				err instanceof Error
					? err.message
					: "Unable to load concept."
			);
		} finally {
			setLoading(false);
		}
	}

	return (
		<main className="page">
			<header className="hero">
				<p className="eyebrow">
					CONLANG PROJECT
				</p>

				<h1>Concept Explorer</h1>

				<p className="intro">
					Explore the semantic knowledge that will
					eventually power the conlang generator.
				</p>
			</header>

			<form
				className="search"
				onSubmit={searchConcepts}
			>
				<input
					value={search}
					onChange={(event) =>
						setSearch(event.target.value)
					}
					placeholder="Search concepts..."
				/>

				<button type="submit">
					Search
				</button>
			</form>

			{loading && (
				<p className="status">
					Loading...
				</p>
			)}

			{error && (
				<p className="error">
					{error}
				</p>
			)}

			<div className="layout">
				<section className="panel">
					<h2>Search results</h2>

					{results.length === 0 && (
						<p className="muted">
							Search for a concept to begin.
						</p>
					)}

					<div className="resultList">
						{results.map((concept) => (
							<button
								key={concept.id}
								type="button"
								className="result"
								onClick={() =>
									openConcept(concept.id)
								}
							>
								<strong>
									{concept.gloss}
								</strong>

								<span>
									Concepticon{" "}
									{concept.concepticon_id}
								</span>
							</button>
						))}
					</div>
				</section>

				<section className="panel detail">
					{!selected && (
						<p className="muted">
							Select a concept to view its
							semantic relationships.
						</p>
					)}

					{selected && (
						<>
							<div className="conceptHeader">
								<p className="eyebrow">
									CONCEPT
								</p>

								<h2>
									{selected.concept.gloss}
								</h2>

								<p>
									{selected.concept.definition ??
										"No definition available."}
								</p>
							</div>

							<div className="metadata">
								<div>
									<span>
										Concepticon
									</span>

									<strong>
										{
											selected.concept
												.concepticon_id
										}
									</strong>
								</div>

								<div>
									<span>
										Semantic field
									</span>

									<strong>
										{
											selected.concept
												.semantic_field ??
											"Unknown"
										}
									</strong>
								</div>

								<div>
									<span>
										Category
									</span>

									<strong>
										{
											selected.concept
												.ontological_category ??
											"Unknown"
										}
									</strong>
								</div>
							</div>

							<h3>
								Related concepts
							</h3>

							{selected.relations.length === 0 && (
								<p className="muted">
									No relationships found.
								</p>
							)}

							<div className="relations">
								{selected.relations.map(
									(relation) => (
										<button
											key={`${relation.related_concept_id}-${relation.relation_type}-${relation.source_id}`}
											type="button"
											className="relation"
											onClick={() =>
												openConcept(
													relation.related_concept_id
												)
											}
										>
											<div>
												<strong>
													{
														relation.related_gloss
													}
												</strong>

												<span>
													{
														relation.relation_type
													}
													{" · "}
													{
														relation.source_id
													}
												</span>
											</div>

											<div className="relationStats">
												{relation.family_count !==
													null && (
													<span>
														{
															relation.family_count
														}{" "}
														families
													</span>
												)}

												{relation.language_count !==
													null && (
													<span>
														{
															relation.language_count
														}{" "}
														languages
													</span>
												)}

												{relation.evidence_count >
													1 && (
													<span>
														{
															relation.evidence_count
														}{" "}
														evidence records
													</span>
												)}
											</div>
										</button>
									)
								)}
							</div>
						</>
					)}
				</section>
			</div>
		</main>
	);
}

export default App;