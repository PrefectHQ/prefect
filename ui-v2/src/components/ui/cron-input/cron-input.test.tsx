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

	it("renders an invalid cron message", async () => {
		// SETUP
		const user = userEvent.setup();
		render(<TestCronInput />);

		// TEST
		await user.type(screen.getByRole("textbox"), "abcd");

		// ASSERT
		expect(screen.getByText("Invalid expression")).toBeVisible();
	});
});
