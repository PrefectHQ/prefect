import { describe, expect, test } from "vitest";
import { removePrefectKindValues } from "./removePrefectKindValues";

describe("removePrefectKindValues", () => {
	test("parses json kind values into native objects", () => {
		const result = removePrefectKindValues({
			env: {
				__prefect_kind: "json",
				value: '{"CDWH_ENVIRONMENT":"dev"}',
			},
		});

		expect(result).toEqual({ env: { CDWH_ENVIRONMENT: "dev" } });
	});

	test("drops json kind values that have no content", () => {
		const result = removePrefectKindValues({
			env: { __prefect_kind: "json", value: undefined },
			labels: { __prefect_kind: "json", value: "  " },
		});

		expect(result).toEqual({ env: undefined, labels: undefined });
	});

	test("drops json kind values with invalid json instead of saving text", () => {
		const result = removePrefectKindValues({
			env: { __prefect_kind: "json", value: '{"CDWH_ENVIRONMENT": ' },
		});

		expect(result).toEqual({ env: undefined });
	});

	test("keeps json string literals as strings", () => {
		const result = removePrefectKindValues({
			name: { __prefect_kind: "json", value: '"hello"' },
		});

		expect(result).toEqual({ name: "hello" });
	});

	test("removes cleared json kind entries from arrays", () => {
		const result = removePrefectKindValues({
			items: [
				{ __prefect_kind: "json", value: undefined },
				{ __prefect_kind: "json", value: "not json" },
				{ __prefect_kind: "json", value: '{"a":1}' },
			],
		});

		expect(result).toEqual({ items: [{ a: 1 }] });
	});

	test("recurses into nested objects and arrays", () => {
		const result = removePrefectKindValues({
			config: {
				nested: { __prefect_kind: "json", value: '{"a":1}' },
				items: [{ __prefect_kind: "json", value: "[1,2]" }, "plain"],
			},
		});

		expect(result).toEqual({
			config: { nested: { a: 1 }, items: [[1, 2], "plain"] },
		});
	});

	test("leaves plain values and block references untouched", () => {
		const values = {
			name: "worker",
			count: 2,
			registry_credentials: { $ref: { block_document_id: "abc" } },
			env: { FOO: "bar" },
		};

		expect(removePrefectKindValues(values)).toEqual(values);
	});
});
