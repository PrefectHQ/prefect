import { useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";
import { type Automation, buildListAutomationsQuery } from "@/api/automations";
import type { components } from "@/api/prefect";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Card } from "@/components/ui/card";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { SearchInput } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { pluralize } from "@/utils";
import {
	AutomationActions,
	AutomationDescription,
	AutomationTrigger,
} from "./automation-details";
import { AutomationEnableToggle } from "./automation-enable-toggle";
import { AutomationsActionsMenu } from "./automations-actions-menu";
import { AutomationsEmptyState } from "./automations-empty-state";
import { AutomationsHeader } from "./automations-header";
import { useDeleteAutomationConfirmationDialog } from "./use-delete-automation-confirmation-dialog";

type AutomationSort = components["schemas"]["AutomationSort"] | "ENABLED_DESC";

export const AutomationsPage = () => {
	const [search, setSearch] = useState("");
	const [sort, setSort] = useState<AutomationSort>("ENABLED_DESC");
	const [dialogState, confirmDelete] = useDeleteAutomationConfirmationDialog();
	const { data } = useSuspenseQuery(
		buildListAutomationsQuery({
			sort: sort === "ENABLED_DESC" ? "CREATED_DESC" : sort,
			offset: 0,
		}),
	);
	const filteredAutomations = data
		.filter((automation) =>
			automation.name.toLowerCase().includes(search.trim().toLowerCase()),
		)
		.sort((a, b) =>
			sort === "ENABLED_DESC" ? Number(b.enabled) - Number(a.enabled) : 0,
		);

	const handleDelete = (automation: Automation) => confirmDelete(automation);

	return (
		<>
			<div className="flex flex-col gap-4">
				<AutomationsHeader />
				{data.length === 0 ? (
					<AutomationsEmptyState />
				) : (
					<div className="flex flex-col gap-4">
						<div className="flex flex-wrap items-center justify-between gap-2">
							<p className="text-sm text-muted-foreground">
								{filteredAutomations.length.toLocaleString()}{" "}
								{pluralize(filteredAutomations.length, "automation")}
							</p>
							<div className="flex flex-wrap items-center gap-2">
								<div className="min-w-56">
									<SearchInput
										aria-label="Search automations by name"
										placeholder="Search by name"
										type="search"
										value={search}
										onChange={(event) => setSearch(event.target.value)}
									/>
								</div>
								<Select
									value={sort}
									onValueChange={(value) => setSort(value as AutomationSort)}
								>
									<SelectTrigger aria-label="Automation sort order">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="ENABLED_DESC">Enabled first</SelectItem>
										<SelectItem value="CREATED_DESC">Newest created</SelectItem>
										<SelectItem value="UPDATED_DESC">
											Recently updated
										</SelectItem>
										<SelectItem value="NAME_ASC">Name: A to Z</SelectItem>
										<SelectItem value="NAME_DESC">Name: Z to A</SelectItem>
									</SelectContent>
								</Select>
							</div>
						</div>
						<ul className="flex flex-col gap-2">
							{filteredAutomations.map((automation) => (
								<li
									key={automation.id}
									aria-label={`automation item ${automation.name}`}
								>
									<AutomationCardDetails
										automation={automation}
										onDelete={() => handleDelete(automation)}
									/>
								</li>
							))}
						</ul>
					</div>
				)}
			</div>
			<DeleteConfirmationDialog {...dialogState} />
		</>
	);
};

type AutomationCardDetailsProps = {
	automation: Automation;
	onDelete: () => void;
};
const AutomationCardDetails = ({
	automation,
	onDelete,
}: AutomationCardDetailsProps) => {
	return (
		<Card className="p-4 pt-5 flex flex-col gap-6">
			<div className="flex items-center justify-between min-w-0 overflow-hidden">
				<NavHeader automation={automation} />
				<div className="flex items-center gap-2">
					<AutomationEnableToggle automation={automation} />
					<AutomationsActionsMenu id={automation.id} onDelete={onDelete} />
				</div>
			</div>
			<div className="flex flex-col gap-4">
				{automation.description && (
					<AutomationDescription automation={automation} />
				)}
				<AutomationTrigger automation={automation} />
				<AutomationActions automation={automation} />
			</div>
		</Card>
	);
};

type NavHeaderProps = {
	automation: Automation;
};

const NavHeader = ({ automation }: NavHeaderProps) => {
	return (
		<Breadcrumb className="min-w-0">
			<BreadcrumbList className="flex-nowrap min-w-0 overflow-hidden">
				<BreadcrumbItem className="text-xl min-w-0">
					<BreadcrumbLink
						to="/automations/automation/$id"
						params={{ id: automation.id }}
						className="text-lg text-foreground truncate block"
						title={automation.name}
					>
						{automation.name}
					</BreadcrumbLink>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};
