import { Toaster } from "@/components/ui/sonner";
import { createFakeDeployment, createFakeFlowRun } from "@/mocks";
import { QueryClient } from "@tanstack/react-query";
import {
	RouterProvider,
	createMemoryHistory,
	createRootRoute,
	createRouter,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { RunFlowButton, type RunFlowButtonProps } from "./run-flow-button";

describe("RunFlowButton", () => {
	// Wraps component in test with a Tanstack router provider
	const RunFlowButtonRouter = (props: RunFlowButtonProps) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<RunFlowButton {...props} />,
				</>
			),
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({
				initialEntries: ["/"],
			}),
			context: { queryClient: new QueryClient() },
		});
		return <RouterProvider router={router} />;
	};

	it("calls quick run option", async () => {
		// ------------ Setup
		const MOCK_DEPLOYMENT = createFakeDeployment();
		const MOCK_FLOW_RUN_RESPONSE = createFakeFlowRun();
		server.use(
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
				return HttpResponse.json(MOCK_FLOW_RUN_RESPONSE);
			}),
		);
		const user = userEvent.setup();
		render(<RunFlowButtonRouter deployment={MOCK_DEPLOYMENT} />, {
			wrapper: createWrapper(),
		});

		// ------------ Act
		await user.click(screen.getByRole("button", { name: "Run", hidden: true }));
		await user.click(screen.getByRole("menuitem", { name: "Quick run" }));

		// ------------ Assert
		await waitFor(() =>
			expect(screen.getByRole("button", { name: /view run/i })).toBeVisible(),
		);
	});

	it("custom run option is a link with deployment parameters", async () => {
		// ------------ Setup
		const MOCK_DEPLOYMENT = createFakeDeployment({
			id: "0",
			parameters: {
				// @ts-expect-error Need to update schema type
				paramKey: "paramValue",
			},
		});
		const user = userEvent.setup();
		render(<RunFlowButtonRouter deployment={MOCK_DEPLOYMENT} />, {
			wrapper: createWrapper(),
		});

		// ------------ Act

		await user.click(screen.getByRole("button", { name: "Run" }));

		// ------------ Assert
		expect(screen.getByRole("menuitem", { name: "Custom run" })).toBeVisible();

		// Validates URL has search parameters with deployment parameters
		expect(screen.getByRole("link", { name: "Custom run" })).toHaveAttribute(
			"href",
			"/deployments/deployment/0/run?parameters=%7B%22paramKey%22%3A%22paramValue%22%7D",
		);
	});
});
