import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { FormattedDate } from "@/components/ui/formatted-date";
import { Separator } from "@/components/ui/separator";
import { WorkPoolQueueStatusBadge } from "@/components/work-pools/work-pool-queue-status-badge";
import { cn } from "@/utils";

type WorkPoolQueueDetailsProps = {
	workPoolName: string;
	queue: WorkPoolQueue;
	alternate?: boolean;
	className?: string;
};

// Helper components for field display
const None = () => <dd className="text-muted-foreground text-sm">None</dd>;
const FieldLabel = ({ children }: { children: React.ReactNode }) => (
	<dt className="text-sm text-muted-foreground">{children}</dt>
);
const FieldValue = ({
	children,
	className,
}: {
	children: React.ReactNode;
	className?: string;
}) => <dd className={cn("text-sm", className)}>{children}</dd>;

// Basic Info Section Component
function BasicInfoSection({
	workPoolName,
	queue,
}: {
	workPoolName: string;
	queue: WorkPoolQueue;
}) {
	const fields = [
		{
			field: "Work Pool",
			ComponentValue: () => <FieldValue>{workPoolName}</FieldValue>,
		},
		{
			field: "Status",
			ComponentValue: () => (
				<dd>
					<WorkPoolQueueStatusBadge status={queue.status || "NOT_READY"} />
				</dd>
			),
		},
		{
			field: "Last Polled",
			ComponentValue: () =>
				queue.last_polled ? (
					<FieldValue>
						<FormattedDate date={queue.last_polled} />
					</FieldValue>
				) : (
					<FieldValue className="text-muted-foreground">Never</FieldValue>
				),
		},
		{
			field: "Description",
			ComponentValue: () =>
				queue.description ? <FieldValue>{queue.description}</FieldValue> : null,
		},
		{
			field: "Priority",
			ComponentValue: () =>
				queue.priority !== null && queue.priority !== undefined ? (
					<FieldValue>{String(queue.priority)}</FieldValue>
				) : (
					<None />
				),
		},
	].filter(({ ComponentValue }) => ComponentValue() !== null);

	return (
		<div>
			<ul className="flex flex-col gap-3">
				{fields.map(({ field, ComponentValue }) => (
					<li key={field}>
						<dl>
							<FieldLabel>{field}</FieldLabel>
							<ComponentValue />
						</dl>
					</li>
				))}
			</ul>
		</div>
	);
}

// Meta Info Section Component
function MetaInfoSection({ queue }: { queue: WorkPoolQueue }) {
	const fields = [
		{
			field: "Work Queue ID",
			ComponentValue: () =>
				queue.id ? <FieldValue>{queue.id}</FieldValue> : <None />,
		},
		{
			field: "Flow Run Concurrency",
			ComponentValue: () => (
				<FieldValue>
					{queue.concurrency_limit !== null &&
					queue.concurrency_limit !== undefined
						? String(queue.concurrency_limit)
						: "Unlimited"}
				</FieldValue>
			),
		},
		{
			field: "Created",
			ComponentValue: () =>
				queue.created ? (
					<FieldValue>
						<FormattedDate date={queue.created} />
					</FieldValue>
				) : (
					<None />
				),
		},
		{
			field: "Last Updated",
			ComponentValue: () =>
				queue.updated ? (
					<FieldValue>
						<FormattedDate date={queue.updated} />
					</FieldValue>
				) : (
					<None />
				),
		},
	];

	return (
		<div>
			<ul className="flex flex-col gap-3">
				{fields.map(({ field, ComponentValue }) => (
					<li key={field}>
						<dl>
							<FieldLabel>{field}</FieldLabel>
							<ComponentValue />
						</dl>
					</li>
				))}
			</ul>
		</div>
	);
}

export function WorkPoolQueueDetails({
	workPoolName,
	queue,
	alternate = false,
	className,
}: WorkPoolQueueDetailsProps) {
	const spacing = alternate ? "space-y-4" : "space-y-6";

	return (
		<div className={cn(spacing, className)}>
			<BasicInfoSection workPoolName={workPoolName} queue={queue} />
			<Separator />
			<MetaInfoSection queue={queue} />
		</div>
	);
}
