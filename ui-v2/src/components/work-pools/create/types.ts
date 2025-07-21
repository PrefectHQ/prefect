/**
 * Represents a worker collection item from the aggregate worker metadata API
 */
export interface WorkerCollectionItem {
	type: string;
	displayName?: string;
	description: string;
	logoUrl: string;
	documentationUrl?: string;
	isBeta?: boolean;
	isPushPool?: boolean;
	isMexPool?: boolean;
	defaultBaseJobConfiguration?: {
		jobConfiguration?: Record<string, unknown>;
		variables?: {
			properties?: Record<string, unknown>;
		};
	};
}

/**
 * Form values for work pool creation
 */
export interface WorkPoolFormValues {
	name?: string;
	description?: string;
	type?: string;
	isPaused?: boolean;
	concurrencyLimit?: number;
	baseJobTemplate?: Record<string, unknown>;
}

/**
 * Option type for work pool type selection
 */
export interface WorkPoolTypeSelectOption {
	label: string;
	value: string;
	logoUrl: string;
	description: string;
	documentationUrl?: string;
	isBeta: boolean;
}
