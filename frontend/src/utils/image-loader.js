/**
 * Optimized image loading utilities for better performance.
 */

/**
 * Creates an optimized image element with lazy loading and error handling.
 * @param {string} src - Image source URL
 * @param {string} alt - Alt text
 * @param {Object} options - Additional options
 * @returns {string} HTML string for the image
 */
export function createOptimizedImage(src, alt, options = {}) {
    const {
        classNames = 'w-full h-full object-cover',
        loading = 'lazy',
        fetchPriority = 'auto',
        placeholder = true,
        onError = null
    } = options;

    // Generate a unique ID for this image
    const imageId = `img-${Math.random().toString(36).substr(2, 9)}`;
    
    // Default error handler
    const defaultErrorHandler = `
        this.style.display='none';
        const placeholder = this.parentElement.querySelector('.image-placeholder');
        if (placeholder) {
            placeholder.style.display = 'flex';
        } else {
            this.parentElement.innerHTML = '<div class="w-full h-full flex items-center justify-center text-gray-400 text-xs bg-gray-200 dark:bg-gray-700">No Image</div>';
        }
    `;

    const errorHandler = onError || defaultErrorHandler;

    return `
        <div class="relative w-full h-full">
            ${placeholder ? `
                <div class="image-placeholder absolute inset-0 flex items-center justify-center bg-gray-200 dark:bg-gray-700 animate-pulse">
                    <div class="w-12 h-12 border-4 border-gray-300 dark:border-gray-600 border-t-primary rounded-full animate-spin"></div>
                </div>
            ` : ''}
            <img 
                id="${imageId}"
                src="${src}" 
                alt="${alt}" 
                class="${classNames}"
                loading="${loading}"
                fetchpriority="${fetchPriority}"
                decoding="async"
                onload="this.parentElement.querySelector('.image-placeholder')?.style.setProperty('display', 'none');"
                onerror="${errorHandler}"
            />
        </div>
    `;
}

/**
 * Preloads an image for faster display when needed.
 * @param {string} src - Image source URL
 */
export function preloadImage(src) {
    if (!src || src === '/placeholder-book.jpg') return;
    
    const link = document.createElement('link');
    link.rel = 'preload';
    link.as = 'image';
    link.href = src;
    link.fetchPriority = 'high';
    document.head.appendChild(link);
}

/**
 * Creates a blur-up placeholder effect (low-res image first, then high-res).
 * @param {string} lowResSrc - Low resolution placeholder
 * @param {string} highResSrc - High resolution image
 * @param {string} alt - Alt text
 * @param {Object} options - Additional options
 * @returns {string} HTML string
 */
export function createBlurUpImage(lowResSrc, highResSrc, alt, options = {}) {
    const {
        classNames = 'w-full h-full object-cover',
        blurClass = 'blur-sm'
    } = options;

    const containerId = `blur-up-${Math.random().toString(36).substr(2, 9)}`;

    return `
        <div id="${containerId}" class="relative w-full h-full overflow-hidden">
            <img 
                src="${lowResSrc}" 
                alt="${alt}" 
                class="${classNames} ${blurClass} absolute inset-0"
                loading="eager"
                fetchpriority="high"
            />
            <img 
                src="${highResSrc}" 
                alt="${alt}" 
                class="${classNames} relative z-10 transition-opacity duration-300 opacity-0"
                loading="lazy"
                onload="this.classList.remove('opacity-0'); this.classList.add('opacity-100'); this.previousElementSibling.style.display='none';"
                onerror="this.style.display='none'; this.previousElementSibling.style.display='block'; this.parentElement.innerHTML += '<div class=\\'absolute inset-0 flex items-center justify-center text-gray-400 text-xs bg-gray-200 dark:bg-gray-700\\'>No Image</div>';"
            />
        </div>
    `;
}

/**
 * Uses Intersection Observer for advanced lazy loading.
 * @param {NodeList|Array} images - Image elements to observe
 * @param {Object} options - Intersection Observer options
 */
export function setupIntersectionObserver(images, options = {}) {
    if (!('IntersectionObserver' in window)) {
        // Fallback: just load all images
        images.forEach(img => {
            if (img.dataset.src) {
                img.src = img.dataset.src;
            }
        });
        return;
    }

    const defaultOptions = {
        root: null,
        rootMargin: '50px',
        threshold: 0.01
    };

    const observerOptions = { ...defaultOptions, ...options };

    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                }
                observer.unobserve(img);
            }
        });
    }, observerOptions);

    images.forEach(img => {
        if (img.dataset.src) {
            imageObserver.observe(img);
        }
    });
}

/**
 * Retry loading an image if it fails.
 * @param {HTMLImageElement} img - Image element
 * @param {number} maxRetries - Maximum number of retries
 */
export function retryImageLoad(img, maxRetries = 2) {
    let retries = 0;
    const originalSrc = img.src;

    img.addEventListener('error', function onError() {
        if (retries < maxRetries) {
            retries++;
            // Add a small delay before retry
            setTimeout(() => {
                img.src = originalSrc + (originalSrc.includes('?') ? '&' : '?') + `retry=${retries}`;
            }, 1000 * retries);
        } else {
            img.removeEventListener('error', onError);
            // Show placeholder
            img.style.display = 'none';
            const placeholder = document.createElement('div');
            placeholder.className = 'w-full h-full flex items-center justify-center text-gray-400 text-xs bg-gray-200 dark:bg-gray-700';
            placeholder.textContent = 'No Image';
            img.parentElement?.appendChild(placeholder);
        }
    });
}

