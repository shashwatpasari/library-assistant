import React from 'react';
import { Rating } from '@mui/material';
import { cn } from '../lib/utils';

export function StarRating({ rating, className }) {
  const numRating = rating ? parseFloat(rating) : 0;
  const displayRating = isNaN(numRating) || numRating === 0 ? null : numRating;

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Rating
        value={displayRating}
        precision={0.1}
        readOnly
        size="medium"
        sx={{
          '& .MuiRating-iconFilled': {
            color: '#fbbf24', // yellow-400
          },
          '& .MuiRating-iconEmpty': {
            color: '#d1d5db', // gray-300 for light mode
          },
          '& .MuiRating-iconHover': {
            color: '#fbbf24',
          },
        }}
        className="dark:[&_.MuiRating-iconEmpty]:text-gray-600"
      />
      <span className="text-lg font-medium text-[#111418] dark:text-white ml-1">
        {displayRating !== null ? displayRating.toFixed(1) : '-'}
      </span>
    </div>
  );
}

