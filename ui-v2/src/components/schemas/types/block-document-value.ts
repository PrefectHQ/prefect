/**
 * The API format for block document references.
 * This is how nested block references come from the server.
 */
export type BlockDocumentReferenceValue = {
	$ref: {
		block_document_id: string;
	};
};

/**
 * The UI format for block document values.
 * This is the transformed format used within the schema form.
 */
export type BlockDocumentValue = {
	blockTypeSlug: string;
	blockDocumentId: string | undefined;
};

/**
 * Type guard to check if a value is an API block document reference.
 */
export function isBlockDocumentReferenceValue(
	value: unknown,
): value is BlockDocumentReferenceValue {
	return (
		typeof value === "object" &&
		value !== null &&
		"$ref" in value &&
		typeof (value as Record<string, unknown>).$ref === "object" &&
		(value as Record<string, unknown>).$ref !== null &&
		"block_document_id" in
			((value as Record<string, unknown>).$ref as Record<string, unknown>)
	);
}

/**
 * Type guard to check if a value is a UI block document value.
 */
export function isBlockDocumentValue(
	value: unknown,
): value is BlockDocumentValue {
	return (
		typeof value === "object" &&
		value !== null &&
		"blockTypeSlug" in value &&
		typeof (value as Record<string, unknown>).blockTypeSlug === "string"
	);
}
