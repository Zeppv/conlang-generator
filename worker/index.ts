type ConceptSummary = {
	id: number;
	concepticon_id: string;
	gloss: string;
	definition: string | null;
	semantic_field: string | null;
	ontological_category: string | null;
};

type RelationRow = {
	related_concept_id: number;
	related_gloss: string;
	relation_type: string;
	source_id: string;
	language_count: number | null;
	family_count: number | null;
	evidence_count: number;
};

function errorResponse(message: string, status = 400) {
	return Response.json(
		{ error: message },
		{ status }
	);
}

export default {
	async fetch(request, env): Promise<Response> {

		const url = new URL(request.url);

		// ------------------------------------------------
		// HEALTH CHECK
		// ------------------------------------------------

		if (
			request.method === "GET" &&
			url.pathname === "/api/health"
		) {

			const result = await env.conlang_reference
				.prepare(
					`
					SELECT
						COUNT(*) AS concept_count
					FROM concept
					`
				)
				.first<{ concept_count: number }>();

			return Response.json({
				ok: true,
				concept_count:
					result?.concept_count ?? 0,
			});
		}


		// ------------------------------------------------
		// SEARCH CONCEPTS
		// ------------------------------------------------

		if (
			request.method === "GET" &&
			url.pathname === "/api/concepts"
		) {

			const search =
				url.searchParams
					.get("search")
					?.trim() ?? "";

			if (!search) {
				return errorResponse(
					"Search text is required."
				);
			}

			const result = await env.conlang_reference
				.prepare(
					`
					SELECT
						id,
						concepticon_id,
						gloss,
						definition,
						semantic_field,
						ontological_category
					FROM concept
					WHERE
						LOWER(gloss) = LOWER(?1)
						OR
						LOWER(gloss) LIKE LOWER(?2)
					ORDER BY
						CASE
							WHEN LOWER(gloss) = LOWER(?1)
							THEN 0
							ELSE 1
						END,
						LENGTH(gloss),
						gloss
					LIMIT 20
					`
				)
				.bind(
					search,
					`%${search}%`
				)
				.all<ConceptSummary>();

			return Response.json({
				results: result.results,
			});
		}


		// ------------------------------------------------
		// GET ONE CONCEPT + RELATIONSHIPS
		// ------------------------------------------------

		const conceptMatch =
			url.pathname.match(
				/^\/api\/concepts\/(\d+)$/
			);

		if (
			request.method === "GET" &&
			conceptMatch
		) {

			const conceptId =
				Number(conceptMatch[1]);

			const concept = await env.conlang_reference
				.prepare(
					`
					SELECT
						id,
						concepticon_id,
						gloss,
						definition,
						semantic_field,
						ontological_category
					FROM concept
					WHERE id = ?1
					`
				)
				.bind(conceptId)
				.first<ConceptSummary>();

			if (!concept) {
				return errorResponse(
					"Concept not found.",
					404
				);
			}


			/*
				The raw Concepticon network can contain
				multiple pieces of evidence for the same
				concept relationship.

				This query groups those duplicates for
				the website while preserving the raw
				evidence in the database.
			*/

			const relations = await env.conlang_reference
				.prepare(
					`
					WITH normalized AS (

						SELECT

							CASE
								WHEN r.source_concept_id = ?1
								THEN r.target_concept_id
								ELSE r.source_concept_id
							END
							AS related_concept_id,

							CASE
								WHEN r.source_concept_id = ?1
								THEN target.gloss
								ELSE source.gloss
							END
							AS related_gloss,

							r.relation_type,
							r.source_id,
							r.language_count,
							r.family_count

						FROM concept_relation r

						JOIN concept source
							ON source.id =
							r.source_concept_id

						JOIN concept target
							ON target.id =
							r.target_concept_id

						WHERE
							r.source_concept_id = ?1
							OR
							r.target_concept_id = ?1
					)

					SELECT

						related_concept_id,
						related_gloss,
						relation_type,
						source_id,

						MAX(language_count)
							AS language_count,

						MAX(family_count)
							AS family_count,

						COUNT(*)
							AS evidence_count

					FROM normalized

					GROUP BY
						related_concept_id,
						related_gloss,
						relation_type,
						source_id

					ORDER BY

            CASE source_id
              WHEN 'datsemshift' THEN 0
              WHEN 'wordnet' THEN 1
              WHEN 'clics' THEN 2
              WHEN 'concepticon' THEN 3
              ELSE 4
            END,

            COALESCE(
              MAX(family_count),
              0
            ) DESC,

            COUNT(*) DESC,

          related_gloss

        LIMIT 200
					`
				)
				.bind(conceptId)
				.all<RelationRow>();


			return Response.json({
				concept,
				relations: relations.results,
			});
		}


		return errorResponse(
			"API route not found.",
			404
		);
	},
} satisfies ExportedHandler<Env>;