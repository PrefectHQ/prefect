import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { useState } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { type FormMode, FormModeToggle } from "./form-mode-toggle";

describe("FormModeToggle", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	const formContent = <div data-testid="form-content">Form Content</div>;
	const jsonContent = <div data-testid="json-content">JSON Content</div>;

	it("renders Form and JSON tabs", () => {
		render(
			<FormModeToggle formContent={formContent} jsonContent={jsonContent} />,
		);

		expect(screen.getByRole("tab", { name: "Form" })).toBeVisible();
		expect(screen.getByRole("tab", { name: "JSON" })).toBeVisible();
	});

	it("shows Form tab as selected by default", () => {
		render(
			<FormModeToggle formContent={formContent} jsonContent={jsonContent} />,
		);

		const formTab = screen.getByRole("tab", { name: "Form" });
		const jsonTab = screen.getByRole("tab", { name: "JSON" });

		expect(formTab).toHaveAttribute("aria-selected", "true");
		expect(jsonTab).toHaveAttribute("aria-selected", "false");
	});

	it("shows JSON tab as selected when defaultValue is JSON", () => {
		render(
			<FormModeToggle
				defaultValue="JSON"
				formContent={formContent}
				jsonContent={jsonContent}
			/>,
		);

		const formTab = screen.getByRole("tab", { name: "Form" });
		const jsonTab = screen.getByRole("tab", { name: "JSON" });

		expect(formTab).toHaveAttribute("aria-selected", "false");
		expect(jsonTab).toHaveAttribute("aria-selected", "true");
	});

	it("renders form content by default", () => {
		render(
			<FormModeToggle formContent={formContent} jsonContent={jsonContent} />,
		);

		expect(screen.getByTestId("form-content")).toBeVisible();
	});

	it("renders json content when defaultValue is JSON", () => {
		render(
			<FormModeToggle
				defaultValue="JSON"
				formContent={formContent}
				jsonContent={jsonContent}
			/>,
		);

		expect(screen.getByTestId("json-content")).toBeVisible();
	});

	it("switches to Form content when Form tab is clicked", async () => {
		const user = userEvent.setup();
		render(
			<FormModeToggle
				defaultValue="JSON"
				formContent={formContent}
				jsonContent={jsonContent}
			/>,
		);

		await user.click(screen.getByRole("tab", { name: "Form" }));

		expect(screen.getByTestId("form-content")).toBeVisible();
		expect(screen.getByRole("tab", { name: "Form" })).toHaveAttribute(
			"aria-selected",
			"true",
		);
	});

	it("switches to JSON content when JSON tab is clicked", async () => {
		const user = userEvent.setup();
		render(
			<FormModeToggle formContent={formContent} jsonContent={jsonContent} />,
		);

		await user.click(screen.getByRole("tab", { name: "JSON" }));

		expect(screen.getByTestId("json-content")).toBeVisible();
		expect(screen.getByRole("tab", { name: "JSON" })).toHaveAttribute(
			"aria-selected",
			"true",
		);
	});

	describe("controlled mode", () => {
		it("uses controlled value when value prop is provided", () => {
			render(
				<FormModeToggle
					value="JSON"
					formContent={formContent}
					jsonContent={jsonContent}
				/>,
			);

			const formTab = screen.getByRole("tab", { name: "Form" });
			const jsonTab = screen.getByRole("tab", { name: "JSON" });

			expect(formTab).toHaveAttribute("aria-selected", "false");
			expect(jsonTab).toHaveAttribute("aria-selected", "true");
			expect(screen.getByTestId("json-content")).toBeVisible();
		});

		it("calls onValueChange when tab is clicked in controlled mode", async () => {
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

		it("allows parent to control mode switching", async () => {
			const user = userEvent.setup();

			const ControlledFormModeToggle = () => {
				const [mode, setMode] = useState<FormMode>("Form");
				return (
					<FormModeToggle
						value={mode}
						onValueChange={setMode}
						formContent={formContent}
						jsonContent={jsonContent}
					/>
				);
			};

			render(<ControlledFormModeToggle />);

			// Initially Form is selected
			expect(screen.getByRole("tab", { name: "Form" })).toHaveAttribute(
				"aria-selected",
				"true",
			);
			expect(screen.getByTestId("form-content")).toBeVisible();

			// Click JSON tab
			await user.click(screen.getByRole("tab", { name: "JSON" }));

			// Now JSON should be selected
			expect(screen.getByRole("tab", { name: "JSON" })).toHaveAttribute(
				"aria-selected",
				"true",
			);
			expect(screen.getByTestId("json-content")).toBeVisible();
		});
	});
});
