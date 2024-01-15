from urllib.parse import urlparse

import aiohttp
from aiohttp_ip_rotator import RotatingClientSession


# TODO: implement logging in grafana
# TODO: implement cleanup queue/script for aws
# TODO: implement session throwaway/restart after x http errors
# TODO: rethink the way the url is passed to proxy
# TODO: implement www domain same session as non-www domain

class RotatingSessionManager:
    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str, verbose: bool = False):
        self._sessions = {}
        self.key_id = aws_access_key_id
        self.key_secret = aws_secret_access_key
        self.verbose = verbose
        self.targets = []

        if self.key_id is None:
            raise Exception("AWS_ACCESS_KEY_ID not passed as environment variable!")
        if self.key_secret is None:
            raise Exception("AWS_SECRET_ACCESS_KEY not passed as environment variables!")

    @staticmethod
    async def target_exists(target: str):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.head(target, timeout=5) as response:
                    return bool(response.status)
            except aiohttp.ClientError as e:
                print(f"Target url: {e} is not accessible (Server not reachable). Maybe a typo?")
                return False

    async def startup_event(self, targets: list[str] = None):
        if targets is None or not isinstance(targets, list):
            return

        for target in targets:
            if await self.target_exists(target):
                print(f"Creating session for: {target}")
                await self.create_session(target=target)

    async def create_session(self, target: str):
        if self._sessions.get(target) is None:
            self._sessions[target] = RotatingClientSession(
                target=target,
                key_id=self.key_id,
                key_secret=self.key_secret,
                verbose=self.verbose
            )
            await self._sessions[target].start()

    async def get_session(self, url: str, force_ssl=True) -> RotatingClientSession:
        scheme, netloc, _, _, _, _ = urlparse(url)
        if force_ssl:
            scheme = "https"
        target = scheme + "://" + netloc

        if self._sessions.get(target, None) is None:
            await self.create_session(target=target)
            # TODO: raise ecxeption if session could not be created
        return self._sessions.get(target)

    async def shutdown_event(self):
        for session_key, session in self._sessions.items():
            print(f"Closing session for: {session_key}")
            await session.close()
        self._sessions.clear()

#
