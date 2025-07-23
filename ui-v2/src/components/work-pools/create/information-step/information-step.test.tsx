import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it, vi } from "vitest";
import { Form } from "@/components/ui/form";
import {
	InformationStep,
	type WorkPoolInformationFormValues,
	workPoolInformationSchema,
} from ".";

const TestWrapper = ({
	defaultValues = {},
	onSubmit = vi.fn(),
}: {
	defaultValues?: Partial<WorkPoolInformationFormValues>;
	onSubmit?: (data: WorkPoolInformationFormValues) => void;
}) => {
	const form = useForm<WorkPoolInformationFormValues>({
		resolver: zodResolver(workPoolInformationSchema),
		defaultValues: {
			name: "",
			description: null,
			concurrencyLimit: null,
			...defaultValues,
		},
	});

	return (
		<Form {...form}>
			<form
				onSubmit={(e) => {
					e.preventDefault();
					void form.handleSubmit((data) => onSubmit(data))(e);
				}}
			>
				<InformationStep />
				<button type="submit">Submit</button>
			</form>
		</Form>
	);
};

describe("InformationStep", () => {
	it("renders all form fields", () => {
		render(<TestWrapper />);

		expect(screen.getByLabelText("Name")).toBeInTheDocument();
		expect(screen.getByLabelText("Description (Optional)")).toBeInTheDocument();
		expect(
			screen.getByLabelText("Flow Run Concurrency (Optional)"),
		).toBeInTheDocument();
	});

	it("displays validation error when name is empty", async () => {
		const user = userEvent.setup();
		render(<TestWrapper />);

		const submitButton = screen.getByRole("button", { name: "Submit" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(screen.getByText("Name is required")).toBeInTheDocument();
		});
	});

	it("displays validation error when name starts with 'prefect'", async () => {
		const user = userEvent.setup();
		render(<TestWrapper />);

		const nameInput = screen.getByLabelText("Name");
		await user.type(nameInput, "prefect-test-pool");

		const submitButton = screen.getByRole("button", { name: "Submit" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(
				screen.getByText(
					"Work pools starting with 'prefect' are reserved for internal use.",
				),
			).toBeInTheDocument();
		});
	});

	it("accepts valid name input", async () => {
		const user = userEvent.setup();
		const onSubmit = vi.fn();
		render(<TestWrapper onSubmit={onSubmit} />);

		const nameInput = screen.getByLabelText("Name");
		await user.type(nameInput, "my-work-pool");

		const submitButton = screen.getByRole("button", { name: "Submit" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(onSubmit).toHaveBeenCalledWith({
				name: "my-work-pool",
				description: null,
				concurrencyLimit: null,
			});
		});
	});

	it("handles description input correctly", async () => {
		const user = userEvent.setup();
		const onSubmit = vi.fn();
		render(<TestWrapper onSubmit={onSubmit} />);

		const nameInput = screen.getByLabelText("Name");
		const descriptionInput = screen.getByLabelText("Description (Optional)");

		await user.type(nameInput, "test-pool");
		await user.type(descriptionInput, "Test description");

		const submitButton = screen.getByRole("button", { name: "Submit" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(onSubmit).toHaveBeenCalledWith({
				name: "test-pool",
				description: "Test description",
				concurrencyLimit: null,
			});
		});
	});

	it("handles concurrency limit input correctly", async () => {
		const user = userEvent.setup();
		const onSubmit = vi.fn();
		render(<TestWrapper onSubmit={onSubmit} />);

		const nameInput = screen.getByLabelText("Name");
		const concurrencyInput = screen.getByLabelText(
			"Flow Run Concurrency (Optional)",
		);

		await user.type(nameInput, "test-pool");
		await user.type(concurrencyInput, "5");

		const submitButton = screen.getByRole("button", { name: "Submit" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(onSubmit).toHaveBeenCalledWith({
				name: "test-pool",
				description: null,
				concurrencyLimit: 5,
			});
		});
	});

	it("handles empty concurrency limit as null", async () => {
		const user = userEvent.setup();
		const onSubmit = vi.fn();
		render(
			<TestWrapper
				defaultValues={{ concurrencyLimit: 5 }}
				onSubmit={onSubmit}
			/>,
		);

		const nameInput = screen.getByLabelText("Name");
		const concurrencyInput = screen.getByLabelText(
			"Flow Run Concurrency (Optional)",
		);

		await user.type(nameInput, "test-pool");
		await user.clear(concurrencyInput);

		const submitButton = screen.getByRole("button", { name: "Submit" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(onSubmit).toHaveBeenCalledWith({
				name: "test-pool",
				description: null,
				concurrencyLimit: null,
			});
		});
	});

	it("validates schema correctly with zod", () => {
		// Test the schema validation directly
		expect(() =>
			workPoolInformationSchema.parse({
				name: "test-pool",
				description: null,
				concurrencyLimit: -1,
			}),
		).toThrow();

		expect(() =>
			workPoolInformationSchema.parse({
				name: "test-pool",
				description: null,
				concurrencyLimit: 5,
			}),
		).not.toThrow();
	});

	it("renders with pre-filled default values", () => {
		const defaultValues = {
			name: "existing-pool",
			description: "Existing description",
			concurrencyLimit: 10,
		};

		render(<TestWrapper defaultValues={defaultValues} />);

		expect(screen.getByDisplayValue("existing-pool")).toBeInTheDocument();
		expect(
			screen.getByDisplayValue("Existing description"),
		).toBeInTheDocument();
		expect(screen.getByDisplayValue("10")).toBeInTheDocument();
	});
});
