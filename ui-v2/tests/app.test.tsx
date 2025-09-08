import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "../src/app";
import { router } from "../src/router";

describe("Navigation tests", () => {
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
		await waitFor(() => render(<App />));
		await user.click(screen.getByRole("link", { name: text }));
		expect(router.state.location.pathname).toBe(path);
	});
});
