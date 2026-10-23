import { render as renderComponent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import type { ReactElement } from "react";
import { useState } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { StateFilter } from "./state-filter";

const render = (ui: ReactElement) =>
	renderComponent(ui, { wrapper: createWrapper() });

describe("FlowRunsDataTable -- StateFilter", () => {
	beforeAll(mockPointerEvents);

	it("searches beyond the discovery cap and keeps deleted selected names", async () => {
		const requests: string[] = [];
		server.use(
			http.get(buildApiUrl("/observed-states"), ({ request }) => {
				const query = new URL(request.url).searchParams.get("query") ?? "";
				requests.push(query);
				return HttpResponse.json(
					query === "Base"
						? [
								{
									state_type: "FAILED",
									state_name: "Baseline, NOT Met",
									first_seen: "2026-01-01T00:00:00Z",
									last_seen: "2026-01-01T00:00:00Z",
								},
							]
						: Array.from({ length: 200 }, (_, index) => ({
								state_type: "FAILED",
								state_name: `Custom ${index}`,
								first_seen: "2026-01-01T00:00:00Z",
								last_seen: "2026-01-01T00:00:00Z",
							})),
				);
			}),
		);
		const onSelect = vi.fn();
		const user = userEvent.setup();
		render(
			<StateFilter
				selectedFilters={new Set(["Deleted state"])}
				onSelectFilter={onSelect}
			/>,
		);
		expect(screen.getByRole("button", { name: /Deleted state/ })).toBeVisible();
		await user.click(screen.getByRole("button", { name: /Deleted state/ }));
		expect(
			screen.getByRole("menuitem", { name: "Deleted state" }),
		).toBeVisible();
		await user.type(screen.getByLabelText("Search state names"), "Base");
		await user.click(
			await screen.findByRole("menuitem", { name: "Baseline, NOT Met" }),
		);
		expect(requests).toContain("Base");
		expect(onSelect).toHaveBeenCalledWith(
			new Set(["Deleted state", "Baseline, NOT Met"]),
		);
	});

	const TestStateFilter = () => {
		const [filters, setFilters] = useState<Set<string>>();
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

	it("includes all pending state names in All except scheduled", async () => {
		// Setup
		const user = userEvent.setup();
		render(<TestStateFilter />);
		// Test
		await user.click(screen.getByRole("button", { name: /all run states/i }));
		await user.click(
			screen.getByRole("menuitem", { name: /all except scheduled/i }),
		);

		// Assert
		expect(screen.getByRole("menuitem", { name: /submitting/i })).toBeVisible();
		expect(
			screen.getByRole("menuitem", { name: /infrastructurepending/i }),
		).toBeVisible();
		await user.keyboard("{Escape}");
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

		// Assert - MAX_FILTERS_DISPLAYED is 2, so we show 2 badges + "+ 3"
		// The button contains badges and overflow count in separate elements
		const button = screen.getByRole("button");
		expect(button).toBeVisible();
		expect(button).toHaveTextContent(/timedout/i);
		expect(button).toHaveTextContent(/crashed/i);
		expect(button).toHaveTextContent(/\+\s*3/);
	});
});
