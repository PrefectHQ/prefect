import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { buildEventsCountQuery, type EventsCountFilter } from "@/api/events";
import { getEventPrefixes } from "@/components/events/events-timeline/utilities";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Typography } from "@/components/ui/typography";

const MAX_EVENT_TYPES_DISPLAYED = 2;

export type EventsTypeFilterProps = {
	filter: EventsCountFilter;
	selectedEventTypes: string[];
	onEventTypesChange: (eventTypes: string[]) => void;
};

export function EventsTypeFilter({
	filter,
	selectedEventTypes,
	onEventTypesChange,
}: EventsTypeFilterProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data: eventCounts = [] } = useQuery(
		buildEventsCountQuery("event", filter),
	);

	const eventTypeOptions = useMemo(() => {
		const prefixSet = new Set<string>();

		for (const eventCount of eventCounts) {
			const prefixes = getEventPrefixes(eventCount.value);
			for (const prefix of prefixes) {
				prefixSet.add(prefix);
			}
		}

		return Array.from(prefixSet).sort();
	}, [eventCounts]);

	const filteredOptions = useMemo(() => {
		if (!deferredSearch) {
			return eventTypeOptions;
		}
		return eventTypeOptions.filter((option) =>
			option.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [eventTypeOptions, deferredSearch]);

	const handleSelectEventType = (eventType: string) => {
		const isSelected = selectedEventTypes.includes(eventType);
		if (isSelected) {
			onEventTypesChange(
				selectedEventTypes.filter((type) => type !== eventType),
			);
		} else {
			onEventTypesChange([...selectedEventTypes, eventType]);
		}
	};

	const handleClearAll = () => {
		onEventTypesChange([]);
	};

	const renderSelectedEventTypes = () => {
		if (selectedEventTypes.length === 0) {
			return "All event types";
		}

		const visible = selectedEventTypes.slice(0, MAX_EVENT_TYPES_DISPLAYED);
		const extraCount = selectedEventTypes.length - MAX_EVENT_TYPES_DISPLAYED;

		return (
			<div className="flex flex-1 min-w-0 items-center gap-2">
				<div className="flex flex-1 min-w-0 items-center gap-2 overflow-hidden">
					<span className="truncate">{visible.join(", ")}</span>
				</div>
				{extraCount > 0 && (
					<Typography variant="bodySmall" className="shrink-0">
						+ {extraCount}
					</Typography>
				)}
			</div>
		);
	};

	return (
		<Combobox>
			<ComboboxTrigger
				aria-label="Filter by event type"
				selected={selectedEventTypes.length === 0}
			>
				{renderSelectedEventTypes()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search event types..."
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No event types found</ComboboxCommandEmtpy>
					<ComboboxCommandGroup>
						<ComboboxCommandItem
							aria-label="All event types"
							onSelect={handleClearAll}
							closeOnSelect={false}
							value="__all__"
						>
							<Checkbox checked={selectedEventTypes.length === 0} />
							All event types
						</ComboboxCommandItem>
						{filteredOptions.map((eventType) => (
							<ComboboxCommandItem
								key={eventType}
								aria-label={eventType}
								onSelect={() => handleSelectEventType(eventType)}
								closeOnSelect={false}
								value={eventType}
							>
								<Checkbox checked={selectedEventTypes.includes(eventType)} />
								{eventType}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
