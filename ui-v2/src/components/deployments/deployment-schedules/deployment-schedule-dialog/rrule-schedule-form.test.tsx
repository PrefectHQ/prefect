import {
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper, server } from "@tests/utils";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { DeploymentSchedule } from "@/api/deployments";
import { Dialog } from "@/components/ui/dialog";
import { RRuleScheduleForm } from "./rrule-schedule-form";
import type { ScheduleParameterOverrides } from "./use-schedule-parameter-overrides";

const existing: DeploymentSchedule = {
	id: "schedule-id",
	deployment_id: "deployment-id",
	created: "2026-01-01T00:00:00Z",
	updated: "2026-01-01T00:00:00Z",
	active: true,
	max_scheduled_runs: null,
	schedule: {
		rrule: "DTSTART;TZID=UTC:20260301T090000\nRRULE:FREQ=DAILY",
		timezone: "UTC",
	},
};
function setup(
	scheduleToEdit?: DeploymentSchedule,
	overrides?: ScheduleParameterOverrides,
) {
	const onSubmit = vi.fn();
	render(
		<Dialog>
			<RRuleScheduleForm
				deployment_id="deployment-id"
				scheduleToEdit={scheduleToEdit}
				onSubmit={onSubmit}
				parameterOverrides={overrides}
			/>
		</Dialog>,
		{ wrapper: createWrapper() },
	);
	return onSubmit;
}

