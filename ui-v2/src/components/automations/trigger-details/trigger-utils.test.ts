import { describe, expect, it } from "vitest";
import {
	AUTOMATION_TRIGGER_TEMPLATES,
	type AutomationTrigger,
	type AutomationTriggerTemplate,
	DEFAULT_EVENT_TRIGGER_THRESHOLD,
	DEPLOYMENT_STATUS_EVENTS,
	type EventTrigger,
	getAutomationTriggerEventPostureLabel,
	getAutomationTriggerTemplate,
	getAutomationTriggerTemplateLabel,
	isAfterResource,
	isAutomationTrigger,
	isAutomationTriggerTemplate,
	isCompoundTrigger,
	isDeploymentStatusTrigger,
	isEventTrigger,
	isExpectResource,
	isFlowRunStateTrigger,
	isForEachResource,
	isMatchResource,
	isSequenceTrigger,
	isWorkPoolStatusTrigger,
	isWorkQueueStatusTrigger,
	WORK_POOL_STATUS_EVENTS,
	WORK_QUEUE_STATUS_EVENTS,
} from "./trigger-utils";

// Helper to create a base event trigger for testing
function createBaseEventTrigger(
	overrides: Partial<EventTrigger> = {},
): EventTrigger {
	return {
		type: "event",
		posture: "Reactive",
		threshold: DEFAULT_EVENT_TRIGGER_THRESHOLD,
		within: 0,
		...overrides,
	};
}

// Helper to create a deployment-status trigger
function createDeploymentStatusTrigger(
	overrides: Partial<EventTrigger> = {},
): EventTrigger {
	return createBaseEventTrigger({
		match: { "prefect.resource.id": "prefect.deployment.*" },
		for_each: ["prefect.resource.id"],
		after: ["prefect.deployment.ready"],
		expect: ["prefect.deployment.not-ready"],
		...overrides,
	});
}

// Helper to create a flow-run-state trigger
function createFlowRunStateTrigger(
	overrides: Partial<EventTrigger> = {},
): EventTrigger {
	return createBaseEventTrigger({
		match: { "prefect.resource.id": "prefect.flow-run.*" },
		match_related: {},
		for_each: ["prefect.resource.id"],
		after: ["prefect.flow-run.Pending"],
		expect: ["prefect.flow-run.Completed"],
		...overrides,
	});
}

// Helper to create a work-pool-status trigger
function createWorkPoolStatusTrigger(
	overrides: Partial<EventTrigger> = {},
): EventTrigger {
	return createBaseEventTrigger({
		match: { "prefect.resource.id": "prefect.work-pool.*" },
		for_each: ["prefect.resource.id"],
		after: ["prefect.work-pool.ready"],
		expect: ["prefect.work-pool.not-ready"],
		...overrides,
	});
}

// Helper to create a work-queue-status trigger
function createWorkQueueStatusTrigger(
	overrides: Partial<EventTrigger> = {},
): EventTrigger {
	return createBaseEventTrigger({
		match: { "prefect.resource.id": "prefect.work-queue.*" },
		for_each: ["prefect.resource.id"],
		after: ["prefect.work-queue.ready"],
		expect: ["prefect.work-queue.not-ready"],
		...overrides,
	});
}

