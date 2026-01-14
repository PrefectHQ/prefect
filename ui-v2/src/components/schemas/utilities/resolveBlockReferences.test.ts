import { describe, expect, test } from "vitest";
import { resolveBlockReferences } from "./resolveBlockReferences";

describe("resolveBlockReferences", () => {
	test("returns values unchanged when no references provided", () => {
		const values = { name: "test", count: 42 };
		const result = resolveBlockReferences(values, undefined);
		expect(result).toEqual(values);
	});

	test("returns values unchanged when references is empty", () => {
		const values = { name: "test", count: 42 };
		const result = resolveBlockReferences(values, {});
		expect(result).toEqual(values);
	});

	test("resolves a simple block reference", () => {
		const values = {
			credentials: { $ref: { block_document_id: "uuid-123" } },
		};
		const references = {
			credentials: {
				block_document: {
					id: "uuid-123",
					name: "my-creds",
					block_type: { slug: "aws-credentials" },
				},
			},
		};

		const result = resolveBlockReferences(values, references);

		expect(result).toEqual({
			credentials: {
				blockTypeSlug: "aws-credentials",
				blockDocumentId: "uuid-123",
			},
		});
	});

	test("preserves non-block-reference values", () => {
		const values = {
			name: "test",
			credentials: { $ref: { block_document_id: "uuid-123" } },
			count: 42,
		};
		const references = {
			credentials: {
				block_document: {
					id: "uuid-123",
					block_type: { slug: "aws-credentials" },
				},
			},
		};

		const result = resolveBlockReferences(values, references);

		expect(result).toEqual({
			name: "test",
			credentials: {
				blockTypeSlug: "aws-credentials",
				blockDocumentId: "uuid-123",
			},
			count: 42,
		});
	});

	test("handles nested objects without block references", () => {
		const values = {
			config: {
				timeout: 30,
				retries: 3,
			},
		};

		const result = resolveBlockReferences(values, {});

		expect(result).toEqual({
			config: {
				timeout: 30,
				retries: 3,
			},
		});
	});

	test("does not resolve when reference key does not match", () => {
		const values = {
			credentials: { $ref: { block_document_id: "uuid-123" } },
		};
		const references = {
			other_credentials: {
				block_document: {
					id: "uuid-456",
					block_type: { slug: "gcp-credentials" },
				},
			},
		};

		const result = resolveBlockReferences(values, references);

		// Should preserve original value since no matching reference
		expect(result).toEqual({
			credentials: { $ref: { block_document_id: "uuid-123" } },
		});
	});
});
