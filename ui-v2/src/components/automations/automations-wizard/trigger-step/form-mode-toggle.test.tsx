import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { FormModeToggle } from "./form-mode-toggle";

describe("FormModeToggle", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	const formContent = <div data-testid="form-content">Form Content</div>;
	const jsonContent = <div data-testid="json-content">JSON Content</div>;

	it("renders Form and JSON tabs", () => {
		const onValueChange = vi.fn();
		render(
			<FormModeToggle
				value="Form"
				onValueChange={onValueChange}
				formContent={formContent}
				jsonContent={jsonContent}
			/>,
		);

		expect(screen.getByRole("tab", { name: "Form" })).toBeVisible();
		expect(screen.getByRole("tab", { name: "JSON" })).toBeVisible();
	});

	it("shows Form tab as selected when value is Form", () => {
		const onValueChange = vi.fn();
		render(
			<FormModeToggle
				value="Form"
				onValueChange={onValueChange}
				formContent={formContent}
				jsonContent={jsonContent}
			/>,
		);

		const formTab = screen.getByRole("tab", { name: "Form" });
		const jsonTab = screen.getByRole("tab", { name: "JSON" });

		expect(formTab).toHaveAttribute("aria-selected", "true");
		expect(jsonTab).toHaveAttribute("aria-selected", "false");
	});

	it("shows JSON tab as selected when value is JSON", () => {
		const onValueChange = vi.fn();
		render(
			<FormModeToggle
				value="JSON"
				onValueChange={onValueChange}
				formContent={formContent}
				jsonContent={jsonContent}
			/>,
		);

		const formTab = screen.getByRole("tab", { name: "Form" });
		const jsonTab = screen.getByRole("tab", { name: "JSON" });

		expect(formTab).toHaveAttribute("aria-selected", "false");
		expect(jsonTab).toHaveAttribute("aria-selected", "true");
	});

	it("renders form content when Form is selected", () => {
		const onValueChange = vi.fn();
		render(
			<FormModeToggle
				value="Form"
				onValueChange={onValueChange}
				formContent={formContent}
				jsonContent={jsonContent}
			/>,
		);

		expect(screen.getByTestId("form-content")).toBeVisible();
	});

	it("renders json content when JSON is selected", () => {
		const onValueChange = vi.fn();
		render(
			<FormModeToggle
				value="JSON"
				onValueChange={onValueChange}
				formContent={formContent}
				jsonContent={jsonContent}
			/>,
		);

		expect(screen.getByTestId("json-content")).toBeVisible();
	});

	it("calls onValueChange with 'Form' when Form tab is clicked", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();
		render(
			<FormModeToggle
				value="JSON"
				onValueChange={onValueChange}
				formContent={formContent}
				jsonContent={jsonContent}
			/>,
		);

		await user.click(screen.getByRole("tab", { name: "Form" }));

		expect(onValueChange).toHaveBeenCalledWith("Form");
	});

	it("calls onValueChange with 'JSON' when JSON tab is clicked", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();
		render(
			<FormModeToggle
				value="Form"
				onValueChange={onValueChange}
				formContent={formContent}
				jsonContent={jsonContent}
			/>,
		);

		await user.click(screen.getByRole("tab", { name: "JSON" }));

		expect(onValueChange).toHaveBeenCalledWith("JSON");
	});
});
