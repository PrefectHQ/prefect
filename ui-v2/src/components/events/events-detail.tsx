import { components } from "@/api/prefect";
import { JsonInput } from "@/components/ui/json-input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

export const EventsDetail = ({ event }: { event: components["schemas"]["Event"] }) => {

  return (
    <>
      <Breadcrumb className="mb-4">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink to="/events" className="font-semibold">
              Events
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem className="font-semibold">
            <BreadcrumbPage>{event.event}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      
      <Tabs defaultValue="raw">
        <TabsList>
          <TabsTrigger value="raw">Raw</TabsTrigger>
        </TabsList>
        <TabsContent value="raw">
          <JsonInput value={JSON.stringify(event, null, 2)} disabled />
        </TabsContent>
      </Tabs>
    </>
  );
};
