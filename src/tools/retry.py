from ..custom import RETRY
from ..custom import wait
from ..translation import _
import time
import random
import ssl

__all__ = ["PrivateRetry"]


class PrivateRetry:
    """重试器，仅适用于本项目！"""

    @staticmethod
    def retry(function):
        """发生错误时尝试重新执行，装饰的函数需要返回布尔值"""

        async def inner(self, *args, **kwargs):
            finished = kwargs.pop("finished", False)
            for i in range(self.max_retry):
                try:
                    if result := await function(self, *args, **kwargs):
                        return result
                except ssl.SSLError as e:
                    self.log.warning(_("SSL错误: {error}，正在尝试重试").format(error=str(e)))
                except Exception as e:
                    self.log.warning(_("请求出错: {error}，正在尝试重试").format(error=str(e)))
                
                # 增加指数退避策略，随着重试次数增加等待时间
                wait_time = 1 + i * 2 + random.uniform(0, 1)
                self.log.warning(_("正在进行第 {index} 次重试，等待 {wait:.1f} 秒").format(index=i + 1, wait=wait_time))
                await wait(wait_time)
                
            try:
                if not (result := await function(self, *args, **kwargs)) and finished:
                    self.finished = True
                return result
            except Exception as e:
                self.log.error(_("最终尝试失败: {error}").format(error=str(e)))
                if finished:
                    self.finished = True
                return None

        return inner

    @staticmethod
    def retry_lite(function):
        async def inner(*args, **kwargs):
            if r := await function(*args, **kwargs):
                return r
            for i in range(RETRY):
                if r := await function(*args, **kwargs):
                    return r
                # 增加等待时间，避免频繁请求
                wait_time = 1 + i * 0.5 + random.uniform(0, 0.5)
                await wait(wait_time)
            return r

        return inner

    @staticmethod
    def retry_limited(function):
        def inner(self, *args, **kwargs):
            while True:
                if function(self, *args, **kwargs):
                    return
                if self.console.input(
                        _(
                            "如需重新尝试处理该对象，请关闭所有正在访问该对象的窗口或程序，然后直接按下回车键！\n"
                            "如需跳过处理该对象，请输入任意字符后按下回车键！"
                        ),
                ):
                    return

        return inner

    @staticmethod
    def retry_infinite(function):
        def inner(self, *args, **kwargs):
            while True:
                if function(self, *args, **kwargs):
                    return
                self.console.input(
                    _("请关闭所有正在访问该对象的窗口或程序，然后按下回车键继续处理！")
                )

        return inner
