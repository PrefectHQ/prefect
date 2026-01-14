import {
	type BlockDocumentReferenceValue,
	isBlockDocumentValue,
} from "../types/block-document-value";
import type { SchemaFormValues } from "../types/values";

/**
 * Transforms UI block document values back to API format.
 * Converts { blockTypeSlug: "...", blockDocumentId: "..." }
 * to { $ref: { block_document_id: "..." } }
 */
export function toBlockReferenceRequest(
	values: SchemaFormValues,
): SchemaFormValues {
	const result: SchemaFormValues = {};

	for (const [key, value] of Object.entries(values)) {
		if (isBlockDocumentValue(value)) {
			if (value.blockDocumentId) {
				const ref: BlockDocumentReferenceValue = {
					$ref: { block_document_id: value.blockDocumentId },
				};
				result[key] = ref;
			} else {
				result[key] = undefined;
			}
		} else if (
			typeof value === "object" &&
			value !== null &&
			!Array.isArray(value)
		) {
			result[key] = toBlockReferenceRequest(value as SchemaFormValues);
		} else {
			result[key] = value;
		}
	}

	return result;
}
