import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import TicketDetails from "@/components/support/TicketDetails";
import TicketReplyContent from "@/components/support/TicketReplyContent";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ticket Reply | TailAdmin - Next.js Admin Dashboard Template",
  description:
    "This is Ticket Reply for TailAdmin - Next.js Tailwind CSS Admin Dashboard Template",
};

export default function TicketReply() {
  return (
    <div>
      <PageBreadcrumb pageTitle="Ticket Reply" />
      <div className="overflow-hidden xl:h-[calc(100vh-180px)]">
        <div className="grid h-full grid-cols-1 gap-5 xl:grid-cols-12">
          <div className="xl:col-span-8 2xl:col-span-9">
            <TicketReplyContent />
          </div>
          <div className="xl:col-span-4 2xl:col-span-3">
            <TicketDetails />
          </div>
        </div>
      </div>
    </div>
  );
}
