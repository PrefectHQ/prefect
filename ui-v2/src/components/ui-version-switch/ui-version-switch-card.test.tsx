import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { UiVersionSwitchCard } from "./ui-version-switch-card";

describe("UiVersionSwitchCard", () => {
	it("renders the switch card and button", async () => {
		const user = userEvent.setup();
		const onSwitch = vi.fn();

		render(<UiVersionSwitchCard onSwitch={onSwitch} />);

		expect(screen.getByText("V1 UI")).toBeInTheDocument();
		const button = screen.getByRole("button", {
			name: "Switch to V1 UI",
		});
		expect(button).toBeInTheDocument();

		await user.click(button);
		expect(onSwitch).toHaveBeenCalledTimes(1);
	});
});
