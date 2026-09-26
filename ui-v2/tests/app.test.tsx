import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "../src/app";
import { createAppRouter } from "../src/router";

describe("Navigation tests", () => {
	let router: ReturnType<typeof createAppRouter>;
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient();
		router = createAppRouter({
			queryClient,
			history: createMemoryHistory({ initialEntries: ["/"] }),
		});
	});

	it.each([
		["/dashboard", "Dashboard"],
		["/runs", "Runs"],
		["/flows", "Flows"],
		["/work-pools", "Work Pools"],
		["/blocks", "Blocks"],
		["/variables", "Variables"],
		["/automations", "Automations"],
		["/events", "Event Feed"],
		["/concurrency-limits", "Concurrency"],
		["/settings", "Settings"],
	])("can navigate to %s", async (path, text) => {
		const user = userEvent.setup();
		render(<App appRouter={router} appQueryClient={queryClient} />);
		await user.click(await screen.findByRole("link", { name: text }));
		await waitFor(() => {
			expect(router.state.location.pathname).toBe(path);
			expect(router.state.status).toBe("idle");
		});
	});
});
