import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { FormModeToggle } from "./form-mode-toggle";

describe("FormModeToggle", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	it("renders Form and JSON buttons", () => {
		const onValueChange = vi.fn();
		render(<FormModeToggle value="Form" onValueChange={onValueChange} />);

		expect(screen.getByRole("button", { name: "Form" })).toBeVisible();
		expect(screen.getByRole("button", { name: "JSON" })).toBeVisible();
	});

	it("shows Form button as active when value is Form", () => {
		const onValueChange = vi.fn();
		render(<FormModeToggle value="Form" onValueChange={onValueChange} />);

		const formButton = screen.getByRole("button", { name: "Form" });
		const jsonButton = screen.getByRole("button", { name: "JSON" });

		expect(formButton).not.toHaveClass("border");
		expect(jsonButton).toHaveClass("border");
	});

	it("shows JSON button as active when value is JSON", () => {
		const onValueChange = vi.fn();
		render(<FormModeToggle value="JSON" onValueChange={onValueChange} />);

		const formButton = screen.getByRole("button", { name: "Form" });
		const jsonButton = screen.getByRole("button", { name: "JSON" });

		expect(formButton).toHaveClass("border");
		expect(jsonButton).not.toHaveClass("border");
	});

	it("calls onValueChange with 'Form' when Form button is clicked", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();
		render(<FormModeToggle value="JSON" onValueChange={onValueChange} />);

		await user.click(screen.getByRole("button", { name: "Form" }));

		expect(onValueChange).toHaveBeenCalledWith("Form");
		expect(onValueChange).toHaveBeenCalledTimes(1);
	});

	it("calls onValueChange with 'JSON' when JSON button is clicked", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();
		render(<FormModeToggle value="Form" onValueChange={onValueChange} />);

		await user.click(screen.getByRole("button", { name: "JSON" }));

		expect(onValueChange).toHaveBeenCalledWith("JSON");
		expect(onValueChange).toHaveBeenCalledTimes(1);
	});

	it("calls onValueChange when clicking the already active button", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();
		render(<FormModeToggle value="Form" onValueChange={onValueChange} />);

		await user.click(screen.getByRole("button", { name: "Form" }));

		expect(onValueChange).toHaveBeenCalledWith("Form");
		expect(onValueChange).toHaveBeenCalledTimes(1);
	});
});
