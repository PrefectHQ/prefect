import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { CronInput } from "./cron-input";

describe("CronInput", () => {
	const TestCronInput = () => {
		const [value, setValue] = useState("");
		return (
			<CronInput value={value} onChange={(e) => setValue(e.target.value)} />
		);
	};

	it("renders a valid cron message", async () => {
		// SETUP
		const user = userEvent.setup();
		render(<TestCronInput />);

		// TEST
		await user.type(screen.getByRole("textbox"), "* * * * *");

		// ASSERT
		expect(screen.getByText("Every minute")).toBeVisible();
	});

	it("renders a slash-step cron message that matches the server", async () => {
		const user = userEvent.setup();
		render(<TestCronInput />);

		await user.type(screen.getByRole("textbox"), "*/15 * * * *");

		expect(screen.getByText(/every 15 minutes/i)).toBeVisible();
	});

	it("renders a cron message for a valid step that stays aligned with the server", async () => {
		const user = userEvent.setup();
		render(<TestCronInput />);

		await user.type(screen.getByRole("textbox"), "0 */6 * * *");

		expect(screen.getByText(/every 6 hours/i)).toBeVisible();
		expect(screen.queryByText("Invalid expression")).not.toBeInTheDocument();
	});

	it("renders an invalid cron message for a server-diverging step", async () => {
		const user = userEvent.setup();
		render(<TestCronInput />);

		await user.type(screen.getByRole("textbox"), "0 23/6 * * *");

		expect(screen.getByText("Invalid expression")).toBeVisible();
	});

	it("renders an invalid cron message", async () => {
		// SETUP
		const user = userEvent.setup();
		render(<TestCronInput />);

		// TEST
		await user.type(screen.getByRole("textbox"), "abcd");

		// ASSERT
		expect(screen.getByText("Invalid expression")).toBeVisible();
	});

	it("renders an invalid cron message for malformed slash steps", async () => {
		const user = userEvent.setup();
		render(<TestCronInput />);

		await user.type(screen.getByRole("textbox"), "/15 * * * *");

		expect(screen.getByText("Invalid expression")).toBeVisible();
	});
});
