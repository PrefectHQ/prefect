import { createFileRoute } from "@tanstack/react-router";
import { getQueryHooks } from "@/api/query";
import { readEventsEventsFilterPostBody } from "@/api/zod/events/events";
import { zodValidator } from "@tanstack/zod-adapter";
import { components } from "@/api/prefect";
import { Link } from "@tanstack/react-router";
import { formatISO } from "date-fns";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChevronDownIcon } from "lucide-react";
import * as React from "react";

export const Route = createFileRoute("/events/")({
	component: RouteComponent,
	validateSearch: zodValidator(readEventsEventsFilterPostBody),
	loaderDeps: ({ search }) => search,
	loader: async ({ context, deps }) => {
		return await Promise.all([
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/events/filter", {
					// Note: There's a type mismatch between deps and the API schema.
					// The API expects 'resource.distinct' to be a required boolean, but our schema defines it as optional.
					// This is an idiosyncrasy between orval and openapi-ts but is fine for now.
					body: deps as components["schemas"]["Body_read_events_events_filter_post"]
				})),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/events/count-by/{countable}", {
					params: {
						path: { countable: "event" }
					},
					body: {
						filter: {
							order: "DESC",
						},
						time_unit: "week",
						time_interval: 1
					}
				})
			),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/flows/filter", {
					body: { offset: 0, sort: "CREATED_DESC" }
				})
			),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/work_pools/filter", {
					body: { offset: 0, sort: "CREATED_DESC" }
				})
			),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/deployments/filter", {
					body: { offset: 0, sort: "CREATED_DESC" }
				})
			),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/block_documents/filter", {
					body: { offset: 0, sort: "NAME_ASC", include_secrets: false }
				})
			),
			context.queryClient.ensureQueryData(
				getQueryHooks().queryOptions("post", "/automations/filter", {
					body: { offset: 0, sort: "CREATED_DESC" }
				})
			),
		])
	},
});

function ResourceCheckboxItem({
	resourceType,
	resourceId,
}: {
	resourceType: string;
	resourceId: string;
	checked?: boolean;
}) {
	const { filter } = Route.useSearch();
	const navigate = Route.useNavigate();
	return (
		<DropdownMenuCheckboxItem
			key={resourceId}
			onSelect={(e) => e.preventDefault()}
			checked={filter?.any_resource?.id?.map(item => item.includes(resourceId)).includes(true)}
			onCheckedChange={(checked) => {navigate({
				to: "/events",
				search: (prev) => {		
					
					return {
						...prev,
						filter: {
							...prev.filter,
							any_resource: {'id': checked ? [...(prev?.filter?.any_resource?.id || []), resourceId] : prev?.filter?.any_resource?.id?.filter(item => item !== resourceId)
			}}}}})}}
		>
			{resourceType}
		</DropdownMenuCheckboxItem>
	);
}

function EventTypeCheckboxItem({
	eventType,
}: {
	eventType: string;
	count?: number;
}) {
	const { filter } = Route.useSearch();
	const navigate = Route.useNavigate();
	const isChecked = filter?.event === eventType;
	
	return (
		<DropdownMenuCheckboxItem
			key={eventType}
			onSelect={(e) => e.preventDefault()}
			checked={isChecked}
			onCheckedChange={(checked) => {
				navigate({
					to: "/events",
					search: (prev) => {
						return {
							...prev,
							filter: {
								...prev.filter,
								event: checked ? eventType : undefined
							}
						}
					},
					replace: true
				})
			}}
		>
			{eventType}
		</DropdownMenuCheckboxItem>
	);
}

