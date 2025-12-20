import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeFlow } from "@/mocks";
import { DeleteFlowDialog } from "./delete-flow-dialog";

describe("DeleteFlowDialog", () => {
	const queryClient = new QueryClient();

	const DeleteFlowDialogRouter = ({
		flow,
		open,
		onOpenChange,
		onDeleted,
	}: {
		flow: ReturnType<typeof createFakeFlow>;
		open: boolean;
		onOpenChange: (open: boolean) => void;
		onDeleted?: () => void;
	}) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<DeleteFlowDialog
						flow={flow}
						open={open}
						onOpenChange={onOpenChange}
						onDeleted={onDeleted}
					/>
				</>
			),
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({
				initialEntries: ["/flows/test-flow-id"],
			}),
			context: { queryClient },
		});
		return <RouterProvider router={router} />;
	};

	const flow = createFakeFlow({
		id: "test-flow-id",
		name: "test-flow",
	});

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders dialog with flow name in description when open", async () => {
		const onOpenChange = vi.fn();

		render(
			<DeleteFlowDialogRouter
				flow={flow}
				open={true}
				onOpenChange={onOpenChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.getByText("Delete Flow")).toBeInTheDocument();
			expect(
				screen.getByText(
					`Are you sure you want to delete ${flow.name}? This action cannot be undone.`,
				),
			).toBeInTheDocument();
		});
	});

	it("does not render when open is false", () => {
		const onOpenChange = vi.fn();

		render(
			<DeleteFlowDialogRouter
				flow={flow}
				open={false}
				onOpenChange={onOpenChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		expect(screen.queryByText("Delete Flow")).not.toBeInTheDocument();
	});

	it("calls onOpenChange with false when Cancel button is clicked", async () => {
		const user = userEvent.setup();
		const onOpenChange = vi.fn();

		render(
			<DeleteFlowDialogRouter
				flow={flow}
				open={true}
				onOpenChange={onOpenChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.getByText("Cancel")).toBeInTheDocument();
		});

		await user.click(screen.getByText("Cancel"));

		expect(onOpenChange).toHaveBeenCalledWith(false);
	});

	it("calls the deletion mutation when Delete button is clicked", async () => {
		const user = userEvent.setup();
		const onOpenChange = vi.fn();
		const onDeleted = vi.fn();

		let deleteWasCalled = false;
		server.use(
			http.delete(buildApiUrl("/flows/:id"), () => {
				deleteWasCalled = true;
				return HttpResponse.json({ status: 204 });
			}),
		);

		render(
			<DeleteFlowDialogRouter
				flow={flow}
				open={true}
				onOpenChange={onOpenChange}
				onDeleted={onDeleted}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});

		await user.click(screen.getByText("Delete"));

		await waitFor(() => {
			expect(deleteWasCalled).toBe(true);
		});
	});

	it("shows loading state during deletion", async () => {
		const user = userEvent.setup();
		const onOpenChange = vi.fn();

		server.use(
			http.delete(buildApiUrl("/flows/:id"), async () => {
				await new Promise((resolve) => setTimeout(resolve, 100));
				return HttpResponse.json({ status: 204 });
			}),
		);

		render(
			<DeleteFlowDialogRouter
				flow={flow}
				open={true}
				onOpenChange={onOpenChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});

		await user.click(screen.getByText("Delete"));

		await waitFor(() => {
			expect(screen.getByText("Deleting...")).toBeInTheDocument();
		});
	});

	it("shows success toast on successful deletion", async () => {
		const user = userEvent.setup();
		const onOpenChange = vi.fn();
		const onDeleted = vi.fn();

		server.use(
			http.delete(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json({ status: 204 });
			}),
		);

		render(
			<DeleteFlowDialogRouter
				flow={flow}
				open={true}
				onOpenChange={onOpenChange}
				onDeleted={onDeleted}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});

		await user.click(screen.getByText("Delete"));

		await waitFor(() => {
			expect(screen.getByText("Flow deleted")).toBeInTheDocument();
		});
	});

	it("calls onDeleted callback on successful deletion", async () => {
		const user = userEvent.setup();
		const onOpenChange = vi.fn();
		const onDeleted = vi.fn();

		server.use(
			http.delete(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json({ status: 204 });
			}),
		);

		render(
			<DeleteFlowDialogRouter
				flow={flow}
				open={true}
				onOpenChange={onOpenChange}
				onDeleted={onDeleted}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});

		await user.click(screen.getByText("Delete"));

		await waitFor(() => {
			expect(onDeleted).toHaveBeenCalled();
		});
	});

	it("shows error toast on deletion failure", async () => {
		const user = userEvent.setup();
		const onOpenChange = vi.fn();

		server.use(
			http.delete(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json(
					{ detail: "Failed to delete flow" },
					{ status: 500 },
				);
			}),
		);

		render(
			<DeleteFlowDialogRouter
				flow={flow}
				open={true}
				onOpenChange={onOpenChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});

		await user.click(screen.getByText("Delete"));

		await waitFor(() => {
			expect(screen.getByText("Failed to delete flow")).toBeInTheDocument();
		});
	});
});
