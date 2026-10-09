import { useIsMutating, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useEffect, useId, useRef, useState } from "react";
import {
	buildPaginateDeploymentsQuery,
	type Deployment,
} from "@/api/deployments";
import { deploymentCreateFlowRunMutationKey } from "@/api/flow-runs";
import { buildDeploymentsCountByFlowQuery } from "@/api/flows";
import type { components } from "@/api/prefect";
import { RunFlowButton } from "@/components/deployments/run-flow-button";
import { Button } from "@/components/ui/button";
import {
	Combobox,
	ComboboxCommandEmtpy,
	ComboboxCommandGroup,
	ComboboxCommandInput,
	ComboboxCommandItem,
	ComboboxCommandList,
	ComboboxContent,
	ComboboxTrigger,
} from "@/components/ui/combobox";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { DocsLink } from "@/components/ui/docs-link";
import { Icon } from "@/components/ui/icons";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";

type Flow = components["schemas"]["Flow"];

const PAGE_SIZE = 10;

export type FlowRunActionProps = {
	flow: Flow;
};

export const FlowRunAction = ({ flow }: FlowRunActionProps) => {
	const [open, setOpen] = useState(false);
	const descriptionId = useId();

	const countQuery = useQuery(
		buildDeploymentsCountByFlowQuery(flow.id ? [flow.id] : [], {
			enabled: !!flow.id,
		}),
	);

	const countKnown =
		countQuery.isSuccess &&
		!countQuery.isPlaceholderData &&
		typeof (flow.id ? countQuery.data[flow.id] : undefined) === "number";

	const disabledReason = countKnown
		? countQuery.data[flow.id ?? ""] === 0
			? "Create a deployment to run this flow from the UI."
			: null
		: countQuery.isError
			? "Could not check deployments. Refresh to retry."
			: "Checking for deployments";

	const runButton = (
		<Button
			variant="outline"
			size="sm"
			disabled={disabledReason !== null}
			aria-describedby={disabledReason ? descriptionId : undefined}
			onClick={() => setOpen(true)}
		>
			Run <Icon id="Play" className="ml-1 size-4" />
		</Button>
	);

	return (
		<>
			{disabledReason ? (
				<Tooltip>
					<TooltipTrigger asChild>
						<span tabIndex={disabledReason ? 0 : -1} className="inline-flex">
							{runButton}
						</span>
					</TooltipTrigger>
					<TooltipContent>{disabledReason}</TooltipContent>
				</Tooltip>
			) : (
				runButton
			)}
			{disabledReason && (
				<span id={descriptionId} className="sr-only">
					{disabledReason}
				</span>
			)}
			<Dialog open={open} onOpenChange={setOpen}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Run {flow.name}</DialogTitle>
					</DialogHeader>
					{open && (
						<FlowRunDialogBody
							key={flow.id}
							flow={flow}
							onRunCreated={() => setOpen(false)}
						/>
					)}
				</DialogContent>
			</Dialog>
		</>
	);
};

