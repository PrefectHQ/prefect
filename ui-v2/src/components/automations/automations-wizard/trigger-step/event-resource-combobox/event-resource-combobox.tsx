import {
	useCallback,
	useDeferredValue,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { useResourceOptions } from "@/components/events/events-resource-filter/use-resource-options";
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

const FALLBACK_MAX_DISPLAYED = 2;
const PLUS_N_WIDTH = 40;

export type EventResourceComboboxProps = {
	selectedResourceIds: string[];
	onToggleResource: (resourceId: string) => void;
	emptyMessage?: string;
};

type ResourceGroup = {
	label: string;
	options: Array<{ label: string; value: string }>;
};

export function EventResourceCombobox({
	selectedResourceIds,
	onToggleResource,
	emptyMessage = "All resources",
}: EventResourceComboboxProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);
	const [containerWidth, setContainerWidth] = useState(0);
	const containerRef = useRef<HTMLDivElement>(null);
	const measureRef = useRef<HTMLDivElement>(null);

	// Measure container width using ResizeObserver
	useEffect(() => {
		const container = containerRef.current;
		if (!container) return;

		const observer = new ResizeObserver((entries) => {
			for (const entry of entries) {
				setContainerWidth(entry.contentRect.width);
			}
		});

		observer.observe(container);
		return () => observer.disconnect();
	}, []);

	// Use existing hook that fetches all resource types
	const { resourceOptions } = useResourceOptions();

	// Group resources by type
	const groupedResources = useMemo(() => {
		const groups: ResourceGroup[] = [
			{ label: "Automations", options: [] },
			{ label: "Blocks", options: [] },
			{ label: "Deployments", options: [] },
			{ label: "Flows", options: [] },
			{ label: "Work Pools", options: [] },
			{ label: "Work Queues", options: [] },
		];

		for (const resource of resourceOptions) {
			const option = {
				label: resource.name,
				value: resource.resourceId,
			};

			switch (resource.type) {
				case "automation":
					groups[0].options.push(option);
					break;
				case "block":
					groups[1].options.push(option);
					break;
				case "deployment":
					groups[2].options.push(option);
					break;
				case "flow":
					groups[3].options.push(option);
					break;
				case "work-pool":
					groups[4].options.push(option);
					break;
				case "work-queue":
					groups[5].options.push(option);
					break;
			}
		}

		return groups
			.map((group) => ({
				...group,
				options: group.options.sort((a, b) => a.label.localeCompare(b.label)),
			}))
			.filter((group) => group.options.length > 0);
	}, [resourceOptions]);

	// Filter based on search
	const filteredGroups = useMemo(() => {
		if (!deferredSearch) return groupedResources;
		const lower = deferredSearch.toLowerCase();
		return groupedResources
			.map((group) => ({
				...group,
				options: group.options.filter(
					(opt) =>
						opt.label.toLowerCase().includes(lower) ||
						opt.value.toLowerCase().includes(lower),
				),
			}))
			.filter((group) => group.options.length > 0);
	}, [groupedResources, deferredSearch]);

	// Check if search term could be a custom resource ID (must contain ".")
	const showCustomOption = useMemo(() => {
		if (!deferredSearch.trim()) return false;
		if (!deferredSearch.includes(".")) return false;
		const lower = deferredSearch.toLowerCase();
		return !resourceOptions.some(
			(opt) => opt.resourceId.toLowerCase() === lower,
		);
	}, [deferredSearch, resourceOptions]);

	// Calculate how many names fit in the available width
	const calculateVisibleCount = useCallback(
		(names: string[]): number => {
			const measureEl = measureRef.current;
			if (!measureEl || containerWidth === 0 || names.length === 0) {
				return Math.min(names.length, FALLBACK_MAX_DISPLAYED);
			}

			// Available width for names (reserve space for "+N" if needed)
			const availableWidth =
				names.length > 1 ? containerWidth - PLUS_N_WIDTH : containerWidth;

			let visibleCount = 0;

			for (let i = 0; i < names.length; i++) {
				// Measure each name by temporarily setting content
				measureEl.textContent = names.slice(0, i + 1).join(", ");
				const nameWidth = measureEl.offsetWidth;

				if (nameWidth <= availableWidth) {
					visibleCount = i + 1;
				} else {
					break;
				}
			}

			// If all names fit, return all
			if (visibleCount === names.length) {
				return names.length;
			}

			// Return at least 1 name
			return Math.max(1, visibleCount);
		},
		[containerWidth],
	);

	const renderSelectedResources = () => {
		if (selectedResourceIds.length === 0) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}
		const selectedNames = selectedResourceIds.map((id) => {
			const resource = resourceOptions.find((r) => r.resourceId === id);
			return resource?.name ?? id;
		});

		const visibleCount = calculateVisibleCount(selectedNames);
		const visible = selectedNames.slice(0, visibleCount);
		const extraCount = selectedNames.length - visibleCount;

		return (
			<div
				ref={containerRef}
				className="flex flex-1 min-w-0 items-center gap-2"
			>
				<div className="flex flex-1 min-w-0 items-center gap-2 overflow-hidden">
					<span className="truncate">{visible.join(", ")}</span>
				</div>
				{extraCount > 0 && (
					<Typography variant="bodySmall" className="shrink-0">
						+ {extraCount}
					</Typography>
				)}
				{/* Hidden element for measuring text width */}
				<div
					ref={measureRef}
					className="absolute invisible whitespace-nowrap"
					aria-hidden="true"
				/>
			</div>
		);
	};

	const handleSelect = (value: string) => {
		onToggleResource(value);
		setSearch("");
	};

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedResourceIds.length > 0}>
				{renderSelectedResources()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search resources..."
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No resources found</ComboboxCommandEmtpy>
					{showCustomOption && (
						<ComboboxCommandGroup>
							<ComboboxCommandItem
								key="__custom__"
								selected={selectedResourceIds.includes(deferredSearch)}
								onSelect={() => handleSelect(deferredSearch)}
								closeOnSelect={false}
								value={deferredSearch}
							>
								Add &quot;{deferredSearch}&quot;
							</ComboboxCommandItem>
						</ComboboxCommandGroup>
					)}
					{filteredGroups.map((group) => (
						<ComboboxCommandGroup key={group.label} heading={group.label}>
							{group.options.map((option) => (
								<ComboboxCommandItem
									key={option.value}
									selected={selectedResourceIds.includes(option.value)}
									onSelect={() => handleSelect(option.value)}
									closeOnSelect={false}
									value={option.value}
								>
									{option.label}
								</ComboboxCommandItem>
							))}
						</ComboboxCommandGroup>
					))}
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
