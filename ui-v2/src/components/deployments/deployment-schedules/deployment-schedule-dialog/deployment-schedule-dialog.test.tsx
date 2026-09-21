import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import type { Deployment, DeploymentSchedule } from "@/api/deployments";
import { Toaster } from "@/components/ui/sonner";
import { createFakeDeployment } from "@/mocks";
import { DeploymentScheduleDialog } from "./deployment-schedule-dialog";

const PARAMETER_SCHEMA = {
	type: "object",
	title: "Parameters",
	properties: {
		name: { type: "string", title: "name", position: 0 },
	},
	required: ["name"],
};

const MOCK_DEPLOYMENT = createFakeDeployment({
	parameter_openapi_schema: PARAMETER_SCHEMA,
	parameters: { name: "deployment default" },
	enforce_parameter_schema: true,
});

const MOCK_SCHEDULE: DeploymentSchedule = {
	active: true,
	created: "0",
	deployment_id: MOCK_DEPLOYMENT.id,
	id: "schedule-id",
	updated: "0",
	schedule: { cron: "* * * * *", day_or: true, timezone: "UTC" },
	parameters: { name: "override" },
};

const DeploymentScheduleDialogTest = ({
	deployment = MOCK_DEPLOYMENT,
	scheduleToEdit,
}: {
	deployment?: Deployment;
	scheduleToEdit?: DeploymentSchedule;
}) => (
	<>
		<Toaster />
		<DeploymentScheduleDialog
			deployment={deployment}
			open
			onOpenChange={vi.fn()}
			onSubmit={vi.fn()}
			scheduleToEdit={scheduleToEdit}
		/>
	</>
);

describe("DeploymentScheduleDialog", () => {
	it("does not render parameter overrides when the deployment has no parameters", () => {
		render(
			<DeploymentScheduleDialogTest
				deployment={createFakeDeployment({
					parameter_openapi_schema: { type: "object", properties: {} },
				})}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.queryByText(/parameter overrides/i)).not.toBeInTheDocument();
	});

	it("renders a schedule's parameter overrides", async () => {
		render(<DeploymentScheduleDialogTest scheduleToEdit={MOCK_SCHEDULE} />, {
			wrapper: createWrapper(),
		});

		expect(await screen.findByText(/parameter overrides/i)).toBeVisible();
		expect(await screen.findByLabelText(/name \(optional\)/i)).toHaveValue(
			"override",
		);
	});

	it("saves parameter overrides with a new schedule", async () => {
		const user = userEvent.setup();
		let createdSchedules: unknown;
		server.use(
			http.post(
				buildApiUrl("/deployments/:id/schedules"),
				async ({ request }) => {
					createdSchedules = await request.json();
					return HttpResponse.json([], { status: 201 });
				},
			),
			http.post(buildApiUrl("/ui/schemas/validate"), () =>
				HttpResponse.json({ valid: true, errors: [] }),
			),
		);

		render(<DeploymentScheduleDialogTest />, { wrapper: createWrapper() });

		await user.type(
			await screen.findByLabelText(/name \(optional\)/i),
			"my override",
		);
		await user.click(screen.getByRole("button", { name: /save/i }));

		await vi.waitFor(() =>
			expect(createdSchedules).toEqual([
				expect.objectContaining({
					parameters: { name: "my override" },
				}),
			]),
		);
	});

	it("saves an override changed immediately before submit", async () => {
		let createdSchedules: unknown;
		server.use(
			http.post(
				buildApiUrl("/deployments/:id/schedules"),
				async ({ request }) => {
					createdSchedules = await request.json();
					return HttpResponse.json([], { status: 201 });
				},
			),
			http.post(buildApiUrl("/ui/schemas/validate"), () =>
				HttpResponse.json({ valid: true, errors: [] }),
			),
		);

		render(<DeploymentScheduleDialogTest />, { wrapper: createWrapper() });

		fireEvent.change(await screen.findByLabelText(/name \(optional\)/i), {
			target: { value: "final edit" },
		});
		await new Promise((resolve) => setTimeout(resolve, 0));
		fireEvent.click(screen.getByRole("button", { name: /save/i }));

		await vi.waitFor(() =>
			expect(createdSchedules).toEqual([
				expect.objectContaining({ parameters: { name: "final edit" } }),
			]),
		);
	});

	it("saves parameter overrides when editing a schedule", async () => {
		const user = userEvent.setup();
		let updatedSchedule: unknown;
		server.use(
			http.patch(
				buildApiUrl("/deployments/:id/schedules/:schedule_id"),
				async ({ request }) => {
					updatedSchedule = await request.json();
					return new HttpResponse(null, { status: 204 });
				},
			),
			http.post(buildApiUrl("/ui/schemas/validate"), () =>
				HttpResponse.json({ valid: true, errors: [] }),
			),
		);

		render(<DeploymentScheduleDialogTest scheduleToEdit={MOCK_SCHEDULE} />, {
			wrapper: createWrapper(),
		});

		await user.type(
			await screen.findByLabelText(/name \(optional\)/i),
			" updated",
		);
		await user.click(screen.getByRole("button", { name: /save/i }));

		await vi.waitFor(() =>
			expect(updatedSchedule).toEqual(
				expect.objectContaining({
					parameters: { name: "override updated" },
				}),
			),
		);
	});

	it("does not save a schedule with invalid parameter overrides", async () => {
		const user = userEvent.setup();
		const createSchedule = vi.fn();
		server.use(
			http.post(buildApiUrl("/deployments/:id/schedules"), () => {
				createSchedule();
				return HttpResponse.json([], { status: 201 });
			}),
			http.post(buildApiUrl("/ui/schemas/validate"), () =>
				HttpResponse.json({
					valid: false,
					errors: [{ property: "name", errors: ["is not of type 'string'"] }],
				}),
			),
		);

		render(<DeploymentScheduleDialogTest />, { wrapper: createWrapper() });

		await user.type(await screen.findByLabelText(/name \(optional\)/i), "1");
		await user.click(screen.getByRole("button", { name: /save/i }));

		expect(await screen.findByText(/is not of type 'string'/i)).toBeVisible();
		expect(createSchedule).not.toHaveBeenCalled();
	});

	it("does not validate overrides when the deployment does not enforce its parameter schema", async () => {
		const user = userEvent.setup();
		const validateSchema = vi.fn();
		let createdSchedules: unknown;
		server.use(
			http.post(
				buildApiUrl("/deployments/:id/schedules"),
				async ({ request }) => {
					createdSchedules = await request.json();
					return HttpResponse.json([], { status: 201 });
				},
			),
			http.post(buildApiUrl("/ui/schemas/validate"), () => {
				validateSchema();
				return HttpResponse.json({ valid: true, errors: [] });
			}),
		);

		render(
			<DeploymentScheduleDialogTest
				deployment={createFakeDeployment({
					parameter_openapi_schema: PARAMETER_SCHEMA,
					enforce_parameter_schema: false,
				})}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.type(
			await screen.findByLabelText(/name \(optional\)/i),
			"my override",
		);
		await user.click(screen.getByRole("button", { name: /save/i }));

		await vi.waitFor(() =>
			expect(createdSchedules).toEqual([
				expect.objectContaining({ parameters: { name: "my override" } }),
			]),
		);
		expect(validateSchema).not.toHaveBeenCalled();
	});
});