describe("trigger-utils", () => {
	describe("Constants", () => {
		it("should have 5 automation trigger templates", () => {
			expect(AUTOMATION_TRIGGER_TEMPLATES).toHaveLength(5);
			expect(AUTOMATION_TRIGGER_TEMPLATES).toContain("deployment-status");
			expect(AUTOMATION_TRIGGER_TEMPLATES).toContain("flow-run-state");
			expect(AUTOMATION_TRIGGER_TEMPLATES).toContain("work-pool-status");
			expect(AUTOMATION_TRIGGER_TEMPLATES).toContain("work-queue-status");
			expect(AUTOMATION_TRIGGER_TEMPLATES).toContain("custom");
		});

		it("should have correct default event trigger threshold", () => {
			expect(DEFAULT_EVENT_TRIGGER_THRESHOLD).toBe(1);
		});

		it("should have correct deployment status events", () => {
			expect(DEPLOYMENT_STATUS_EVENTS).toContain("prefect.deployment.ready");
			expect(DEPLOYMENT_STATUS_EVENTS).toContain(
				"prefect.deployment.not-ready",
			);
			expect(DEPLOYMENT_STATUS_EVENTS).toContain("prefect.deployment.disabled");
		});

		it("should have correct work pool status events", () => {
			expect(WORK_POOL_STATUS_EVENTS).toContain("prefect.work-pool.ready");
			expect(WORK_POOL_STATUS_EVENTS).toContain("prefect.work-pool.not-ready");
			expect(WORK_POOL_STATUS_EVENTS).toContain("prefect.work-pool.paused");
		});

		it("should have correct work queue status events", () => {
			expect(WORK_QUEUE_STATUS_EVENTS).toContain("prefect.work-queue.ready");
			expect(WORK_QUEUE_STATUS_EVENTS).toContain(
				"prefect.work-queue.not-ready",
			);
			expect(WORK_QUEUE_STATUS_EVENTS).toContain("prefect.work-queue.paused");
		});
	});

	describe("Type Guards", () => {
		describe("isEventTrigger", () => {
			it("should return true for valid event trigger", () => {
				const trigger = createBaseEventTrigger();
				expect(isEventTrigger(trigger)).toBe(true);
			});

			it("should return true for Proactive posture", () => {
				const trigger = createBaseEventTrigger({ posture: "Proactive" });
				expect(isEventTrigger(trigger)).toBe(true);
			});

			it("should return false for compound trigger", () => {
				const trigger = {
					type: "compound",
					triggers: [],
					within: 0,
					require: "all",
				};
				expect(isEventTrigger(trigger)).toBe(false);
			});

			it("should return false for sequence trigger", () => {
				const trigger = { type: "sequence", triggers: [], within: 0 };
				expect(isEventTrigger(trigger)).toBe(false);
			});

			it("should return false for null", () => {
				expect(isEventTrigger(null)).toBe(false);
			});

			it("should return false for undefined", () => {
				expect(isEventTrigger(undefined)).toBe(false);
			});

			it("should return false for invalid posture", () => {
				const trigger = { type: "event", posture: "Invalid" };
				expect(isEventTrigger(trigger)).toBe(false);
			});
		});

		describe("isCompoundTrigger", () => {
			it("should return true for valid compound trigger", () => {
				const trigger = {
					type: "compound",
					triggers: [],
					within: 0,
					require: "all",
				};
				expect(isCompoundTrigger(trigger)).toBe(true);
			});

			it("should return true for compound trigger with nested triggers", () => {
				const trigger = {
					type: "compound",
					triggers: [createBaseEventTrigger()],
					within: 60,
					require: 1,
				};
				expect(isCompoundTrigger(trigger)).toBe(true);
			});

			it("should return false for event trigger", () => {
				const trigger = createBaseEventTrigger();
				expect(isCompoundTrigger(trigger)).toBe(false);
			});

			it("should return false for missing triggers array", () => {
				const trigger = { type: "compound", within: 0, require: "all" };
				expect(isCompoundTrigger(trigger)).toBe(false);
			});
		});

		describe("isSequenceTrigger", () => {
			it("should return true for valid sequence trigger", () => {
				const trigger = { type: "sequence", triggers: [], within: 0 };
				expect(isSequenceTrigger(trigger)).toBe(true);
			});

			it("should return true for sequence trigger with nested triggers", () => {
				const trigger = {
					type: "sequence",
					triggers: [createBaseEventTrigger()],
					within: 60,
				};
				expect(isSequenceTrigger(trigger)).toBe(true);
			});

			it("should return false for event trigger", () => {
				const trigger = createBaseEventTrigger();
				expect(isSequenceTrigger(trigger)).toBe(false);
			});

			it("should return false for compound trigger", () => {
				const trigger = {
					type: "compound",
					triggers: [],
					within: 0,
					require: "all",
				};
				expect(isSequenceTrigger(trigger)).toBe(false);
			});
		});

		describe("isAutomationTrigger", () => {
			it("should return true for event trigger", () => {
				const trigger = createBaseEventTrigger();
				expect(isAutomationTrigger(trigger)).toBe(true);
			});

			it("should return true for compound trigger", () => {
				const trigger = {
					type: "compound",
					triggers: [],
					within: 0,
					require: "all",
				};
				expect(isAutomationTrigger(trigger)).toBe(true);
			});

			it("should return true for sequence trigger", () => {
				const trigger = { type: "sequence", triggers: [], within: 0 };
				expect(isAutomationTrigger(trigger)).toBe(true);
			});

			it("should return false for invalid trigger", () => {
				expect(isAutomationTrigger({ type: "invalid" })).toBe(false);
				expect(isAutomationTrigger(null)).toBe(false);
				expect(isAutomationTrigger(undefined)).toBe(false);
			});
		});

		describe("isAutomationTriggerTemplate", () => {
			it("should return true for valid templates", () => {
				expect(isAutomationTriggerTemplate("deployment-status")).toBe(true);
				expect(isAutomationTriggerTemplate("flow-run-state")).toBe(true);
				expect(isAutomationTriggerTemplate("work-pool-status")).toBe(true);
				expect(isAutomationTriggerTemplate("work-queue-status")).toBe(true);
				expect(isAutomationTriggerTemplate("custom")).toBe(true);
			});

			it("should return false for invalid templates", () => {
				expect(isAutomationTriggerTemplate("invalid")).toBe(false);
				expect(isAutomationTriggerTemplate("")).toBe(false);
				expect(isAutomationTriggerTemplate("compound")).toBe(false);
				expect(isAutomationTriggerTemplate("sequence")).toBe(false);
			});
		});
	});

	describe("Validation Helpers", () => {
		describe("isMatchResource", () => {
			it("should return true when predicate matches", () => {
				const trigger = createDeploymentStatusTrigger();
				expect(
					isMatchResource(trigger, (ids) =>
						ids.every((id) => id.startsWith("prefect.deployment")),
					),
				).toBe(true);
			});

			it("should return false when predicate does not match", () => {
				const trigger = createDeploymentStatusTrigger();
				expect(
					isMatchResource(trigger, (ids) =>
						ids.every((id) => id.startsWith("prefect.flow-run")),
					),
				).toBe(false);
			});

			it("should return false when match is empty", () => {
				const trigger = createBaseEventTrigger({ match: {} });
				expect(isMatchResource(trigger, () => true)).toBe(false);
			});

			it("should handle array of resource ids", () => {
				const trigger = createBaseEventTrigger({
					match: {
						"prefect.resource.id": [
							"prefect.deployment.123",
							"prefect.deployment.456",
						],
					},
				});
				expect(
					isMatchResource(trigger, (ids) =>
						ids.every((id) => id.startsWith("prefect.deployment")),
					),
				).toBe(true);
			});
		});

		describe("isForEachResource", () => {
			it("should return true when for_each contains expected resource", () => {
				const trigger = createDeploymentStatusTrigger();
				expect(isForEachResource(trigger, "prefect.resource.id")).toBe(true);
			});

			it("should return true when for_each is empty (every() on empty array returns true)", () => {
				const trigger = createBaseEventTrigger({ for_each: [] });
				expect(isForEachResource(trigger, "prefect.resource.id")).toBe(true);
			});

			it("should return false for non-event trigger", () => {
				const trigger = {
					type: "compound",
					triggers: [],
					within: 0,
					require: "all",
				} as unknown as AutomationTrigger;
				expect(isForEachResource(trigger, "prefect.resource.id")).toBe(false);
			});
		});

		describe("isAfterResource", () => {
			it("should return true when predicate matches after events", () => {
				const trigger = createDeploymentStatusTrigger();
				expect(
					isAfterResource(trigger, (events) =>
						events.every((e) => e.startsWith("prefect.deployment")),
					),
				).toBe(true);
			});

			it("should return true for empty after array with matching predicate", () => {
				const trigger = createBaseEventTrigger({ after: [] });
				expect(isAfterResource(trigger, (events) => events.length === 0)).toBe(
					true,
				);
			});
		});

		describe("isExpectResource", () => {
			it("should return true when predicate matches expect events", () => {
				const trigger = createDeploymentStatusTrigger();
				expect(
					isExpectResource(trigger, (events) =>
						events.every((e) => e.startsWith("prefect.deployment")),
					),
				).toBe(true);
			});

			it("should return true for empty expect array with matching predicate", () => {
				const trigger = createBaseEventTrigger({ expect: [] });
				expect(isExpectResource(trigger, (events) => events.length === 0)).toBe(
					true,
				);
			});
		});
	});

	describe("Template Detection", () => {
		describe("isDeploymentStatusTrigger", () => {
			it("should return true for valid deployment-status trigger", () => {
				const trigger = createDeploymentStatusTrigger();
				expect(isDeploymentStatusTrigger(trigger)).toBe(true);
			});

			it("should return false when match does not start with prefect.deployment", () => {
				const trigger = createDeploymentStatusTrigger({
					match: { "prefect.resource.id": "prefect.flow-run.*" },
				});
				expect(isDeploymentStatusTrigger(trigger)).toBe(false);
			});

			it("should return false when threshold is not 1", () => {
				const trigger = createDeploymentStatusTrigger({ threshold: 2 });
				expect(isDeploymentStatusTrigger(trigger)).toBe(false);
			});

			it("should return false when after events are not deployment status events", () => {
				const trigger = createDeploymentStatusTrigger({
					after: ["prefect.flow-run.Completed"],
				});
				expect(isDeploymentStatusTrigger(trigger)).toBe(false);
			});

			it("should return false when expect events are not deployment status events", () => {
				const trigger = createDeploymentStatusTrigger({
					expect: ["prefect.flow-run.Failed"],
				});
				expect(isDeploymentStatusTrigger(trigger)).toBe(false);
			});
		});

		describe("isFlowRunStateTrigger", () => {
			it("should return true for valid flow-run-state trigger", () => {
				const trigger = createFlowRunStateTrigger();
				expect(isFlowRunStateTrigger(trigger)).toBe(true);
			});

			it("should return true with empty matchRelated", () => {
				const trigger = createFlowRunStateTrigger({ match_related: {} });
				expect(isFlowRunStateTrigger(trigger)).toBe(true);
			});

			it("should return true with flow matchRelated", () => {
				const trigger = createFlowRunStateTrigger({
					match_related: {
						"prefect.resource.role": "flow",
						"prefect.resource.id": "prefect.flow.123",
					},
				});
				expect(isFlowRunStateTrigger(trigger)).toBe(true);
			});

			it("should return true with tag matchRelated", () => {
				const trigger = createFlowRunStateTrigger({
					match_related: {
						"prefect.resource.role": "tag",
						"prefect.resource.id": "prefect.tag.my-tag",
					},
				});
				expect(isFlowRunStateTrigger(trigger)).toBe(true);
			});

			it("should return false when match does not start with prefect.flow-run", () => {
				const trigger = createFlowRunStateTrigger({
					match: { "prefect.resource.id": "prefect.deployment.*" },
				});
				expect(isFlowRunStateTrigger(trigger)).toBe(false);
			});

			it("should return false when threshold is not 1", () => {
				const trigger = createFlowRunStateTrigger({ threshold: 5 });
				expect(isFlowRunStateTrigger(trigger)).toBe(false);
			});

			it("should return false when after events do not start with prefect.flow-run", () => {
				const trigger = createFlowRunStateTrigger({
					after: ["prefect.deployment.ready"],
				});
				expect(isFlowRunStateTrigger(trigger)).toBe(false);
			});
		});

		describe("isWorkPoolStatusTrigger", () => {
			it("should return true for valid work-pool-status trigger", () => {
				const trigger = createWorkPoolStatusTrigger();
				expect(isWorkPoolStatusTrigger(trigger)).toBe(true);
			});

			it("should return false when match does not start with prefect.work-pool", () => {
				const trigger = createWorkPoolStatusTrigger({
					match: { "prefect.resource.id": "prefect.flow-run.*" },
				});
				expect(isWorkPoolStatusTrigger(trigger)).toBe(false);
			});

			it("should return false when threshold is not 1", () => {
				const trigger = createWorkPoolStatusTrigger({ threshold: 3 });
				expect(isWorkPoolStatusTrigger(trigger)).toBe(false);
			});

			it("should return false when after events are not work pool status events", () => {
				const trigger = createWorkPoolStatusTrigger({
					after: ["prefect.deployment.ready"],
				});
				expect(isWorkPoolStatusTrigger(trigger)).toBe(false);
			});
		});

		describe("isWorkQueueStatusTrigger", () => {
			it("should return true for valid work-queue-status trigger", () => {
				const trigger = createWorkQueueStatusTrigger();
				expect(isWorkQueueStatusTrigger(trigger)).toBe(true);
			});

			it("should return false when match does not start with prefect.work-queue", () => {
				const trigger = createWorkQueueStatusTrigger({
					match: { "prefect.resource.id": "prefect.flow-run.*" },
				});
				expect(isWorkQueueStatusTrigger(trigger)).toBe(false);
			});

			it("should return false when threshold is not 1", () => {
				const trigger = createWorkQueueStatusTrigger({ threshold: 2 });
				expect(isWorkQueueStatusTrigger(trigger)).toBe(false);
			});

			it("should return false when after events are not work queue status events", () => {
				const trigger = createWorkQueueStatusTrigger({
					after: ["prefect.work-pool.ready"],
				});
				expect(isWorkQueueStatusTrigger(trigger)).toBe(false);
			});
		});

		describe("getAutomationTriggerTemplate", () => {
			it("should detect deployment-status template", () => {
				const trigger = createDeploymentStatusTrigger();
				expect(getAutomationTriggerTemplate(trigger)).toBe("deployment-status");
			});

			it("should detect flow-run-state template", () => {
				const trigger = createFlowRunStateTrigger();
				expect(getAutomationTriggerTemplate(trigger)).toBe("flow-run-state");
			});

			it("should detect work-pool-status template", () => {
				const trigger = createWorkPoolStatusTrigger();
				expect(getAutomationTriggerTemplate(trigger)).toBe("work-pool-status");
			});

			it("should detect work-queue-status template", () => {
				const trigger = createWorkQueueStatusTrigger();
				expect(getAutomationTriggerTemplate(trigger)).toBe("work-queue-status");
			});

			it("should return custom for compound trigger", () => {
				const trigger = {
					type: "compound",
					triggers: [],
					within: 0,
					require: "all",
				} as unknown as AutomationTrigger;
				expect(getAutomationTriggerTemplate(trigger)).toBe("custom");
			});

			it("should return custom for sequence trigger", () => {
				const trigger = {
					type: "sequence",
					triggers: [],
					within: 0,
				} as unknown as AutomationTrigger;
				expect(getAutomationTriggerTemplate(trigger)).toBe("custom");
			});

			it("should return custom for event trigger that does not match any template", () => {
				const trigger = createBaseEventTrigger({
					match: { "prefect.resource.id": "custom.resource.*" },
					for_each: ["prefect.resource.id"],
					after: ["custom.event"],
					expect: ["custom.event"],
				});
				expect(getAutomationTriggerTemplate(trigger)).toBe("custom");
			});

			it("should return custom when threshold is not 1", () => {
				const trigger = createDeploymentStatusTrigger({ threshold: 5 });
				expect(getAutomationTriggerTemplate(trigger)).toBe("custom");
			});
		});
	});

	describe("Label Functions", () => {
		describe("getAutomationTriggerTemplateLabel", () => {
			it("should return correct label for deployment-status", () => {
				expect(getAutomationTriggerTemplateLabel("deployment-status")).toBe(
					"Deployment status",
				);
			});

			it("should return correct label for flow-run-state", () => {
				expect(getAutomationTriggerTemplateLabel("flow-run-state")).toBe(
					"Flow run state",
				);
			});

			it("should return correct label for work-pool-status", () => {
				expect(getAutomationTriggerTemplateLabel("work-pool-status")).toBe(
					"Work pool status",
				);
			});

			it("should return correct label for work-queue-status", () => {
				expect(getAutomationTriggerTemplateLabel("work-queue-status")).toBe(
					"Work queue status",
				);
			});

			it("should return correct label for custom", () => {
				expect(getAutomationTriggerTemplateLabel("custom")).toBe("Custom");
			});

			it("should return correct labels for all templates", () => {
				const expectedLabels: Record<AutomationTriggerTemplate, string> = {
					"deployment-status": "Deployment status",
					"flow-run-state": "Flow run state",
					"work-pool-status": "Work pool status",
					"work-queue-status": "Work queue status",
					custom: "Custom",
				};

				for (const template of AUTOMATION_TRIGGER_TEMPLATES) {
					expect(getAutomationTriggerTemplateLabel(template)).toBe(
						expectedLabels[template],
					);
				}
			});
		});

		describe("getAutomationTriggerEventPostureLabel", () => {
			it("should return 'enters' for Reactive posture", () => {
				expect(getAutomationTriggerEventPostureLabel("Reactive")).toBe(
					"enters",
				);
			});

			it("should return 'stays in' for Proactive posture", () => {
				expect(getAutomationTriggerEventPostureLabel("Proactive")).toBe(
					"stays in",
				);
			});
		});
	});

	describe("Edge Cases", () => {
		it("should handle trigger with undefined optional fields", () => {
			const trigger: EventTrigger = {
				type: "event",
				posture: "Reactive",
				threshold: 1,
				within: 0,
			};
			expect(isEventTrigger(trigger)).toBe(true);
			expect(getAutomationTriggerTemplate(trigger)).toBe("custom");
		});

		it("should handle trigger with null-like values", () => {
			const trigger = createBaseEventTrigger({
				match: undefined,
				for_each: undefined,
				after: undefined,
				expect: undefined,
			});
			expect(isEventTrigger(trigger)).toBe(true);
			expect(getAutomationTriggerTemplate(trigger)).toBe("custom");
		});

		it("should handle trigger with array of resource ids in match", () => {
			const trigger = createDeploymentStatusTrigger({
				match: {
					"prefect.resource.id": [
						"prefect.deployment.abc",
						"prefect.deployment.xyz",
					],
				},
			});
			expect(isDeploymentStatusTrigger(trigger)).toBe(true);
			expect(getAutomationTriggerTemplate(trigger)).toBe("deployment-status");
		});

		it("should handle flow-run-state trigger with array matchRelated", () => {
			const trigger = createFlowRunStateTrigger({
				match_related: [
					{
						"prefect.resource.role": "flow",
						"prefect.resource.id": "prefect.flow.123",
					},
				],
			});
			expect(isFlowRunStateTrigger(trigger)).toBe(true);
		});

		it("should return custom for malformed trigger", () => {
			const malformedTrigger = {
				type: "event",
				posture: "Reactive",
				threshold: 1,
				within: 0,
				match: { "prefect.resource.id": "invalid" },
				for_each: ["wrong.resource"],
			} as unknown as AutomationTrigger;
			expect(getAutomationTriggerTemplate(malformedTrigger)).toBe("custom");
		});
	});
});
