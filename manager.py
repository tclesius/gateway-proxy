from typing import Union, Optional
from urllib.parse import urlparse

import aiohttp
import validators
from aiohttp_ip_rotator import RotatingClientSession
import coloredlogs, logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

coloredlogs.install(fmt='%(levelname)-9s %(message)s')


# TODO: implement logging in grafana
# TODO: implement cleanup queue/script for aws
# TODO: implement session throwaway/restart after x http errors
# TODO: rethink the way the url is passed to proxy
# TODO: implement www domain same session as non-www domain

class LRotatingClientSession(RotatingClientSession):
    def __init__(self, target: str, key_id: Optional[str] = None, key_secret: Optional[str] = None,
                 host_header: Optional[str] = None, verbose: bool = False, *args, **kwargs):
        super().__init__(target, key_id, key_secret, host_header, verbose, *args, **kwargs)

    def _print_if_verbose(self, message: str):
        if self.verbose: logging.info(message)


class RotatingSessionManager:
    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str, verbose: bool = False):
        self._sessions = {}
        self.key_id = aws_access_key_id
        self.key_secret = aws_secret_access_key
        self.verbose = verbose
        self.targets = []

        if self.key_id is None:
            logging.exception("AWS_ACCESS_KEY_ID must be passed as environment variable!")
            exit(0)
        if self.key_secret is None:
            logging.exception("AWS_ACCESS_KEY_ID must be passed as environment variable!")
            exit(0)

    @staticmethod
    async def url_accessible(url: str):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.head(url, timeout=5) as response:
                    return bool(response.status)
            except aiohttp.ClientError as e:
                return False

    async def startup_event(self, targets: list[str] = None):
        if not isinstance(targets, list) or len(targets) == 0:
            logging.info("No targets passed.")
            return

        for target in targets:
            if await self.url_accessible(target):
                logging.info(f"Creating session for: '{target}'")
                await self.create_session(target=target)

    async def create_session(self, target: str) -> Union[None, RotatingClientSession]:
        if not await self.url_accessible(target):
            logging.warning(
                f"Couldn't create a session for target '{target}' ( Skipped ). Please check if url is valid."
            )
            return

        self._sessions[target] = LRotatingClientSession(
            target=target,
            key_id=self.key_id,
            key_secret=self.key_secret,
            verbose=self.verbose
        )

        await self._sessions[target].start()

        if len(self._sessions[target].endpoints) == 0:
            self._sessions[target] = None
            logging.exception(f"Couldn't create a session for '{target}'. AWS credentials are probably invalid.")

    async def get_session(self, url: str, force_ssl=True) -> Union[None, RotatingClientSession]:
        scheme, netloc, _, _, _, _ = urlparse(url)
        if force_ssl:
            scheme = "https"
        target = scheme + "://" + netloc

        if not validators.url(target):
            raise Exception(f"Invalid url: '{url}'")

        if self._sessions.get(target, None) is None:
            logging.info(f"Creating session for '{target}'")
            await self.create_session(target=target)
        return self._sessions.get(target)

    async def shutdown_event(self):
        for session_key, session in self._sessions.items():
            logging.info(f"Closing session for '{session_key}'")
            await session.close()
        self._sessions.clear()

#
