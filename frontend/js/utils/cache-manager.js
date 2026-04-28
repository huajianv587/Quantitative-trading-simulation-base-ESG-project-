/* ═══════════════════════════════════════════════════════════════
   Advanced Cache Manager
   智能缓存管理系统 - 支持TTL、LRU、持久化
   ═══════════════════════════════════════════════════════════════ */

/**
 * Cache entry structure
 */
class CacheEntry {
  constructor(value, ttl = 5 * 60 * 1000) {
    this.value = value;
    this.expires = Date.now() + ttl;
    this.hits = 0;
    this.lastAccess = Date.now();
  }

  isExpired() {
    return Date.now() > this.expires;
  }

  touch() {
    this.hits++;
    this.lastAccess = Date.now();
  }
}

/**
 * Advanced Cache Manager with LRU eviction
 */
class CacheManager {
  constructor(options = {}) {
    const {
      maxSize = 100,              // 最大缓存条目数
      defaultTTL = 5 * 60 * 1000, // 默认5分钟
      enablePersistence = true,   // 启用持久化
      storageKey = 'qt_cache'     // localStorage key
    } = options;

    this.maxSize = maxSize;
    this.defaultTTL = defaultTTL;
    this.enablePersistence = enablePersistence;
    this.storageKey = storageKey;
    this.cache = new Map();
    this.stats = {
      hits: 0,
      misses: 0,
      evictions: 0
    };

    // 从 localStorage 恢复缓存
    if (this.enablePersistence) {
      this.loadFromStorage();
    }

    // 定期清理过期条目
    this.startCleanupTimer();
  }

  /**
   * Set cache entry
   */
  set(key, value, ttl = this.defaultTTL) {
    // LRU eviction if cache is full
    if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
      this.evictLRU();
    }

    const entry = new CacheEntry(value, ttl);
    this.cache.set(key, entry);

    // 持久化到 localStorage
    if (this.enablePersistence) {
      this.saveToStorage();
    }

    return value;
  }

  /**
   * Get cache entry
   */
  get(key) {
    const entry = this.cache.get(key);

    if (!entry) {
      this.stats.misses++;
      return null;
    }

    if (entry.isExpired()) {
      this.cache.delete(key);
      this.stats.misses++;
      return null;
    }

    entry.touch();
    this.stats.hits++;
    return entry.value;
  }

  /**
   * Check if key exists and is valid
   */
  has(key) {
    const entry = this.cache.get(key);
    if (!entry) return false;
    if (entry.isExpired()) {
      this.cache.delete(key);
      return false;
    }
    return true;
  }

  /**
   * Delete cache entry
   */
  delete(key) {
    const deleted = this.cache.delete(key);
    if (deleted && this.enablePersistence) {
      this.saveToStorage();
    }
    return deleted;
  }

  /**
   * Clear all cache
   */
  clear() {
    this.cache.clear();
    this.stats = { hits: 0, misses: 0, evictions: 0 };
    if (this.enablePersistence) {
      localStorage.removeItem(this.storageKey);
    }
  }

  /**
   * Evict least recently used entry
   */
  evictLRU() {
    let lruKey = null;
    let lruTime = Infinity;

    for (const [key, entry] of this.cache.entries()) {
      if (entry.lastAccess < lruTime) {
        lruTime = entry.lastAccess;
        lruKey = key;
      }
    }

    if (lruKey) {
      this.cache.delete(lruKey);
      this.stats.evictions++;
    }
  }

  /**
   * Clean up expired entries
   */
  cleanup() {
    let cleaned = 0;
    for (const [key, entry] of this.cache.entries()) {
      if (entry.isExpired()) {
        this.cache.delete(key);
        cleaned++;
      }
    }

    if (cleaned > 0 && this.enablePersistence) {
      this.saveToStorage();
    }

    return cleaned;
  }

  /**
   * Start cleanup timer
   */
  startCleanupTimer() {
    this.cleanupTimer = setInterval(() => {
      this.cleanup();
    }, 60 * 1000); // 每分钟清理一次
  }

  /**
   * Stop cleanup timer
   */
  stopCleanupTimer() {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
    }
  }

  /**
   * Save cache to localStorage
   */
  saveToStorage() {
    try {
      const data = {};
      for (const [key, entry] of this.cache.entries()) {
        if (!entry.isExpired()) {
          data[key] = {
            value: entry.value,
            expires: entry.expires,
            hits: entry.hits,
            lastAccess: entry.lastAccess
          };
        }
      }
      localStorage.setItem(this.storageKey, JSON.stringify(data));
    } catch (error) {
      console.warn('Failed to save cache to storage:', error);
    }
  }

  /**
   * Load cache from localStorage
   */
  loadFromStorage() {
    try {
      const data = localStorage.getItem(this.storageKey);
      if (!data) return;

      const parsed = JSON.parse(data);
      const now = Date.now();

      for (const [key, item] of Object.entries(parsed)) {
        if (item.expires > now) {
          const entry = new CacheEntry(item.value, item.expires - now);
          entry.hits = item.hits || 0;
          entry.lastAccess = item.lastAccess || now;
          this.cache.set(key, entry);
        }
      }
    } catch (error) {
      console.warn('Failed to load cache from storage:', error);
    }
  }

  /**
   * Get cache statistics
   */
  getStats() {
    const hitRate = this.stats.hits + this.stats.misses > 0
      ? (this.stats.hits / (this.stats.hits + this.stats.misses) * 100).toFixed(2)
      : 0;

    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      hits: this.stats.hits,
      misses: this.stats.misses,
      evictions: this.stats.evictions,
      hitRate: `${hitRate}%`
    };
  }

  /**
   * Get all cache keys
   */
  keys() {
    return Array.from(this.cache.keys());
  }

  /**
   * Get cache size
   */
  size() {
    return this.cache.size;
  }
}

