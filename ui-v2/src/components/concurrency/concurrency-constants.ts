export const TAB_OPTIONS = {
	Global: "Global",
	"Task Run": "Task Run",
} as const;
export type TabOptions = keyof typeof TAB_OPTIONS;
