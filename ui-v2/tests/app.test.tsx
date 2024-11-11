import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
		["/notifications", "Notifications"],
		["/concurrency-limits", "Concurrency"],
		["/settings", "Settings"],
	])("can navigate to %s", async (path, text) => {
		const user = userEvent.setup();
		render(<App />);
		await user.click(screen.getByText(text));
		expect(router.state.location.pathname).toBe(path);
	});
});