function RouteComponent() {
	const [ events, eventGroupCounts, flows, workPools, deployments, blockDocuments, automations ]= Route.useLoaderData();
	const search = Route.useSearch();
	const navigate = Route.useNavigate();
	
	// Get selected resources from search params
	const resourceFilter = search.filter?.resource || {};
	const resourceIds = resourceFilter.id || [];
	const resourceArray = Array.isArray(resourceIds) ? resourceIds : [resourceIds];
	

	const countSelected = () => {
		return resourceArray.length > 0 ? `${resourceArray.length} selected` : "Filter by resource";
	};
	
	
	return (
		<ul>
			<div className="flex space-x-4 mb-4">
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button variant="outline" className="w-[280px] justify-between">
							{countSelected()}
							<ChevronDownIcon className="ml-2 h-4 w-4" />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent className="w-[280px]">
						{automations.length > 0 && (
							<>
								<DropdownMenuLabel>Automations</DropdownMenuLabel>
								<DropdownMenuGroup>
									{automations.map((automation) => (
										<ResourceCheckboxItem
											key={automation.id}
											resourceType={automation.name}
											resourceId={'prefect.automation.' + automation.id}
										/>
									))}
								</DropdownMenuGroup>
								<DropdownMenuSeparator />
							</>
						)}
						{blockDocuments.length > 0 && (
							<>
								<DropdownMenuLabel>Blocks</DropdownMenuLabel>
								<DropdownMenuGroup>
									{blockDocuments.map((blockDocument) => (
										<ResourceCheckboxItem
											key={blockDocument.id}
											resourceType={blockDocument.name || 'Unnamed Block'}
											resourceId={'prefect.block_document.' + blockDocument.id}
										/>
									))}
								</DropdownMenuGroup>
								<DropdownMenuSeparator />
							</>
						)}
						{deployments.length > 0 && (
							<>
								<DropdownMenuLabel>Deployments</DropdownMenuLabel>
								<DropdownMenuGroup>
									{deployments.map((deployment) => (
										<ResourceCheckboxItem
											key={deployment.id}
											resourceType={deployment.name}
											resourceId={'prefect.deployment.' + deployment.id}
										/>
									))}
								</DropdownMenuGroup>
								<DropdownMenuSeparator />
							</>
						)}
						{flows.length > 0 && (
							<>
								<DropdownMenuLabel>Flows</DropdownMenuLabel>
								<DropdownMenuGroup>
									{flows.map((flow) => (
										<ResourceCheckboxItem
											key={flow.id}
											resourceType={flow.name}
											resourceId={'prefect.flow.' + flow.id}
										/>
									))}
								</DropdownMenuGroup>
								<DropdownMenuSeparator />
							</>
						)}
						{workPools.length > 0 && (
							<>
								<DropdownMenuLabel>Work Pools</DropdownMenuLabel>
								<DropdownMenuGroup>
									{workPools.map((workPool) => (
										<ResourceCheckboxItem
											key={workPool.id}
											resourceType={workPool.name}
											resourceId={'prefect.work_pool.' + workPool.id}
										/>
									))}
								</DropdownMenuGroup>
							</>
						)}
					</DropdownMenuContent>
				</DropdownMenu>
				
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button variant="outline" className="w-[280px] justify-between">
							{"Filter by event type"}
							<ChevronDownIcon className="ml-2 h-4 w-4" />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent className="w-[280px]">
						<DropdownMenuLabel>Event Types</DropdownMenuLabel>
						{eventGroupCounts.map((label, index) => (
							<DropdownMenuCheckboxItem 
								key={index}
								onSelect={(e) => e.preventDefault()}
								checked={search.filter?.event?.name?.includes(label.label)}
								onCheckedChange={(checked) => {
									navigate({
										to: "/events",
										search: (prev) => {
											return {
												...prev,
												filter: {
													...prev.filter,
													event: {
														"name": checked ? [...(prev?.filter?.event?.name || []), label.label] : prev?.filter?.event?.name?.filter(item => item !== label.label)
													}
												}
											}
										},
										replace: true
									})
								}}
								>{label.label}</DropdownMenuCheckboxItem>
						
						))}
					</DropdownMenuContent>
				</DropdownMenu>
			</div>

			{events.events.map((event) => {
				const eventDate = new Date(event.occurred);
				return (
					<li key={event.id}>
						<Link
							to="/events/event/$date/$eventId"
							params={{
								date: formatISO(eventDate, {'representation': 'date'}),
								eventId: event.id
							}}
						>
							{event.event}
							{event.resource?.['prefect.resource.name']}
						</Link>
					</li>
				);
			})}
		</ul>
	);
}