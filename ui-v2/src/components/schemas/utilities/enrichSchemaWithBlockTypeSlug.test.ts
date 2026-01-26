import { describe, expect, it } from "vitest";
import type { PrefectSchemaObject } from "../types/schemas";
import { enrichSchemaWithBlockTypeSlug } from "./enrichSchemaWithBlockTypeSlug";

describe("enrichSchemaWithBlockTypeSlug", () => {
	it("converts block_type_slug to blockTypeSlug at the root level", () => {
		const schema = {
			type: "object",
			block_type_slug: "aws-credentials",
		} as unknown as PrefectSchemaObject;

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(result.blockTypeSlug).toBe("aws-credentials");
		expect((result as unknown as Record<string, unknown>).block_type_slug).toBe(
			"aws-credentials",
		);
	});

	it("converts block_type_slug in definitions", () => {
		const schema = {
			type: "object",
			definitions: {
				AwsCredentials: {
					type: "object",
					block_type_slug: "aws-credentials",
				},
				MinIOCredentials: {
					type: "object",
					block_type_slug: "minio-credentials",
				},
			},
		} as unknown as PrefectSchemaObject;

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(
			(result.definitions?.AwsCredentials as { blockTypeSlug?: string })
				?.blockTypeSlug,
		).toBe("aws-credentials");
		expect(
			(result.definitions?.MinIOCredentials as { blockTypeSlug?: string })
				?.blockTypeSlug,
		).toBe("minio-credentials");
	});

	it("converts block_type_slug in properties", () => {
		const schema = {
			type: "object",
			properties: {
				credentials: {
					type: "object",
					block_type_slug: "aws-credentials",
				},
			},
		} as unknown as PrefectSchemaObject;

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(
			(result.properties?.credentials as { blockTypeSlug?: string })
				?.blockTypeSlug,
		).toBe("aws-credentials");
	});

	it("converts block_type_slug in anyOf", () => {
		const schema = {
			type: "object",
			anyOf: [
				{ type: "object", block_type_slug: "aws-credentials" },
				{ type: "object", block_type_slug: "minio-credentials" },
			],
		} as unknown as PrefectSchemaObject;

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(
			(result.anyOf?.[0] as { blockTypeSlug?: string })?.blockTypeSlug,
		).toBe("aws-credentials");
		expect(
			(result.anyOf?.[1] as { blockTypeSlug?: string })?.blockTypeSlug,
		).toBe("minio-credentials");
	});

	it("converts block_type_slug in allOf", () => {
		const schema = {
			type: "object",
			allOf: [{ type: "object", block_type_slug: "aws-credentials" }],
		} as unknown as PrefectSchemaObject;

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(
			(result.allOf?.[0] as { blockTypeSlug?: string })?.blockTypeSlug,
		).toBe("aws-credentials");
	});

	it("converts block_type_slug in oneOf", () => {
		const schema = {
			type: "object",
			oneOf: [{ type: "object", block_type_slug: "aws-credentials" }],
		} as unknown as PrefectSchemaObject;

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(
			(result.oneOf?.[0] as { blockTypeSlug?: string })?.blockTypeSlug,
		).toBe("aws-credentials");
	});

	it("converts block_type_slug in items (single)", () => {
		const schema = {
			type: "array",
			items: {
				type: "object",
				block_type_slug: "aws-credentials",
			},
		} as unknown as PrefectSchemaObject;

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(
			(
				(result as unknown as Record<string, unknown>).items as {
					blockTypeSlug?: string;
				}
			)?.blockTypeSlug,
		).toBe("aws-credentials");
	});

	it("converts block_type_slug in items (array)", () => {
		const schema = {
			type: "array",
			items: [
				{ type: "object", block_type_slug: "aws-credentials" },
				{ type: "object", block_type_slug: "minio-credentials" },
			],
		} as unknown as PrefectSchemaObject;

		const result = enrichSchemaWithBlockTypeSlug(schema);

		const items = (result as unknown as Record<string, unknown>)
			.items as Array<{
			blockTypeSlug?: string;
		}>;
		expect(items[0]?.blockTypeSlug).toBe("aws-credentials");
		expect(items[1]?.blockTypeSlug).toBe("minio-credentials");
	});

	it("handles nested structures", () => {
		const schema = {
			type: "object",
			properties: {
				credentials: {
					anyOf: [
						{
							$ref: "#/definitions/AwsCredentials",
						},
					],
				},
			},
			definitions: {
				AwsCredentials: {
					type: "object",
					block_type_slug: "aws-credentials",
					properties: {
						nested_creds: {
							type: "object",
							block_type_slug: "nested-credentials",
						},
					},
				},
			},
		} as unknown as PrefectSchemaObject;

		type DefinitionWithBlockTypeSlug = {
			blockTypeSlug?: string;
			properties?: Record<string, { blockTypeSlug?: string }>;
		};

		const result = enrichSchemaWithBlockTypeSlug(schema);

		const awsCredentials = result.definitions
			?.AwsCredentials as DefinitionWithBlockTypeSlug;
		expect(awsCredentials?.blockTypeSlug).toBe("aws-credentials");
		expect(awsCredentials?.properties?.nested_creds?.blockTypeSlug).toBe(
			"nested-credentials",
		);
	});

	it("returns the schema unchanged if no block_type_slug is present", () => {
		const schema = {
			type: "object",
			properties: {
				name: { type: "string" },
			},
		} as unknown as PrefectSchemaObject;

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(result).toEqual(schema);
		expect(result.blockTypeSlug).toBeUndefined();
	});

	it("handles null and undefined gracefully", () => {
		expect(
			enrichSchemaWithBlockTypeSlug(null as unknown as PrefectSchemaObject),
		).toBeNull();
		expect(
			enrichSchemaWithBlockTypeSlug(
				undefined as unknown as PrefectSchemaObject,
			),
		).toBeUndefined();
	});
});
