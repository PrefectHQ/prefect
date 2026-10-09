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
import type { ReactNode } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import {
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
} from "@/mocks";
import { FlowActionMenu } from "./cells";

beforeAll(() => {
	// Polyfill scrollIntoView used by cmdk
	Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
		configurable: true,
		value: vi.fn(),
	});
});

const FlowActionMenuRouter = ({ children }: { children: ReactNode }) => {
	const rootRoute = createRootRoute({
		component: () => (
			<>
				<Toaster />
				{children}
			</>
		),
	});
	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

const renderMenu = async (children: ReactNode) => {
	await waitFor(() =>
		render(<FlowActionMenuRouter>{children}</FlowActionMenuRouter>, {
			wrapper: createWrapper(),
		}),
	);
};

const mockPaginate = (results: ReturnType<typeof createFakeDeployment>[]) => {
	server.use(
		http.post(buildApiUrl("/deployments/paginate"), () =>
			HttpResponse.json({
				results,
				count: results.length,
				page: 1,
				pages: 1,
				limit: 10,
			}),
		),
	);
};

const openMenu = async () => {
	const user = userEvent.setup();
	await user.click(await screen.findByRole("button", { name: /open menu/i }));
	return user;
};

describe("FlowActionMenu", () => {
	it("renders no standalone Run button in the row", async () => {
		const flow = createFakeFlow();
		await renderMenu(<FlowActionMenu row={{ original: flow }} />);

		expect(screen.getByRole("button", { name: /open menu/i })).toBeVisible();
		expect(
			screen.queryByRole("button", { name: "Run" }),
		).not.toBeInTheDocument();
	});

	it("lists Run first in the overflow menu", async () => {
		const flow = createFakeFlow();
		await renderMenu(<FlowActionMenu row={{ original: flow }} />);
		await openMenu();

		await waitFor(() =>
			expect(
				screen.getAllByRole("menuitem").map((item) => item.textContent),
			).toEqual(["Run", "Copy ID", "Delete", "Automate"]),
		);
	});

	it("opens the run dialog from the menu", async () => {
		const flow = createFakeFlow({ name: "my-flow" });
		mockPaginate([]);
		await renderMenu(<FlowActionMenu row={{ original: flow }} />);
		const user = await openMenu();

		await user.click(await screen.findByRole("menuitem", { name: "Run" }));

		expect(
			await screen.findByRole("dialog", { name: "Run my-flow" }),
		).toBeVisible();
	});

	it("preselects a single deployment, creates nothing until Quick run, and closes on success", async () => {
		const flow = createFakeFlow();
		const deployment = createFakeDeployment({ flow_id: flow.id });
		mockPaginate([deployment]);
		const createFlowRun = vi.fn();
		server.use(
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
				createFlowRun();
				return HttpResponse.json(createFakeFlowRun());
			}),
		);
		await renderMenu(<FlowActionMenu row={{ original: flow }} />);
		const user = await openMenu();
		await user.click(await screen.findByRole("menuitem", { name: "Run" }));

		const dialog = await screen.findByRole("dialog", {
			name: `Run ${flow.name}`,
		});
		expect(
			await screen.findByRole("button", { name: "Select a deployment" }),
		).toHaveTextContent(deployment.name);
		expect(createFlowRun).not.toHaveBeenCalled();

		await user.click(screen.getByRole("button", { name: "Run" }));
		await user.click(
			await screen.findByRole("menuitem", { name: "Quick run" }),
		);

		await waitFor(() => expect(createFlowRun).toHaveBeenCalledTimes(1));
		await waitFor(() => expect(dialog).not.toBeInTheDocument());
	});
});
