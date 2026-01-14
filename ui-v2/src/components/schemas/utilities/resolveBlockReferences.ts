import type { components } from "@/api/prefect";
import {
	type BlockDocumentValue,
	isBlockDocumentReferenceValue,
} from "../types/block-document-value";
import type { SchemaFormValues } from "../types/values";

type BlockDocumentReferences =
	components["schemas"]["BlockDocument"]["block_document_references"];

/**
 * Resolves block document references in schema values.
 * Transforms API format { $ref: { block_document_id: "..." } }
 * to UI format { blockTypeSlug: "...", blockDocumentId: "..." }
 */
export function resolveBlockReferences(
	values: SchemaFormValues,
	references: BlockDocumentReferences | undefined,
): SchemaFormValues {
	if (!references || Object.keys(references).length === 0) {
		return values;
	}

	const result: SchemaFormValues = {};

	for (const [key, value] of Object.entries(values)) {
		const reference = references[key];

		if (reference && isBlockDocumentReferenceValue(value)) {
			// Convert to UI format
			const blockDocument = reference as {
				block_document?: {
					id?: string;
					block_type?: { slug?: string };
				};
			};
			const resolved: BlockDocumentValue = {
				blockTypeSlug: blockDocument.block_document?.block_type?.slug ?? "",
				blockDocumentId: blockDocument.block_document?.id,
			};
			result[key] = resolved;
		} else if (
			typeof value === "object" &&
			value !== null &&
			!Array.isArray(value)
		) {
			// Recursively resolve nested objects
			result[key] = resolveBlockReferences(
				value as SchemaFormValues,
				references,
			);
		} else {
			result[key] = value;
		}
	}

	return result;
}
