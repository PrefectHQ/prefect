import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeAutomation } from "@/mocks";
import { AutomationEnableToggle } from "./automation-enable-toggle";

const MOCK_DATA = createFakeAutomation({ enabled: true });

test("AutomationEnableToggle can toggle switch", async () => {
	const user = userEvent.setup();

	render(
		<>
			<Toaster />
			<AutomationEnableToggle automation={MOCK_DATA} />
		</>,
		{ wrapper: createWrapper() },
	);

	expect(
		screen.getByRole("switch", { name: /toggle automation/i }),
	).toBeChecked();

	await user.click(screen.getByRole("switch", { name: /toggle automation/i }));

	await waitFor(() => {
		expect(screen.getByText(/automation disabled/i)).toBeVisible();
	});
});
