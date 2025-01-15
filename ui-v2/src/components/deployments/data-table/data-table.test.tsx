import type { DeploymentWithFlow } from "@/api/deployments";
import { Toaster } from "@/components/ui/toaster";
import { createFakeFlowRunWithDeploymentAndFlow } from "@/mocks/create-fake-flow-run";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse } from "msw";
import { http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DeploymentsDataTable } from ".";

describe("DeploymentsDataTable", () => {
	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), async ({ request }) => {
				const { limit } = (await request.json()) as { limit: number };

				return HttpResponse.json(
					Array.from({ length: limit }, createFakeFlowRunWithDeploymentAndFlow),
				);
			}),
		);
	});
	const mockDeployment: DeploymentWithFlow = {
		id: "test-id",
		created: new Date().toISOString(),
		updated: new Date().toISOString(),
		name: "Test Deployment",
		flow_id: "flow-id",
		paused: false,
		status: "READY",
		enforce_parameter_schema: true,
		tags: ["tag1", "tag2"],
		flow: {
			id: "flow-id",
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			name: "test-flow",
		},
	};

	const defaultProps = {
		deployments: [mockDeployment],
		currentDeploymentsCount: 1,
		pageCount: 5,
		pagination: {
			pageSize: 10,
			pageIndex: 2,
		},
		sort: "NAME_ASC" as const,
		columnFilters: [],
		onPaginationChange: vi.fn(),
		onSortChange: vi.fn(),
		onColumnFiltersChange: vi.fn(),
		onQuickRun: vi.fn(),
		onCustomRun: vi.fn(),
		onEdit: vi.fn(),
		onDuplicate: vi.fn(),
	};

	it("renders deployment name and flow name", () => {
		render(<DeploymentsDataTable {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Test Deployment")).toBeInTheDocument();
		expect(screen.getByText("test-flow")).toBeInTheDocument();
	});

	it("renders status badge", () => {
		render(<DeploymentsDataTable {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Ready")).toBeInTheDocument();
	});

	it("renders tags", () => {
		render(<DeploymentsDataTable {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("tag1")).toBeInTheDocument();
		expect(screen.getByText("tag2")).toBeInTheDocument();
	});

	it("renders with empty deployments array", () => {
		render(<DeploymentsDataTable {...defaultProps} deployments={[]} />, {
			wrapper: createWrapper(),
		});

		expect(screen.queryByText("No Results")).not.toBeInTheDocument();
	});

	it("renders multiple deployments", () => {
		const multipleDeployments = [
			mockDeployment,
			{
				...mockDeployment,
				id: "test-id-2",
				created: new Date().toISOString(),
				updated: new Date().toISOString(),
				name: "Second Deployment",
				flow: {
					id: "flow-id-2",
					created: new Date().toISOString(),
					updated: new Date().toISOString(),
					name: "second-flow",
				},
			},
		];

		render(
			<DeploymentsDataTable
				{...defaultProps}
				deployments={multipleDeployments}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(screen.getByText("Test Deployment")).toBeInTheDocument();
		expect(screen.getByText("Second Deployment")).toBeInTheDocument();
		expect(screen.getByText("test-flow")).toBeInTheDocument();
		expect(screen.getByText("second-flow")).toBeInTheDocument();
		expect(screen.getByText("1 Deployment")).toBeInTheDocument();
	});

	it("calls onQuickRun when quick run action is clicked", async () => {
		const onQuickRun = vi.fn();
		render(<DeploymentsDataTable {...defaultProps} onQuickRun={onQuickRun} />, {
			wrapper: createWrapper(),
		});

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const quickRunButton = screen.getByRole("menuitem", { name: "Quick Run" });
		await userEvent.click(quickRunButton);

		expect(onQuickRun).toHaveBeenCalledWith(mockDeployment);
	});

	it("calls onCustomRun when custom run action is clicked", async () => {
		const onCustomRun = vi.fn();
		render(
			<DeploymentsDataTable {...defaultProps} onCustomRun={onCustomRun} />,
			{
				wrapper: createWrapper(),
			},
		);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const customRunButton = screen.getByRole("menuitem", {
			name: "Custom Run",
		});
		await userEvent.click(customRunButton);

		expect(onCustomRun).toHaveBeenCalledWith(mockDeployment);
	});

	it("calls onEdit when edit action is clicked", async () => {
		const onEdit = vi.fn();
		render(<DeploymentsDataTable {...defaultProps} onEdit={onEdit} />, {
			wrapper: createWrapper(),
		});

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const editButton = screen.getByRole("menuitem", { name: "Edit" });
		await userEvent.click(editButton);

		expect(onEdit).toHaveBeenCalledWith(mockDeployment);
	});

	it("handles deletion", async () => {
		render(
			<>
				<Toaster />
				<DeploymentsDataTable {...defaultProps} />
			</>,
			{
				wrapper: createWrapper(),
			},
		);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const deleteButton = screen.getByRole("menuitem", { name: "Delete" });
		await userEvent.click(deleteButton);

		const confirmDeleteButton = screen.getByRole("button", {
			name: "Delete",
		});
		await userEvent.click(confirmDeleteButton);

		expect(screen.getByText("Deployment deleted")).toBeInTheDocument();
	});

	it("calls onDuplicate when duplicate action is clicked", async () => {
		const onDuplicate = vi.fn();
		render(
			<DeploymentsDataTable {...defaultProps} onDuplicate={onDuplicate} />,
			{
				wrapper: createWrapper(),
			},
		);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const duplicateButton = screen.getByRole("menuitem", { name: "Duplicate" });
		await userEvent.click(duplicateButton);

		expect(onDuplicate).toHaveBeenCalledWith(mockDeployment);
	});

	it("calls onPaginationChange when pagination buttons are clicked", async () => {
		const onPaginationChange = vi.fn();
		render(
			<DeploymentsDataTable
				{...defaultProps}
				onPaginationChange={onPaginationChange}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await userEvent.click(
			screen.getByRole("button", { name: "Go to next page" }),
		);

		expect(onPaginationChange).toHaveBeenCalledWith({
			pageIndex: 3,
			pageSize: 10,
		});

		await userEvent.click(
			screen.getByRole("button", { name: "Go to previous page" }),
		);

		expect(onPaginationChange).toHaveBeenCalledWith({
			pageIndex: 1,
			pageSize: 10,
		});

		await userEvent.click(
			screen.getByRole("button", { name: "Go to first page" }),
		);

		expect(onPaginationChange).toHaveBeenCalledWith({
			pageIndex: 0,
			pageSize: 10,
		});

		await userEvent.click(
			screen.getByRole("button", { name: "Go to last page" }),
		);

		expect(onPaginationChange).toHaveBeenCalledWith({
			pageIndex: 4,
			pageSize: 10,
		});
	});

	it("calls onSortChange when sort is changed", async () => {
		const user = userEvent.setup();

		mockPointerEvents();
		const onSortChange = vi.fn();
		render(
			<DeploymentsDataTable {...defaultProps} onSortChange={onSortChange} />,
			{
				wrapper: createWrapper(),
			},
		);

		const select = screen.getByRole("combobox", {
			name: "Deployment sort order",
		});
		await userEvent.click(select);
		await userEvent.click(screen.getByText("Created"));

		expect(onSortChange).toHaveBeenCalledWith("CREATED_DESC");

		await user.click(select);
		await user.click(screen.getByText("Updated"));
		expect(onSortChange).toHaveBeenCalledWith("UPDATED_DESC");

		await user.click(select);
		await user.click(screen.getByText("Z to A"));
		expect(onSortChange).toHaveBeenCalledWith("NAME_DESC");
	});

	it("calls onColumnFiltersChange on deployment name search", async () => {
		const user = userEvent.setup();

		const onColumnFiltersChange = vi.fn();
		render(
			<DeploymentsDataTable
				{...defaultProps}
				columnFilters={[{ id: "flowOrDeploymentName", value: "start value" }]}
				onColumnFiltersChange={onColumnFiltersChange}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		// Clear any initial calls from mounting
		onColumnFiltersChange.mockClear();

		const nameSearchInput = screen.getByPlaceholderText("Search deployments");
		expect(nameSearchInput).toHaveValue("start value");

		await user.clear(nameSearchInput);
		await user.type(nameSearchInput, "my-deployment");

		expect(onColumnFiltersChange).toHaveBeenCalledWith([
			{ id: "flowOrDeploymentName", value: "my-deployment" },
		]);
	});

	it("calls onColumnFiltersChange on tags search", async () => {
		const user = userEvent.setup();

		const onColumnFiltersChange = vi.fn();
		render(
			<DeploymentsDataTable
				{...defaultProps}
				columnFilters={[{ id: "tags", value: ["tag3"] }]}
				onColumnFiltersChange={onColumnFiltersChange}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		// Clear any initial calls from mounting
		onColumnFiltersChange.mockClear();

		const tagsSearchInput = screen.getByPlaceholderText("Filter by tags");
		expect(await screen.findByText("tag3")).toBeVisible();

		await user.type(tagsSearchInput, "tag4");
		await user.keyboard("{enter}");

		expect(onColumnFiltersChange).toHaveBeenCalledWith([
			{ id: "tags", value: ["tag3", "tag4"] },
		]);
	});
});