/**
 * API Cache Wrapper
 */
class APICacheWrapper {
  constructor(cacheManager, options = {}) {
    this.cache = cacheManager;
    this.options = {
      defaultTTL: 5 * 60 * 1000,
      cacheableStatuses: [200],
      cacheableMethods: ['GET'],
      ...options
    };
  }

  /**
   * Generate cache key from request
   */
  generateKey(url, options = {}) {
    const method = options.method || 'GET';
    const body = options.body ? JSON.stringify(options.body) : '';
    return `${method}:${url}:${body}`;
  }

  /**
   * Fetch with cache
   */
  async fetch(url, options = {}) {
    const method = options.method || 'GET';
    const key = this.generateKey(url, options);

    // 只缓存可缓存的方法
    if (!this.options.cacheableMethods.includes(method)) {
      return await fetch(url, options);
    }

    // 检查缓存
    const cached = this.cache.get(key);
    if (cached) {
      console.log(`[Cache HIT] ${key}`);
      return cached;
    }

    console.log(`[Cache MISS] ${key}`);

    // 发起请求
    const response = await fetch(url, options);

    // 只缓存成功的响应
    if (this.options.cacheableStatuses.includes(response.status)) {
      const data = await response.json();
      this.cache.set(key, data, this.options.defaultTTL);
      return data;
    }

    return response;
  }

  /**
   * Invalidate cache by pattern
   */
  invalidate(pattern) {
    const keys = this.cache.keys();
    let invalidated = 0;

    for (const key of keys) {
      if (key.includes(pattern)) {
        this.cache.delete(key);
        invalidated++;
      }
    }

    console.log(`[Cache] Invalidated ${invalidated} entries matching "${pattern}"`);
    return invalidated;
  }

  /**
   * Invalidate all cache
   */
  invalidateAll() {
    this.cache.clear();
    console.log('[Cache] All entries invalidated');
  }
}

/**
 * Query Cache for specific data types
 */
class QueryCache {
  constructor(cacheManager) {
    this.cache = cacheManager;
  }

  /**
   * Cache query result
   */
  setQuery(queryKey, data, ttl) {
    return this.cache.set(`query:${queryKey}`, data, ttl);
  }

  /**
   * Get cached query result
   */
  getQuery(queryKey) {
    return this.cache.get(`query:${queryKey}`);
  }

  /**
   * Invalidate query
   */
  invalidateQuery(queryKey) {
    return this.cache.delete(`query:${queryKey}`);
  }

  /**
   * Invalidate queries by prefix
   */
  invalidateQueries(prefix) {
    const keys = this.cache.keys();
    let invalidated = 0;

    for (const key of keys) {
      if (key.startsWith(`query:${prefix}`)) {
        this.cache.delete(key);
        invalidated++;
      }
    }

    return invalidated;
  }
}

// Create singleton instances
const cacheManager = new CacheManager({
  maxSize: 200,
  defaultTTL: 5 * 60 * 1000,
  enablePersistence: true
});

const apiCache = new APICacheWrapper(cacheManager, {
  defaultTTL: 5 * 60 * 1000,
  cacheableStatuses: [200],
  cacheableMethods: ['GET']
});

const queryCache = new QueryCache(cacheManager);

// Export instances
export {
  CacheManager,
  APICacheWrapper,
  QueryCache,
  cacheManager,
  apiCache,
  queryCache
};

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  cacheManager.stopCleanupTimer();
});

function isDevelopmentRuntime() {
  return (typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'development')
    || window.__ESG_NODE_ENV__ === 'development';
}

// Expose cache stats in development
if (isDevelopmentRuntime()) {
  window.__CACHE_STATS__ = () => cacheManager.getStats();
  window.__CACHE_CLEAR__ = () => cacheManager.clear();
}