describe("RRuleScheduleForm", () => {
	beforeAll(() => {
		window.HTMLElement.prototype.scrollIntoView = vi.fn();
		window.HTMLElement.prototype.releasePointerCapture = vi.fn();
		window.HTMLElement.prototype.hasPointerCapture = vi.fn();
	});
	it("creates a daily 09:00 UTC schedule with today's DTSTART and overrides", async () => {
		let body: unknown;
		server.use(
			http.post(
				buildApiUrl("/deployments/:id/schedules"),
				async ({ request }) => {
					body = await request.json();
					return HttpResponse.json([], { status: 201 });
				},
			),
		);
		const overrides = {
			schema: undefined,
			values: { name: "override" },
			errors: [],
			setValues: vi.fn(),
			validate: vi.fn().mockResolvedValue(true),
		};
		const onSubmit = setup(undefined, overrides);
		expect(screen.getByLabelText("Time (UTC)")).toHaveValue("09:00");
		expect(
			screen
				.getByRole("region", { name: "Upcoming runs" })
				.querySelectorAll("time"),
		).toHaveLength(5);
		await userEvent.click(screen.getByRole("switch", { name: "Active" }));
		await userEvent.click(screen.getByRole("button", { name: "Save" }));
		await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
		expect(body).toEqual([
			{
				active: false,
				parameters: { name: "override" },
				schedule: {
					timezone: "UTC",
					rrule: `DTSTART;TZID=UTC:${new Date().toISOString().slice(0, 10).replaceAll("-", "")}T090000\nRRULE:FREQ=DAILY;INTERVAL=1;BYHOUR=9;BYMINUTE=0;BYSECOND=0`,
				},
			},
		]);
		expect(overrides.validate).toHaveBeenCalledOnce();
	});
	it("updates an existing supported schedule instead of creating one", async () => {
		let body: unknown;
		server.use(
			http.patch(
				buildApiUrl("/deployments/deployment-id/schedules/schedule-id"),
				async ({ request }) => {
					body = await request.json();
					return new HttpResponse(null, { status: 204 });
				},
			),
		);
		const onSubmit = setup(existing);
		fireEvent.change(screen.getByLabelText("Time (UTC)"), {
			target: { value: "10:30" },
		});
		await userEvent.click(screen.getByRole("button", { name: "Save" }));
		await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
		expect(body).toEqual({
			active: true,
			schedule: {
				timezone: "UTC",
				rrule:
					"DTSTART;TZID=UTC:20260301T103000\nRRULE:FREQ=DAILY;INTERVAL=1;BYHOUR=10;BYMINUTE=30;BYSECOND=0",
			},
		});
	});
	it("saves only active and parameters for an unsupported rule", async () => {
		let body: unknown;
		server.use(
			http.patch(
				buildApiUrl("/deployments/:id/schedules/:schedule_id"),
				async ({ request }) => {
					body = await request.json();
					return new HttpResponse(null, { status: 204 });
				},
			),
		);
		const onSubmit = setup(
			{
				...existing,
				schedule: {
					rrule: "DTSTART;TZID=UTC:20260301T090000\nRRULE:FREQ=HOURLY",
					timezone: "UTC",
				},
			},
			{
				schema: undefined,
				values: { name: "changed" },
				errors: [],
				setValues: vi.fn(),
				validate: vi.fn().mockResolvedValue(true),
			},
		);
		expect(screen.getByText(/Save updates only Active/)).toBeVisible();
		expect(
			screen.queryByRole("region", { name: "Upcoming runs" }),
		).not.toBeInTheDocument();
		expect(screen.queryByLabelText(/select timezone/i)).not.toBeInTheDocument();
		await userEvent.click(screen.getByRole("switch", { name: "Active" }));
		await userEvent.click(screen.getByRole("button", { name: "Save" }));
		await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
		expect(body).toEqual({ active: false, parameters: { name: "changed" } });
	});
	it("blocks Save and stale preview while the builder has an invalid draft", async () => {
		setup();
		fireEvent.change(screen.getByLabelText("Repeat every"), {
			target: { value: "" },
		});
		expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
		expect(
			screen.getByText("Enter a valid recurrence to see upcoming runs."),
		).toBeVisible();
		expect(screen.queryAllByRole("listitem")).toHaveLength(0);
		fireEvent.change(screen.getByLabelText("Repeat every"), {
			target: { value: "2" },
		});
		expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
		await waitFor(() =>
			expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
		);
	});
	it("does not close or discard edits on a failed save", async () => {
		server.use(
			http.patch(buildApiUrl("/deployments/:id/schedules/:schedule_id"), () =>
				HttpResponse.json({ detail: "Could not update" }, { status: 500 }),
			),
		);
		const onSubmit = setup(existing);
		fireEvent.change(screen.getByLabelText("Time (UTC)"), {
			target: { value: "10:30" },
		});
		await userEvent.click(screen.getByRole("button", { name: "Save" }));
		expect(await screen.findByRole("alert")).toHaveTextContent(
			"Could not update",
		);
		expect(onSubmit).not.toHaveBeenCalled();
		expect(screen.getByLabelText("Time (UTC)")).toHaveValue("10:30");
	});
	it("does not save invalid parameter overrides", async () => {
		const validate = vi.fn().mockResolvedValue(false);
		const onSubmit = setup(undefined, {
			schema: undefined,
			values: {},
			errors: [],
			setValues: vi.fn(),
			validate,
		});
		await userEvent.click(screen.getByRole("button", { name: "Save" }));
		await waitFor(() => expect(validate).toHaveBeenCalledOnce());
		expect(onSubmit).not.toHaveBeenCalled();
	});
	it("preserves wall-clock DTSTART when changing timezone", async () => {
		setup(existing);
		await userEvent.click(screen.getByLabelText(/select timezone/i));
		await userEvent.type(screen.getByPlaceholderText(/search/i), "Chicago");
		await userEvent.click(
			await screen.findByRole("option", { name: /Chicago/i }),
		);
		expect(screen.getByLabelText("Start date")).toHaveValue("2026-03-01");
		expect(screen.getByLabelText("Time (America/Chicago)")).toHaveValue(
			"09:00",
		);
		expect(
			within(screen.getByRole("region", { name: "Upcoming runs" })).getByRole(
				"heading",
			),
		).toHaveTextContent("America/Chicago");
	});
	it("shows exhausted and computation-limit states", () => {
		setup({
			...existing,
			schedule: {
				rrule:
					"DTSTART;TZID=UTC:20000401T090000\nRRULE:FREQ=MONTHLY;INTERVAL=12;BYMONTHDAY=31",
				timezone: "UTC",
			},
		});
		expect(
			screen.getByText(
				"Couldn't compute upcoming runs within the preview limit.",
			),
		).toBeVisible();
	});
});
