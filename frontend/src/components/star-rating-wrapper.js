/**
 * Star rating component with proportional fill using SVG gradients
 */

/**
 * Creates a star SVG with a specific fill percentage
 * @param {number} fillPercent - Fill percentage (0-100)
 * @param {string} id - Unique ID for the gradient
 */
function createStar(fillPercent, id) {
  if (fillPercent >= 100) {
    return `<svg class="w-5 h-5" viewBox="0 0 20 20"><path fill="#facc15" d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path></svg>`;
  }
  if (fillPercent <= 0) {
    return `<svg class="w-5 h-5" viewBox="0 0 20 20"><path fill="#4b5563" d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path></svg>`;
  }
  // Partial fill using gradient
  return `<svg class="w-5 h-5" viewBox="0 0 20 20">
        <defs>
            <linearGradient id="${id}">
                <stop offset="${fillPercent}%" stop-color="#facc15"/>
                <stop offset="${fillPercent}%" stop-color="#4b5563"/>
            </linearGradient>
        </defs>
        <path fill="url(#${id})" d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path>
    </svg>`;
}

/**
 * Mounts a star rating display with proportional fill.
 * @param {string} containerId - The ID of the container element
 * @param {number} rating - The rating value (0-5)
 */
export function mountStarRating(containerId, rating) {
  const container = document.getElementById(containerId);
  if (!container) {
    console.error(`Container with id "${containerId}" not found`);
    return;
  }

  const numRating = parseFloat(rating) || 0;
  const uniqueId = `star-${Date.now()}`;
  let starsHTML = '';

  for (let i = 0; i < 5; i++) {
    const starValue = numRating - i;
    let fillPercent;

    if (starValue >= 1) {
      fillPercent = 100; // Full star
    } else if (starValue <= 0) {
      fillPercent = 0; // Empty star
    } else {
      fillPercent = starValue * 100; // Partial fill (e.g., 0.2 = 20%)
    }

    starsHTML += createStar(fillPercent, `${uniqueId}-${i}`);
  }

  // Rating text
  starsHTML += `<span class="ml-2 text-sm text-gray-400">${numRating.toFixed(1)}</span>`;

  container.innerHTML = `<div class="flex items-center gap-0.5">${starsHTML}</div>`;
}
