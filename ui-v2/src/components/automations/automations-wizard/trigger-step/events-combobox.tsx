import { useQuery } from "@tanstack/react-query";
import { endOfHour, subWeeks } from "date-fns";
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

const MAX_VISIBLE_EVENTS = 2;

type EventsComboboxProps = {
	selectedEvents: string[];
	onEventsChange: (events: string[]) => void;
	emptyMessage?: string;
};

function getEventPrefixValues(values: string[]): string[] {
	const prefixes = new Set<string>();

	values.forEach((value) => {
		const parts = value.split(".");

		for (let index = 1; index < parts.length; index++) {
			const prefix = parts.slice(0, index).join(".");
			prefixes.add(prefix);
		}
	});

	return Array.from(prefixes)
		.filter((prefix) => {
			const matches = values.filter((value) =>
				value.startsWith(`${prefix}.`),
			).length;
			return matches > 1 && matches < values.length;
		})
		.map((value) => `${value}.*`);
}

export function EventsCombobox({
	selectedEvents,
	onEventsChange,
	emptyMessage = "All events",
}: EventsComboboxProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const defaultUntil = useMemo(() => endOfHour(new Date()), []);
	const defaultSince = useMemo(() => subWeeks(defaultUntil, 1), [defaultUntil]);

	const { data: eventsData = [] } = useQuery(
		buildEventsCountQuery("event", {
			filter: {
				occurred: {
					since: defaultSince.toISOString(),
					until: defaultUntil.toISOString(),
				},
				order: "DESC",
			},
			time_unit: "day",
			time_interval: 1,
		}),
	);

	const options = useMemo(() => {
		const eventNames = eventsData.map((event) => event.label);
		const prefixes = getEventPrefixValues(eventNames);
		const allEventNames = [...eventNames, ...prefixes].sort((a, b) =>
			a.localeCompare(b),
		);

		return allEventNames.map((event) => ({
			value: event,
			label: event,
		}));
	}, [eventsData]);

	const filteredOptions = useMemo(() => {
		const lowerSearch = deferredSearch.toLowerCase();
		return options.filter((option) =>
			option.label.toLowerCase().includes(lowerSearch),
		);
	}, [options, deferredSearch]);

	const handleEventToggle = (eventName: string) => {
		if (selectedEvents.includes(eventName)) {
			onEventsChange(selectedEvents.filter((e) => e !== eventName));
		} else {
			onEventsChange([...selectedEvents, eventName]);
		}
		setSearch("");
	};

	const handleAddCustomEvent = () => {
		if (search.trim() && !selectedEvents.includes(search.trim())) {
			onEventsChange([...selectedEvents, search.trim()]);
			setSearch("");
		}
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "Enter" && search.trim()) {
			e.preventDefault();
			handleAddCustomEvent();
		}
	};

	const renderSelectedEvents = () => {
		if (selectedEvents.length === 0) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}

		const visibleEvents = selectedEvents.slice(0, MAX_VISIBLE_EVENTS);
		const overflow = selectedEvents.length - visibleEvents.length;

		return (
			<div className="flex min-w-0 items-center justify-start gap-1">
				<span className="truncate min-w-0 text-left">
					{visibleEvents.join(", ")}
				</span>
				{overflow > 0 && (
					<span className="shrink-0 text-muted-foreground">+{overflow}</span>
				)}
			</div>
		);
	};

	const showAddCustomOption =
		search.trim() &&
		!options.some(
			(opt) => opt.value.toLowerCase() === search.trim().toLowerCase(),
		) &&
		!selectedEvents.includes(search.trim());

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
					onKeyDown={handleKeyDown}
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>
						{search.trim() ? (
							<button
								type="button"
								className="w-full text-left px-2 py-1.5 text-sm hover:bg-accent rounded cursor-pointer"
								onClick={handleAddCustomEvent}
							>
								Add &quot;{search.trim()}&quot;
							</button>
						) : (
							"No events found"
						)}
					</ComboboxCommandEmtpy>
					<ComboboxCommandGroup>
						{showAddCustomOption && (
							<ComboboxCommandItem
								key={`add-${search.trim()}`}
								onSelect={handleAddCustomEvent}
								value={`add-custom-${search.trim()}`}
								closeOnSelect={false}
							>
								Add &quot;{search.trim()}&quot;
							</ComboboxCommandItem>
						)}
						{filteredOptions.map((option) => (
							<ComboboxCommandItem
								key={option.value}
								selected={selectedEvents.includes(option.value)}
								onSelect={() => handleEventToggle(option.value)}
								value={option.value}
								closeOnSelect={false}
							>
								{option.label}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
