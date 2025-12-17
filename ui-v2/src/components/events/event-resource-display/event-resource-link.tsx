import { Link } from "@tanstack/react-router";
import type { components } from "@/api/prefect";
import { getResourceRoute } from "./resource-routes";

type RelatedResource = components["schemas"]["RelatedResource"];

type EventResourceLinkProps = {
	resource: RelatedResource;
	relatedResources?: RelatedResource[];
	children: React.ReactNode;
	className?: string;
};

export function EventResourceLink({
	resource,
	relatedResources = [],
	children,
	className,
}: EventResourceLinkProps) {
	const routeConfig = getResourceRoute(resource, relatedResources);

	if (!routeConfig) {
		return <span className={className}>{children}</span>;
	}

	return (
		<Link to={routeConfig.to} params={routeConfig.params} className={className}>
			{children}
		</Link>
	);
}
