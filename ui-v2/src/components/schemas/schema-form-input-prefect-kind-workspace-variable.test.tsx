import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { createFakeVariable } from "@/mocks";
import { SchemaFormInputPrefectKindWorkspaceVariable } from "./schema-form-input-prefect-kind-workspace-variable";

describe("SchemaFormInputPrefectKindWorkspaceVariable", () => {
	beforeAll(mockPointerEvents);

	const mockListVariablesAPI = () => {
		server.use(
			http.post(buildApiUrl("/variables/filter"), () => {
				return HttpResponse.json([
					createFakeVariable({ name: "my_variable_0" }),
					createFakeVariable({ name: "my_variable_1" }),
				]);
			}),
		);
	};

	it("renders without crashing", async () => {
		mockListVariablesAPI();
		const value = {
			__prefect_kind: "workspace_variable" as const,
			variable_name: undefined,
		};
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputPrefectKindWorkspaceVariable
				value={value}
				onValueChange={onValueChange}
				id="test-id"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a variable/i)).toBeVisible(),
		);
	});

	it("displays the selected variable name", async () => {
		mockListVariablesAPI();
		const value = {
			__prefect_kind: "workspace_variable" as const,
			variable_name: "my_variable_0",
		};
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputPrefectKindWorkspaceVariable
				value={value}
				onValueChange={onValueChange}
				id="test-id"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByText("my_variable_0")).toBeVisible(),
		);
	});

	it("calls onValueChange with correct structure when user selects a variable", async () => {
		mockListVariablesAPI();
		const value = {
			__prefect_kind: "workspace_variable" as const,
			variable_name: undefined,
		};
		const onValueChange = vi.fn();

		const user = userEvent.setup();

		render(
			<SchemaFormInputPrefectKindWorkspaceVariable
				value={value}
				onValueChange={onValueChange}
				id="test-id"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a variable/i)).toBeVisible(),
		);

		await user.click(screen.getByLabelText(/select a variable/i));
		await user.click(screen.getByRole("option", { name: "my_variable_0" }));

		expect(onValueChange).toHaveBeenCalledWith({
			__prefect_kind: "workspace_variable",
			variable_name: "my_variable_0",
		});
	});

	it("preserves __prefect_kind: workspace_variable in the value", async () => {
		mockListVariablesAPI();
		const value = {
			__prefect_kind: "workspace_variable" as const,
			variable_name: "initial",
		};
		const onValueChange = vi.fn();

		const user = userEvent.setup();

		render(
			<SchemaFormInputPrefectKindWorkspaceVariable
				value={value}
				onValueChange={onValueChange}
				id="test-id"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a variable/i)).toBeVisible(),
		);

		await user.click(screen.getByLabelText(/select a variable/i));
		await user.click(screen.getByRole("option", { name: "my_variable_1" }));

		expect(onValueChange).toHaveBeenCalledWith(
			expect.objectContaining({
				__prefect_kind: "workspace_variable",
			}),
		);
	});
});
