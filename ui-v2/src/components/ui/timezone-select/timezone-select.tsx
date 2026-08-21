import { useVirtualizer } from "@tanstack/react-virtual";
import { useDeferredValue, useMemo, useState } from "react";
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
	DropdownMenuLabel,
	DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

function getTimezoneLabel(value: string): string {
	return value.replaceAll("/", " / ").replaceAll("_", " ");
}

const UTC_ALIASES = new Set([
	"UTC",
	"Etc/UTC",
	"Etc/UCT",
	"Etc/Universal",
	"Etc/Zulu",
	"Etc/GMT",
	"Etc/GMT+0",
	"Etc/GMT-0",
	"Etc/GMT0",
	"Etc/Greenwich",
]);

function isUTCAlias(timezone: string): boolean {
	return UTC_ALIASES.has(timezone);
}

function normalizeTimezone(timezone: string): string;
function normalizeTimezone(
	timezone: string | undefined | null,
): string | undefined | null;
function normalizeTimezone(
	timezone: string | undefined | null,
): string | undefined | null {
	if (!timezone) {
		return timezone;
	}
	return isUTCAlias(timezone) ? "UTC" : timezone;
}

const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
const normalizedLocalTimezone = normalizeTimezone(localTimezone);

const SUGGESTED_TIMEZONES = [
	{ label: "UTC", value: "UTC" },
	...(normalizedLocalTimezone !== "UTC"
		? [
				{
					label: getTimezoneLabel(localTimezone),
					value: normalizedLocalTimezone,
				},
			]
		: []),
];

const TIMEZONES = Intl.supportedValuesOf("timeZone")
	.filter(
		(timezone) =>
			normalizeTimezone(timezone) !== "UTC" &&
			timezone !== normalizedLocalTimezone,
	)
	.map((timezone) => ({
		label: getTimezoneLabel(timezone),
		value: timezone,
	}));

const ALL_TIMEZONES = [...SUGGESTED_TIMEZONES, ...TIMEZONES];

// Matches the height of a `ComboboxCommandItem`
const OPTION_HEIGHT = 32;

type TimezoneSelectProps = {
	selectedValue: string | undefined | null;
	onSelect: (value: string) => void;
};

export const TimezoneSelect = ({
	selectedValue = "",
	onSelect,
}: TimezoneSelectProps) => {
	const [search, setSearch] = useState("");
	// State rather than a ref so the virtualizer measures the list once the
	// combobox's content is mounted
	const [listElement, setListElement] = useState<HTMLDivElement | null>(null);

	const deferredSearch = useDeferredValue(search);
	const normalizedSelectedValue = normalizeTimezone(selectedValue);

	const filteredSuggestedTimezones = useMemo(() => {
		return SUGGESTED_TIMEZONES.filter(
			(timeZone) =>
				timeZone.label.toLowerCase().includes(deferredSearch.toLowerCase()) ||
				timeZone.value.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [deferredSearch]);

	const filteredTimezones = useMemo(() => {
		return TIMEZONES.filter(
			(timeZone) =>
				timeZone.label.toLowerCase().includes(deferredSearch.toLowerCase()) ||
				timeZone.value.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [deferredSearch]);

	// There are several hundred timezones, so only render the visible ones
	const virtualizer = useVirtualizer({
		count: filteredTimezones.length,
		getScrollElement: () => listElement,
		estimateSize: () => OPTION_HEIGHT,
		overscan: 10,
		getItemKey: (index) => filteredTimezones[index].value,
	});

	const selectedLabel = useMemo(() => {
		if (!normalizedSelectedValue) {
			return undefined;
		}
		return (
			ALL_TIMEZONES.find(({ value }) => value === normalizedSelectedValue)
				?.label ?? getTimezoneLabel(normalizedSelectedValue)
		);
	}, [normalizedSelectedValue]);

	return (
		<Combobox>
			<ComboboxTrigger
				selected={Boolean(normalizedSelectedValue)}
				aria-label="Select timezone"
			>
				{selectedLabel ?? "Select timezone"}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search"
				/>
				<ComboboxCommandEmtpy>No timezone found</ComboboxCommandEmtpy>
				<ComboboxCommandList ref={setListElement}>
					<ComboboxCommandGroup>
						{filteredSuggestedTimezones.length > 0 && (
							<DropdownMenuLabel>Suggested timezones</DropdownMenuLabel>
						)}
						{filteredSuggestedTimezones.map(({ label, value }) => {
							return (
								<ComboboxCommandItem
									key={value}
									selected={normalizedSelectedValue === value}
									onSelect={(value) => {
										onSelect(value);
										setSearch("");
									}}
									value={value}
								>
									{label}
								</ComboboxCommandItem>
							);
						})}
						<DropdownMenuSeparator />
						{filteredTimezones.length > 0 && (
							<DropdownMenuLabel>All timezones</DropdownMenuLabel>
						)}
						<div
							className="relative"
							style={{ height: `${virtualizer.getTotalSize()}px` }}
						>
							{virtualizer.getVirtualItems().map((virtualOption) => {
								const { label, value } = filteredTimezones[virtualOption.index];
								return (
									<div
										key={value}
										data-index={virtualOption.index}
										// Options with long labels wrap on narrow triggers, so
										// measure rather than assume every option's height
										ref={virtualizer.measureElement}
										className="absolute inset-x-0 top-0"
										style={{
											transform: `translateY(${virtualOption.start}px)`,
										}}
									>
										<ComboboxCommandItem
											selected={normalizedSelectedValue === value}
											onSelect={(value) => {
												onSelect(value);
												setSearch("");
											}}
											value={value}
										>
											{label}
										</ComboboxCommandItem>
									</div>
								);
							})}
						</div>
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
