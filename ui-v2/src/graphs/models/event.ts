export type RunGraphEventResource = {
	"prefect.resource.id": string;
	"prefect.resource.role"?: string;
	"prefect.resource.name"?: string;
	"prefect.name"?: string;
	"prefect-cloud.name"?: string;
} & Record<string, string | undefined>;

export type EventRelatedResource = RunGraphEventResource & {
	"prefect.resource.role": string;
};

export type RunGraphEvent = {
	id: string;
	occurred: Date;
	event: string;
	payload: unknown;
	received: Date;
	related: EventRelatedResource[];
	resource: RunGraphEventResource;
};
