import React from 'react';

interface SectionSkeletonProps {
  heading: string;
  icon: string;
}

/**
 * Loading skeleton for a brief section — shows heading with animated placeholder lines.
 */
const SectionSkeleton: React.FC<SectionSkeletonProps> = ({ heading, icon }) => {
  return (
    <div className="px-8 py-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-base opacity-20">{icon}</span>
        <span className="text-sm font-bold text-gray-200">{heading}</span>
        <div className="flex-1 h-px bg-gray-100 ml-2" />
      </div>
      <div className="space-y-2.5">
        <div className="h-3 rounded-md bg-gray-100 animate-pulse w-full" />
        <div className="h-3 rounded-md bg-gray-100 animate-pulse w-11/12" />
        <div className="h-3 rounded-md bg-gray-100 animate-pulse w-4/6" />
      </div>
    </div>
  );
};

export default SectionSkeleton;
