import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { InformationStep } from "./information-step";

describe("InformationStep", () => {
	const mockOnChange = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders all form fields", () => {
		render(
			<InformationStep
				values={{
					name: "",
					description: "",
					concurrencyLimit: null,
				}}
				onChange={mockOnChange}
			/>,
		);

		expect(screen.getByLabelText("Name")).toBeInTheDocument();
		expect(screen.getByLabelText("Description (Optional)")).toBeInTheDocument();
		expect(
			screen.getByLabelText("Flow Run Concurrency (Optional)"),
		).toBeInTheDocument();
	});

	it("displays initial values", () => {
		render(
			<InformationStep
				values={{
					name: "test-pool",
					description: "Test description",
					concurrencyLimit: 10,
				}}
				onChange={mockOnChange}
			/>,
		);

		expect(screen.getByDisplayValue("test-pool")).toBeInTheDocument();
		expect(screen.getByDisplayValue("Test description")).toBeInTheDocument();
		expect(screen.getByDisplayValue("10")).toBeInTheDocument();
	});

	it("calls onChange when name is changed", async () => {
		const user = userEvent.setup();
		render(
			<InformationStep
				values={{
					name: "",
					description: "",
					concurrencyLimit: null,
				}}
				onChange={mockOnChange}
			/>,
		);

		const nameInput = screen.getByLabelText("Name");
		await user.type(nameInput, "n");

		expect(mockOnChange).toHaveBeenCalledWith({
			name: "n",
		});
	});

	it("calls onChange when description is changed", async () => {
		const user = userEvent.setup();
		render(
			<InformationStep
				values={{
					name: "test-pool",
					description: "",
					concurrencyLimit: null,
				}}
				onChange={mockOnChange}
			/>,
		);

		const descriptionInput = screen.getByLabelText("Description (Optional)");
		await user.type(descriptionInput, "N");

		expect(mockOnChange).toHaveBeenCalledWith({
			description: "N",
		});
	});

	it("calls onChange when concurrency limit is changed", async () => {
		const user = userEvent.setup();
		render(
			<InformationStep
				values={{
					name: "test-pool",
					description: "",
					concurrencyLimit: null,
				}}
				onChange={mockOnChange}
			/>,
		);

		const concurrencyInput = screen.getByLabelText(
			"Flow Run Concurrency (Optional)",
		);
		await user.type(concurrencyInput, "5");

		expect(mockOnChange).toHaveBeenCalledWith({
			concurrencyLimit: 5,
		});
	});

	// Note: isPaused field removed as it's not in the actual component

	// Note: The actual component doesn't display validation errors

	// Note: The actual component doesn't have an onBlur prop

	it("handles empty concurrency limit", async () => {
		const user = userEvent.setup();
		render(
			<InformationStep
				values={{
					name: "test-pool",
					description: "",
					concurrencyLimit: 10,
				}}
				onChange={mockOnChange}
			/>,
		);

		const concurrencyInput = screen.getByLabelText(
			"Flow Run Concurrency (Optional)",
		);
		await user.clear(concurrencyInput);

		expect(mockOnChange).toHaveBeenCalledWith({
			concurrencyLimit: null,
		});
	});

	// Note: The actual component doesn't show helpful text
});
