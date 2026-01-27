import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";

import type { BlockDocument } from "@/api/block-documents";
import { createFakeBlockDocument } from "@/mocks";

import { CallWebhookActionDetails } from "./action-details";

type CallWebhookActionDetailsProps = {
	label: string;
	blockDocument: BlockDocument;
};

const CallWebhookActionDetailsRouter = (
	props: CallWebhookActionDetailsProps,
) => {
	const rootRoute = createRootRoute({
		component: () => <CallWebhookActionDetails {...props} />,
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

describe("CallWebhookActionDetails", () => {
	it("renders block document name with link", async () => {
		const blockDocument = createFakeBlockDocument({
			id: "test-block-id",
			name: "my-webhook-block",
		});

		await waitFor(() =>
			render(
				<CallWebhookActionDetailsRouter
					label="Call webhook using"
					blockDocument={blockDocument}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		expect(screen.getByText("Call webhook using")).toBeInTheDocument();
		expect(screen.getByText("my-webhook-block")).toBeInTheDocument();
		expect(screen.getByLabelText("my-webhook-block")).toHaveAttribute(
			"href",
			"/blocks/block/test-block-id",
		);
	});

	it("renders 'Block not found' when block document has no name", async () => {
		const blockDocument = createFakeBlockDocument({
			id: "test-block-id",
			name: undefined,
		});

		await waitFor(() =>
			render(
				<CallWebhookActionDetailsRouter
					label="Call webhook using"
					blockDocument={blockDocument}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		expect(screen.getByText("Block not found")).toBeInTheDocument();
	});
});
