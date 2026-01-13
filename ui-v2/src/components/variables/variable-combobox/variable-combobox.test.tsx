import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { components } from "@/api/prefect";
import { createFakeVariable } from "@/mocks";
import { VariableCombobox } from "./variable-combobox";

describe("VariableCombobox", () => {
	beforeAll(mockPointerEvents);

	const mockListVariablesAPI = (
		variables: Array<components["schemas"]["Variable"]>,
	) => {
		server.use(
			http.post(buildApiUrl("/variables/filter"), () => {
				return HttpResponse.json(variables);
			}),
		);
	};

	it("able to select a variable", async () => {
		const mockOnSelect = vi.fn();
		mockListVariablesAPI([
			createFakeVariable({ name: "my_variable_0" }),
			createFakeVariable({ name: "my_variable_1" }),
		]);

		const user = userEvent.setup();

		render(
			<VariableCombobox
				selectedVariableName={undefined}
				onSelect={mockOnSelect}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a variable/i)).toBeVisible(),
		);

		await user.click(screen.getByLabelText(/select a variable/i));
		await user.click(screen.getByRole("option", { name: "my_variable_0" }));

		expect(mockOnSelect).toHaveBeenLastCalledWith("my_variable_0");
	});

	it("has the selected value displayed", async () => {
		mockListVariablesAPI([
			createFakeVariable({ name: "my_variable_0" }),
			createFakeVariable({ name: "my_variable_1" }),
		]);

		render(
			<VariableCombobox
				selectedVariableName="my_variable_0"
				onSelect={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByText("my_variable_0")).toBeVisible(),
		);
	});

	it("shows placeholder when no variable is selected", async () => {
		mockListVariablesAPI([]);

		render(
			<VariableCombobox selectedVariableName={undefined} onSelect={vi.fn()} />,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByText("Select a variable...")).toBeVisible(),
		);
	});
});
