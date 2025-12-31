import { useQuery } from "@tanstack/react-query";
import {
	useCallback,
	useDeferredValue,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import {
	buildFilterDeploymentsQuery,
	type Deployment,
} from "@/api/deployments";
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

const FALLBACK_MAX_DISPLAYED = 2;
const PLUS_N_WIDTH = 40;

type AutomationDeploymentComboboxProps = {
	selectedDeploymentIds: string[];
	onSelectDeploymentIds: (deploymentIds: string[]) => void;
};

export const AutomationDeploymentCombobox = ({
	selectedDeploymentIds,
	onSelectDeploymentIds,
}: AutomationDeploymentComboboxProps) => {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);
	const [containerWidth, setContainerWidth] = useState(0);
	const containerRef = useRef<HTMLDivElement>(null);
	const measureRef = useRef<HTMLDivElement>(null);

	const selectedDeploymentsSet = useMemo(
		() => new Set(selectedDeploymentIds),
		[selectedDeploymentIds],
	);

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

	const { data: deployments = [] } = useQuery(
		buildFilterDeploymentsQuery({
			deployments: deferredSearch
				? {
						operator: "and_",
						name: { like_: deferredSearch },
					}
				: undefined,
			limit: 100,
			offset: 0,
			sort: "NAME_ASC",
		}),
	);

	const { data: selectedDeploymentsData = [] } = useQuery(
		buildFilterDeploymentsQuery(
			{
				deployments:
					selectedDeploymentsSet.size > 0
						? {
								operator: "and_",
								id: { any_: selectedDeploymentIds },
							}
						: undefined,
				limit: selectedDeploymentsSet.size || 1,
				offset: 0,
				sort: "NAME_ASC",
			},
			{ enabled: selectedDeploymentsSet.size > 0 },
		),
	);

	const handleSelectDeployment = (deploymentId: string) => {
		const updatedDeployments = new Set(selectedDeploymentsSet);
		if (selectedDeploymentsSet.has(deploymentId)) {
			updatedDeployments.delete(deploymentId);
		} else {
			updatedDeployments.add(deploymentId);
		}
		onSelectDeploymentIds(Array.from(updatedDeployments));
	};

	const handleClearAll = () => {
		onSelectDeploymentIds([]);
	};

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

	const renderSelectedDeployments = () => {
		if (selectedDeploymentsSet.size === 0) {
			return "All deployments";
		}

		const selectedDeploymentNames = selectedDeploymentsData
			.filter((deployment) => selectedDeploymentsSet.has(deployment.id))
			.map((deployment) => deployment.name);

		const visibleCount = calculateVisibleCount(selectedDeploymentNames);
		const visible = selectedDeploymentNames.slice(0, visibleCount);
		const extraCount = selectedDeploymentNames.length - visibleCount;

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

	const filteredDeployments = useMemo(() => {
		return deployments.filter(
			(deployment: Deployment) =>
				!deferredSearch ||
				deployment.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [deployments, deferredSearch]);

	return (
		<Combobox>
			<ComboboxTrigger
				aria-label="Select deployments"
				selected={selectedDeploymentsSet.size === 0}
			>
				{renderSelectedDeployments()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search deployments..."
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No deployments found</ComboboxCommandEmtpy>
					<ComboboxCommandGroup>
						<ComboboxCommandItem
							aria-label="All deployments"
							onSelect={handleClearAll}
							closeOnSelect={false}
							value="__all__"
						>
							<Checkbox checked={selectedDeploymentsSet.size === 0} />
							All deployments
						</ComboboxCommandItem>
						{filteredDeployments.map((deployment: Deployment) => (
							<ComboboxCommandItem
								key={deployment.id}
								aria-label={deployment.name}
								onSelect={() => handleSelectDeployment(deployment.id)}
								closeOnSelect={false}
								value={deployment.id}
							>
								<Checkbox checked={selectedDeploymentsSet.has(deployment.id)} />
								{deployment.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
