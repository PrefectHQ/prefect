import type { components } from "@/api/prefect";

export type WorkPoolCreate = components["schemas"]["WorkPoolCreate"];

export type WorkPoolFormValues = {
	name?: string;
	description?: string;
	type?: string;
	concurrencyLimit?: number | null;
	isPaused?: boolean;
	baseJobTemplate?: {
		job_configuration?: Record<string, unknown>;
		variables?: unknown;
	};
};

export type WorkerCollectionItem = {
	type: string;
	displayName?: string;
	description?: string;
	documentationUrl?: string;
	logoUrl?: string;
	isBeta?: boolean;
	defaultBaseJobConfiguration?: Record<string, unknown>;
};

export type WizardStep =
	| "infrastructure-type"
	| "information"
	| "configuration";
