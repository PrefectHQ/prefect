import { Toaster } from "@/components/ui/toaster";
import { createFakeAutomation } from "@/mocks";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test } from "vitest";
import { AutomationEnableToggle } from "./automation-enable-toggle";

const MOCK_DATA = createFakeAutomation({ enabled: true });

test("AutomationEnableToggle can toggle switch", async () => {
	const user = userEvent.setup();

	render(
		<>
			<Toaster />
			<AutomationEnableToggle data={MOCK_DATA} />
		</>,
		{ wrapper: createWrapper() },
	);

	expect(
		screen.getByRole("switch", { name: /toggle automation/i }),
	).toBeChecked();

	await user.click(screen.getByRole("switch", { name: /toggle automation/i }));
	expect(screen.getByText(/automation disabled/i)).toBeVisible();
});
