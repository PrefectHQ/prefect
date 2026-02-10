import type { SchemaObject } from "openapi-typescript";
import { describe, expect, test } from "vitest";
import { getSchemaObjectLabel } from "./getSchemaObjectLabel";

describe("getSchemaObjectLabel", () => {
	test("returns title for a plain schema object", () => {
		const property: SchemaObject = { type: "string", title: "My String" };
		const schema: SchemaObject = { type: "object" };

		expect(getSchemaObjectLabel(property, schema)).toBe("My String");
	});

	test("returns format when no title", () => {
		const property: SchemaObject = { type: "string", format: "date-time" };
		const schema: SchemaObject = { type: "object" };

		expect(getSchemaObjectLabel(property, schema)).toBe("date-time");
	});

	test("returns type label when no title or format", () => {
		const property: SchemaObject = { type: "string" };
		const schema: SchemaObject = { type: "object" };

		expect(getSchemaObjectLabel(property, schema)).toBe("str");
	});

	test("returns 'Field' when no title, format, or type", () => {
		const property: SchemaObject = {};
		const schema: SchemaObject = { type: "object" };

		expect(getSchemaObjectLabel(property, schema)).toBe("Field");
	});

	test("resolves $ref and returns definition title", () => {
		const property = { $ref: "#/definitions/MyType" };
		const schema: SchemaObject = {
			type: "object",
			definitions: {
				MyType: { type: "string", title: "Resolved Title" },
			},
		};

		expect(getSchemaObjectLabel(property, schema)).toBe("Resolved Title");
	});

	test("preserves sibling title from $ref when definition has no title", () => {
		const property = { $ref: "#/definitions/MyType", title: "Sibling Title" };
		const schema: SchemaObject = {
			type: "object",
			definitions: {
				MyType: { type: "string" },
			},
		};

		expect(getSchemaObjectLabel(property, schema)).toBe("Sibling Title");
	});

	test("uses sibling title when schema has no definitions", () => {
		const property = {
			$ref: "#/definitions/JsonValue",
			title: "JSON",
		};
		const schema: SchemaObject = {
			type: "object",
			properties: {},
		};

		expect(getSchemaObjectLabel(property, schema)).toBe("JSON");
	});

	test("returns 'Field' for $ref with no definitions and no sibling properties", () => {
		const property = { $ref: "#/definitions/Unknown" };
		const schema: SchemaObject = { type: "object" };

		expect(getSchemaObjectLabel(property, schema)).toBe("Field");
	});

	test("definition title takes precedence over sibling title", () => {
		const property = {
			$ref: "#/definitions/MyType",
			title: "Sibling",
		};
		const schema: SchemaObject = {
			type: "object",
			definitions: {
				MyType: { type: "string", title: "Definition" },
			},
		};

		expect(getSchemaObjectLabel(property, schema)).toBe("Sibling");
	});
});
