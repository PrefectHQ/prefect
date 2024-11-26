import {
	Workflow,
	MoreHorizontal,
	ExternalLinkIcon,
	Rocket,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export const DeploymentsEmptyState = () => (
	<Card>
		<CardContent className="flex flex-col gap-2 items-center justify-center py-16">
			<div className="flex items-center gap-3 text-muted-foreground mb-6">
				<Workflow className="h-12 w-12" />
				<MoreHorizontal className="h-12 w-12" />
				<Rocket className="h-12 w-12" />
			</div>

			<h3 className="text-2xl font-semibold mb-2">
				Create a deployment to get started
			</h3>

			<p className="text-md text-muted-foreground">
				Deployments elevate workflows from functions you call manually to API
				objects that can be remotely triggered.
			</p>

			<div className="flex gap-2 mt-4">
				<a
					href="https://docs.prefect.io/latest/get-started/quickstart"
					target="_blank"
					rel="noreferrer"
				>
					<Button variant="outline" className="gap-1">
						View Docs
						<ExternalLinkIcon className="h-4 w-4 ml-2" />
					</Button>
				</a>
			</div>
		</CardContent>
	</Card>
);
