import { useMemo, useState } from "react";
import type { Deployment } from "@/api/deployments";
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

type DeploymentComboboxProps = {
	deployments: Deployment[];
	selectedDeploymentIds: string[];
	onSelectDeployments: (deploymentIds: string[]) => void;
};

export const DeploymentCombobox = ({
	deployments,
	selectedDeploymentIds,
	onSelectDeployments,
}: DeploymentComboboxProps) => {
	const [search, setSearch] = useState("");

	const selectedSet = useMemo(
		() => new Set(selectedDeploymentIds),
		[selectedDeploymentIds],
	);

	const filteredDeployments = useMemo(() => {
		if (!search) return deployments;
		const lowerSearch = search.toLowerCase();
		return deployments.filter((deployment) =>
			deployment.name.toLowerCase().includes(lowerSearch),
		);
	}, [deployments, search]);

	const handleSelect = (deploymentId: string) => {
		const updatedSet = new Set(selectedSet);
		if (selectedSet.has(deploymentId)) {
			updatedSet.delete(deploymentId);
		} else {
			updatedSet.add(deploymentId);
		}
		onSelectDeployments(Array.from(updatedSet));
	};

	const getDisplayText = () => {
		if (selectedDeploymentIds.length === 0) {
			return "All deployments";
		}
		if (selectedDeploymentIds.length === 1) {
			const deployment = deployments.find(
				(d) => d.id === selectedDeploymentIds[0],
			);
			return deployment?.name ?? "1 deployment";
		}
		return `${selectedDeploymentIds.length} deployments`;
	};

	return (
		<Combobox>
			<ComboboxTrigger
				aria-label="Filter by deployment"
				selected={selectedDeploymentIds.length === 0}
			>
				{getDisplayText()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					placeholder="Search deployments..."
					value={search}
					onValueChange={setSearch}
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No deployments found</ComboboxCommandEmtpy>
					<ComboboxCommandGroup>
						{filteredDeployments.map((deployment) => (
							<ComboboxCommandItem
								key={deployment.id}
								value={deployment.id}
								onSelect={handleSelect}
								selected={selectedSet.has(deployment.id)}
								closeOnSelect={false}
							>
								{deployment.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
