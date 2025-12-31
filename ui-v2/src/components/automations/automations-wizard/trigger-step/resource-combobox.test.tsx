import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { ResourceCombobox } from "./resource-combobox";

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});
	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("ResourceCombobox", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	it("renders with empty message when no resources are selected", () => {
		render(
			<ResourceCombobox
				selectedResources={[]}
				onResourcesChange={vi.fn()}
				emptyMessage="All resources"
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("All resources")).toBeVisible();
	});

	it("displays selected resources", () => {
		render(
			<ResourceCombobox
				selectedResources={["prefect.flow.123"]}
				onResourcesChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("prefect.flow.123")).toBeVisible();
	});

	it("displays overflow indicator when more than 2 resources are selected", () => {
		render(
			<ResourceCombobox
				selectedResources={[
					"prefect.flow.1",
					"prefect.flow.2",
					"prefect.flow.3",
				]}
				onResourcesChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("+1")).toBeVisible();
	});

	it("opens dropdown when clicked", async () => {
		const user = userEvent.setup();

		render(
			<ResourceCombobox selectedResources={[]} onResourcesChange={vi.fn()} />,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button"));

		expect(screen.getByPlaceholderText("Search resources...")).toBeVisible();
	});

	it("can deselect resources", async () => {
		const user = userEvent.setup();
		const onResourcesChange = vi.fn();

		render(
			<ResourceCombobox
				selectedResources={["prefect.flow.1", "prefect.flow.2"]}
				onResourcesChange={onResourcesChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button"));
		await user.click(screen.getByRole("option", { name: "Flow 1" }));

		expect(onResourcesChange).toHaveBeenCalledWith(["prefect.flow.2"]);
	});

	it("can add custom resources via Enter key", async () => {
		const user = userEvent.setup();
		const onResourcesChange = vi.fn();

		render(
			<ResourceCombobox
				selectedResources={[]}
				onResourcesChange={onResourcesChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button"));
		await user.type(
			screen.getByPlaceholderText("Search resources..."),
			"prefect.custom.resource{Enter}",
		);

		expect(onResourcesChange).toHaveBeenCalledWith(["prefect.custom.resource"]);
	});

	it("shows custom empty message", () => {
		render(
			<ResourceCombobox
				selectedResources={[]}
				onResourcesChange={vi.fn()}
				emptyMessage="Select resources"
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Select resources")).toBeVisible();
	});
});
