import inspect
from functools import wraps

from app import Config


class AddCmd:
    @staticmethod
    def add_cmd(cmd: str | list, allow_sudo: bool = True):
        def the_decorator(func):
            path = inspect.stack()[1][1]

            @wraps(func)
            def wrapper():
                if isinstance(cmd, list):
                    for _cmd in cmd:
                        Config.CMD_DICT[_cmd] = Config.CMD(
                            cmd=_cmd, func=func, path=path, sudo=allow_sudo
                        )
                else:
                    Config.CMD_DICT[cmd] = Config.CMD(
                        cmd=cmd, func=func, path=path, sudo=allow_sudo
                    )

            wrapper()
            return func

        return the_decorator
