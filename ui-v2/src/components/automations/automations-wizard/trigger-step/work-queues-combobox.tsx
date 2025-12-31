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

	// Group work queues by work pool name
	const groupedWorkQueues = useMemo(() => {
		const groups: Record<string, WorkQueue[]> = {};

		for (const workQueue of filteredWorkQueues) {
			const poolName = workQueue.work_pool_name ?? "Unknown";
			if (!groups[poolName]) {
				groups[poolName] = [];
			}
			groups[poolName].push(workQueue);
		}

		// Sort groups by pool name and sort queues within each group by name
		const sortedGroupNames = Object.keys(groups).sort((a, b) =>
			a.localeCompare(b),
		);

		return sortedGroupNames.map((poolName) => ({
			poolName,
			queues: groups[poolName].sort((a, b) => a.name.localeCompare(b.name)),
		}));
	}, [filteredWorkQueues]);

	const renderSelectedWorkQueues = () => {
		if (selectedWorkQueueIds.length === 0) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}

		const selectedWorkQueueNames = workQueues
			.filter((workQueue) => selectedWorkQueueIds.includes(workQueue.id))
			.map((workQueue) => workQueue.name);

		return (
			<span className="truncate min-w-0 text-left">
				{selectedWorkQueueNames.join(", ")}
			</span>
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
					{groupedWorkQueues.map((group) => (
						<ComboboxCommandGroup key={group.poolName} heading={group.poolName}>
							{group.queues.map((workQueue: WorkQueue) => (
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
					))}
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
