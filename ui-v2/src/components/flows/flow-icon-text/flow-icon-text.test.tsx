import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { describe, expect, it } from "vitest";
import { createFakeFlow } from "@/mocks";
import { FlowIconText, FlowIconTextFromFlow } from "./flow-icon-text";

const mockFlow = createFakeFlow({
	id: "flow-123",
	name: "my-flow",
});

type FlowIconTextRouterProps = {
	flowId: string;
};

const FlowIconTextRouter = ({ flowId }: FlowIconTextRouterProps) => {
	const rootRoute = createRootRoute({
		component: () => (
			<Suspense fallback={<div>Loading...</div>}>
				<FlowIconText flowId={flowId} />
			</Suspense>
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

describe("FlowIconText", () => {
	it("fetches and displays flow name", async () => {
		server.use(
			http.get(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json(mockFlow);
			}),
		);

		render(<FlowIconTextRouter flowId="flow-123" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("my-flow")).toBeInTheDocument();
		});
	});

	it("renders a link to the flow detail page", async () => {
		server.use(
			http.get(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json(mockFlow);
			}),
		);

		render(<FlowIconTextRouter flowId="flow-123" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			const link = screen.getByRole("link");
			expect(link).toHaveAttribute("href", "/flows/flow/flow-123");
		});
	});
});

type FlowIconTextFromFlowRouterProps = {
	flow: typeof mockFlow;
	className?: string;
	iconSize?: number;
	onClick?: (e: React.MouseEvent<HTMLAnchorElement>) => void;
};

const FlowIconTextFromFlowRouter = ({
	flow,
	className,
	iconSize,
	onClick,
}: FlowIconTextFromFlowRouterProps) => {
	const rootRoute = createRootRoute({
		component: () => (
			<FlowIconTextFromFlow
				flow={flow}
				className={className}
				iconSize={iconSize}
				onClick={onClick}
			/>
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

describe("FlowIconTextFromFlow", () => {
	it("displays flow name without fetching", async () => {
		render(<FlowIconTextFromFlowRouter flow={mockFlow} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("my-flow")).toBeInTheDocument();
		});
	});

	it("renders a link to the flow detail page", async () => {
		render(<FlowIconTextFromFlowRouter flow={mockFlow} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			const link = screen.getByRole("link");
			expect(link).toHaveAttribute("href", "/flows/flow/flow-123");
		});
	});

	it("applies custom className", async () => {
		render(
			<FlowIconTextFromFlowRouter flow={mockFlow} className="custom-class" />,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			const link = screen.getByRole("link");
			expect(link).toHaveClass("custom-class");
		});
	});
});
