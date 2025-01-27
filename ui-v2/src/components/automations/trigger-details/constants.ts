import type { Automation } from "@/api/automations";

export type AutomationTrigger = Extract<
	Automation["trigger"],
	{ type: "event" }
>;

export const AUTOMATION_TRIGGER_EVENT_POSTURE_LABEL = {
	Proactive: "stays in",
	Reactive: "enters",
} as const satisfies Record<AutomationTrigger["posture"], string>;
