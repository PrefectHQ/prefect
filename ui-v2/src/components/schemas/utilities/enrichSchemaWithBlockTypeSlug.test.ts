import { describe, expect, it } from "vitest";
import { enrichSchemaWithBlockTypeSlug } from "./enrichSchemaWithBlockTypeSlug";

describe("enrichSchemaWithBlockTypeSlug", () => {
	it("converts block_type_slug to blockTypeSlug at the root level", () => {
		const schema = {
			type: "object" as const,
			block_type_slug: "aws-credentials",
		};

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(result.blockTypeSlug).toBe("aws-credentials");
		expect(result.block_type_slug).toBe("aws-credentials");
	});

	it("converts block_type_slug in definitions", () => {
		const schema = {
			type: "object" as const,
			definitions: {
				AwsCredentials: {
					type: "object" as const,
					block_type_slug: "aws-credentials",
				},
				MinIOCredentials: {
					type: "object" as const,
					block_type_slug: "minio-credentials",
				},
			},
		};

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(result.definitions?.AwsCredentials?.blockTypeSlug).toBe(
			"aws-credentials",
		);
		expect(result.definitions?.MinIOCredentials?.blockTypeSlug).toBe(
			"minio-credentials",
		);
	});

	it("converts block_type_slug in properties", () => {
		const schema = {
			type: "object" as const,
			properties: {
				credentials: {
					type: "object" as const,
					block_type_slug: "aws-credentials",
				},
			},
		};

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(result.properties?.credentials?.blockTypeSlug).toBe(
			"aws-credentials",
		);
	});

	it("converts block_type_slug in anyOf", () => {
		const schema = {
			type: "object" as const,
			anyOf: [
				{ type: "object" as const, block_type_slug: "aws-credentials" },
				{ type: "object" as const, block_type_slug: "minio-credentials" },
			],
		};

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(result.anyOf?.[0]?.blockTypeSlug).toBe("aws-credentials");
		expect(result.anyOf?.[1]?.blockTypeSlug).toBe("minio-credentials");
	});

	it("converts block_type_slug in allOf", () => {
		const schema = {
			type: "object" as const,
			allOf: [{ type: "object" as const, block_type_slug: "aws-credentials" }],
		};

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(result.allOf?.[0]?.blockTypeSlug).toBe("aws-credentials");
	});

	it("converts block_type_slug in oneOf", () => {
		const schema = {
			type: "object" as const,
			oneOf: [{ type: "object" as const, block_type_slug: "aws-credentials" }],
		};

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(result.oneOf?.[0]?.blockTypeSlug).toBe("aws-credentials");
	});

	it("converts block_type_slug in items (single)", () => {
		const schema = {
			type: "array" as const,
			items: {
				type: "object" as const,
				block_type_slug: "aws-credentials",
			},
		};

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect((result.items as { blockTypeSlug?: string })?.blockTypeSlug).toBe(
			"aws-credentials",
		);
	});

	it("converts block_type_slug in items (array)", () => {
		const schema = {
			type: "array" as const,
			items: [
				{ type: "object" as const, block_type_slug: "aws-credentials" },
				{ type: "object" as const, block_type_slug: "minio-credentials" },
			],
		};

		const result = enrichSchemaWithBlockTypeSlug(schema);

		const items = result.items as Array<{ blockTypeSlug?: string }>;
		expect(items[0]?.blockTypeSlug).toBe("aws-credentials");
		expect(items[1]?.blockTypeSlug).toBe("minio-credentials");
	});

	it("handles nested structures", () => {
		const schema = {
			type: "object" as const,
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
					type: "object" as const,
					block_type_slug: "aws-credentials",
					properties: {
						nested_creds: {
							type: "object" as const,
							block_type_slug: "nested-credentials",
						},
					},
				},
			},
		};

		type DefinitionWithBlockTypeSlug = {
			blockTypeSlug?: string;
			properties?: Record<string, { blockTypeSlug?: string }>;
		};

		const result = enrichSchemaWithBlockTypeSlug(schema) as {
			definitions?: Record<string, DefinitionWithBlockTypeSlug>;
		};

		const awsCredentials = result.definitions?.["AwsCredentials"];
		expect(awsCredentials?.blockTypeSlug).toBe("aws-credentials");
		expect(awsCredentials?.properties?.["nested_creds"]?.blockTypeSlug).toBe(
			"nested-credentials",
		);
	});

	it("returns the schema unchanged if no block_type_slug is present", () => {
		const schema = {
			type: "object" as const,
			properties: {
				name: { type: "string" as const },
			},
		};

		const result = enrichSchemaWithBlockTypeSlug(schema);

		expect(result).toEqual(schema);
		expect(result.blockTypeSlug).toBeUndefined();
	});

	it("handles null and undefined gracefully", () => {
		expect(enrichSchemaWithBlockTypeSlug(null as never)).toBeNull();
		expect(enrichSchemaWithBlockTypeSlug(undefined as never)).toBeUndefined();
	});
});
