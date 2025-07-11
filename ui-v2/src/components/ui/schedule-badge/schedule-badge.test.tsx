import { randUuid } from "@ngneat/falso";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import * as useIsOverflowingModule from "@/hooks/use-is-overflowing";
import { ScheduleBadge, ScheduleBadgeGroup } from ".";

describe("ScheduleBadge", () => {
	it("renders a cron schedule correctly", async () => {
		const user = userEvent.setup();
		const schedule = {
			id: "test-id",
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			active: true,
			schedule: {
				cron: "0 0 * * *",
				timezone: "UTC",
				day_or: false,
			},
		};

		render(<ScheduleBadge schedule={schedule} />);

		const badge = screen.getByText("At 12:00 AM");
		expect(badge).toBeInTheDocument();
		await user.hover(badge);
		await waitFor(() => {
			expect(screen.getByRole("tooltip")).toBeVisible();
		});
		const tooltip = screen.getByRole("tooltip");
		expect(tooltip).toHaveTextContent("At 12:00 AM (UTC)");
	});

	it("renders a paused cron schedule correctly", async () => {
		const user = userEvent.setup();
		const schedule = {
			id: "test-id",
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			active: false,
			schedule: {
				cron: "0 0 * * *",
				timezone: "UTC",
				day_or: false,
			},
		};
		render(<ScheduleBadge schedule={schedule} />);

		const badge = screen.getByText("At 12:00 AM");
		expect(badge).toBeInTheDocument();
		await user.hover(badge);
		await waitFor(() => {
			expect(screen.getByRole("tooltip")).toBeVisible();
		});
		const tooltip = screen.getByRole("tooltip");
		expect(tooltip).toHaveTextContent("(Paused)");
	});

	it("renders an interval schedule correctly", async () => {
		const user = userEvent.setup();
		const schedule = {
			id: "test-id",
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			active: true,
			schedule: {
				interval: 3661,
				timezone: "UTC",
				anchor_date: "2024-01-01T00:00:00Z",
			},
		};
		render(<ScheduleBadge schedule={schedule} />);

		const badge = screen.getByText("Every 1 hour, 1 minute, 1 second");
		expect(badge).toBeInTheDocument();
		await user.hover(badge);
		await waitFor(() => {
			expect(screen.getByRole("tooltip")).toBeVisible();
		});
		const tooltip = screen.getByRole("tooltip");
		expect(tooltip).toHaveTextContent(
			/Every 1 hour, 1 minute, 1 second using .* \(UTC\) as the anchor date/i,
		);
	});

	it("renders a paused interval schedule correctly", async () => {
		const user = userEvent.setup();
		const schedule = {
			id: "test-id",
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			active: false,
			schedule: {
				interval: 3661,
				timezone: "UTC",
				anchor_date: "2024-01-01T00:00:00Z",
			},
		};
		render(<ScheduleBadge schedule={schedule} />);

		const badge = screen.getByText("Every 1 hour, 1 minute, 1 second");
		expect(badge).toBeInTheDocument();
		await user.hover(badge);
		await waitFor(() => {
			expect(screen.getByRole("tooltip")).toBeVisible();
		});
		const tooltip = screen.getByRole("tooltip");
		expect(tooltip).toHaveTextContent("(Paused)");
	});

	it("renders an rrule schedule correctly", async () => {
		const user = userEvent.setup();
		const schedule = {
			id: "test-id",
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			active: true,
			schedule: {
				rrule: "RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR",
				timezone: "UTC",
			},
		};
		render(<ScheduleBadge schedule={schedule} />);

		const badge = screen.getByText("Every weekday");
		expect(badge).toBeInTheDocument();
		await user.hover(badge);
		await waitFor(() => {
			expect(screen.getByRole("tooltip")).toBeVisible();
		});
		const tooltip = screen.getByRole("tooltip");
		expect(tooltip).toHaveTextContent("Every weekday (UTC)");
	});

	it("renders a paused rrule schedule correctly", async () => {
		const user = userEvent.setup();
		const schedule = {
			id: "test-id",
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			active: false,
			schedule: {
				rrule: "RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR",
				timezone: "UTC",
			},
		};
		render(<ScheduleBadge schedule={schedule} />);

		const badge = screen.getByText("Every weekday");
		expect(badge).toBeInTheDocument();
		await user.hover(badge);
		await waitFor(() => {
			expect(screen.getByRole("tooltip")).toBeVisible();
		});
		const tooltip = screen.getByRole("tooltip");
		expect(tooltip).toHaveTextContent("(Paused)");
	});
});

describe("ScheduleBadgeGroup", () => {
	it("renders a group of schedule badges correctly", () => {
		const schedules = [
			{
				id: "test-id-1",
				created: new Date().toISOString(),
				updated: new Date().toISOString(),
				active: true,
				schedule: { cron: "0 0 * * *", timezone: "UTC", day_or: false },
			},
			{
				id: "test-id-2",
				created: new Date().toISOString(),
				updated: new Date().toISOString(),
				active: false,
				schedule: { cron: "0 0 * * *", timezone: "UTC", day_or: false },
			},
		];

		render(<ScheduleBadgeGroup schedules={schedules} />);

		const badges = screen.getAllByText("At 12:00 AM");
		expect(badges).toHaveLength(2);
	});

	it("collapses a group of schedule badges correctly", async () => {
		const spy = vi
			.spyOn(useIsOverflowingModule, "useIsOverflowing")
			.mockReturnValue(true);
		const user = userEvent.setup();
		const schedules = Array.from({ length: 10 }, () => ({
			id: randUuid(),
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			active: true,
			schedule: {
				interval: 3661,
				timezone: "UTC",
				anchor_date: "2024-01-01T00:00:00Z",
			},
		}));

		render(<ScheduleBadgeGroup schedules={schedules} />);

		const collapsedBadge = screen.getByText("10 schedules");
		expect(collapsedBadge).toBeInTheDocument();
		await user.hover(collapsedBadge);

		let badges: HTMLElement[] = [];
		await waitFor(() => {
			badges = screen.getAllByText("Every 1 hour, 1 minute, 1 second");
			expect(badges[0]).toBeVisible();
		});
		expect(badges).toHaveLength(10);
		spy.mockRestore();
	});
});
