"use client";

import Image from "next/image";
import Link from "next/link";

type BrandLogoProps = {
  compact?: boolean;
  className?: string;
};

const BrandLogo = ({ compact = false, className = "" }: BrandLogoProps) => {
  const sizeClass = compact ? "h-10 w-10" : "h-12 w-12";

  return (
    <Link
      href="/tenx-hunter/us"
      aria-label="繁花 Stock Rose"
      className={`inline-flex items-center ${className}`}
    >
      <Image
        src="/images/logo/stock-rose-logo.png"
        alt=""
        width={1254}
        height={1254}
        className={`${sizeClass} object-contain`}
        priority
      />
    </Link>
  );
};

export default BrandLogo;
