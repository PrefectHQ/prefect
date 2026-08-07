import type { SchemaObject } from "openapi-typescript";
import { describe, expect, test } from "vitest";
import { getIndexForAnyOfPropertyValue } from "./getIndexForAnyOfPropertyValue";

describe("getIndexForAnyOfPropertyValue", () => {
	const schema: SchemaObject = {
		type: "object",
		properties: {},
	};

	test("returns 0 when value is undefined", () => {
		const property = {
			anyOf: [{ type: "string" }, { type: "number" }],
		} as unknown as SchemaObject;
		expect(
			getIndexForAnyOfPropertyValue({ value: undefined, property, schema }),
		).toBe(0);
	});

	test("returns index of string definition for string value", () => {
		const property = {
			anyOf: [{ type: "number" }, { type: "string" }],
		} as unknown as SchemaObject;
		expect(
			getIndexForAnyOfPropertyValue({ value: "hello", property, schema }),
		).toBe(1);
	});

	test("returns index of number definition for number value", () => {
		const property = {
			anyOf: [{ type: "string" }, { type: "number" }],
		} as unknown as SchemaObject;
		expect(getIndexForAnyOfPropertyValue({ value: 42, property, schema })).toBe(
			1,
		);
	});

	test("returns index of boolean definition for boolean value", () => {
		const property = {
			anyOf: [{ type: "string" }, { type: "boolean" }],
		} as unknown as SchemaObject;
		expect(
			getIndexForAnyOfPropertyValue({ value: true, property, schema }),
		).toBe(1);
	});

	test("returns index of enum definition for string value in the enum", () => {
		const property = {
			anyOf: [
				{ type: "string", format: "date" },
				{ type: "string", enum: ["today", "prev", "prev_td"] },
			],
		} as unknown as SchemaObject;
		expect(
			getIndexForAnyOfPropertyValue({ value: "prev_td", property, schema }),
		).toBe(1);
	});

	test("returns index of non enum definition for string value not in the enum", () => {
		const property = {
			anyOf: [
				{ type: "string", format: "date" },
				{ type: "string", enum: ["today", "prev", "prev_td"] },
			],
		} as unknown as SchemaObject;
		expect(
			getIndexForAnyOfPropertyValue({ value: "2024-01-15", property, schema }),
		).toBe(0);
	});

	test("returns index of matching enum definition when every definition is an enum", () => {
		const property = {
			anyOf: [
				{ type: "string", enum: ["a", "b"] },
				{ type: "string", enum: ["c", "d"] },
			],
		} as unknown as SchemaObject;
		expect(
			getIndexForAnyOfPropertyValue({ value: "c", property, schema }),
		).toBe(1);
	});

	test("returns index of enum definition for number value in the enum", () => {
		const property = {
			anyOf: [{ type: "integer" }, { type: "integer", enum: [1, 2, 3] }],
		} as unknown as SchemaObject;
		expect(getIndexForAnyOfPropertyValue({ value: 2, property, schema })).toBe(
			1,
		);
	});

	describe("prefect kind values", () => {
		test("returns index of typeless definition for json prefect kind value", () => {
			const property = {
				anyOf: [{ type: "string", format: "password" }, { type: "string" }, {}],
			} as unknown as SchemaObject;
			const value = { __prefect_kind: "json", value: '{"key": "val"}' };
			expect(getIndexForAnyOfPropertyValue({ value, property, schema })).toBe(
				2,
			);
		});

		test("returns index of typeless definition for jinja prefect kind value", () => {
			const property = {
				anyOf: [{ type: "string", format: "password" }, { type: "string" }, {}],
			} as unknown as SchemaObject;
			const value = {
				__prefect_kind: "jinja",
				template: "{{ flow_run.name }}",
			};
			expect(getIndexForAnyOfPropertyValue({ value, property, schema })).toBe(
				2,
			);
		});

		test("returns index of typeless definition for workspace_variable prefect kind value", () => {
			const property = {
				anyOf: [{ type: "string", format: "password" }, { type: "string" }, {}],
			} as unknown as SchemaObject;
			const value = {
				__prefect_kind: "workspace_variable",
				variable_name: "my_var",
			};
			expect(getIndexForAnyOfPropertyValue({ value, property, schema })).toBe(
				2,
			);
		});

		test("falls back to 0 when no typeless definition exists for prefect kind value", () => {
			const property = {
				anyOf: [{ type: "string" }, { type: "number" }],
			} as unknown as SchemaObject;
			const value = { __prefect_kind: "json", value: '{"key": "val"}' };
			expect(getIndexForAnyOfPropertyValue({ value, property, schema })).toBe(
				0,
			);
		});
	});

	test("returns 0 when using default value and value is undefined", () => {
		const property = {
			anyOf: [{ type: "string" }, { type: "number" }],
			default: "default-value",
		} as unknown as SchemaObject;
		expect(
			getIndexForAnyOfPropertyValue({ value: undefined, property, schema }),
		).toBe(0);
	});
});
