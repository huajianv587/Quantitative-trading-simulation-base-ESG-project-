/* ═══════════════════════════════════════════════════════════════
   Lazy Loading & Performance Optimization
   ═══════════════════════════════════════════════════════════════ */

/**
 * Intersection Observer for lazy loading
 */
const observerOptions = {
  root: null,
  rootMargin: '50px',
  threshold: 0.01
};

let lazyObserver = null;

/**
 * Initialize lazy loading
 */
export function initLazyLoading() {
  if (!('IntersectionObserver' in window)) {
    // Fallback for browsers without IntersectionObserver
    loadAllImagesImmediately();
    return;
  }

  lazyObserver = new IntersectionObserver(handleIntersection, observerOptions);

  // Observe all lazy elements
  observeLazyElements();
}

/**
 * Observe lazy elements
 */
function observeLazyElements() {
  // Lazy images
  const lazyImages = document.querySelectorAll('img[data-src], img[loading="lazy"]');
  lazyImages.forEach(img => lazyObserver.observe(img));

  // Lazy backgrounds
  const lazyBackgrounds = document.querySelectorAll('[data-bg]');
  lazyBackgrounds.forEach(el => lazyObserver.observe(el));

  // Lazy content
  const lazyContent = document.querySelectorAll('[data-lazy-content]');
  lazyContent.forEach(el => lazyObserver.observe(el));

  // Lazy iframes
  const lazyIframes = document.querySelectorAll('iframe[data-src]');
  lazyIframes.forEach(iframe => lazyObserver.observe(iframe));
}

/**
 * Handle intersection
 */
function handleIntersection(entries, observer) {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const element = entry.target;

      if (element.tagName === 'IMG') {
        loadImage(element);
      } else if (element.tagName === 'IFRAME') {
        loadIframe(element);
      } else if (element.hasAttribute('data-bg')) {
        loadBackground(element);
      } else if (element.hasAttribute('data-lazy-content')) {
        loadContent(element);
      }

      observer.unobserve(element);
    }
  });
}

/**
 * Load image
 */
function loadImage(img) {
  const src = img.dataset.src || img.getAttribute('data-src');
  if (!src) return;

  // Create a new image to preload
  const tempImg = new Image();

  tempImg.onload = () => {
    img.src = src;
    img.classList.add('loaded');
    img.removeAttribute('data-src');

    // Trigger custom event
    img.dispatchEvent(new CustomEvent('lazyloaded', { bubbles: true }));
  };

  tempImg.onerror = () => {
    img.classList.add('error');
    img.alt = 'Failed to load image';
  };

  tempImg.src = src;
}

/**
 * Load background image
 */
function loadBackground(element) {
  const bg = element.dataset.bg;
  if (!bg) return;

  const tempImg = new Image();

  tempImg.onload = () => {
    element.style.backgroundImage = `url(${bg})`;
    element.classList.add('loaded');
    element.removeAttribute('data-bg');
  };

  tempImg.onerror = () => {
    element.classList.add('error');
  };

  tempImg.src = bg;
}

/**
 * Load iframe
 */
function loadIframe(iframe) {
  const src = iframe.dataset.src;
  if (!src) return;

  iframe.src = src;
  iframe.classList.add('loaded');
  iframe.removeAttribute('data-src');
}

/**
 * Load content dynamically
 */
async function loadContent(element) {
  const url = element.dataset.lazyContent;
  if (!url) return;

  try {
    element.classList.add('loading');

    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const html = await response.text();
    element.innerHTML = html;
    element.classList.remove('loading');
    element.classList.add('loaded');
    element.removeAttribute('data-lazy-content');

  } catch (error) {
    console.error('Failed to load content:', error);
    element.classList.remove('loading');
    element.classList.add('error');
    element.innerHTML = '<p class="error-message">Failed to load content</p>';
  }
}

/**
 * Fallback: Load all images immediately
 */
function loadAllImagesImmediately() {
  const lazyImages = document.querySelectorAll('img[data-src]');
  lazyImages.forEach(img => {
    const src = img.dataset.src;
    if (src) {
      img.src = src;
      img.removeAttribute('data-src');
    }
  });

  const lazyBackgrounds = document.querySelectorAll('[data-bg]');
  lazyBackgrounds.forEach(el => {
    const bg = el.dataset.bg;
    if (bg) {
      el.style.backgroundImage = `url(${bg})`;
      el.removeAttribute('data-bg');
    }
  });
}

/**
 * Preload critical resources
 */
