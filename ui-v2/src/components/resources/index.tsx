import { components } from "@/api/prefect";

export const ResourceCard = ({ resource }: { resource: components["schemas"]["Resource"] }) => {
    return (
        <div>
            'lol'
            <h2>{resource.name}</h2>
        </div>
    )
}