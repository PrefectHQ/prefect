import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { buildEventsCountQuery } from "@/api/events";
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

export type EventsComboboxProps = {
	selectedEvents: string[];
	onToggleEvent: (event: string) => void;
	emptyMessage?: string;
};

/**
 * Generate wildcard prefix options from event names.
 * E.g., ["prefect.flow-run.Completed", "prefect.flow-run.Failed"]
 * generates ["prefect.*", "prefect.flow-run.*"]
 *
 * Only includes prefixes that match more than one event but not all events.
 */
function getEventPrefixValues(events: string[]): string[] {
	const prefixCounts = new Map<string, number>();

	for (const event of events) {
		const parts = event.split(".");
		for (let i = 1; i < parts.length; i++) {
			const prefix = parts.slice(0, i).join(".");
			prefixCounts.set(prefix, (prefixCounts.get(prefix) ?? 0) + 1);
		}
	}

	return Array.from(prefixCounts.entries())
		.filter(([, count]) => count > 1 && count < events.length)
		.map(([prefix]) => `${prefix}.*`);
}

export function EventsCombobox({
	selectedEvents,
	onToggleEvent,
	emptyMessage = "All events",
}: EventsComboboxProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	// Create a stable filter for the past week (computed once on mount)
	const [occurredFilter] = useState(() => ({
		since: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
		until: new Date().toISOString(),
	}));

	// Fetch event counts for the past week
	const { data: eventCounts = [] } = useQuery(
		buildEventsCountQuery("event", {
			filter: {
				occurred: occurredFilter,
				order: "DESC",
			},
			time_unit: "day",
			time_interval: 1,
		}),
	);

	// Extract event labels and generate prefix options
	const options = useMemo(() => {
		const eventLabels = eventCounts.map((e) => e.label);
		const prefixes = getEventPrefixValues(eventLabels);
		return [...eventLabels, ...prefixes].sort((a, b) => a.localeCompare(b));
	}, [eventCounts]);

	// Filter options based on search
	const filteredOptions = useMemo(() => {
		if (!deferredSearch) return options;
		const lower = deferredSearch.toLowerCase();
		return options.filter((opt) => opt.toLowerCase().includes(lower));
	}, [options, deferredSearch]);

	// Check if search term is a valid custom value
	const showCustomOption = useMemo(() => {
		if (!deferredSearch.trim()) return false;
		const lower = deferredSearch.toLowerCase();
		return !options.some((opt) => opt.toLowerCase() === lower);
	}, [deferredSearch, options]);

	const renderSelectedEvents = () => {
		if (selectedEvents.length === 0) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}
		const visibleNames = selectedEvents.slice(0, 2);
		const overflow = selectedEvents.length - visibleNames.length;
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

	const handleSelect = (value: string) => {
		onToggleEvent(value);
		setSearch("");
	};

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedEvents.length > 0}>
				{renderSelectedEvents()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search events..."
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No events found</ComboboxCommandEmtpy>
					<ComboboxCommandGroup>
						{showCustomOption && (
							<ComboboxCommandItem
								key="__custom__"
								selected={selectedEvents.includes(deferredSearch)}
								onSelect={() => handleSelect(deferredSearch)}
								closeOnSelect={false}
								value={deferredSearch}
							>
								Add &quot;{deferredSearch}&quot;
							</ComboboxCommandItem>
						)}
						{filteredOptions.map((event) => (
							<ComboboxCommandItem
								key={event}
								selected={selectedEvents.includes(event)}
								onSelect={() => handleSelect(event)}
								closeOnSelect={false}
								value={event}
							>
								{event}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
