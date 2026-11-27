import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import "@/mocks/mock-json-input";
import type { Deployment } from "@/api/deployments";
import { createFakeDeployment } from "@/mocks";
import { CreateFlowRunForm } from "./create-flow-run-form";

const renderCreateFlowRunForm = (deployment: Deployment) => {
	const rootRoute = createRootRoute({
		component: () => (
			<CreateFlowRunForm deployment={deployment} overrideParameters={{}} />
		),
	});
	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});

	return render(<RouterProvider router={router} />, {
		wrapper: createWrapper(),
	});
};

describe("CreateFlowRunForm parameters", () => {
	it("keeps values removed in JSON after switching to Form and back", async () => {
		const user = userEvent.setup();
		const deployment = createFakeDeployment({
			parameters: {},
			parameter_openapi_schema: {
				type: "object",
				properties: {
					count: { type: "integer", title: "count", default: 1 },
				},
			},
		});

		renderCreateFlowRunForm(deployment);

		await screen.findByRole("spinbutton");

		await user.click(screen.getByRole("tab", { name: "JSON" }));
		const jsonInput =
			await screen.findByTestId<HTMLTextAreaElement>("mock-json-input");
		expect(JSON.parse(jsonInput.value)).toEqual({
			count: 1,
		});

		fireEvent.change(jsonInput, { target: { value: "{}" } });

		await user.click(screen.getByRole("tab", { name: "Form" }));
		await screen.findByRole("spinbutton");

		await user.click(screen.getByRole("tab", { name: "JSON" }));
		expect(
			JSON.parse(
				screen.getByTestId<HTMLTextAreaElement>("mock-json-input").value,
			),
		).toEqual({});
	});
});
