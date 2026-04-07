import time
import functools
from gateway.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_RETRIES = 3      # 最大重试次数
DEFAULT_DELAY   = 1.0    # 首次重试等待秒数
DEFAULT_BACKOFF = 2.0    # 指数退避倍数（每次失败后等待时间 × backoff）


def retry(
    max_retries: int = DEFAULT_RETRIES,
    delay: float = DEFAULT_DELAY,
    backoff: float = DEFAULT_BACKOFF,
    exceptions: tuple = (Exception,),
):
    """
    指数退避重试装饰器。

    参数:
        max_retries: 最大重试次数（不含首次调用）
        delay:       首次重试前等待秒数
        backoff:     退避倍数，每次失败后 delay *= backoff
                     例: delay=1, backoff=2 → 等待 1s、2s、4s
        exceptions:  只对这些异常类型触发重试，其他异常直接抛出

    用法:
        @retry(max_retries=3, delay=1.0, backoff=2.0)
        def call_api():
            ...

        或临时包裹一个函数:
        result = with_retry(some_func, arg1, arg2)
    """
    def decorator(func):
        @functools.wraps(func)   # 保留原函数的 __name__ / __doc__，方便调试
        def wrapper(*args, **kwargs):
            wait = delay
            last_exc = None

            for attempt in range(1, max_retries + 2):  # +2: 首次调用 + max_retries 次重试
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt <= max_retries:
                        logger.warning(
                            f"[Retry] {func.__name__} failed "
                            f"(attempt {attempt}/{max_retries + 1}): {e}. "
                            f"Retrying in {wait:.1f}s ..."
                        )
                        time.sleep(wait)
                        wait *= backoff   # 指数退避：下次等待时间翻倍
                    else:
                        logger.error(
                            f"[Retry] {func.__name__} failed after "
                            f"{max_retries + 1} attempts. Giving up."
                        )

            raise last_exc   # 全部重试耗尽后抛出最后一次异常

        return wrapper
    return decorator


# 别名：与 retry 完全相同，兼容 data_sources.py 的导入
retry_with_backoff = retry


def with_retry(func, *args, max_retries=DEFAULT_RETRIES, delay=DEFAULT_DELAY,
               backoff=DEFAULT_BACKOFF, **kwargs):
    """
    不用装饰器时的函数式调用方式。

    用法:
        result = with_retry(chat, messages, max_retries=2)
    """
    wrapped = retry(max_retries=max_retries, delay=delay, backoff=backoff)(func)
    return wrapped(*args, **kwargs)
