import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
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

const MAX_DEPLOYMENTS_DISPLAYED = 2;

type DeploymentFilterProps = {
	selectedDeployments: Set<string>;
	onSelectDeployments: (deployments: Set<string>) => void;
};

export const DeploymentFilter = ({
	selectedDeployments,
	onSelectDeployments,
}: DeploymentFilterProps) => {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

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
					selectedDeployments.size > 0
						? {
								operator: "and_",
								id: { any_: Array.from(selectedDeployments) },
							}
						: undefined,
				limit: selectedDeployments.size || 1,
				offset: 0,
				sort: "NAME_ASC",
			},
			{ enabled: selectedDeployments.size > 0 },
		),
	);

	const handleSelectDeployment = (deploymentId: string) => {
		const updatedDeployments = new Set(selectedDeployments);
		if (selectedDeployments.has(deploymentId)) {
			updatedDeployments.delete(deploymentId);
		} else {
			updatedDeployments.add(deploymentId);
		}
		onSelectDeployments(updatedDeployments);
	};

	const handleClearAll = () => {
		onSelectDeployments(new Set());
	};

	const renderSelectedDeployments = () => {
		if (selectedDeployments.size === 0) {
			return "All deployments";
		}

		const selectedDeploymentNames = selectedDeploymentsData
			.filter((deployment) => selectedDeployments.has(deployment.id))
			.map((deployment) => deployment.name);

		const visible = selectedDeploymentNames.slice(0, MAX_DEPLOYMENTS_DISPLAYED);
		const extraCount =
			selectedDeploymentNames.length - MAX_DEPLOYMENTS_DISPLAYED;

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
				aria-label="Filter by deployment"
				selected={selectedDeployments.size === 0}
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
							<Checkbox checked={selectedDeployments.size === 0} />
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
								<Checkbox checked={selectedDeployments.has(deployment.id)} />
								{deployment.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
