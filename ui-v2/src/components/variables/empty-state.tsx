import { ExternalLinkIcon, PlusIcon, VariableIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type VariablesEmptyStateProps = {
	onAddVariableClick: () => void;
};
export const VariablesEmptyState = ({
	onAddVariableClick,
}: VariablesEmptyStateProps) => (
	<Card>
		<CardContent className="flex flex-col gap-2 items-center justify-center py-16">
			<VariableIcon className="h-12 w-12 text-muted-foreground mb-8" />
			<h3 className="text-2xl font-bold">Add a variable to get started</h3>
			<p className="text-md text-muted-foreground">
				Variables store non-sensitive pieces of JSON.
			</p>
			<div className="flex gap-2 mt-4">
				<Button onClick={() => onAddVariableClick()}>
					Add Variable <PlusIcon className="h-4 w-4 ml-2" />
				</Button>
				<a
					href="https://docs.prefect.io/latest/guides/variables/"
					target="_blank"
					rel="noreferrer"
				>
					<Button variant="outline">
						View Docs <ExternalLinkIcon className="h-4 w-4 ml-2" />
					</Button>
				</a>
			</div>
		</CardContent>
	</Card>
);
