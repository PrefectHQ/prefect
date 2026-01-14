import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { SchemaFormInputStringFormatPassword } from "./schema-form-input-string-format-password";

describe("SchemaFormInputStringFormatPassword", () => {
	test("renders with type password by default", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatPassword
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = document.getElementById("test-id");
		expect(input).toBeInTheDocument();
		expect(input).toHaveAttribute("type", "password");
	});

	test("has correct id attribute", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatPassword
				value={undefined}
				onValueChange={onValueChange}
				id="my-custom-id"
			/>,
		);

		const input = document.getElementById("my-custom-id");
		expect(input).toBeInTheDocument();
	});

	test("displays value when provided", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatPassword
				value="secret123"
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = document.getElementById("test-id") as HTMLInputElement;
		expect(input.value).toBe("secret123");
	});

	test("toggles visibility when eye button is clicked", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatPassword
				value="secret123"
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = document.getElementById("test-id") as HTMLInputElement;
		const toggleButton = screen.getByRole("button", { name: /show password/i });

		expect(input).toHaveAttribute("type", "password");

		await user.click(toggleButton);

		expect(input).toHaveAttribute("type", "text");
		expect(
			screen.getByRole("button", { name: /hide password/i }),
		).toBeInTheDocument();

		await user.click(screen.getByRole("button", { name: /hide password/i }));

		expect(input).toHaveAttribute("type", "password");
	});

	test("calls onValueChange when input changes", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatPassword
				value=""
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = document.getElementById("test-id") as HTMLInputElement;
		await user.type(input, "newpassword");

		expect(onValueChange).toHaveBeenCalled();
	});

	test("converts empty string to undefined", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatPassword
				value="a"
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = document.getElementById("test-id") as HTMLInputElement;
		await user.clear(input);

		expect(onValueChange).toHaveBeenLastCalledWith(undefined);
	});
});
