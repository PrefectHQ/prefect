import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { buildFilterWorkQueuesQuery, type WorkQueue } from "@/api/work-queues";
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

const MAX_VISIBLE_ITEMS = 2;

type WorkQueuesComboboxProps = {
	selectedWorkQueueIds: string[];
	onToggleWorkQueue: (workQueueId: string) => void;
	workPoolIds?: string[];
	emptyMessage?: string;
};

export function WorkQueuesCombobox({
	selectedWorkQueueIds,
	onToggleWorkQueue,
	workPoolIds = [],
	emptyMessage = "All work queues",
}: WorkQueuesComboboxProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data: workQueues = [] } = useQuery(
		buildFilterWorkQueuesQuery({
			limit: 100,
			offset: 0,
		}),
	);

	const filteredWorkQueues = useMemo(() => {
		return workQueues.filter((workQueue: WorkQueue) => {
			// Filter by work pool IDs if specified
			if (
				workPoolIds.length > 0 &&
				(!workQueue.work_pool_id ||
					!workPoolIds.includes(workQueue.work_pool_id))
			) {
				return false;
			}
			if (!deferredSearch) {
				return true;
			}
			return workQueue.name
				.toLowerCase()
				.includes(deferredSearch.toLowerCase());
		});
	}, [workQueues, workPoolIds, deferredSearch]);

	const renderSelectedWorkQueues = () => {
		if (selectedWorkQueueIds.length === 0) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}

		const selectedWorkQueueNames = workQueues
			.filter((workQueue) => selectedWorkQueueIds.includes(workQueue.id))
			.map((workQueue) => workQueue.name);

		const visibleNames = selectedWorkQueueNames.slice(0, MAX_VISIBLE_ITEMS);
		const overflow = selectedWorkQueueIds.length - visibleNames.length;

		return (
			<div className="flex min-w-0 items-center justify-start gap-1">
				<span className="truncate min-w-0 text-left">
					{visibleNames.join(", ")}
				</span>
				{overflow > 0 && (
					<span className="shrink-0 text-muted-foreground">+{overflow}</span>
				)}
			</div>
		);
	};

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedWorkQueueIds.length > 0}>
				{renderSelectedWorkQueues()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search work queues..."
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No work queues found</ComboboxCommandEmtpy>
					<ComboboxCommandGroup>
						{filteredWorkQueues.map((workQueue: WorkQueue) => (
							<ComboboxCommandItem
								key={workQueue.id}
								selected={selectedWorkQueueIds.includes(workQueue.id)}
								onSelect={() => {
									onToggleWorkQueue(workQueue.id);
									setSearch("");
								}}
								closeOnSelect={false}
								value={workQueue.id}
							>
								{workQueue.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
