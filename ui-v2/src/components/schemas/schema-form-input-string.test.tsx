import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { SchemaFormInputString } from "./schema-form-input-string";

describe("SchemaFormInputString", () => {
	test("clearing the textarea reports null instead of undefined", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputString
				value="value.split(',')"
				onValueChange={onValueChange}
				property={{ type: "string" }}
				id="format-rule"
			/>,
		);

		const input = document.getElementById("format-rule") as HTMLTextAreaElement;
		expect(input).toBeTruthy();
		await user.clear(input);

		expect(onValueChange).toHaveBeenCalled();
		const last = onValueChange.mock.calls.at(-1)?.[0];
		expect(last).toBeNull();
	});

	test("typing a non-empty value reports the string", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputString
				value=""
				onValueChange={onValueChange}
				property={{ type: "string" }}
				id="format-rule"
			/>,
		);

		const input = document.getElementById("format-rule") as HTMLTextAreaElement;
		await user.type(input, "abc");

		const last = onValueChange.mock.calls.at(-1)?.[0];
		expect(last).toBe("abc");
	});
});
