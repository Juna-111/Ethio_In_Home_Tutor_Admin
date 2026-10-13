import React from 'react';
import { BookOpen, Home } from 'lucide-react';

/**
 * Shared MentorLink brand mark.
 * Keep the same recognizable home-and-learning symbol in the header and welcome hero.
 */
export default function BrandMark({ size = 'small', className = '' }) {
  const large = size === 'large';

  return (
    <span
      className={`relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-citrus/45 bg-white/10 shadow-inner ${large ? 'h-16 w-16' : 'h-10 w-10'} ${className}`}
      role="img"
      aria-label="MentorLink"
    >
      <Home
        aria-hidden="true"
        className={large ? 'absolute h-8 w-8 text-citrus' : 'absolute h-5 w-5 text-citrus'}
        strokeWidth={1.8}
      />
      <BookOpen
        aria-hidden="true"
        className={large ? 'absolute h-5 w-5 translate-y-1 text-paper' : 'absolute h-3.5 w-3.5 translate-y-0.5 text-paper'}
        strokeWidth={2.2}
      />
    </span>
  );
}
