import { describe, expect, test } from "vitest";
import { toBlockReferenceRequest } from "./toBlockReferenceRequest";

describe("toBlockReferenceRequest", () => {
	test("transforms block document value to API format", () => {
		const values = {
			credentials: {
				blockTypeSlug: "aws-credentials",
				blockDocumentId: "uuid-123",
			},
		};

		const result = toBlockReferenceRequest(values);

		expect(result).toEqual({
			credentials: { $ref: { block_document_id: "uuid-123" } },
		});
	});

	test("sets undefined when blockDocumentId is missing", () => {
		const values = {
			credentials: {
				blockTypeSlug: "aws-credentials",
				blockDocumentId: undefined,
			},
		};

		const result = toBlockReferenceRequest(values);

		expect(result).toEqual({
			credentials: undefined,
		});
	});

	test("preserves non-block values", () => {
		const values = {
			name: "test",
			credentials: {
				blockTypeSlug: "aws-credentials",
				blockDocumentId: "uuid-123",
			},
			count: 42,
		};

		const result = toBlockReferenceRequest(values);

		expect(result).toEqual({
			name: "test",
			credentials: { $ref: { block_document_id: "uuid-123" } },
			count: 42,
		});
	});

	test("handles nested objects", () => {
		const values = {
			config: {
				timeout: 30,
				retries: 3,
			},
		};

		const result = toBlockReferenceRequest(values);

		expect(result).toEqual({
			config: {
				timeout: 30,
				retries: 3,
			},
		});
	});

	test("handles deeply nested block values", () => {
		const values = {
			outer: {
				inner: {
					credentials: {
						blockTypeSlug: "aws-credentials",
						blockDocumentId: "uuid-123",
					},
				},
			},
		};

		const result = toBlockReferenceRequest(values);

		expect(result).toEqual({
			outer: {
				inner: {
					credentials: { $ref: { block_document_id: "uuid-123" } },
				},
			},
		});
	});
});