const FlowRunDialogBody = ({
	flow,
	onRunCreated,
}: {
	flow: Flow;
	onRunCreated: () => void;
}) => {
	const queryClient = useQueryClient();
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);
	const [page, setPage] = useState(1);
	const [selectedDeployment, setSelectedDeployment] =
		useState<Deployment | null>(null);
	const isMutating =
		useIsMutating({ mutationKey: deploymentCreateFlowRunMutationKey }) > 0;

	const flowsFilter = {
		operator: "and_" as const,
		id: { any_: [flow.id ?? ""] },
	};

	const deploymentsQuery = useQuery(
		buildPaginateDeploymentsQuery({
			page,
			limit: PAGE_SIZE,
			sort: "NAME_ASC",
			flows: flowsFilter,
			deployments: deferredSearch
				? { operator: "and_", name: { like_: deferredSearch } }
				: undefined,
		}),
	);

	const baselineQuery = useQuery(
		buildPaginateDeploymentsQuery({
			page: 1,
			limit: PAGE_SIZE,
			sort: "NAME_ASC",
			flows: flowsFilter,
		}),
	);

	const baselineSingle =
		baselineQuery.isSuccess &&
		!baselineQuery.isPlaceholderData &&
		baselineQuery.data.count === 1 &&
		baselineQuery.data.results[0]?.flow_id === flow.id;

	const baselineEmpty =
		baselineQuery.isSuccess &&
		!baselineQuery.isPlaceholderData &&
		baselineQuery.data.count === 0;

	const selection =
		selectedDeployment ??
		(baselineSingle ? (baselineQuery.data.results[0] ?? null) : null);

	// Reconcile the shared count query if every deployment was deleted between
	// the row's count check and the dialog opening.
	const reconciledRef = useRef(false);
	useEffect(() => {
		if (baselineEmpty && !reconciledRef.current && flow.id) {
			reconciledRef.current = true;
			void queryClient.invalidateQueries({
				queryKey: buildDeploymentsCountByFlowQuery([flow.id]).queryKey,
			});
		}
	}, [baselineEmpty, flow.id, queryClient]);

	if (baselineEmpty) {
		return (
			<div className="flex flex-col items-start gap-3">
				<p className="text-sm text-muted-foreground">
					This flow has no deployments.
				</p>
				<DocsLink id="deployments-guide" />
			</div>
		);
	}

	const results = deploymentsQuery.data?.results ?? [];
	const pages = deploymentsQuery.data?.pages ?? 0;

	return (
		<div className="space-y-4">
			<Combobox>
				<ComboboxTrigger
					aria-label="Select a deployment"
					disabled={isMutating}
					selected={!selection}
				>
					{selection ? selection.name : "Select a deployment"}
				</ComboboxTrigger>
				<ComboboxContent className="flex flex-col overflow-hidden">
					<ComboboxCommandInput
						value={search}
						onValueChange={(value) => {
							setSearch(value);
							setPage(1);
						}}
						placeholder="Search deployments..."
					/>
					<ComboboxCommandList className="min-h-0 flex-1">
						<ComboboxCommandEmtpy>
							{deferredSearch
								? "No deployments match your search"
								: "No deployments found"}
						</ComboboxCommandEmtpy>
						<ComboboxCommandGroup>
							{results.map((deployment) => (
								<ComboboxCommandItem
									key={deployment.id}
									aria-label={deployment.name}
									value={deployment.id}
									disabled={deploymentsQuery.isPlaceholderData}
									selected={selection?.id === deployment.id}
									onSelect={() => {
										if (deployment.flow_id === flow.id) {
											setSelectedDeployment(deployment);
										}
									}}
								>
									{deployment.name}
								</ComboboxCommandItem>
							))}
						</ComboboxCommandGroup>
					</ComboboxCommandList>
					{pages > 1 && (
						<div className="flex items-center justify-between border-t p-2">
							<Button
								variant="outline"
								size="sm"
								disabled={page <= 1 || isMutating}
								onClick={() => setPage((p) => p - 1)}
							>
								Previous
							</Button>
							<span className="text-sm text-muted-foreground">
								Page {page} of {pages}
							</span>
							<Button
								variant="outline"
								size="sm"
								disabled={page >= pages || isMutating}
								onClick={() => setPage((p) => p + 1)}
							>
								Next
							</Button>
						</div>
					)}
				</ComboboxContent>
			</Combobox>
			{deploymentsQuery.isLoading && (
				<p className="text-sm text-muted-foreground">Loading deployments…</p>
			)}
			{deploymentsQuery.isError && (
				<div className="flex items-center gap-2">
					<p className="text-sm text-destructive">
						Could not load deployments.
					</p>
					<Button
						variant="outline"
						size="sm"
						onClick={() => void deploymentsQuery.refetch()}
					>
						Retry
					</Button>
				</div>
			)}
			{selection ? (
				<RunFlowButton
					key={selection.id}
					deployment={selection}
					onRunCreated={onRunCreated}
				/>
			) : (
				<p className="text-sm text-muted-foreground">
					Select a deployment to run it.
				</p>
			)}
		</div>
	);
};
