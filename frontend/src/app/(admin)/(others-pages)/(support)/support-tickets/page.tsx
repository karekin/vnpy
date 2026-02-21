import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import SupportTicketsList from "@/components/support/SupportList";
import SupportMetrics from "@/components/support/SupportMetrics";
import { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "Support Tickets | TailAdmin - Next.js Admin Dashboard Template",
  description:
    "This is Support Tickets for TailAdmin - Next.js Tailwind CSS Admin Dashboard Template",
};

export default function SupportTicketsPage() {
  return (
    <div>
      <PageBreadcrumb pageTitle="Support Tickets" />
      <SupportMetrics />
      <SupportTicketsList />
    </div>
  );
}
