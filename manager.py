import os
from urllib.parse import urlparse

import yaml
from aiohttp_ip_rotator import RotatingClientSession
from dotenv import load_dotenv
from tqdm import tqdm


# TODO: implement logging in grafana
# TODO: implement cleanup queue/script for aws
# TODO: implement session throwaway/restart after x http errors
# TODO: rethink the way the url is passed to proxy
# TODO: implement www domain same session as non-www domain

class RotatingSessionManager:
    def __init__(self, aws_access_key_id, aws_secret_access_key, verbose: bool = False, targets: list[str] = None):
        self._sessions = {}
        self.key_id = aws_access_key_id
        self.key_secret = aws_secret_access_key
        self.verbose = verbose
        self.targets = targets

        if self.key_id is None:
            raise Exception("AWS_ACCESS_KEY_ID not passed as environment variable!")
        if self.key_secret is None:
            raise Exception("AWS_SECRET_ACCESS_KEY not passed as environment variables!")

    async def startup_event(self):
        if self.targets is None:
            return

        for target in self.targets:
            parsed_url = urlparse(target)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise Exception(f"Invalid target url: {target}")

        with tqdm(total=len(self.targets), desc="Creating startup sessions", disable=not self.verbose) as progress_bar:
            for target in self.targets:
                progress_bar.set_description(f"Creating session for: {target}")
                await self.create_session(target=target)
                progress_bar.update(1)

    async def create_session(self, target: str):
        if self._sessions.get(target) is None:
            # if self.verbose:
            #    print(f"[INFO]: Creating RotatingClientSession for target: " + target + "... ",
            #          end='')
            self._sessions[target] = RotatingClientSession(
                target=target,
                key_id=self.key_id,
                key_secret=self.key_secret,
                verbose=self.verbose
            )
            await self._sessions[target].start()

            # if self.verbose: print("SUCCESS\n")

    async def get_session(self, url: str, force_ssl=True) -> RotatingClientSession:
        scheme, netloc, _, _, _, _ = urlparse(url)
        if force_ssl:
            scheme = "https"
        target = scheme + "://" + netloc

        if self._sessions.get(target) is None:
            await self.create_session(target=target)
            # TODO: raise ecxeption if session could not be created

        return self._sessions[target]

    async def shutdown_event(self):
        # if self.verbose: print(f"[INFO]: Closing all open Http Sessions... ", end='')
        with tqdm(total=len(self._sessions), desc="Closing sessions") as pbar:
            for session_key, session in self._sessions.items():
                pbar.set_description(f"Closing session for: {session_key}")
                await session.close()
                pbar.update(1)

        self._sessions.clear()
        # if self.verbose: print("SUCCESS\n")

#
