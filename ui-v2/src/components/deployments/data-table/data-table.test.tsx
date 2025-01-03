import type { DeploymentWithFlow } from "@/api/deployments";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { DeploymentsDataTable } from ".";

describe("DeploymentsDataTable", () => {
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
		onQuickRun: vi.fn(),
		onCustomRun: vi.fn(),
		onEdit: vi.fn(),
		onDelete: vi.fn(),
		onDuplicate: vi.fn(),
	};

	test("renders deployment name and flow name", () => {
		render(<DeploymentsDataTable {...defaultProps} />);

		expect(screen.getByText("Test Deployment")).toBeInTheDocument();
		expect(screen.getByText("test-flow")).toBeInTheDocument();
	});

	test("renders status badge", () => {
		render(<DeploymentsDataTable {...defaultProps} />);

		expect(screen.getByText("Ready")).toBeInTheDocument();
	});

	test("renders tags", () => {
		render(<DeploymentsDataTable {...defaultProps} />);

		expect(screen.getByText("tag1")).toBeInTheDocument();
		expect(screen.getByText("tag2")).toBeInTheDocument();
	});

	test("renders with empty deployments array", () => {
		render(<DeploymentsDataTable {...defaultProps} deployments={[]} />);

		expect(screen.queryByText("No Results")).not.toBeInTheDocument();
	});

	test("renders multiple deployments", () => {
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
		);

		expect(screen.getByText("Test Deployment")).toBeInTheDocument();
		expect(screen.getByText("Second Deployment")).toBeInTheDocument();
		expect(screen.getByText("test-flow")).toBeInTheDocument();
		expect(screen.getByText("second-flow")).toBeInTheDocument();
	});

	test("calls onQuickRun when quick run action is clicked", async () => {
		const onQuickRun = vi.fn();
		render(<DeploymentsDataTable {...defaultProps} onQuickRun={onQuickRun} />);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const quickRunButton = screen.getByRole("menuitem", { name: "Quick Run" });
		await userEvent.click(quickRunButton);

		expect(onQuickRun).toHaveBeenCalledWith(mockDeployment);
	});

	test("calls onCustomRun when custom run action is clicked", async () => {
		const onCustomRun = vi.fn();
		render(
			<DeploymentsDataTable {...defaultProps} onCustomRun={onCustomRun} />,
		);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const customRunButton = screen.getByRole("menuitem", {
			name: "Custom Run",
		});
		await userEvent.click(customRunButton);

		expect(onCustomRun).toHaveBeenCalledWith(mockDeployment);
	});

	test("calls onEdit when edit action is clicked", async () => {
		const onEdit = vi.fn();
		render(<DeploymentsDataTable {...defaultProps} onEdit={onEdit} />);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const editButton = screen.getByRole("menuitem", { name: "Edit" });
		await userEvent.click(editButton);

		expect(onEdit).toHaveBeenCalledWith(mockDeployment);
	});

	test("calls onDelete when delete action is clicked", async () => {
		const onDelete = vi.fn();
		render(<DeploymentsDataTable {...defaultProps} onDelete={onDelete} />);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const deleteButton = screen.getByRole("menuitem", { name: "Delete" });
		await userEvent.click(deleteButton);

		expect(onDelete).toHaveBeenCalledWith(mockDeployment);
	});

	test("calls onDuplicate when duplicate action is clicked", async () => {
		const onDuplicate = vi.fn();
		render(
			<DeploymentsDataTable {...defaultProps} onDuplicate={onDuplicate} />,
		);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const duplicateButton = screen.getByRole("menuitem", { name: "Duplicate" });
		await userEvent.click(duplicateButton);

		expect(onDuplicate).toHaveBeenCalledWith(mockDeployment);
	});
});
