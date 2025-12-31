import { QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import type { Automation } from "@/api/automations";
import { createFakeAutomation } from "@/mocks";
import { UNASSIGNED } from "./automation-schema";
import {
	transformAutomationToFormValues,
	transformFormValuesToApi,
	useEditAutomation,
} from "./use-edit-automation";

describe("useEditAutomation", () => {
	const mockFetchGetAutomationAPI = (automation: Automation) => {
		server.use(
			http.get(buildApiUrl("/automations/:id"), () => {
				return HttpResponse.json(automation);
			}),
		);
	};

	const mockReplaceAutomationAPI = () => {
		server.use(
			http.put(buildApiUrl("/automations/:id"), () => {
				return new HttpResponse(null, { status: 204 });
			}),
		);
	};

	describe("transformAutomationToFormValues", () => {
		describe("action transformations", () => {
			it("transforms run-deployment action with selected deployment", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "run-deployment",
							source: "selected",
							deployment_id: "deployment-123",
							parameters: { key: "value" },
							job_variables: { var: "val" },
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "run-deployment",
					deployment_id: "deployment-123",
					parameters: { key: "value" },
					job_variables: { var: "val" },
				});
			});

			it("transforms run-deployment action with inferred deployment to UNASSIGNED", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "run-deployment",
							source: "inferred",
							deployment_id: null,
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "run-deployment",
					deployment_id: UNASSIGNED,
					parameters: undefined,
					job_variables: undefined,
				});
			});

			it("transforms pause-deployment action with selected deployment", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "pause-deployment",
							source: "selected",
							deployment_id: "deployment-456",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "pause-deployment",
					deployment_id: "deployment-456",
				});
			});

			it("transforms pause-deployment action with inferred deployment to UNASSIGNED", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "pause-deployment",
							source: "inferred",
							deployment_id: null,
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "pause-deployment",
					deployment_id: UNASSIGNED,
				});
			});

			it("transforms resume-deployment action", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "resume-deployment",
							source: "selected",
							deployment_id: "deployment-789",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "resume-deployment",
					deployment_id: "deployment-789",
				});
			});

			it("transforms pause-work-queue action with selected work queue", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "pause-work-queue",
							source: "selected",
							work_queue_id: "queue-123",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "pause-work-queue",
					work_queue_id: "queue-123",
				});
			});

			it("transforms pause-work-queue action with inferred work queue to UNASSIGNED", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "pause-work-queue",
							source: "inferred",
							work_queue_id: null,
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "pause-work-queue",
					work_queue_id: UNASSIGNED,
				});
			});

			it("transforms resume-work-queue action", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "resume-work-queue",
							source: "selected",
							work_queue_id: "queue-456",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "resume-work-queue",
					work_queue_id: "queue-456",
				});
			});

			it("transforms pause-work-pool action with selected work pool", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "pause-work-pool",
							source: "selected",
							work_pool_id: "pool-123",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "pause-work-pool",
					work_pool_id: "pool-123",
				});
			});

			it("transforms pause-work-pool action with inferred work pool to UNASSIGNED", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "pause-work-pool",
							source: "inferred",
							work_pool_id: null,
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "pause-work-pool",
					work_pool_id: UNASSIGNED,
				});
			});

			it("transforms resume-work-pool action", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "resume-work-pool",
							source: "selected",
							work_pool_id: "pool-456",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "resume-work-pool",
					work_pool_id: "pool-456",
				});
			});

			it("transforms pause-automation action with selected automation", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "pause-automation",
							source: "selected",
							automation_id: "automation-123",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "pause-automation",
					automation_id: "automation-123",
				});
			});

			it("transforms pause-automation action with inferred automation to UNASSIGNED", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "pause-automation",
							source: "inferred",
							automation_id: null,
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "pause-automation",
					automation_id: UNASSIGNED,
				});
			});

			it("transforms resume-automation action", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "resume-automation",
							source: "selected",
							automation_id: "automation-456",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "resume-automation",
					automation_id: "automation-456",
				});
			});

			it("transforms cancel-flow-run action", () => {
				const automation = createFakeAutomation({
					actions: [{ type: "cancel-flow-run" }],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "cancel-flow-run",
				});
			});

			it("transforms suspend-flow-run action", () => {
				const automation = createFakeAutomation({
					actions: [{ type: "suspend-flow-run" }],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "suspend-flow-run",
				});
			});

			it("transforms resume-flow-run action", () => {
				const automation = createFakeAutomation({
					actions: [{ type: "resume-flow-run" }],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "resume-flow-run",
				});
			});

			it("transforms change-flow-run-state action", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "change-flow-run-state",
							state: "COMPLETED",
							name: "Custom State",
							message: "State changed by automation",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "change-flow-run-state",
					state: "COMPLETED",
					name: "Custom State",
					message: "State changed by automation",
				});
			});

			it("transforms change-flow-run-state action with null optional fields", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "change-flow-run-state",
							state: "FAILED",
							name: null,
							message: null,
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "change-flow-run-state",
					state: "FAILED",
					name: undefined,
					message: undefined,
				});
			});

			it("transforms send-notification action", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "send-notification",
							block_document_id: "block-123",
							body: "Notification body",
							subject: "Notification subject",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "send-notification",
					block_document_id: "block-123",
					body: "Notification body",
					subject: "Notification subject",
				});
			});

			it("transforms do-nothing action", () => {
				const automation = createFakeAutomation({
					actions: [{ type: "do-nothing" }],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "do-nothing",
				});
			});

			it("transforms call-webhook action to do-nothing (unsupported in form)", () => {
				const automation = createFakeAutomation({
					actions: [
						{
							type: "call-webhook",
							block_document_id: "webhook-block",
							payload: "{}",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions[0]).toEqual({
					type: "do-nothing",
				});
			});

			it("transforms multiple actions", () => {
				const automation = createFakeAutomation({
					actions: [
						{ type: "cancel-flow-run" },
						{
							type: "pause-deployment",
							source: "selected",
							deployment_id: "dep-1",
						},
						{
							type: "send-notification",
							block_document_id: "block-1",
							body: "Body",
							subject: "Subject",
						},
					],
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.actions).toHaveLength(3);
				expect(result.actions[0]).toEqual({ type: "cancel-flow-run" });
				expect(result.actions[1]).toEqual({
					type: "pause-deployment",
					deployment_id: "dep-1",
				});
				expect(result.actions[2]).toEqual({
					type: "send-notification",
					block_document_id: "block-1",
					body: "Body",
					subject: "Subject",
				});
			});
		});

		describe("trigger transformations", () => {
			it("transforms simple event trigger", () => {
				const automation = createFakeAutomation({
					trigger: {
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
						match: { "prefect.resource.id": "prefect.deployment.*" },
						match_related: {},
						after: [],
						expect: ["prefect.deployment.not-ready"],
						for_each: ["prefect.resource.id"],
					},
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.trigger).toEqual({
					type: "event",
					posture: "Reactive",
					threshold: 1,
					within: 0,
					match: { "prefect.resource.id": "prefect.deployment.*" },
					match_related: {},
					after: [],
					expect: ["prefect.deployment.not-ready"],
					for_each: ["prefect.resource.id"],
				});
			});

			it("transforms proactive event trigger", () => {
				const automation = createFakeAutomation({
					trigger: {
						type: "event",
						posture: "Proactive",
						threshold: 5,
						within: 300,
						match: { "prefect.resource.id": "prefect.flow-run.*" },
						expect: ["prefect.flow-run.Completed"],
					},
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.trigger).toEqual({
					type: "event",
					posture: "Proactive",
					threshold: 5,
					within: 300,
					match: { "prefect.resource.id": "prefect.flow-run.*" },
					match_related: undefined,
					expect: ["prefect.flow-run.Completed"],
					after: undefined,
					for_each: undefined,
				});
			});

			it("transforms event trigger with array match_related to single object", () => {
				const automation = createFakeAutomation({
					trigger: {
						type: "event",
						posture: "Reactive",
						threshold: 1,
						within: 0,
						match_related: [
							{ "prefect.resource.role": "flow" },
							{ "prefect.resource.role": "deployment" },
						],
					},
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.trigger.type).toBe("event");
				if (result.trigger.type === "event") {
					expect(result.trigger.match_related).toEqual({
						"prefect.resource.role": "flow",
					});
				}
			});

			it("transforms compound trigger", () => {
				const automation = createFakeAutomation({
					trigger: {
						type: "compound",
						require: "all",
						within: 60,
						triggers: [
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
								expect: ["prefect.flow-run.Running"],
							},
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
								expect: ["prefect.flow-run.Completed"],
							},
						],
					},
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.trigger.type).toBe("compound");
				if (result.trigger.type === "compound") {
					expect(result.trigger.require).toBe("all");
					expect(result.trigger.within).toBe(60);
					expect(result.trigger.triggers).toHaveLength(2);
				}
			});

			it("transforms compound trigger with numeric require", () => {
				const automation = createFakeAutomation({
					trigger: {
						type: "compound",
						require: 2,
						within: 120,
						triggers: [
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
								expect: ["event1"],
							},
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
								expect: ["event2"],
							},
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
								expect: ["event3"],
							},
						],
					},
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.trigger.type).toBe("compound");
				if (result.trigger.type === "compound") {
					expect(result.trigger.require).toBe(2);
				}
			});

			it("transforms sequence trigger", () => {
				const automation = createFakeAutomation({
					trigger: {
						type: "sequence",
						within: 180,
						triggers: [
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
								expect: ["prefect.flow-run.Pending"],
							},
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
								expect: ["prefect.flow-run.Running"],
							},
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
								expect: ["prefect.flow-run.Completed"],
							},
						],
					},
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.trigger.type).toBe("sequence");
				if (result.trigger.type === "sequence") {
					expect(result.trigger.within).toBe(180);
					expect(result.trigger.triggers).toHaveLength(3);
				}
			});

			it("transforms nested compound triggers", () => {
				const automation = createFakeAutomation({
					trigger: {
						type: "compound",
						require: "any",
						within: 300,
						triggers: [
							{
								type: "compound",
								require: "all",
								within: 60,
								triggers: [
									{
										type: "event",
										posture: "Reactive",
										threshold: 1,
										within: 0,
										expect: ["event1"],
									},
									{
										type: "event",
										posture: "Reactive",
										threshold: 1,
										within: 0,
										expect: ["event2"],
									},
								],
							},
							{
								type: "event",
								posture: "Reactive",
								threshold: 1,
								within: 0,
								expect: ["event3"],
							},
						],
					},
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.trigger.type).toBe("compound");
				if (result.trigger.type === "compound") {
					expect(result.trigger.triggers[0].type).toBe("compound");
					expect(result.trigger.triggers[1].type).toBe("event");
				}
			});
		});

		describe("basic field transformations", () => {
			it("transforms name field", () => {
				const automation = createFakeAutomation({
					name: "Test Automation",
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.name).toBe("Test Automation");
			});

			it("transforms description field", () => {
				const automation = createFakeAutomation({
					description: "Test description",
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.description).toBe("Test description");
			});

			it("transforms empty description to undefined", () => {
				const automation = createFakeAutomation({
					description: "",
				});

				const result = transformAutomationToFormValues(automation);

				expect(result.description).toBeUndefined();
			});
		});
	});

	describe("transformFormValuesToApi", () => {
		it("transforms form values to API format", () => {
			const formValues = {
				name: "Test Automation",
				description: "Test description",
				trigger: {
					type: "event" as const,
					posture: "Reactive" as const,
					threshold: 1,
					within: 0,
				},
				actions: [
					{
						type: "cancel-flow-run" as const,
					},
				],
			};

			const result = transformFormValuesToApi(formValues);

			expect(result.name).toBe("Test Automation");
			expect(result.description).toBe("Test description");
			expect(result.trigger).toEqual(formValues.trigger);
			expect(result.actions).toEqual(formValues.actions);
		});

		it("transforms undefined description to empty string", () => {
			const formValues = {
				name: "Test Automation",
				description: undefined,
				trigger: {
					type: "event" as const,
					posture: "Reactive" as const,
					threshold: 1,
					within: 0,
				},
				actions: [{ type: "do-nothing" as const }],
			};

			const result = transformFormValuesToApi(formValues);

			expect(result.description).toBe("");
		});
	});

	describe("useEditAutomation hook", () => {
		it("fetches automation data and provides default values", async () => {
			const mockAutomation = createFakeAutomation({
				id: "automation-123",
				name: "Test Automation",
				description: "Test description",
			});
			mockFetchGetAutomationAPI(mockAutomation);

			const { result } = renderHook(
				() => useEditAutomation({ automationId: "automation-123" }),
				{ wrapper: createWrapper() },
			);

			await waitFor(() => expect(result.current.isLoading).toBe(false));

			expect(result.current.defaultValues).toBeDefined();
			expect(result.current.defaultValues?.name).toBe("Test Automation");
			expect(result.current.defaultValues?.description).toBe(
				"Test description",
			);
		});

		it("calls updateAutomation mutation with transformed values", async () => {
			const queryClient = new QueryClient();
			const mockAutomation = createFakeAutomation({
				id: "automation-123",
				enabled: true,
			});
			mockFetchGetAutomationAPI(mockAutomation);
			mockReplaceAutomationAPI();

			const onSuccess = vi.fn();
			const onError = vi.fn();

			const { result } = renderHook(
				() =>
					useEditAutomation({
						automationId: "automation-123",
						onSuccess,
						onError,
					}),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isLoading).toBe(false));

			const updatedValues = {
				name: "Updated Automation",
				description: "Updated description",
				trigger: {
					type: "event" as const,
					posture: "Reactive" as const,
					threshold: 1,
					within: 0,
				},
				actions: [{ type: "cancel-flow-run" as const }],
			};

			act(() => {
				result.current.updateAutomation(updatedValues);
			});

			await waitFor(() => expect(result.current.isPending).toBe(false));
			await waitFor(() => expect(onSuccess).toHaveBeenCalled());
			expect(onError).not.toHaveBeenCalled();
		});

		it("calls onError callback when update fails", async () => {
			const queryClient = new QueryClient();
			const mockAutomation = createFakeAutomation({
				id: "automation-123",
			});
			mockFetchGetAutomationAPI(mockAutomation);

			server.use(
				http.put(buildApiUrl("/automations/:id"), () => {
					return HttpResponse.json(
						{ detail: "Update failed" },
						{ status: 500 },
					);
				}),
			);

			const onSuccess = vi.fn();
			const onError = vi.fn();

			const { result } = renderHook(
				() =>
					useEditAutomation({
						automationId: "automation-123",
						onSuccess,
						onError,
					}),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isLoading).toBe(false));

			const updatedValues = {
				name: "Updated Automation",
				trigger: {
					type: "event" as const,
					posture: "Reactive" as const,
					threshold: 1,
					within: 0,
				},
				actions: [{ type: "do-nothing" as const }],
			};

			act(() => {
				result.current.updateAutomation(updatedValues);
			});

			await waitFor(() => expect(onError).toHaveBeenCalled());
			expect(onSuccess).not.toHaveBeenCalled();
		});

		it("preserves enabled state from fetched automation", async () => {
			const queryClient = new QueryClient();
			const mockAutomation = createFakeAutomation({
				id: "automation-123",
				enabled: false,
			});
			mockFetchGetAutomationAPI(mockAutomation);

			let capturedBody: { enabled?: boolean } | null = null;
			server.use(
				http.put(buildApiUrl("/automations/:id"), async ({ request }) => {
					capturedBody = (await request.json()) as { enabled?: boolean };
					return new HttpResponse(null, { status: 204 });
				}),
			);

			const { result } = renderHook(
				() => useEditAutomation({ automationId: "automation-123" }),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isLoading).toBe(false));

			const updatedValues = {
				name: "Updated Automation",
				trigger: {
					type: "event" as const,
					posture: "Reactive" as const,
					threshold: 1,
					within: 0,
				},
				actions: [{ type: "do-nothing" as const }],
			};

			act(() => {
				result.current.updateAutomation(updatedValues);
			});

			await waitFor(() => expect(capturedBody).not.toBeNull());
			expect((capturedBody as unknown as { enabled: boolean }).enabled).toBe(
				false,
			);
		});
	});
});