export function preloadCriticalResources(resources = []) {
  resources.forEach(resource => {
    const link = document.createElement('link');
    link.rel = 'preload';
    link.href = resource.url;
    link.as = resource.type || 'image';

    if (resource.type === 'font') {
      link.crossOrigin = 'anonymous';
    }

    document.head.appendChild(link);
  });
}

/**
 * Prefetch resources for next page
 */
export function prefetchResources(urls = []) {
  urls.forEach(url => {
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = url;
    document.head.appendChild(link);
  });
}

/**
 * Lazy load module/script
 */
export async function lazyLoadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.async = true;

    script.onload = () => resolve(script);
    script.onerror = () => reject(new Error(`Failed to load script: ${src}`));

    document.body.appendChild(script);
  });
}

/**
 * Lazy load CSS
 */
export function lazyLoadCSS(href) {
  return new Promise((resolve, reject) => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;

    link.onload = () => resolve(link);
    link.onerror = () => reject(new Error(`Failed to load CSS: ${href}`));

    document.head.appendChild(link);
  });
}

/**
 * Debounce function for performance
 */
export function debounce(func, wait = 300) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * Throttle function for performance
 */
export function throttle(func, limit = 300) {
  let inThrottle;
  return function executedFunction(...args) {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

/**
 * Request Idle Callback wrapper
 */
export function runWhenIdle(callback, options = {}) {
  if ('requestIdleCallback' in window) {
    return requestIdleCallback(callback, options);
  } else {
    // Fallback
    return setTimeout(callback, 1);
  }
}

/**
 * Cancel idle callback
 */
export function cancelIdle(id) {
  if ('cancelIdleCallback' in window) {
    cancelIdleCallback(id);
  } else {
    clearTimeout(id);
  }
}

/**
 * Measure performance
 */
export function measurePerformance(name, fn) {
  const start = performance.now();
  const result = fn();
  const end = performance.now();

  console.log(`[Performance] ${name}: ${(end - start).toFixed(2)}ms`);

  return result;
}

/**
 * Async measure performance
 */
export async function measurePerformanceAsync(name, fn) {
  const start = performance.now();
  const result = await fn();
  const end = performance.now();

  console.log(`[Performance] ${name}: ${(end - start).toFixed(2)}ms`);

  return result;
}

/**
 * Get page load metrics
 */
export function getPageLoadMetrics() {
  if (!('performance' in window)) return null;

  const perfData = window.performance.timing;
  const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
  const connectTime = perfData.responseEnd - perfData.requestStart;
  const renderTime = perfData.domComplete - perfData.domLoading;

  return {
    pageLoadTime,
    connectTime,
    renderTime,
    domReady: perfData.domContentLoadedEventEnd - perfData.navigationStart,
    firstPaint: performance.getEntriesByType('paint')[0]?.startTime || 0
  };
}

/**
 * Monitor long tasks
 */
export function monitorLongTasks(callback) {
  if (!('PerformanceObserver' in window)) return;

  try {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > 50) {
          callback({
            duration: entry.duration,
            startTime: entry.startTime,
            name: entry.name
          });
        }
      }
    });

    observer.observe({ entryTypes: ['longtask'] });
    return observer;
  } catch (e) {
    console.warn('Long task monitoring not supported');
  }
}

/**
 * Optimize images on the fly
 */
export function optimizeImage(img, options = {}) {
  const { maxWidth = 1920, quality = 0.85 } = options;

  if (img.naturalWidth > maxWidth) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    const ratio = maxWidth / img.naturalWidth;
    canvas.width = maxWidth;
    canvas.height = img.naturalHeight * ratio;

    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    return canvas.toDataURL('image/jpeg', quality);
  }

  return img.src;
}

/**
 * Initialize all performance optimizations
 */
function isDevelopmentRuntime() {
  return (typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'development')
    || window.__ESG_NODE_ENV__ === 'development';
}

export function initPerformanceOptimizations() {
  // Initialize lazy loading
  initLazyLoading();

  // Log page load metrics
  window.addEventListener('load', () => {
    runWhenIdle(() => {
      const metrics = getPageLoadMetrics();
      if (metrics) {
        console.log('[Performance Metrics]', metrics);
      }
    });
  });

  // Monitor long tasks in development
  if (isDevelopmentRuntime()) {
    monitorLongTasks((task) => {
      console.warn('[Long Task]', task);
    });
  }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPerformanceOptimizations);
} else {
  initPerformanceOptimizations();
}
