import { render } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { SchemaFormInputNumber } from "./schema-form-input-number";

describe("SchemaFormInputNumber", () => {
	test("uses step=any so high-precision float defaults pass HTML validation", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputNumber
				value={0.001}
				onValueChange={onValueChange}
				property={{ type: "number" }}
				id="precision-test"
			/>,
		);

		const input = document.getElementById("precision-test");
		expect(input).toBeInTheDocument();
		expect(input).toHaveAttribute("step", "any");
		expect(input).toHaveAttribute("type", "number");
	});
});
