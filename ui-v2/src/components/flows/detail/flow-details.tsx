import type { Flow } from "@/api/flows";
import { FormattedDate } from "@/components/ui/formatted-date";

type FlowDetailsProps = {
	flow: Flow;
};

export const FlowDetails = ({ flow }: FlowDetailsProps) => {
	return (
		<div className="flex flex-col gap-4">
			<dl className="flex flex-col gap-2">
				<dt className="text-muted-foreground">Flow ID</dt>
				<dd className="text-sm font-medium leading-none font-mono">
					{flow.id}
				</dd>
			</dl>
			<dl className="flex flex-col gap-2">
				<dt className="text-muted-foreground">Created</dt>
				<dd className="text-sm font-medium leading-none font-mono">
					{flow.created ? (
						<FormattedDate date={flow.created} format="absolute" />
					) : (
						"N/A"
					)}
				</dd>
			</dl>
			<dl className="flex flex-col gap-2">
				<dt className="text-muted-foreground">Updated</dt>
				<dd className="text-sm font-medium leading-none font-mono">
					{flow.updated ? (
						<FormattedDate date={flow.updated} format="absolute" />
					) : (
						"N/A"
					)}
				</dd>
			</dl>
		</div>
	);
};
