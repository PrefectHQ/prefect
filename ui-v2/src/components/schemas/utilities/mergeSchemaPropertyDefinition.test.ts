import type { ObjectSubtype, SchemaObject } from "openapi-typescript";
import { describe, expect, test } from "vitest";
import {
	getSchemaDefinition,
	mergeSchemaPropertyDefinition,
} from "./mergeSchemaPropertyDefinition";

describe("getSchemaDefinition", () => {
	test("resolves a definition from #/definitions/", () => {
		const schema = {
			type: "object",
			definitions: {
				MyType: { type: "string", title: "My Type" },
			},
		} as unknown as SchemaObject;

		const result = getSchemaDefinition(schema, "#/definitions/MyType");
		expect(result).toEqual({ type: "string", title: "My Type" });
	});

	test("resolves a definition from #/$defs/", () => {
		const schema: SchemaObject = {
			type: "object",
			$defs: {
				MyType: { type: "integer", title: "My Int" },
			},
		};

		const result = getSchemaDefinition(schema, "#/$defs/MyType");
		expect(result).toEqual({ type: "integer", title: "My Int" });
	});

	test("resolves a #/definitions/ ref when the schema only has $defs", () => {
		const schema: SchemaObject = {
			type: "object",
			$defs: {
				DockerRegistryCredentials: { type: "object", title: "Credentials" },
			},
		};

		const result = getSchemaDefinition(
			schema,
			"#/definitions/DockerRegistryCredentials",
		);
		expect(result).toEqual({ type: "object", title: "Credentials" });
	});

	test("resolves a #/$defs/ ref when the schema only has definitions", () => {
		const schema = {
			type: "object",
			definitions: {
				MyType: { type: "string" },
			},
		} as unknown as SchemaObject;

		const result = getSchemaDefinition(schema, "#/$defs/MyType");
		expect(result).toEqual({ type: "string" });
	});

	test("falls back to $defs when definitions does not have the key", () => {
		const schema = {
			type: "object",
			definitions: {},
			$defs: {
				MyType: { type: "string" },
			},
		} as unknown as SchemaObject;

		const result = getSchemaDefinition(schema, "#/definitions/MyType");
		expect(result).toEqual({ type: "string" });
	});

	test("prefers the container named in the ref when both define the key", () => {
		const schema = {
			type: "object",
			definitions: {
				MyType: { type: "string" },
			},
			$defs: {
				MyType: { type: "integer" },
			},
		} as unknown as SchemaObject;

		expect(getSchemaDefinition(schema, "#/definitions/MyType")).toEqual({
			type: "string",
		});
		expect(getSchemaDefinition(schema, "#/$defs/MyType")).toEqual({
			type: "integer",
		});
	});

	test("throws when definition key is not found in definitions", () => {
		const schema = {
			type: "object",
			definitions: {
				MyType: { type: "string" },
			},
		} as unknown as SchemaObject;

		expect(() => getSchemaDefinition(schema, "#/definitions/Missing")).toThrow(
			"Definition not found for #/definitions/Missing",
		);
	});

	test("returns empty object when schema has no definitions or $defs", () => {
		const schema = {
			type: "object",
			properties: {
				value: { type: "string" },
			},
		} as unknown as SchemaObject;

		const result = getSchemaDefinition(schema, "#/definitions/JsonValue");
		expect(result).toEqual({});
	});
});

describe("mergeSchemaPropertyDefinition", () => {
	test("resolves $ref and merges with sibling properties", () => {
		const property = {
			$ref: "#/definitions/MyType",
			title: "Custom Title",
		};
		const schema = {
			type: "object",
			properties: {},
			definitions: {
				MyType: { type: "string" },
			},
		} as unknown as SchemaObject & ObjectSubtype;

		const result = mergeSchemaPropertyDefinition(property, schema);
		expect(result).toEqual({ type: "string", title: "Custom Title" });
	});

	test("returns sibling properties when schema has no definitions", () => {
		const property = {
			$ref: "#/definitions/JsonValue",
			title: "JSON",
		};
		const schema = {
			type: "object",
			properties: {},
		} as unknown as SchemaObject & ObjectSubtype;

		const result = mergeSchemaPropertyDefinition(property, schema);
		expect(result).toEqual({ title: "JSON" });
	});

	test("returns property as-is when not a reference object", () => {
		const property: SchemaObject = { type: "string", title: "Name" };
		const schema = {
			type: "object",
			properties: {},
		} as unknown as SchemaObject & ObjectSubtype;

		const result = mergeSchemaPropertyDefinition(property, schema);
		expect(result).toEqual({ type: "string", title: "Name" });
	});
});
