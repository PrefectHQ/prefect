import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { CronInput, type CronInputProps } from "./cron-input";

describe("CronInput", () => {
	const TestCronInput = ({ getIsCronValid }: CronInputProps) => {
		const [value, setValue] = useState("");
		return (
			<CronInput
				value={value}
				onChange={(e) => setValue(e.target.value)}
				getIsCronValid={getIsCronValid}
			/>
		);
	};

	it("renders a valid cron message", async () => {
		// SETUP
		const user = userEvent.setup();
		const mockGetIsCronValid = vi.fn();
		render(<TestCronInput getIsCronValid={mockGetIsCronValid} />);

		// TEST
		await user.type(screen.getByRole("textbox"), "* * * * *");

		// ASSERT
		expect(screen.getByText("Every minute")).toBeVisible();
		expect(mockGetIsCronValid).toHaveBeenLastCalledWith(true);
	});

	it("renders an valid cron message", async () => {
		// SETUP
		const user = userEvent.setup();
		const mockGetIsCronValid = vi.fn();
		render(<TestCronInput getIsCronValid={mockGetIsCronValid} />);

		// TEST
		await user.type(screen.getByRole("textbox"), "abcd");

		// ASSERT
		expect(screen.getByText("Invalid expression")).toBeVisible();
		expect(mockGetIsCronValid).toHaveBeenLastCalledWith(false);
	});
});
