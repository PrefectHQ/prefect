import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { useState } from "react";
import { beforeAll, describe, expect, it } from "vitest";
import { StateFilter } from "./state-filter";
import type { FlowRunState } from "./state-filters.constants";

describe("FlowRunsDataTable -- StateFilter", () => {
	beforeAll(mockPointerEvents);

	const TestStateFilter = () => {
		const [filters, setFilters] = useState<Set<FlowRunState>>();
		return (
			<StateFilter selectedFilters={filters} onSelectFilter={setFilters} />
		);
	};

	it("selects All except scheduled option", async () => {
		// Setup
		const user = userEvent.setup();
		render(<TestStateFilter />);
		// Test
		await user.click(screen.getByRole("button", { name: /all run states/i }));
		await user.click(
			screen.getByRole("menuitem", { name: /all except scheduled/i }),
		);
		await user.keyboard("{Escape}");

		// Assert
		expect(
			screen.getByRole("button", { name: /all except scheduled/i }),
		).toBeVisible();
	});

	it("selects All run states option", async () => {
		// Setup
		const user = userEvent.setup();
		render(<TestStateFilter />);
		// Test
		await user.click(screen.getByRole("button", { name: /all run states/i }));
		await user.click(screen.getByRole("menuitem", { name: /all run states/i }));
		await user.keyboard("{Escape}");

		// Assert
		expect(
			screen.getByRole("button", { name: /all run states/i }),
		).toBeVisible();
	});

	it("selects a single run state option", async () => {
		// Setup
		const user = userEvent.setup();
		render(<TestStateFilter />);
		// Test
		await user.click(screen.getByRole("button", { name: /all run states/i }));
		await user.click(screen.getByRole("menuitem", { name: /failed/i }));

		await user.keyboard("{Escape}");

		// Assert
		expect(screen.getByRole("button", { name: /failed/i })).toBeVisible();
	});

	it("selects multiple run state options", async () => {
		// Setup
		const user = userEvent.setup();
		render(<TestStateFilter />);
		// Test
		await user.click(screen.getByRole("button", { name: /all run states/i }));
		await user.click(screen.getByRole("menuitem", { name: /timedout/i }));
		await user.click(screen.getByRole("menuitem", { name: /crashed/i }));

		await user.click(screen.getByRole("menuitem", { name: /failed/i }));
		await user.click(screen.getByRole("menuitem", { name: /running/i }));
		await user.click(screen.getByRole("menuitem", { name: /retrying/i }));

		await user.keyboard("{Escape}");

		// Assert
		expect(
			screen.getByRole("button", {
				name: /timedout crashed failed running \+ 1/i,
			}),
		).toBeVisible();
	});
});
