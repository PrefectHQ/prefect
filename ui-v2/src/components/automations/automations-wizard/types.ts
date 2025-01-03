import { components } from "@/api/prefect";

// Action type that excludes "do-nothing" and "call-webhook". These types are currently not used in the automation creation UI
export type ActionType = Exclude<
	components["schemas"]["AutomationCreate"]["actions"][number]["type"],
	"do-nothing" | "call-webhook"
>;
